// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#include <stdlib.h>
#ifdef _CRTDBG_MAP_ALLOC
#include <crtdbg.h>
#endif
#include <stddef.h>
#include <stdio.h>
#include <stdbool.h>
#include "azure_c_shared_utility/gballoc.h"
#include "azure_c_shared_utility/httpheaders.h"
#include "azure_c_shared_utility/wsio.h"
#include "azure_c_shared_utility/xlogging.h"
#include "azure_c_shared_utility/list.h"
#include "libwebsockets.h"
#include "openssl/ssl.h"
#include "azure_c_shared_utility/xio.h"

typedef enum IO_STATE_TAG
{
    IO_STATE_NOT_OPEN,
    IO_STATE_OPENING,
    IO_STATE_OPEN,
    IO_STATE_CLOSING,
    IO_STATE_ERROR
} IO_STATE;

typedef struct PENDING_SOCKET_IO_TAG
{
    const unsigned char* bytes;
    size_t size;
    ON_SEND_COMPLETE on_send_complete;
    void* callback_context;
    LIST_HANDLE pending_io_list;
    bool is_partially_sent;
    enum lws_write_protocol msgtype;
} PENDING_SOCKET_IO;

typedef struct WSIO_INSTANCE_TAG
{
    ON_BYTES_RECEIVED on_bytes_received;
    ON_WSIO_BYTES_RECEIVED on_bytes_received_wsio;
    void* on_bytes_received_context;
    ON_IO_OPEN_COMPLETE on_io_open_complete;
    void* on_io_open_complete_context;
    ON_IO_ERROR on_io_error;
    void* on_io_error_context;
    IO_STATE io_state;
    LIST_HANDLE pending_io_list;
    struct lws_context* ws_context;
    struct lws* wsi;
    int port;
    char* host;
    char* relative_path;
    char* protocol_name;
    char* trusted_ca;
    struct lws_protocols* protocols;
    int use_ssl;
    HTTP_HEADERS_HANDLE hHeaders;
	unsigned char* rx_buffer;
	size_t rx_buffer_offset;
	size_t rx_buffer_size;
    int ka_time;
    int http_code;
} WSIO_INSTANCE;

static void lws_loggercb(int level, const char *line)
{
    switch (level)
    {
    case LLL_ERR:
    case LLL_WARN:
        LogError("%s", line);
        break;
    default:
        LogInfo("%s", line);
        break;
    }
}

#if defined(GB_DEBUG_ALLOC) && defined(GB_MEASURE_MEMORY_FOR_THIS)
static void *wsio_gb_realloc(void *ptr, size_t size)
{
    if (size)
        return (void *)gballoc_realloc(ptr, size);
    else if (ptr)
        gballoc_free(ptr);
    return NULL;
}
#endif // defined(GB_DEBUG_ALLOC) && defined(GB_MEASURE_MEMORY_FOR_THIS)

static void AddHeadersBeforeToRequest(HTTP_HEADERS_HANDLE httpHeadersHandle, char **p)
{
    size_t headersCount;
    size_t i;

    if (HTTPHeaders_GetHeaderCount(httpHeadersHandle, &headersCount) != HTTP_HEADERS_OK)
    {
        LogError("HTTPHeaders_GetHeaderCount failed.");
    }
    else
    {
        for (i = 0; i < headersCount; i++)
        {
            char *temp;
            if (HTTPHeaders_GetHeader(httpHeadersHandle, i, &temp) == HTTP_HEADERS_OK)
            {
                *p += sprintf(*p, "%s\x0d\x0a", temp);
                free(temp);
            }
            else
            {
                LogError("HTTPHeaders_GetHeader failed");
                break;
            }
        }
    }
}

static void cancel_io(WSIO_INSTANCE* wsio_instance)
{
    /* cancel all pending IOs */
    LIST_ITEM_HANDLE first_pending_io;

    /* Codes_SRS_WSIO_01_108: [wsio_close shall obtain all the pending IO items by repetitively querying for the head of the pending IO list and freeing that head item.] */
    /* Codes_SRS_WSIO_01_111: [Obtaining the head of the pending IO list shall be done by calling list_get_head_item.] */
    while ((first_pending_io = list_get_head_item(wsio_instance->pending_io_list)) != NULL)
    {
        PENDING_SOCKET_IO* pending_socket_io = (PENDING_SOCKET_IO*)list_item_get_value(first_pending_io);

        if (pending_socket_io != NULL)
        {
            /* Codes_SRS_WSIO_01_060: [The argument on_send_complete shall be optional, if NULL is passed by the caller then no send complete callback shall be triggered.] */
            if (pending_socket_io->on_send_complete != NULL)
            {
                /* Codes_SRS_WSIO_01_109: [For each pending item the send complete callback shall be called with IO_SEND_CANCELLED.] */
                /* Codes_SRS_WSIO_01_110: [The callback context passed to the on_send_complete callback shall be the context given to wsio_send.] */
                /* Codes_SRS_WSIO_01_059: [The callback_context argument shall be passed to on_send_complete as is.] */
                pending_socket_io->on_send_complete(pending_socket_io->callback_context, IO_SEND_CANCELLED);
            }

            if (pending_socket_io != NULL)
            {
                free(pending_socket_io);
            }
        }

        (void)list_remove(wsio_instance->pending_io_list, first_pending_io);
    }
}

static void destroy_context(WSIO_INSTANCE* wsio_instance, IO_STATE io_state)
{
    if (NULL != wsio_instance->ws_context)
    {
        lws_context_destroy(wsio_instance->ws_context);
        wsio_instance->ws_context = NULL;
    }

    wsio_instance->io_state = io_state;
}

static void _indicate_error(WSIO_INSTANCE* wsio_instance)
{
    cancel_io(wsio_instance);

    destroy_context(wsio_instance, IO_STATE_ERROR);

    if (wsio_instance->on_io_error != NULL)
    {
        wsio_instance->on_io_error(wsio_instance->on_io_error_context);
    }
}

#define indicate_error(__wsio_instance) \
    LogError("lwserror: %s @ %d", __FILE__, __LINE__);    \
    _indicate_error(__wsio_instance)

static void indicate_open_complete(WSIO_INSTANCE* ws_io_instance, IO_OPEN_RESULT open_result)
{
    /* Codes_SRS_WSIO_01_040: [The argument on_io_open_complete shall be optional, if NULL is passed by the caller then no open complete callback shall be triggered.] */
    if (ws_io_instance->on_io_open_complete != NULL)
    {
        /* Codes_SRS_WSIO_01_039: [The callback_context argument shall be passed to on_io_open_complete as is.] */
        ws_io_instance->on_io_open_complete(ws_io_instance->on_io_open_complete_context, open_result);
    }
}

static int add_pending_io(WSIO_INSTANCE* ws_io_instance, const unsigned char* buffer, size_t size, WSIO_MSG_TYPE message_type, ON_SEND_COMPLETE on_send_complete, void* callback_context)
{
    int result;
    enum lws_write_protocol msgtype;

    switch (message_type)
    {
    case WSIO_MSG_TYPE_TEXT:
        msgtype = LWS_WRITE_TEXT;
        break;
    case WSIO_MSG_TYPE_BINARY:
        msgtype = LWS_WRITE_BINARY;
        break;
    default:
        return __LINE__;
    }

    PENDING_SOCKET_IO* pending_socket_io = (PENDING_SOCKET_IO*)malloc(sizeof(PENDING_SOCKET_IO));
    if (pending_socket_io == NULL)
    {
        /* Codes_SRS_WSIO_01_055: [If queueing the data fails (i.e. due to insufficient memory), wsio_send shall fail and return a non-zero value.] */
        result = __LINE__;
    }
    else
    {
        pending_socket_io->msgtype = msgtype;
        pending_socket_io->bytes = buffer;
        pending_socket_io->is_partially_sent = false;
        pending_socket_io->size = size;
        pending_socket_io->on_send_complete = on_send_complete;
        pending_socket_io->callback_context = callback_context;
        pending_socket_io->pending_io_list = ws_io_instance->pending_io_list;

        /* Codes_SRS_WSIO_01_105: [The data and callback shall be queued by calling list_add on the list created in wsio_create.] */
        if (list_add(ws_io_instance->pending_io_list, pending_socket_io) == NULL)
        {
            /* Codes_SRS_WSIO_01_055: [If queueing the data fails (i.e. due to insufficient memory), wsio_send shall fail and return a non-zero value.] */
            free(pending_socket_io);
            result = __LINE__;
        }
        else
        {
            result = 0;
        }
    }

    return result;
}

static int remove_pending_io(WSIO_INSTANCE* wsio_instance, LIST_ITEM_HANDLE item_handle, PENDING_SOCKET_IO* pending_socket_io, IO_SEND_RESULT error)
{
    int result;

    if (pending_socket_io->on_send_complete != NULL)
    {
        pending_socket_io->on_send_complete(pending_socket_io->callback_context, error);
    }

    free(pending_socket_io);
    if (list_remove(wsio_instance->pending_io_list, item_handle) != 0)
    {
        result = __LINE__;
    }
    else
    {
        result = 0;
    }

    return result;
}

static int wsio_send_xio(
    CONCRETE_IO_HANDLE ws_io, 
    const void* buffer, 
    size_t size, 
    ON_SEND_COMPLETE on_send_complete, 
    void* callback_context)
{
    return wsio_send(ws_io, buffer, size, WSIO_MSG_TYPE_BINARY, on_send_complete, callback_context);
}

static int wsio_open_xio(
    CONCRETE_IO_HANDLE ws_io, 
    ON_IO_OPEN_COMPLETE on_io_open_complete, 
    void* on_io_open_complete_context, 
    ON_BYTES_RECEIVED on_bytes_received, 
    void* on_bytes_received_context, 
    ON_IO_ERROR on_io_error, 
    void* on_io_error_context);

static const IO_INTERFACE_DESCRIPTION ws_io_interface_description =
{
    wsio_create,
    wsio_destroy,
    wsio_open_xio,
    wsio_close,
    wsio_send_xio,
    wsio_dowork,
    wsio_setoption
};

static void on_bytes_received(
    WSIO_INSTANCE* wsio_instance, 
    const unsigned char* in,
    size_t len,
    int frame_is_binary)
{
    if (wsio_instance->on_bytes_received)
    {
        wsio_instance->on_bytes_received(
            wsio_instance->on_bytes_received_context, 
            in, 
            len);
    }

    if (wsio_instance->on_bytes_received_wsio)
    {
        wsio_instance->on_bytes_received_wsio(
            wsio_instance->on_bytes_received_context, 
            in, 
            len, 
            frame_is_binary ? WSIO_MSG_TYPE_BINARY : WSIO_MSG_TYPE_TEXT);
    }
}

static void processhttpresponse(WSIO_INSTANCE* wsio_instance, struct lws *wsi)
{
    int n;
    // copy out the HTTP status code.
    n = lws_hdr_total_length(wsi, WSI_TOKEN_HTTP);
    if (n > 0)
    {
        char* buff = malloc(n + 1);
        if (buff)
        {
            lws_hdr_copy(wsi, buff, n + 1, WSI_TOKEN_HTTP);
            wsio_instance->http_code = atoi(buff);
            LogInfo("http_code: %d", wsio_instance->http_code);
            free(buff);
        }
    }
}

static int on_ws_callback(struct lws *wsi, enum lws_callback_reasons reason, void *user, void *in, size_t len)
{
    struct lws_context* context;
    WSIO_INSTANCE* wsio_instance;
    switch (reason)
    {
    case LWS_CALLBACK_CLOSED:
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);
        // called when the network or remote server dropped the connection or when calling lws_context_destroy.
        if (wsio_instance->io_state != IO_STATE_NOT_OPEN)
        {
            indicate_error(wsio_instance);
            wsio_instance->io_state = IO_STATE_NOT_OPEN;
        }
        break;

    case LWS_CALLBACK_CLIENT_FILTER_PRE_ESTABLISH:
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);
        processhttpresponse(wsio_instance, wsi);
        break;

    case LWS_CALLBACK_CLIENT_ESTABLISHED:
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);

        /* Codes_SRS_WSIO_01_066: [If an open action is pending, the on_io_open_complete callback shall be triggered with IO_OPEN_OK and from now on it shall be possible to send/receive data.] */
        switch (wsio_instance->io_state)
        {
        default:
            break;

        case IO_STATE_OPEN:
            /* Codes_SRS_WSIO_01_068: [If the IO is already open, the on_io_error callback shall be triggered.] */
            indicate_error(wsio_instance);
            break;

        case IO_STATE_OPENING:
            /* Codes_SRS_WSIO_01_036: [The callback on_io_open_complete shall be called with io_open_result being set to IO_OPEN_OK when the open action is succesfull.] */
            wsio_instance->io_state = IO_STATE_OPEN;
            indicate_open_complete(wsio_instance, IO_OPEN_OK);
            break;
        }

        break;

    case LWS_CALLBACK_CLIENT_CONNECTION_ERROR:
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);
        processhttpresponse(wsio_instance, wsi);

        switch (wsio_instance->io_state)
        {
        default:
            break;

        case IO_STATE_OPEN:
            /* Codes_SRS_WSIO_01_070: [If the IO is already open, the on_io_error callback shall be triggered.] */
            indicate_error(wsio_instance);
            break;

        case IO_STATE_OPENING:
            LogError("LWS_CALLBACK_CLIENT_CONNECTION_ERROR: %s", (char*)in);
            /* Codes_SRS_WSIO_01_037: [If any error occurs while the open action is in progress, the callback on_io_open_complete shall be called with io_open_result being set to IO_OPEN_ERROR.] */
            /* Codes_SRS_WSIO_01_069: [If an open action is pending, the on_io_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
            indicate_open_complete(wsio_instance, IO_OPEN_ERROR);
            wsio_instance->io_state = IO_STATE_NOT_OPEN;
            break;
        }

        break;

    case LWS_CALLBACK_CLIENT_WRITEABLE:
    {
        LIST_ITEM_HANDLE first_pending_io;

        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);

        switch (wsio_instance->io_state)
        {
        default:
            break;

        case IO_STATE_OPENING:
            /* Codes_SRS_WSIO_01_121: [If this event is received in while an open action is incomplete, the open_complete callback shall be called with IO_OPEN_ERROR.] */
            indicate_open_complete(wsio_instance, IO_OPEN_ERROR);
            wsio_instance->io_state = IO_STATE_NOT_OPEN;
            break;

        case IO_STATE_OPEN:
            /* Codes_SRS_WSIO_01_120: [This event shall only be processed if the IO is open.] */
            /* Codes_SRS_WSIO_01_071: [If any pending IO chunks queued in wsio_send are to be sent, then the first one shall be retrieved from the queue.] */
            first_pending_io = list_get_head_item(wsio_instance->pending_io_list);

            if (first_pending_io != NULL)
            {
                PENDING_SOCKET_IO* pending_socket_io = (PENDING_SOCKET_IO*)list_item_get_value(first_pending_io);
                if (pending_socket_io == NULL)
                {
                    indicate_error(wsio_instance);
                }
                else
                {
                    bool is_partially_sent = pending_socket_io->is_partially_sent;

                    /* Codes_SRS_WSIO_01_072: [Enough space to fit the data and LWS_SEND_BUFFER_PRE_PADDING and LWS_SEND_BUFFER_POST_PADDING shall be allocated.] */
                    unsigned char* ws_buffer = (unsigned char*)malloc(LWS_SEND_BUFFER_PRE_PADDING + pending_socket_io->size + LWS_SEND_BUFFER_POST_PADDING);
                    if (ws_buffer == NULL)
                    {
                        /* Codes_SRS_WSIO_01_113: [If allocating the memory fails for a pending IO that has been partially sent already then the on_io_error callback shall also be triggered.] */
                        if (is_partially_sent)
                        {
                            indicate_error(wsio_instance);
                        }
                        else
                        {
                            /* Codes_SRS_WSIO_01_081: [If any pending IOs are in the list, lws_callback_on_writable shall be called, while passing the websockets instance obtained in wsio_open as arguments if:] */
                            /* Codes_SRS_WSIO_01_116: [The send failed writing to lws or allocating memory for the data to be passed to lws and no partial data has been sent previously for the pending IO.] */
                            if (list_get_head_item(wsio_instance->pending_io_list) != NULL)
                            {
                                (void)lws_callback_on_writable(wsi);
                            }
                        }

                        if ((remove_pending_io(wsio_instance, first_pending_io, pending_socket_io, IO_SEND_ERROR) != 0) && !is_partially_sent)
                        {
                            /* Codes_SRS_WSIO_01_117: [on_io_error should not be triggered twice when removing a pending IO that failed and a partial send for it has already been done.] */
                            indicate_error(wsio_instance);
                        }
                    }
                    else
                    {
                        int sent;

                        /* Codes_SRS_WSIO_01_074: [The payload queued in wsio_send shall be copied to the newly allocated buffer at the position LWS_SEND_BUFFER_PRE_PADDING.] */
                        (void)memcpy(ws_buffer + LWS_SEND_BUFFER_PRE_PADDING, pending_socket_io->bytes, pending_socket_io->size);

                        /* Codes_SRS_WSIO_01_075: [lws_write shall be called with the websockets interface obtained in wsio_open, the newly constructed padded buffer, the data size queued in wsio_send (actual payload) and the payload type should be set to LWS_WRITE_BINARY.] */
                        sent = lws_write(wsio_instance->wsi, &ws_buffer[LWS_SEND_BUFFER_PRE_PADDING], pending_socket_io->size, pending_socket_io->msgtype);

                        /* Codes_SRS_WSIO_01_118: [If lws_write indicates more bytes sent than were passed to it an error shall be indicated via on_io_error.] */
                        if ((sent < 0) || ((size_t)sent > pending_socket_io->size))
                        {
                            /* Codes_SRS_WSIO_01_114: [Additionally, if the failure is for a pending IO that has been partially sent already then the on_io_error callback shall also be triggered.] */
                            /* Codes_SRS_WSIO_01_119: [If this error happens after the pending IO being partially sent, the on_io_error shall also be indicated.] */
                            if (pending_socket_io->is_partially_sent)
                            {
                                indicate_error(wsio_instance);
                            }
                            else
                            {
                                /* Codes_SRS_WSIO_01_081: [If any pending IOs are in the list, lws_callback_on_writable shall be called, while passing the websockets instance obtained in wsio_open as arguments if:] */
                                /* Codes_SRS_WSIO_01_116: [The send failed writing to lws or allocating memory for the data to be passed to lws and no partial data has been sent previously for the pending IO.] */
                                if (list_get_head_item(wsio_instance->pending_io_list) != NULL)
                                {
                                    (void)lws_callback_on_writable(wsi);
                                }
                            }

                            if ((remove_pending_io(wsio_instance, first_pending_io, pending_socket_io, IO_SEND_ERROR) != 0) && !is_partially_sent)
                            {
                                /* Codes_SRS_WSIO_01_117: [on_io_error should not be triggered twice when removing a pending IO that failed and a partial send for it has already been done.] */
                                indicate_error(wsio_instance);
                            }
                        }
                        else
                        {
                            if ((size_t)sent < pending_socket_io->size)
                            {
                                /* Codes_SRS_WSIO_01_080: [If lws_write succeeds and less bytes than the complete payload have been sent, then the sent bytes shall be removed from the pending IO and only the leftover bytes shall be left as pending and sent upon subsequent events.] */
                                pending_socket_io->bytes += sent;
                                pending_socket_io->size -= sent;
                                pending_socket_io->is_partially_sent = true;

                                /* Codes_SRS_WSIO_01_081: [If any pending IOs are in the list, lws_callback_on_writable shall be called, while passing the websockets instance obtained in wsio_open as arguments if:] */
                                (void)lws_callback_on_writable(wsi);
                            }
                            else
                            {
                                /* Codes_SRS_WSIO_01_060: [The argument on_send_complete shall be optional, if NULL is passed by the caller then no send complete callback shall be triggered.] */
                                /* Codes_SRS_WSIO_01_078: [If the pending IO had an associated on_send_complete, then the on_send_complete function shall be called with the callback_context and IO_SEND_OK as arguments.] */
                                /* Codes_SRS_WSIO_01_057: [The callback on_send_complete shall be called with SEND_RESULT_OK when the send is indicated as complete.] */
                                /* Codes_SRS_WSIO_01_059: [The callback_context argument shall be passed to on_send_complete as is.] */
                                /* Codes_SRS_WSIO_01_077: [If lws_write succeeds and the complete payload has been sent, the queued pending IO shall be removed from the pending list.] */
                                if (remove_pending_io(wsio_instance, first_pending_io, pending_socket_io, IO_SEND_OK) != 0)
                                {
                                    /* Codes_SRS_WSIO_01_079: [If the send was successful and any error occurs during removing the pending IO from the list then the on_io_error callback shall be triggered.]  */
                                    indicate_error(wsio_instance);
                                }
                                else
                                {
                                    /* Codes_SRS_WSIO_01_081: [If any pending IOs are in the list, lws_callback_on_writable shall be called, while passing the websockets instance obtained in wsio_open as arguments if:] */
                                    /* Codes_SRS_WSIO_01_115: [The send over websockets was successful] */
                                    if (list_get_head_item(wsio_instance->pending_io_list) != NULL)
                                    {
                                        (void)lws_callback_on_writable(wsi);
                                    }
                                }
                            }
                        }

                        free(ws_buffer);
                    }
                }
            }
        }

        break;
    }

    case LWS_CALLBACK_CLIENT_RECEIVE:
    {
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);

        switch (wsio_instance->io_state)
        {
        default:
            break;

        case IO_STATE_OPENING:
            /* Codes_SRS_WSIO_01_122: [If an open action is in progress then the on_open_complete callback shall be invoked with IO_OPEN_ERROR.] */
            indicate_open_complete(wsio_instance, IO_OPEN_ERROR);
            wsio_instance->io_state = IO_STATE_NOT_OPEN;
            break;

        case IO_STATE_OPEN:
            /* Codes_SRS_WSIO_01_087: [If the number of bytes is 0 then the on_io_error callback shall be called.] */
            if ((len == 0) ||
                /* Codes_SRS_WSIO_01_088: [If the number of bytes received is positive, but the buffer indicated by the in parameter is NULL, then the on_io_error callback shall be called.] */
                (in == NULL))
            {
                indicate_error(wsio_instance);
            }
            else
            {
				/* Codes_SRS_WSIO_01_082: [LWS_CALLBACK_CLIENT_RECEIVE shall only be processed when the IO is open.] */
				/* Codes_SRS_WSIO_01_083: [When LWS_CALLBACK_CLIENT_RECEIVE is triggered and the IO is open, the on_bytes_received callback passed in wsio_open shall be called.] */
				/* Codes_SRS_WSIO_01_084: [The bytes argument shall point to the received bytes as indicated by the LWS_CALLBACK_CLIENT_RECEIVE in argument.] */
				/* Codes_SRS_WSIO_01_085: [The length argument shall be set to the number of received bytes as indicated by the LWS_CALLBACK_CLIENT_RECEIVE len argument.] */
				/* Codes_SRS_WSIO_01_086: [The callback_context shall be set to the callback_context that was passed in wsio_open.] */
				if (!wsio_instance->rx_buffer_offset && lws_is_final_fragment(wsi))
				{
					// pass the buffer directly to the caller.
                    on_bytes_received(wsio_instance, in, len, lws_frame_is_binary(wsi));
				}
				else // we need to buffer.
				{
					size_t requiredSize = (wsio_instance->rx_buffer_offset + len);
					// ensure we have enough buffer
					if (requiredSize > wsio_instance->rx_buffer_size)
					{
						if (0 == wsio_instance->rx_buffer_size)
						{
							wsio_instance->rx_buffer = (unsigned char*)malloc(requiredSize);
						}
						else
						{
							wsio_instance->rx_buffer = realloc(wsio_instance->rx_buffer, requiredSize);
						}

						if (NULL == wsio_instance->rx_buffer)
						{
							LogError("LWS_CALLBACK_CLIENT_RECEIVE failed to allocate buffer %d.", len);
							indicate_error(wsio_instance);
							break;
						}

						wsio_instance->rx_buffer_size = requiredSize;
					}

					memcpy(wsio_instance->rx_buffer + wsio_instance->rx_buffer_offset, in, len);
					wsio_instance->rx_buffer_offset += len;

					if (lws_is_final_fragment(wsi))
					{
                        on_bytes_received(
                            wsio_instance,
							wsio_instance->rx_buffer, 
							wsio_instance->rx_buffer_offset,
                            lws_frame_is_binary(wsi));
						wsio_instance->rx_buffer_offset = 0;
					}
				}
            }
        }

        break;
    }

    case LWS_CALLBACK_OPENSSL_LOAD_EXTRA_CLIENT_VERIFY_CERTS:
    {
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);

        switch (wsio_instance->io_state)
        {
        default:
            break;

        case IO_STATE_OPEN:
            /* Codes_SRS_WSIO_01_130: [If the event is received when the IO is already open the on_io_error callback shall be triggered.]  */
            indicate_error(wsio_instance);
            break;

        case IO_STATE_NOT_OPEN:
        case IO_STATE_OPENING:
        {
            if (wsio_instance->trusted_ca != NULL)
            {
            /* Codes_SRS_WSIO_01_089: [When LWS_CALLBACK_OPENSSL_LOAD_EXTRA_CLIENT_VERIFY_CERTS is triggered, the certificates passed in the trusted_ca member of WSIO_CONFIG passed in wsio_init shall be loaded in the certificate store.] */
            /* Codes_SRS_WSIO_01_131: [Get the certificate store for the OpenSSL context by calling SSL_CTX_get_cert_store] */
            /* Codes_SRS_WSIO_01_090: [The OpenSSL certificate store is passed in the user argument.] */
            X509_STORE* cert_store = SSL_CTX_get_cert_store(user);
            BIO* cert_memory_bio;
            X509* certificate;
            bool is_error = false;

            if (cert_store == NULL)
            {
                /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                is_error = true;
            }
            else
            {
                /* Codes_SRS_WSIO_01_123: [Creating a new BIO by calling BIO_new.] */
                /* Codes_SRS_WSIO_01_124: [The BIO shall be a memory one (obtained by calling BIO_s_mem).] */
                BIO_METHOD* bio_method = BIO_s_mem();
                if (bio_method == NULL)
                {
                    /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                    is_error = true;
                }
                else
                {
                    cert_memory_bio = BIO_new(bio_method);
                    if (cert_memory_bio == NULL)
                    {
                        /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                        is_error = true;
                    }
                    else
                    {
                        int puts_result = BIO_puts(cert_memory_bio, wsio_instance->trusted_ca);

                        /* Codes_SRS_WSIO_01_125: [Setting the certificates string as the input by using BIO_puts.] */
                        if ((puts_result < 0) || 
                            ((size_t)puts_result != strlen(wsio_instance->trusted_ca)))
                        {
                            /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                            is_error = true;
                        }
                        else
                        {
                            do
                            {
                                /* Codes_SRS_WSIO_01_126: [Reading every certificate by calling PEM_read_bio_X509] */
                                certificate = PEM_read_bio_X509(cert_memory_bio, NULL, NULL, NULL);

                                /* Codes_SRS_WSIO_01_132: [When PEM_read_bio_X509 returns NULL then no more certificates are available in the input string.] */
                                if (certificate != NULL)
                                {
                                    /* Codes_SRS_WSIO_01_127: [Adding the read certificate to the store by calling X509_STORE_add_cert] */
                                    if (!X509_STORE_add_cert(cert_store, certificate))
                                    {
                                        /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                                        is_error = true;
                                        X509_free(certificate);
                                        break;
                                    }
                                }
                            } while (certificate != NULL);
                        }

                        /* Codes_SRS_WSIO_01_128: [Freeing the BIO] */
                        BIO_free(cert_memory_bio);
                    }
                }
            }

            if (is_error)
            {
                /* Codes_SRS_WSIO_01_129: [If any of the APIs fails and an open call is pending the on_open_complete callback shall be triggered with IO_OPEN_ERROR.] */
                if (wsio_instance->io_state == IO_STATE_OPENING)
                {
                    indicate_open_complete(wsio_instance, IO_OPEN_ERROR);
                }
            }

            break;
        }
        }
        }
        break;
    }
    case LWS_CALLBACK_CLIENT_APPEND_HANDSHAKE_HEADER:
    {
        context = lws_get_context(wsi);
        wsio_instance = lws_context_user(context);

        if (len < 100)
        {
            return 1;
        }
        
        AddHeadersBeforeToRequest(wsio_instance->hHeaders, (char **) in);
    }
    default:
        break;
    }

    return 0;
}

CONCRETE_IO_HANDLE wsio_create(void* io_create_parameters)
{
    /* Codes_SRS_WSIO_01_003: [io_create_parameters shall be used as a WSIO_CONFIG*.] */
    WSIO_CONFIG* ws_io_config = io_create_parameters;
    WSIO_INSTANCE* result;

#if defined(GB_DEBUG_ALLOC) && defined(GB_MEASURE_MEMORY_FOR_THIS)
    lws_set_allocator(wsio_gb_realloc);
#endif // defined(GB_DEBUG_ALLOC) && defined(GB_MEASURE_MEMORY_FOR_THIS)

    lws_set_log_level(LLL_ERR | LLL_WARN, lws_loggercb);

    if ((ws_io_config == NULL) ||
        /* Codes_SRS_WSIO_01_004: [If any of the WSIO_CONFIG fields host, protocol_name or relative_path is NULL then wsio_create shall return NULL.] */
        (ws_io_config->host == NULL) ||
        (ws_io_config->relative_path == NULL))
    {
        result = NULL;
    }
    else
    {
        /* Codes_SRS_WSIO_01_001: [wsio_create shall create an instance of a wsio and return a non-NULL handle to it.] */
        result = malloc(sizeof(WSIO_INSTANCE));
        if (result != NULL)
        {
			memset(result, 0, sizeof(WSIO_INSTANCE));

            /* Codes_SRS_WSIO_01_098: [wsio_create shall create a pending IO list that is to be used when sending buffers over the libwebsockets IO by calling list_create.] */
            result->pending_io_list = list_create();
            if (result->pending_io_list == NULL)
            {
                /* Codes_SRS_WSIO_01_099: [If list_create fails then wsio_create shall fail and return NULL.] */
                free(result);
                result = NULL;
            }
            else
            {
                /* Codes_SRS_WSIO_01_006: [The members host, protocol_name, relative_path and trusted_ca shall be copied for later use (they are needed when the IO is opened).] */
                result->host = (char*)malloc(strlen(ws_io_config->host) + 1);
                if (result->host == NULL)
                {
                    /* Codes_SRS_WSIO_01_005: [If allocating memory for the new wsio instance fails then wsio_create shall return NULL.] */
                    list_destroy(result->pending_io_list);
                    free(result);
                    result = NULL;
                }
                else
                {
                    result->relative_path = (char*)malloc(strlen(ws_io_config->relative_path) + 1);
                    if (result->relative_path == NULL)
                    {
                        /* Codes_SRS_WSIO_01_005: [If allocating memory for the new wsio instance fails then wsio_create shall return NULL.] */
                        free(result->host);
                        list_destroy(result->pending_io_list);
                        free(result);
                        result = NULL;
                    }
                    else
                    {
                        if (NULL != ws_io_config->protocol_name)
                        {
                            result->protocol_name = (char*)malloc(strlen(ws_io_config->protocol_name) + 1);
                            if (result->protocol_name == NULL)
                            {
                                /* Codes_SRS_WSIO_01_005: [If allocating memory for the new wsio instance fails then wsio_create shall return NULL.] */
                                free(result->relative_path);
                                free(result->host);
                                list_destroy(result->pending_io_list);
                                free(result);
                                result = NULL;
                            }
                        }
                        else
                        {
                            result->protocol_name = NULL;
                        }

                        if (result != NULL)
                        {
                            result->protocols = (struct lws_protocols*)malloc(sizeof(struct lws_protocols) * 2);
                            if (result->protocols == NULL)
                            {
                                /* Codes_SRS_WSIO_01_005: [If allocating memory for the new wsio instance fails then wsio_create shall return NULL.] */
                                free(result->relative_path);
                                if (result->protocol_name) free(result->protocol_name);
                                free(result->host);
                                list_destroy(result->pending_io_list);
                                free(result);
                                result = NULL;
                            }
                            else
                            {
                                result->trusted_ca = NULL;

                                /* Codes_SRS_WSIO_01_012: [The protocols member shall be populated with 2 protocol entries, one containing the actual protocol to be used and one empty (fields shall be NULL or 0).] */
                                /* Codes_SRS_WSIO_01_013: [callback shall be set to a callback used by the wsio module to listen to libwebsockets events.] */
                                result->protocols[0].callback = on_ws_callback;
                                /* Codes_SRS_WSIO_01_014: [id shall be set to 0] */
                                result->protocols[0].id = 0;
                                /* Codes_SRS_WSIO_01_015: [name shall be set to protocol_name as passed to wsio_create] */
                                result->protocols[0].name = result->protocol_name;
                                /* Codes_SRS_WSIO_01_016: [per_session_data_size shall be set to 0] */
                                result->protocols[0].per_session_data_size = 0;
                                /* Codes_SRS_WSIO_01_017: [rx_buffer_size shall be set to 0, as there is no need for atomic frames] */
                                result->protocols[0].rx_buffer_size = 0;
                                /* Codes_SRS_WSIO_01_019: [user shall be set to NULL] */
                                result->protocols[0].user = NULL;

                                result->protocols[1].callback = NULL;
                                result->protocols[1].id = 0;
                                result->protocols[1].name = NULL;
                                result->protocols[1].per_session_data_size = 0;
                                result->protocols[1].rx_buffer_size = 0;
                                result->protocols[1].user = NULL;

                                (void)strcpy(result->host, ws_io_config->host);
								(void)strcpy(result->relative_path, ws_io_config->relative_path);
                                result->port = ws_io_config->port;
                                result->use_ssl = ws_io_config->use_ssl;
                                result->io_state = IO_STATE_NOT_OPEN;

                                /* Codes_SRS_WSIO_01_100: [The trusted_ca member shall be optional (it can be NULL).] */
                                if (ws_io_config->trusted_ca != NULL)
                                {
                                    result->trusted_ca = (char*)malloc(strlen(ws_io_config->trusted_ca) + 1);
                                    if (result->trusted_ca == NULL)
                                    {
                                        /* Codes_SRS_WSIO_01_005: [If allocating memory for the new wsio instance fails then wsio_create shall return NULL.] */
                                        free(result->protocols);
                                        free(result->protocol_name);
                                        free(result->relative_path);
                                        free(result->host);
                                        list_destroy(result->pending_io_list);
                                        free(result);
                                        result = NULL;
                                    }
                                    else
                                    {
                                        (void)strcpy(result->trusted_ca, ws_io_config->trusted_ca);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    return result;
}

void wsio_destroy(CONCRETE_IO_HANDLE ws_io)
{
    /* Codes_SRS_WSIO_01_008: [If ws_io is NULL, wsio_destroy shall do nothing.] */
    if (ws_io != NULL)
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)ws_io;

        /* Codes_SRS_WSIO_01_009: [wsio_destroy shall execute a close action if the IO has already been open or an open action is already pending.] */
        (void)wsio_close(wsio_instance, NULL, NULL);

        /* Codes_SRS_WSIO_01_007: [wsio_destroy shall free all resources associated with the wsio instance.] */
        free(wsio_instance->protocols);
        free(wsio_instance->host);
        free(wsio_instance->protocol_name);
        free(wsio_instance->relative_path);
        free(wsio_instance->trusted_ca);
		if (wsio_instance->rx_buffer)
		{
			free(wsio_instance->rx_buffer);
		}

        list_destroy(wsio_instance->pending_io_list);

        free(ws_io);
    }
}

static int wsio_open_ex(CONCRETE_IO_HANDLE ws_io, ON_IO_OPEN_COMPLETE on_io_open_complete, void* on_io_open_complete_context, ON_BYTES_RECEIVED on_bytes_received, ON_WSIO_BYTES_RECEIVED on_bytes_received_wsio, void* on_bytes_received_context, ON_IO_ERROR on_io_error, void* on_io_error_context)
{
    int result = 0;

    if (ws_io == NULL)
    {
        result = __LINE__;
    }
    else
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)ws_io;

        /* Codes_SRS_WSIO_01_034: [If another open is in progress or has completed successfully (the IO is open), wsio_open shall fail and return a non-zero value without performing any connection related activities.] */
        if (wsio_instance->io_state != IO_STATE_NOT_OPEN)
        {
            result = __LINE__;
        }
        else
        {
            wsio_instance->on_bytes_received_wsio = on_bytes_received_wsio;
            wsio_instance->on_bytes_received = on_bytes_received;
            wsio_instance->on_bytes_received_context = on_bytes_received_context;
            wsio_instance->on_io_open_complete = on_io_open_complete;
            wsio_instance->on_io_open_complete_context = on_io_open_complete_context;
            wsio_instance->on_io_error = on_io_error;
            wsio_instance->on_io_error_context = on_io_error_context;
            wsio_instance->http_code = 0;

            int ietf_version = -1; /* latest */
            struct lws_context_creation_info info;
			struct lws_client_connect_info ccinfo;

			memset(&info, 0, sizeof info);
			memset(&ccinfo, 0, sizeof ccinfo);

            /* Codes_SRS_WSIO_01_011: [The port member of the info argument shall be set to CONTEXT_PORT_NO_LISTEN.] */
            info.port = CONTEXT_PORT_NO_LISTEN;
            /* Codes_SRS_WSIO_01_012: [The protocols member shall be populated with 2 protocol entries, one containing the actual protocol to be used and one empty (fields shall be NULL or 0).] */
            info.protocols = wsio_instance->protocols;
            /* Codes_SRS_WSIO_01_092: [gid and uid shall be set to -1.] */
            info.gid = -1;
            info.uid = -1;
            /* Codes_SRS_WSIO_01_096: [The member user shall be set to a user context that will be later passed by the libwebsockets callbacks.] */
            info.user = wsio_instance;
            /* Codes_SRS_WSIO_01_093: [The members iface, token_limits, ssl_cert_filepath, ssl_private_key_filepath, ssl_private_key_password, ssl_ca_filepath, ssl_cipher_list and provided_client_ssl_ctx shall be set to NULL.] */
            info.iface = NULL;
            info.token_limits = NULL;
            info.ssl_ca_filepath = NULL;
            info.ssl_cert_filepath = NULL;
            info.ssl_cipher_list = NULL;
            info.ssl_private_key_filepath = NULL;
            info.ssl_private_key_password = NULL;
            info.provided_client_ssl_ctx = NULL;
            /* Codes_SRS_WSIO_01_094: [No proxy support shall be implemented, thus setting http_proxy_address to NULL.] */
            info.http_proxy_address = NULL;
            /* Codes_SRS_WSIO_01_095: [The member options shall be set to 0.] */
            info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;
            info.ka_time = wsio_instance->ka_time;
            if (info.ka_time)
            {
                info.ka_interval = 1;
                info.ka_probes = 1;
            }

			/* Codes_SRS_WSIO_01_025: [address shall be the hostname passed to wsio_create] */
			ccinfo.address = wsio_instance->host;
			/* Codes_SRS_WSIO_01_026: [port shall be the port passed to wsio_create] */
			/* Codes_SRS_WSIO_01_103: [otherwise it shall be 0.] */
			ccinfo.port = wsio_instance->port;
			/* Codes_SRS_WSIO_01_028: [path shall be the relative_path passed in wsio_create] */
			ccinfo.path = wsio_instance->relative_path;
			/* Codes_SRS_WSIO_01_029: [host shall be the host passed to wsio_create] */
			ccinfo.host = wsio_instance->host;
			/* Codes_SRS_WSIO_01_030: [origin shall be the host passed to wsio_create] */
			ccinfo.origin = wsio_instance->host;
			/* Codes_SRS_WSIO_01_031: [protocol shall be the protocol_name passed to wsio_create] */
			ccinfo.protocol = wsio_instance->protocols[0].name;
			/* Codes_SRS_WSIO_01_032: [ietf_version_or_minus_one shall be -1] */
			ccinfo.ietf_version_or_minus_one = ietf_version;
			ccinfo.ssl_connection = wsio_instance->use_ssl;

            /* Codes_SRS_WSIO_01_010: [wsio_open shall create a context for the libwebsockets connection by calling lws_create_context.] */
            wsio_instance->ws_context = lws_create_context(&info);
            if (wsio_instance->ws_context == NULL)
            {
                /* Codes_SRS_WSIO_01_022: [If creating the context fails then wsio_open shall fail and return a non-zero value.] */
                result = __LINE__;
            }
            else
            {
                wsio_instance->io_state = IO_STATE_OPENING;
				ccinfo.context = wsio_instance->ws_context;

                /* Codes_SRS_WSIO_01_023: [wsio_open shall trigger the libwebsocket connect by calling lws_client_connect_via_info] */
				wsio_instance->wsi = lws_client_connect_via_info(&ccinfo);
                if (wsio_instance->wsi == NULL)
                {
                    /* Codes_SRS_WSIO_01_033: [If lws_client_connect fails then wsio_open shall fail and return a non-zero value.] */
                    destroy_context(wsio_instance, IO_STATE_NOT_OPEN);

                    result = __LINE__;
                }
                else
                {
                    /* Codes_SRS_WSIO_01_104: [On success, wsio_open shall return 0.] */
                    result = 0;
                }
            }
        }
    }
    
    return result;
}

int wsio_open(
    CONCRETE_IO_HANDLE ws_io, 
    ON_IO_OPEN_COMPLETE on_io_open_complete, 
    void* on_io_open_complete_context, 
    ON_WSIO_BYTES_RECEIVED on_bytes_received, 
    void* on_bytes_received_context, 
    ON_IO_ERROR on_io_error, 
    void* on_io_error_context)
{
    return wsio_open_ex(
        ws_io, 
        on_io_open_complete, 
        on_io_open_complete_context, 
        NULL, on_bytes_received, 
        on_bytes_received_context, 
        on_io_error, 
        on_io_error_context);
}

static int wsio_open_xio(
    CONCRETE_IO_HANDLE ws_io, 
    ON_IO_OPEN_COMPLETE on_io_open_complete, 
    void* on_io_open_complete_context, 
    ON_BYTES_RECEIVED on_bytes_received, 
    void* on_bytes_received_context, 
    ON_IO_ERROR on_io_error, 
    void* on_io_error_context)
{
    return wsio_open_ex(
        ws_io, 
        on_io_open_complete, 
        on_io_open_complete_context, 
        on_bytes_received, 
        NULL, 
        on_bytes_received_context, 
        on_io_error, 
        on_io_error_context);
}

int wsio_close(CONCRETE_IO_HANDLE ws_io, ON_IO_CLOSE_COMPLETE on_io_close_complete, void* on_io_close_complete_context)
{
    int result = 0;

    if (ws_io == NULL)
    {
        /* Codes_SRS_WSIO_01_042: [if ws_io is NULL, wsio_close shall return a non-zero value.] */
        result = __LINE__;
    }
    else
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)ws_io;

        /* Codes_SRS_WSIO_01_045: [wsio_close when no open action has been issued shall fail and return a non-zero value.] */
        /* Codes_SRS_WSIO_01_046: [wsio_close after a wsio_close shall fail and return a non-zero value.] */
        if (wsio_instance->io_state == IO_STATE_NOT_OPEN)
        {
            result = __LINE__;
        }
        else
        {
            /* Codes_SRS_WSIO_01_038: [If wsio_close is called while the open action is in progress, the callback on_io_open_complete shall be called with io_open_result being set to IO_OPEN_CANCELLED and then the wsio_close shall proceed to close the IO.] */
            if (wsio_instance->io_state == IO_STATE_OPENING)
            {
                indicate_open_complete(wsio_instance, IO_OPEN_CANCELLED);
            }
            else
            {
                cancel_io(wsio_instance);
            }

            /* Codes_SRS_WSIO_01_041: [wsio_close shall close the websockets IO if an open action is either pending or has completed successfully (if the IO is open).] */
            /* Codes_SRS_WSIO_01_043: [wsio_close shall close the connection by calling lws_context_destroy.] */
            destroy_context(wsio_instance, IO_STATE_NOT_OPEN);

            /* Codes_SRS_WSIO_01_049: [The argument on_io_close_complete shall be optional, if NULL is passed by the caller then no close complete callback shall be triggered.] */
            if (on_io_close_complete != NULL)
            {
                /* Codes_SRS_WSIO_01_047: [The callback on_io_close_complete shall be called after the close action has been completed in the context of wsio_close (wsio_close is effectively blocking).] */
                /* Codes_SRS_WSIO_01_048: [The callback_context argument shall be passed to on_io_close_complete as is.] */
                on_io_close_complete(on_io_close_complete_context);
            }

            /* Codes_SRS_WSIO_01_044: [On success wsio_close shall return 0.] */
            result = 0;
        }
    }

    return result;
}

/* Codes_SRS_WSIO_01_050: [wsio_send shall send the buffer bytes through the websockets connection.] */
int wsio_send(CONCRETE_IO_HANDLE ws_io, const void* buffer, size_t size, WSIO_MSG_TYPE message_type, ON_SEND_COMPLETE on_send_complete, void* callback_context)
{
    int result;

    /* Codes_SRS_WSIO_01_052: [If any of the arguments ws_io or buffer are NULL, wsio_send shall fail and return a non-zero value.] */
    if ((ws_io == NULL) ||
        (buffer == NULL) ||
        /* Codes_SRS_WSIO_01_053: [If size is zero then wsio_send shall fail and return a non-zero value.] */
        (size == 0))
    {
        result = __LINE__;
    }
    else
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)ws_io;

        /* Codes_SRS_WSIO_01_051: [If the wsio is not OPEN (open has not been called or is still in progress) then wsio_send shall fail and return a non-zero value.] */
        if (wsio_instance->io_state != IO_STATE_OPEN)
        {
            result = __LINE__;
        }
        else
        {
            /* Codes_SRS_WSIO_01_054: [wsio_send shall queue the buffer and size until the libwebsockets callback is invoked with the event LWS_CALLBACK_CLIENT_WRITEABLE.] */
            if (add_pending_io(wsio_instance, buffer, size, message_type, on_send_complete, callback_context) != 0)
            {
                result = __LINE__;
            }
            else
            {
                /* Codes_SRS_WSIO_01_056: [After queueing the data, wsio_send shall call lws_callback_on_writable, while passing as arguments the websockets instance previously obtained in wsio_open from lws_client_connect.] */
                if (lws_callback_on_writable(wsio_instance->wsi) < 0)
                {
                    /* Codes_SRS_WSIO_01_106: [If lws_callback_on_writable returns a negative value, wsio_send shall fail and return a non-zero value.] */
                    result = __LINE__;
                }
                else
                {
                    /* Codes_SRS_WSIO_01_107: [On success, wsio_send shall return 0.] */
                    result = 0;
                }
            }
        }
    }

    return result;
}

void wsio_dowork(CONCRETE_IO_HANDLE ws_io)
{
    /* Codes_SRS_WSIO_01_063: [If the ws_io argument is NULL, wsio_dowork shall do nothing.] */
    if (ws_io != NULL)
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)ws_io;

        /* Codes_SRS_WSIO_01_062: [This shall be done if the IO is not closed.] */
        if ((wsio_instance->io_state == IO_STATE_OPEN) ||
            (wsio_instance->io_state == IO_STATE_OPENING))
        {
            /* Codes_SRS_WSIO_01_061: [wsio_dowork shall service the libwebsockets context by calling lws_service and passing as argument the context obtained in wsio_open.] */
            /* Codes_SRS_WSIO_01_112: [The timeout for lws_service shall be 0.] */
            (void)lws_service(wsio_instance->ws_context, 0);
        }
    }
}

/* Codes_SRS_WSIO_03_001: [wsio_setoption does not support any options and shall always return non-zero value.] */
int wsio_setoption(CONCRETE_IO_HANDLE socket_io, const char* optionName, const void* value)
{
    /* Codes_SRS_WSIO_01_052: [If any of the arguments ws_io or buffer are NULL, wsio_send shall fail and return a non-zero value.] */
    if ((socket_io == NULL) ||
        (optionName == NULL))
    {
        return __LINE__;
    }
    else
    {
        WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)socket_io;
        if (!strcmp(optionName, "connectionheaders"))
        {
            wsio_instance->hHeaders = (HTTP_HEADERS_HANDLE)value;
            return 0;
        }
        else if (!strcmp(optionName, "idletimeout"))
        {
            // idletimeout is in seconds.  ka_time is in whole seconds.
            wsio_instance->ka_time = (*(const int *)value) / 1000;
            return 0;
        }
    }
    return __LINE__;
}

/* Codes_SRS_WSIO_01_064: [wsio_get_interface_description shall return a pointer to an IO_INTERFACE_DESCRIPTION structure that contains pointers to the functions: wsio_create, wsio_destroy, wsio_open, wsio_close, wsio_send and wsio_dowork.] */
const IO_INTERFACE_DESCRIPTION* wsio_get_interface_description(void)
{
    return &ws_io_interface_description;
}

int wsio_gethttpstatus(CONCRETE_IO_HANDLE socket_io)
{
    WSIO_INSTANCE* wsio_instance = (WSIO_INSTANCE*)socket_io;
    if (!wsio_instance)
    {
        return -1;
    }

    return wsio_instance->http_code;
}