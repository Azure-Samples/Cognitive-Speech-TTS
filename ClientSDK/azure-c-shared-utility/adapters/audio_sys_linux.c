// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#if !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 201112L
#endif

#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <math.h>
#include <alsa/asoundlib.h>
#include "azure_c_shared_utility/audio_sys.h"
#include "azure_c_shared_utility/xlogging.h"
#include "azure_c_shared_utility/buffer_.h"
#include "azure_c_shared_utility/threadapi.h"
#include "azure_c_shared_utility/lock.h"

#define MAGIC_TAG_RIFF      0x46464952
#define MAGIC_TAG_WAVE      0x45564157
#define MAGIC_TAG_data      0x61746164
#define MAGIC_TAG_fmt       0x20746d66

#define AUDIO_CHANNELS_MONO     1
#define AUDIO_SAMPLE_RATE       16000
#define AUDIO_BITS              16

// MAX_DEVICES is the maximum amount of PCM output instances we can have per device.
#define MAX_DEVICES 4
#define OUTPUT_FRAME_COUNT (snd_pcm_uframes_t) 768
#define INPUT_FRAME_COUNT (snd_pcm_uframes_t) 232

#define alloca __builtin_alloca

typedef bool(*DEVICE_IO_COMPARE_FUNCTION)(const char* ioType);

// ALSA on Pi doesn't properly downsample dynamically per device.
// This structure is for allowing multiple devices to lock into a single rate and channel.
typedef struct AUDIOOUT_DEVICE_TAG
{
    snd_pcm_t* pcmHandle;
    uint32_t   rate;
    uint16_t   nChannels;
} AUDIOOUT_DEVICE;

typedef struct AUDIO_SYS_DATA_TAG
{
    ON_AUDIOOUTPUT_STATE_CALLBACK output_state_cb;
    ON_AUDIOINPUT_STATE_CALLBACK input_state_cb;
    AUDIOINPUT_WRITE audio_write_cb;
    void* user_write_ctx;
    void* user_outputctx;
    void* user_inputctx;
    uint16_t channels;
    uint32_t sampleRate;
    uint16_t bitsPerSample;
    bool waveDataDirty;
    AUDIO_STATE current_output_state;
    AUDIO_STATE current_input_state;
    THREAD_HANDLE input_thread;
    snd_pcm_t* pcmHandle;
    AUDIOOUT_DEVICE audioDevices[MAX_DEVICES];
    bool output_canceled;
    LOCK_HANDLE lock;
    STRING_HANDLE hDeviceName;
    uint16_t inputFrameCnt;
} AUDIO_SYS_DATA;

struct _ASYNCAUDIO
{
    AUDIO_SYS_DATA*        audioData;
    FILE *                 fp;
    AUDIO_WAVEFORMAT       format;
    AUDIOINPUT_WRITE       pfnReadCallback;
    AUDIOCOMPLETE_CALLBACK pfnComplete;
    void*                  pContext;
    uint32_t               dataChunk;
    THREAD_HANDLE          output_thread;
};

static bool Mic_OnlyInput(const char *io)
{
    if ((io == NULL) || (io != NULL && (strcmp(io, "Input") == 0)))
    {
        return true;
    }
    return false;
}

static bool Mic_InputOutput(const char *io)
{
    if ((io == NULL) || (io != NULL && (strcmp(io, "Output") != 0)))
    {
        return true;
    }
    return false;
}

static bool Speaker_Comparator(const char *io)
{
    if ((io == NULL) || (io != NULL && (strcmp(io, "Output") == 0)))
    {
        return true;
    }
    return false;
}

static AUDIO_RESULT write_audio_stream(
    AUDIO_SYS_DATA* audioData,
    const AUDIO_WAVEFORMAT* outputWaveFmt,
    AUDIOINPUT_WRITE pfnReadCallback,
    AUDIOCOMPLETE_CALLBACK pfnComplete,
    void* pContext)
{
    AUDIO_RESULT result = AUDIO_RESULT_OK;
    AUDIOOUT_DEVICE* audioDevice = NULL;
    snd_pcm_hw_params_t* hw_params = NULL;
    AUDIO_STATE current_output_state;
    bool output_canceled;
    uint8_t buffer[3200];
    uint8_t *data;
    int length;
    snd_pcm_format_t fmt;

    if (NULL == pfnReadCallback)
    {
        return AUDIO_RESULT_ERROR;
    }

    switch (outputWaveFmt->wBitsPerSample)
    {
    case 8:
        fmt = SND_PCM_FORMAT_S8;
        break;

    case 16:
        fmt = SND_PCM_FORMAT_S16_LE;
        break;

    case 24:
        fmt = SND_PCM_FORMAT_S24_3LE;
        break;

    default:
        LogError("Invalid wBitsPerSample %d", outputWaveFmt->wBitsPerSample);
        return AUDIO_RESULT_ERROR;
    }

    Lock(audioData->lock);

    current_output_state = audioData->current_output_state;
    if (current_output_state == AUDIO_STATE_STOPPED)
    {
        audioData->current_output_state = AUDIO_STATE_RUNNING;
        audioData->output_canceled = false;
    }

    for (size_t index = 0; index < MAX_DEVICES; index++)
    {
        if ( audioData->audioDevices[index].rate == 0 ||
            // alsa doesn't do a good job with starting a device instance with a 
            // lower samplerate and channels (garbage audio).  Make the ALSA 
            // pool match the assigned settings before using it.
            ((audioData->audioDevices[index].rate == outputWaveFmt->nSamplesPerSec) && (audioData->audioDevices[index].nChannels == outputWaveFmt->nChannels)))
        {
            audioDevice = &audioData->audioDevices[index];
            break;
        }
    }

    Unlock(audioData->lock);

    if (audioDevice == NULL)
    {
        result = AUDIO_RESULT_ERROR;
        LogError("audioDevice is null");
    }
    else if (current_output_state != AUDIO_STATE_STOPPED)
    {
        LogError("invalid output state");
    }
    else
    {
        if (audioDevice->rate == 0)
        {
            snd_pcm_uframes_t frames = OUTPUT_FRAME_COUNT;

            if (0 != snd_pcm_hw_params_malloc(&hw_params) ||
                0 != snd_pcm_hw_params_any(audioDevice->pcmHandle, hw_params) ||
                0 != snd_pcm_hw_params_set_access(audioDevice->pcmHandle, hw_params, SND_PCM_ACCESS_RW_INTERLEAVED) ||
                0 != snd_pcm_hw_params_set_format(audioDevice->pcmHandle, hw_params, fmt) ||
                0 != snd_pcm_hw_params_set_rate(audioDevice->pcmHandle, hw_params, outputWaveFmt->nSamplesPerSec, 0) ||
                0 != snd_pcm_hw_params_set_period_size_near(audioDevice->pcmHandle, hw_params, &frames, 0) ||
                0 != snd_pcm_hw_params_set_channels(audioDevice->pcmHandle, hw_params, outputWaveFmt->nChannels) ||
                0 != snd_pcm_hw_params(audioDevice->pcmHandle, hw_params))
            {
                result = AUDIO_RESULT_ERROR;
                LogError("alsa error: %d %d %d",
                    outputWaveFmt->wBitsPerSample,
                    outputWaveFmt->nSamplesPerSec,
                    outputWaveFmt->nChannels);
            }
            else
            {
                audioDevice->rate = outputWaveFmt->nSamplesPerSec;
                audioDevice->nChannels = outputWaveFmt->nChannels;
            }
        }

        if (result == AUDIO_RESULT_OK)
        {
            size_t blockAlign = (size_t)(outputWaveFmt->nChannels * (outputWaveFmt->wBitsPerSample >> 3));

            // prepare the speaker for audio
            snd_pcm_prepare(audioDevice->pcmHandle);
            if (audioData->output_state_cb != NULL)
            {
                audioData->output_state_cb(audioData->user_outputctx, audioData->current_output_state);
            }

            int writeSuccess = 0;

            data = buffer;
            // block align the bytes to read.
            length = pfnReadCallback(pContext, buffer, sizeof(buffer) - (sizeof(buffer) % blockAlign));

            while(length > 0)
            {
                Lock(audioData->lock);
                current_output_state = audioData->current_output_state;
                output_canceled = audioData->output_canceled;
                Unlock(audioData->lock);

                if (output_canceled)
                {
                    break;
                }

                // send chunks twice the size of the ALSA buffer size / period.
                int chunk = (OUTPUT_FRAME_COUNT * blockAlign * 2);
                if (chunk > length)
                {
                    chunk = length;
                }

                writeSuccess = snd_pcm_writei(audioDevice->pcmHandle, data, chunk / blockAlign);
                if (writeSuccess == -EPIPE)
                {
                    // EPIPE means overrun
                    LogError("snd_pcm_writei overrun occurred");
                    snd_pcm_prepare(audioDevice->pcmHandle);
                    continue;
                }
                else if (writeSuccess < 0)
                {
                    LogError("error from snd_pcm_writei: %s", snd_strerror(writeSuccess));
                    break;
                }

                data += chunk;
                length -= chunk;

                if (!length)
                {
                    data = buffer;
                    // block align the bytes to read.
                    length = pfnReadCallback(pContext, buffer, sizeof(buffer) - (sizeof(buffer) % blockAlign));
                }
            }

            snd_pcm_drain(audioDevice->pcmHandle);

            if (hw_params)
            {
                snd_pcm_hw_params_free(hw_params);
            }

            audioData->current_output_state = AUDIO_STATE_STOPPED;
            if (audioData->output_state_cb != NULL)
            {
                audioData->output_state_cb(audioData->user_outputctx, audioData->current_output_state);
            }
        }
    }

    // we must always call the completion callback.
    if (pfnComplete)
    {
        pfnComplete(pContext);
    }

    return result;
}

static int Alsa_GetDevice(snd_pcm_t** ppPcmHandle, snd_pcm_stream_t streamType, DEVICE_IO_COMPARE_FUNCTION comparator)
{
    int result = __LINE__;
    bool deviceFound = false;
    void** hints = NULL, **iterator;
    char* name, *io;

    if (snd_device_name_hint(-1, "pcm", &hints) < 0 && hints != NULL)
    {
        result = __LINE__;
    }
    else
    {
        iterator = hints;
        while (*iterator != NULL)
        {
            name = snd_device_name_get_hint(*iterator, "NAME");
            io = snd_device_name_get_hint(*iterator, "IOID");
            if (name != NULL && strcmp("null", name) != 0)
            {
                if (comparator(io))
                {
                    if (0 == snd_pcm_open(ppPcmHandle, name, streamType, 0))
                    {
                        LogInfo("Successfully opened '%s' device for %s.", name, io);
                        deviceFound = true;
                        result = 0;
                    }
                }
            }

            if (name)
            {
                free(name);
            }
            if (io)
            {
                free(io);
            }

            if (deviceFound)
            {
                break;
            }
            iterator++;
        }
        snd_device_name_free_hint(hints);
    }
    return result;
}

static int init_alsa_pcm_device(snd_pcm_t** pcmHandle, snd_pcm_stream_t streamType, snd_pcm_uframes_t frames, AUDIO_SYS_DATA* audioData)
{
    int result = 0;
    bool deviceFound = false;

    if (audioData->hDeviceName)
    {
        if (0 == snd_pcm_open(pcmHandle, STRING_c_str(audioData->hDeviceName), streamType, 0))
        {
            LogInfo("Successfully opened '%s' device.", STRING_c_str(audioData->hDeviceName));
            deviceFound = true;
        }
        else
        {
            LogError("snd_pcm_open failed to open device '%s'.", STRING_c_str(audioData->hDeviceName));
        }
    }
    else if (streamType == SND_PCM_STREAM_CAPTURE)
    {
        if (0 == Alsa_GetDevice(pcmHandle, streamType, Mic_OnlyInput) ||
            0 == Alsa_GetDevice(pcmHandle, streamType, Mic_InputOutput))
        {
            deviceFound = true;
        }
    }
    else
    {
        // Get speaker device
        if (0 == Alsa_GetDevice(pcmHandle, streamType, Mic_InputOutput) ||
            !Alsa_GetDevice(pcmHandle, streamType, Speaker_Comparator))
        {
            deviceFound = true;
        }
    }

    if (deviceFound)
    {
        int paramerr = 0;
        snd_pcm_hw_params_t* hw_params = NULL;

        if ((paramerr = snd_pcm_hw_params_malloc(&hw_params)) < 0 || (paramerr = snd_pcm_hw_params_any(*pcmHandle, hw_params)) < 0 ||
            (paramerr = snd_pcm_hw_params_set_access(*pcmHandle, hw_params, SND_PCM_ACCESS_RW_INTERLEAVED)) < 0  ||
            (paramerr = snd_pcm_hw_params_set_format(*pcmHandle, hw_params, audioData->bitsPerSample == 8 ? SND_PCM_FORMAT_S8 : SND_PCM_FORMAT_S16_LE)) < 0 ||
            (paramerr = snd_pcm_hw_params_set_rate(*pcmHandle, hw_params, audioData->sampleRate, 0)) < 0 ||
            (paramerr = snd_pcm_hw_params_set_period_size_near(*pcmHandle, hw_params, &frames, 0)) < 0 ||
            (paramerr = snd_pcm_hw_params_set_channels(*pcmHandle, hw_params, audioData->channels)) < 0 ||
            (paramerr = snd_pcm_hw_params(*pcmHandle, hw_params)) < 0)
        {
            LogError("Failure setting up send hardware info: %d:%s - %s.", paramerr, snd_strerror(paramerr), (streamType == SND_PCM_STREAM_PLAYBACK) ? "playback" : "recording");
            result = __LINE__;
        }
        if (hw_params)
        {
            snd_pcm_hw_params_free(hw_params);
        }
    }
    else
    {
        LogError("No %s device was found.", (streamType == SND_PCM_STREAM_PLAYBACK) ? "playback" : "recording");
        result = __LINE__;
    }
    return result;
}

static int open_wave_data(AUDIO_SYS_DATA* audioData, snd_pcm_stream_t streamType)
{
    int result = 0;

    switch (streamType)
    {
    case SND_PCM_STREAM_CAPTURE:
        if (!audioData->pcmHandle)
        {
            if (init_alsa_pcm_device(&audioData->pcmHandle, SND_PCM_STREAM_CAPTURE, INPUT_FRAME_COUNT, audioData) != 0)
            {
                result = __LINE__;
            }
        }
        break;

    case SND_PCM_STREAM_PLAYBACK:
        for (size_t index = 0; index < MAX_DEVICES; index++)
        {
            int err = init_alsa_pcm_device(&audioData->audioDevices[index].pcmHandle, SND_PCM_STREAM_PLAYBACK, OUTPUT_FRAME_COUNT, audioData);
            if (err != 0)
            {
                result = __LINE__;
                break;
            }
            err = snd_pcm_prepare(audioData->audioDevices[index].pcmHandle);
            if (err < 0)
            {
                LogError("Failure calling snd_pcm_prepare %s.", snd_strerror(err));
                result = __LINE__;
                break;
            }
        }

        if (result == 0)
        {
            audioData->waveDataDirty = false;
        }
        break;
    }

    return result;
}

AUDIO_SYS_HANDLE audio_create()
{
    AUDIO_SYS_DATA* result;

    result = (AUDIO_SYS_DATA*)malloc(sizeof(AUDIO_SYS_DATA));
    if (result != NULL)
    {
        memset(result, 0, sizeof(AUDIO_SYS_DATA));
        result->channels = AUDIO_CHANNELS_MONO;
        result->sampleRate = AUDIO_SAMPLE_RATE;
        result->bitsPerSample = AUDIO_BITS;
        result->waveDataDirty = true;
        result->inputFrameCnt = INPUT_FRAME_COUNT;
        result->current_output_state = AUDIO_STATE_STOPPED;
        result->current_input_state = AUDIO_STATE_STOPPED;
        result->lock = Lock_Init();
    }
    return result;
}

void audio_destroy(AUDIO_SYS_HANDLE handle)
{
    if (handle != NULL)
    {
        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
        if (audioData->pcmHandle != NULL)
        {
            snd_pcm_close(audioData->pcmHandle);
        }

        for (size_t index = 0; index < MAX_DEVICES; index++)
        {
            if (audioData->audioDevices[index].pcmHandle != NULL)
            {
                snd_pcm_close(audioData->audioDevices[index].pcmHandle);
            }
        }

        if (audioData->hDeviceName)
        {
            STRING_delete(audioData->hDeviceName);
        }

        Lock_Deinit(audioData->lock);
        free(audioData);
    }
}

AUDIO_RESULT audio_setcallbacks(AUDIO_SYS_HANDLE handle, ON_AUDIOOUTPUT_STATE_CALLBACK output_cb, void* output_ctx, ON_AUDIOINPUT_STATE_CALLBACK input_cb, void* input_ctx, AUDIOINPUT_WRITE audio_write_cb, void* audio_write_ctx)
{
    AUDIO_RESULT result;
    if (handle != NULL && audio_write_cb != NULL)
    {
        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
        audioData->input_state_cb = input_cb;
        audioData->user_inputctx = input_ctx;
        audioData->output_state_cb = output_cb;
        audioData->user_outputctx = output_ctx;
        audioData->audio_write_cb = audio_write_cb;
        audioData->user_write_ctx = audio_write_ctx;
        result = AUDIO_RESULT_OK;
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }
    return result;
}

static int OutputAsync_Read(void* pContext, uint8_t* pBuffer, size_t size);
static int OutputAsync(void *p)
{
    struct _ASYNCAUDIO *async = (struct _ASYNCAUDIO *)p;
    if (async != NULL)
    {
        uint32_t magic;
        uint32_t chunkSize;
        AUDIO_WAVEFORMAT outputWaveFmt;

        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)async->audioData;
        if (audioData->current_output_state == AUDIO_STATE_RUNNING)
        {
            goto Exit;
        }
        else
        {
            if (audioData->waveDataDirty)
            {
                if (open_wave_data(audioData, SND_PCM_STREAM_PLAYBACK) != 0)
                {
                    LogError("open_wave_data");
                    goto Exit;
                }
            }

            // read up to the format tag
            while (sizeof(magic) == fread(&magic, 1, sizeof(magic), async->fp))
            {
                switch (magic)
                {
                case MAGIC_TAG_RIFF: // RIFF
                    if (sizeof(chunkSize) != fread(&chunkSize, 1, sizeof(chunkSize), async->fp))
                    {
                        goto Exit;
                    }
                    // we don't care about the RIFF size
                    break;

                case MAGIC_TAG_WAVE: // WAVE no length
                    break;

                case MAGIC_TAG_fmt:  // fmt - WAVEFORMAT
                    if (sizeof(chunkSize) != fread(&chunkSize, 1, sizeof(chunkSize), async->fp))
                    {
                        goto Exit;
                    }
                    else if (chunkSize < sizeof(AUDIO_WAVEFORMAT))
                    {
                        goto Exit;
                    }
                    else if (sizeof(outputWaveFmt) != fread(&outputWaveFmt, 1, sizeof(outputWaveFmt), async->fp))
                    {
                        goto Exit;
                    }
                    chunkSize -= sizeof(AUDIO_WAVEFORMAT);
                    if (chunkSize)
                    {
                        fseek(async->fp, chunkSize, SEEK_CUR);
                    }
                    (void)write_audio_stream(audioData, &outputWaveFmt, OutputAsync_Read, NULL, async);
                    // we're done.  All processing has completed within the write_audio_stream call.
                    goto Exit;

                default:
                    if (sizeof(chunkSize) != fread(&chunkSize, 1, sizeof(chunkSize), async->fp))
                    {
                        goto Exit;
                    }
                    fseek(async->fp, chunkSize, SEEK_CUR);
                    break;
                }
            }
        }
    Exit:

        fclose(async->fp);
        ThreadAPI_Join(async->output_thread, NULL);
        free(async);
    }

    return 0;
}

static int OutputAsync_Read(void* pContext, uint8_t* pBuffer, size_t size)
{
    struct _ASYNCAUDIO *async = (struct _ASYNCAUDIO *)pContext;
    uint32_t magic;
    uint32_t chunkSize;

    while (async->dataChunk == 0)
    {
        if ((sizeof(magic) != fread(&magic, 1, sizeof(magic), async->fp)) ||
            (sizeof(chunkSize) != fread(&chunkSize, 1, sizeof(chunkSize), async->fp)))
        {
            return -1;
        }

        switch (magic)
        {
        case MAGIC_TAG_data: // data
            async->dataChunk = chunkSize;
            break;

        default:
            fseek(async->fp, chunkSize, SEEK_CUR);
            break;
        }
    }

    if (size > async->dataChunk)
    {
        size = async->dataChunk;
    }

    if (size != fread(pBuffer, 1, size, async->fp))
    {
        return -1;
    }

    async->dataChunk -= size;

    return (int)size;
}

AUDIO_RESULT audio_output_pause(AUDIO_SYS_HANDLE handle)
{
    AUDIO_RESULT result;
    if (handle != NULL)
    {
        result = AUDIO_RESULT_OK;
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }
    return result;
}

AUDIO_RESULT audio_output_restart(AUDIO_SYS_HANDLE handle)
{
    AUDIO_RESULT result;
    if (handle != NULL)
    {
        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
        if (audioData->current_output_state != AUDIO_STATE_RUNNING)
        {
            result = AUDIO_RESULT_INVALID_STATE;
        }
        else
        {
            result = AUDIO_RESULT_OK;
        }
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }
    return result;
}

AUDIO_RESULT audio_output_stop(AUDIO_SYS_HANDLE handle)
{
    AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
    AUDIO_RESULT result = AUDIO_RESULT_INVALID_ARG;
    AUDIO_STATE current_output_state;

    if (handle != NULL)
    {
        do
        {
            // copy out the thread to cancel any outstanding work.
            Lock(audioData->lock);

            audioData->output_canceled = true;
            current_output_state = audioData->current_output_state;

            Unlock(audioData->lock);

            // set result only once.
            if (result == AUDIO_RESULT_INVALID_ARG)
            {
                if (current_output_state != AUDIO_STATE_RUNNING)
                {
                    result = AUDIO_RESULT_INVALID_STATE;
                }
                else
                {
                    result = AUDIO_RESULT_OK;
                }
            }

            // continue until the state has been reset.
        } while (current_output_state == AUDIO_STATE_RUNNING);
    }
    return result;
}

STRING_HANDLE audio_output_get_name(AUDIO_SYS_HANDLE handle)
{
    AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
    const char *name;
    int i;

    if (handle)
    {
        if (audioData->hDeviceName)
        {
            return STRING_clone(audioData->hDeviceName);
        }

        for (i = 0; i < MAX_DEVICES; i++)
        {
            if (audioData->audioDevices[i].pcmHandle)
            {
                name = snd_pcm_name(audioData->audioDevices[i].pcmHandle);
                if (name)
                {
                    return STRING_construct(name);
                }
            }
        }
        if(audioData->pcmHandle)
        {
            name = snd_pcm_name(audioData->pcmHandle);
            if (name)
            {
                return STRING_construct(name);
            }
        }
    }

    return NULL;
}

static int OutputWriteAsync(void *p)
{
    struct _ASYNCAUDIO *async = (struct _ASYNCAUDIO *)p;
    write_audio_stream(
        async->audioData,
        &async->format,
        async->pfnReadCallback,
        async->pfnComplete,
        async->pContext);
    ThreadAPI_Join(async->output_thread, NULL);
    free(async);
    return 0;
}

AUDIO_RESULT  audio_output_startasync(
    AUDIO_SYS_HANDLE handle,
    const AUDIO_WAVEFORMAT* format,
    AUDIOINPUT_WRITE pfnReadCallback,
    AUDIOCOMPLETE_CALLBACK pfnComplete,
    void* pContext)
{
    AUDIO_RESULT        ret = -1;
    struct _ASYNCAUDIO *async;

    if (!handle || !format || !pfnReadCallback || !pfnComplete)
    {
        return ret;
    }

    if (handle->waveDataDirty)
    {
        if (open_wave_data(handle, SND_PCM_STREAM_PLAYBACK) != 0)
        {
            LogError("open_wave_data");
            return ret;
        }
    }

    async = (struct _ASYNCAUDIO *)malloc(sizeof(struct _ASYNCAUDIO));
    if (!async)
    {
        return ret;
    }

    async->audioData = (AUDIO_SYS_DATA*)handle;
    async->fp = NULL;
    async->format = *format;
    async->pfnReadCallback = pfnReadCallback;
    async->pfnComplete = pfnComplete;
    async->pContext = pContext;
    ret = ThreadAPI_Create(&async->output_thread, OutputWriteAsync, async);

    if (ret)
    {
        free(async);
    }

    return ret;
}

static int SendAudio(void *p)
{
    AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA *)p;
    int  ret;
    uint16_t      audioBufferAlsa[audioData->inputFrameCnt];

    if (audioData->input_state_cb)
    {
        audioData->input_state_cb(audioData->user_inputctx, AUDIO_STATE_RUNNING);
    }

    snd_pcm_prepare(audioData->pcmHandle);

    while (audioData->current_input_state == AUDIO_STATE_RUNNING)
    {
        ret = snd_pcm_readi(audioData->pcmHandle, audioBufferAlsa, audioData->inputFrameCnt);
        if (ret == -EPIPE)
        {
            snd_pcm_prepare(audioData->pcmHandle);
            continue;
        }
        if (ret < 0)
        {
            LogError("error from snd_pcm_readi: %s", snd_strerror(ret));
            break;
        }

        if (audioData->current_input_state == AUDIO_STATE_RUNNING && 
            audioData->audio_write_cb)
        {
            if (audioData->audio_write_cb(
                audioData->user_write_ctx,
                (uint8_t*)audioBufferAlsa,
                (size_t)ret * sizeof(uint16_t)))
            {
                break;
            }
        }
    }

    snd_pcm_drain(audioData->pcmHandle);

    audioData->current_input_state = AUDIO_STATE_STOPPED;
    if (audioData->input_state_cb)
    {
        audioData->input_state_cb(audioData->user_inputctx, audioData->current_input_state);
    }

    return 0;
}

AUDIO_RESULT audio_input_start(AUDIO_SYS_HANDLE handle)
{
    AUDIO_RESULT result;

    if (handle != NULL)
    {
        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
        if (audioData->current_input_state == AUDIO_STATE_RUNNING)
        {
            result = AUDIO_RESULT_INVALID_STATE;
        }
        else
        {
            if (open_wave_data(audioData, SND_PCM_STREAM_CAPTURE) != 0)
            {
                result = AUDIO_RESULT_ERROR;
            }
            else
            {
                audioData->current_input_state = AUDIO_STATE_RUNNING;
                result = ThreadAPI_Create(&audioData->input_thread, SendAudio, audioData);
            }
        }
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }
    return result;
}


AUDIO_RESULT audio_input_stop(AUDIO_SYS_HANDLE handle)
{
    AUDIO_RESULT result;
    AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;
    if (handle != NULL)
    {
        if (audioData->current_input_state != AUDIO_STATE_RUNNING)
        {
            return AUDIO_RESULT_INVALID_STATE;
        }

        audioData->current_input_state = AUDIO_STATE_STOPPED;
        result = ThreadAPI_Join(audioData->input_thread, NULL);
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }
    return result;
}

AUDIO_RESULT audio_set_options(AUDIO_SYS_HANDLE handle, const char* optionName, const void* value)
{
    AUDIO_RESULT result = AUDIO_RESULT_INVALID_ARG;
    if (handle != NULL && optionName != NULL)
    {
        AUDIO_SYS_DATA* audioData = (AUDIO_SYS_DATA*)handle;

        if (strcmp("channels", optionName) == 0)
        {
            uint16_t channel = (uint16_t)*((int*)value);
            if (channel == 1 || channel == 2)
            {
                audioData->channels = channel;
                audioData->waveDataDirty = true;
                result = AUDIO_RESULT_OK;
            }
        }
        else if (strcmp("bits_per_sample", optionName) == 0)
        {
            uint16_t bitPerSample = (uint16_t)*((int*)value);
            if (bitPerSample == 8 || bitPerSample == 16)
            {
                audioData->bitsPerSample = bitPerSample;
                audioData->waveDataDirty = true;
                result = AUDIO_RESULT_OK;
            }
        }
        else if (strcmp("buff_frame_cnt", optionName) == 0)
        {
            audioData->inputFrameCnt = (uint16_t)*((int*)value);
            result = AUDIO_RESULT_OK;
        }
        else if (strcmp("sample_rate", optionName) == 0)
        {
            uint32_t sampleRate = *((uint32_t*)value);
            if (sampleRate == 11025 || sampleRate == 22050 || sampleRate == 44100|| sampleRate == 96000)
            {
                audioData->sampleRate = sampleRate;
                audioData->waveDataDirty = true;
                result = AUDIO_RESULT_OK;
            }
        }
        else if (strcmp(AUDIO_OPTION_DEVICENAME, optionName) == 0)
        {
            if (!audioData->hDeviceName)
            {
                audioData->hDeviceName = STRING_construct((char*)value);
            }
            else
            {
                STRING_copy(audioData->hDeviceName, (char*)value);
            }

            if (audioData->hDeviceName)
            {
                result = AUDIO_RESULT_OK;
            }
        }
    }
    return result;
}

AUDIO_RESULT audio_playwavfile(AUDIO_SYS_HANDLE handle, const char* audioFile)
{
    AUDIO_RESULT        ret = -1;
    struct _ASYNCAUDIO *async;

    if (!handle)
    {
        return ret;
    }

    async = (struct _ASYNCAUDIO *)malloc(sizeof(struct _ASYNCAUDIO));
    if (!async)
    {
        return ret;
    }

    async->audioData = (AUDIO_SYS_DATA*)handle;
    async->dataChunk = 0;
    async->fp = fopen(audioFile, "rb");
    if (!async->fp) { LogError("%s not found", audioFile); goto Exit; }

    ret = ThreadAPI_Create(&async->output_thread, OutputAsync, async);
Exit:

    if (ret)
    {
        free(async);
    }

    return ret;
}

static AUDIO_RESULT audio_output_get_volume_device(int idx, char* hint, snd_mixer_t** handle, snd_mixer_elem_t** device)
{
    snd_mixer_selem_id_t* sid;
    snd_hctl_t* hctl;
    char card[32] = {0};
    snprintf(card, sizeof(card), "hw:%d", idx);

    snd_mixer_selem_id_alloca(&sid);
    snd_mixer_selem_id_set_index(sid, 0);
    snd_mixer_selem_id_set_name(sid, hint);

    if(0 != snd_hctl_open(&hctl, card, 0) ||
       0 != snd_mixer_open(handle, 0) || 0 != snd_mixer_attach_hctl(*handle, hctl) ||
       0 != snd_mixer_selem_register(*handle, NULL, NULL) || 0 != snd_mixer_load(*handle))
    {
        return AUDIO_RESULT_ERROR;
    }

    *device = snd_mixer_find_selem(*handle, sid);
    return AUDIO_RESULT_OK;
}

AUDIO_RESULT  audio_output_set_volume(AUDIO_SYS_HANDLE handle, long volume)
{
    AUDIO_RESULT result = AUDIO_RESULT_ERROR;
    if(volume >= 0 && volume <= 100)
    {
        // Pick the last device, as it is most likely to be accurate
        int cardIdx = -1;
        snd_mixer_t* mhandle = NULL;
        snd_mixer_elem_t* device = NULL;

        while(snd_card_next(&cardIdx) == 0 && cardIdx >= 0)
        {
            if(AUDIO_RESULT_ERROR == audio_output_get_volume_device(cardIdx, "PCM", &mhandle, &device))
            {
                result = AUDIO_RESULT_ERROR;
                continue;
            }
        }

        long min, max;
        if(0 == snd_mixer_selem_get_playback_volume_range(device, &min, &max))
        {
            long newVolume = (long)ceil(((volume / 100.0) * (max-min)) + min);
            if(0 != snd_mixer_selem_set_playback_volume_all(device, newVolume))
            {
                result = AUDIO_RESULT_ERROR;
            } 
        }

        snd_mixer_close(mhandle);
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }

    return result;
}

AUDIO_RESULT  audio_output_get_volume(AUDIO_SYS_HANDLE handle, long* volume)
{
    AUDIO_RESULT result = AUDIO_RESULT_ERROR;
    if(volume != NULL)
    {
        // Pick the last device, as it is most likely to be accurate
        int cardIdx = -1;
        snd_mixer_t* mhandle = NULL;
        snd_mixer_elem_t* device = NULL;

        while(snd_card_next(&cardIdx) == 0 && cardIdx >= 0)
        {
            if(AUDIO_RESULT_ERROR == audio_output_get_volume_device(cardIdx, "PCM", &mhandle, &device))
            {
                result = AUDIO_RESULT_ERROR;
                continue;
            }
        }

        long min, max, currVolume;
        if(0 != snd_mixer_selem_get_playback_volume_range(device, &min, &max) ||
                0 != snd_mixer_selem_get_playback_volume(device, 0, &currVolume))
        {
            result = AUDIO_RESULT_ERROR;
        } 
        else
        {
            *volume = (long)(((double)(currVolume - min)  / (double)(max-min)) * 100.0);
            result = AUDIO_RESULT_OK;
        }

        snd_mixer_close(mhandle);

        result = AUDIO_RESULT_OK;
    }
    else
    {
        result = AUDIO_RESULT_INVALID_ARG;
    }

    return result;
}
