#include<stdio.h>
#include<time.h>
#include"TTS_SDK.h"
#include"iconv\iconv.h"
#include"azure_c_shared_utility\httpheaders.h"
#include"azure_c_shared_utility\httpapi.h"
#include"azure_c_shared_utility\audio_sys.h"
#include "SKP_Silk_SDK_API.h"
#include<windows.h>

const unsigned char* cVoiceName = "Microsoft Server Speech Text to Speech Voice (zh-CN, HuihuiRUS)";
const unsigned char* cLang = "zh-CN";

typedef struct MSTTSHANDLE_TAG
{
	MSTTSVoiceInfo* VoiceInfo;
	unsigned char* ApiKey;
	unsigned char* Token;
	time_t  timeStamp;
}MSTTS_HANDLE;

/////////////////////////////////////////////////////////////////////////////////////////////////
#pragma region AUDIO_DATA_STRUCTURE
const char kSilkV3[] = "#!SILK_V3";
#define SILK_SAMPLESPERFRAME        320
#define SILK_MAXBYTESPERBLOCK       (SILK_SAMPLESPERFRAME * sizeof(uint16_t)) // VBR
#define MAX_BYTES_PER_FRAME         250 // Equals peak bitrate of 100 kbps 

#define WAVE_FORMAT_SIZE            (2 + 2 + 4 + 4 + 2 + 2)
#define WAVE_FORMAT_PCM             1
#define AUDIO_CHANNEL               1
#define AUDIO_BITS                  16
#define AUDIO_SAMPLE_RATE           16000
#define AUDIO_BLOCK_ALIGN           (AUDIO_CHANNEL * (AUDIO_BITS >> 3))
#define AUDIO_BYTE_RATE             (AUDIO_SAMPLE_RATE * AUDIO_BLOCK_ALIGN)
#define MAX_SILK_FRAMES             5

const AUDIO_WAVEFORMAT kSilkFormat =
{
	WAVE_FORMAT_PCM,
	AUDIO_CHANNEL,
	AUDIO_SAMPLE_RATE,
	AUDIO_BYTE_RATE,
	AUDIO_BLOCK_ALIGN,
	AUDIO_BITS
};

static void*   hEncoder = NULL;
static uint8_t encoderBuffer[SILK_MAXBYTESPERBLOCK];
static size_t  encoderBufferOffset = 0;
#pragma endregion
/////////////////////////////////////////////////////////////////////////////////////////////////
#pragma region TRUE_SILK_DECODE
static void*     hDecoder = NULL;

static int silk_decode_frame(
	const SKP_uint8 *inData,
	SKP_int         nBytesIn,
	SKP_int16*      outData,
	size_t          *nBytesOut)
{
	SKP_int16 len;
	int       tot_len = 0;
	SKP_int   ret;
	SKP_SILK_SDK_DecControlStruct DecControl;
	SKP_int   decodedBytes;

	DecControl.API_sampleRate = AUDIO_SAMPLE_RATE;

	// Loop through frames in packet
	do
	{
		// Decode one frame
		ret = SKP_Silk_SDK_Decode(hDecoder, &DecControl, 0, inData, nBytesIn, outData, &len);
		if (ret)
		{
			break;
		}

		outData += len;
		tot_len += len;

		decodedBytes = DecControl.frameSize * DecControl.framesPerPacket;
		if (nBytesIn >= decodedBytes)
		{
			inData += decodedBytes;
			nBytesIn -= decodedBytes;
			DecControl.moreInternalDecoderFrames = 1;
		}

	} while (DecControl.moreInternalDecoderFrames);

	// Convert short array count to byte array count
	*nBytesOut = (size_t)tot_len * sizeof(SKP_int16);

	return ret;
}

static int initdecoder()
{
	SKP_int ret;
	if (!hDecoder)
	{
		SKP_int32 decsize = 0;
		ret = SKP_Silk_SDK_Get_Decoder_Size(&decsize);
		if (ret)
		{
			return ret;
		}

		hDecoder = malloc((size_t)decsize);
		if (!hDecoder)
		{
			return -1;
		}
	}

	return 0;
}

static void audio_decoder_uninitialize(void)
{
	if (hDecoder)
	{
		free(hDecoder);
		hDecoder = NULL;
	}
}
#pragma endregion
/////////////////////////////////////////////////////////////////////////////////////////////////
#pragma region AUDIO_CALLBACK
typedef struct _AsyncAudio
{
	BUFFER_HANDLE       pBuffer;
	size_t				offset;
	void*				hSpeech;
} AsyncAudio;

static int AsyncRead(void* pContext, uint8_t* pBuffer, size_t size)
{
	AsyncAudio *aAudio = (AsyncAudio *)pContext;
	size_t      nBytes;
	uint16_t	len;
	int			ret;
	size_t		decodedBytes = 0;
	size_t		bufferSize;

	//Get pBuffer size
	ret = BUFFER_size(aAudio->pBuffer, &bufferSize);
	if (ret) {
		return -1;
	}

	if (!aAudio || aAudio->offset == bufferSize) {
		return -1;
	}

	ret = initdecoder();
	if (ret) {
		return ret;
	}

	if (!aAudio->offset) {
		ret = SKP_Silk_SDK_InitDecoder(hDecoder);
		if (ret) {
			return ret;
		}
	}

	unsigned char *content = NULL;
	ret = BUFFER_content(aAudio->pBuffer, &content);
	if (ret) {
		return -1;
	}

	if (aAudio->offset < bufferSize && (decodedBytes + SILK_MAXBYTESPERBLOCK) <= size) {
		//The first two bytes of silk are the data length
		len = *(uint16_t*)(content + aAudio->offset);

		nBytes = size - decodedBytes;
		ret = silk_decode_frame(
			content + aAudio->offset + sizeof(uint16_t),
			len,
			(short*)(pBuffer + decodedBytes),
			&nBytes);

		if (ret) {
			return -1;
		}

		aAudio->offset += (sizeof(uint16_t) + len);
		decodedBytes += nBytes;
	}

	Sleep(95);
	return (int)decodedBytes;
}

static void AsyncComplete(void* pContext)
{
	if (pContext) {
		AsyncAudio *aAudio = (AsyncAudio *)pContext;

		audio_decoder_uninitialize();
		if (aAudio->pBuffer) {
			BUFFER_delete(aAudio->pBuffer);
		}
		if (aAudio->hSpeech) {
			//audio_destroy(aAudio->hSpeech);
		}

		free(aAudio);
	}
}
#pragma endregion
/////////////////////////////////////////////////////////////////////////////////////////////////
#pragma region SOME_FUCTIONS
MSTTS_RESULT getKeyValue(const unsigned char* ApiKey, unsigned char** KeyValue) {
	if (ApiKey == NULL || KeyValue == NULL) {
		return MSTTS_INVALID_ARG;
	}

	const char* ApiKey_header = "Ocp-Apim-Subscription-Key";
	const char* URL = "api.cognitive.microsoft.com";
	const char* relativePath = "/sts/v1.0/issueToken";

	MSTTS_RESULT result = MSTTS_OK;
	HTTPAPI_RESULT httpResult;
	HTTP_HEADERS_RESULT headerResult;
	unsigned int httpStatusCode;

	//init HTTPAPI
	httpResult = HTTPAPI_Init();
	if (httpResult == HTTPAPI_OK) {
		//init HTTP handle
		HTTP_HANDLE httpHandle = HTTPAPI_CreateConnection(URL);
		if (httpHandle != NULL) {
			//init HTTP header handle
			HTTP_HEADERS_HANDLE requestHeadersHandle = HTTPHeaders_Alloc();
			HTTP_HEADERS_HANDLE responseHeadersHandle = HTTPHeaders_Alloc();
			if (requestHeadersHandle != NULL && responseHeadersHandle != NULL) {
				//init buffer
				BUFFER_HANDLE responseContent = BUFFER_new();
				if (responseContent != NULL) {
					//add apiKey to header
					headerResult = HTTPHeaders_AddHeaderNameValuePair(requestHeadersHandle, ApiKey_header, ApiKey);
					if (headerResult == HTTPAPI_OK) {
						//send request
						httpResult = HTTPAPI_ExecuteRequest(httpHandle, HTTPAPI_REQUEST_POST, relativePath,
							requestHeadersHandle, NULL, 0, &httpStatusCode, responseHeadersHandle, responseContent);
						if (httpResult == HTTPAPI_OK) {
							size_t ContentSize;
							if (!BUFFER_size(responseContent, &ContentSize)) {
								unsigned char *content = NULL;
								if (!BUFFER_content(responseContent, &content)) {
									unsigned char* KeyValue_tmp = malloc(ContentSize + 1);
									if (KeyValue_tmp) {
										memset(KeyValue_tmp, 0, ContentSize + 1);
										strncpy(KeyValue_tmp, content, ContentSize);
										*KeyValue = KeyValue_tmp;
									}
									else {
										result = MSTTS_ALLOC_FAILED;
									}
								}
								else {
									result = MSTTS_ERROR;
								}
							}
							else {
								result = MSTTS_ERROR;
							}
						}
						else {
							result = MSTTS_ERROR;
						}
					}
					else {
						result = MSTTS_ERROR;
					}
					BUFFER_delete(responseContent);
				}
				else {
					result = MSTTS_ALLOC_FAILED;
				}
				if (requestHeadersHandle) {
					HTTPHeaders_Free(requestHeadersHandle);
				}
				if (responseHeadersHandle) {
					HTTPHeaders_Free(responseHeadersHandle);
				}
			}
			else {
				result = MSTTS_ALLOC_FAILED;
			}
			HTTPAPI_CloseConnection(httpHandle);
		}
		else {
			result = MSTTS_CONNECTION_ERROR;
		}
		HTTPAPI_Deinit();
	}
	else {
		result = MSTTS_INIT_ERROR;
	}

	return result;
}

MSTTS_RESULT getSSML(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType, unsigned char** body) {
	if (hSynthesizerHandle == NULL || pszContent == NULL || body == NULL) {
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;
	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	if (eContentType == MSTTSContentType_SSML) {
		size_t len = 10240;

		*body = malloc(len + 1);
		memset(*body, 0, len + 1);
		snprintf(*body, len+1, "<speak version='1.0' xml:lang='%s'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>",
			SynthesizerHandle->VoiceInfo->lang,
			SynthesizerHandle->VoiceInfo->lang,
			"male",
			SynthesizerHandle->VoiceInfo->voiceName,
			pszContent);
	}
	else {
		size_t len = 10240;

		*body = malloc(len + 1);
		memset(*body, 0, len + 1);
		snprintf(*body, len + 1, "<speak version='1.0' xml:lang='%s'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>",
			SynthesizerHandle->VoiceInfo->lang,
			SynthesizerHandle->VoiceInfo->lang,
			"male",
			SynthesizerHandle->VoiceInfo->voiceName,
			pszContent);
	}

	return MSTTS_OK;
}

MSTTS_RESULT getHeader(HTTP_HEADERS_HANDLE* httpHeadersHandle, unsigned char* KeyValue) {
	if (KeyValue == NULL) {
		return MSTTS_INVALID_ARG;
	}

	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "Content-type", "application/ssml+xml")) {
		return MSTTS_GETHEADER_ERROR;
	}
	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Microsoft-OutputFormat", "raw-16khz-16bit-mono-truesilk")) {
		return MSTTS_GETHEADER_ERROR;
	}
	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Search-AppId", "07D3234E49CE426DAA29772419F436CA")) {
		return MSTTS_GETHEADER_ERROR;
	}
	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Search-ClientID", "1ECFAE91408841A480F00935DC390960")) {
		return MSTTS_GETHEADER_ERROR;
	}
	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "User-Agent", "TTSForPython")) {
		return MSTTS_GETHEADER_ERROR;
	}

	unsigned char* Token = malloc(1000);
	if (Token == NULL) {
		return MSTTS_ALLOC_FAILED;
	}
	memset(Token, 0, 1000);
	strcpy(Token, "Bearer ");
	strcat(Token, KeyValue);
	if (HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "Authorization", Token)) {
		free(Token);
		return MSTTS_GETHEADER_ERROR;
	}
	free(Token);
	return MSTTS_OK;
}
#pragma endregion
/////////////////////////////////////////////////////////////////////////////////////////////////
#pragma region TTS_CLIENT_API
MSTTS_RESULT MSTTS_CreateSpeechSynthesizerHandler(MSTTSHANDLE* phSynthesizerHandle, const unsigned char* MSTTS_ApiKey) {
	if (MSTTS_ApiKey == NULL) {
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;

	//init MSTTSVOICE_HANDLE
	MSTTSVoiceInfo* MSTTSvoicehandle = (MSTTSVoiceInfo*)malloc(sizeof(MSTTSVoiceInfo));
	if (MSTTSvoicehandle) {
		//set default lang
		unsigned char* lang = malloc(strlen(cLang)+1);
		if (lang) {
			memset(lang, 0, strlen(cLang)+1);
			strcpy(lang, cLang);
			MSTTSvoicehandle->lang = lang;

			//set default voiceName
			unsigned char* voiceName = malloc(strlen(cVoiceName)+1);
			if (voiceName) {
				memset(voiceName, 0, strlen(cVoiceName) + 1);
				strcpy(voiceName, cVoiceName);
				MSTTSvoicehandle->voiceName = voiceName;

				//init MSTTS_HANDLE
				MSTTS_HANDLE* MSTTShandle = (MSTTS_HANDLE*)malloc(sizeof(MSTTS_HANDLE));
				if (MSTTShandle) {
					//init ApiKey
					unsigned char* ApiKey = malloc(strlen(MSTTS_ApiKey)+1);
					if (ApiKey) {
						memset(ApiKey, 0, strlen(MSTTS_ApiKey) + 1);
						strcpy(ApiKey, MSTTS_ApiKey);

						//init Token
						unsigned char* token;

						//Get token
						if (getKeyValue(ApiKey, &token) == MSTTS_OK) {
							MSTTShandle->ApiKey = ApiKey;
							MSTTShandle->VoiceInfo = MSTTSvoicehandle;
							MSTTShandle->Token = token;
							time(&MSTTShandle->timeStamp);
							*phSynthesizerHandle = MSTTShandle;
							return MSTTS_OK;
						}
						free(ApiKey);
					}
					else {
						result = MSTTS_ALLOC_FAILED;
					}
					free(MSTTShandle);
				}
				else {
					result = MSTTS_ALLOC_FAILED;
				}
				free(voiceName);
			}
			else {
				result = MSTTS_ALLOC_FAILED;
			}
			free(lang);
		}
		else {
			result = MSTTS_ALLOC_FAILED;
		}
		free(MSTTSvoicehandle);
	}
	else {
		result = MSTTS_ALLOC_FAILED;
	}
	return result;
}

MSTTS_RESULT MSTTS_Speak(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType){
	if (hSynthesizerHandle == NULL || pszContent == NULL) {
		return MSTTS_INVALID_ARG;
	}

	const char* speech_URL = "speech.platform.bing.com";
	const char* relPath = "/synthesize";

	MSTTS_RESULT result = MSTTS_OK;
	HTTPAPI_RESULT ret;

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	unsigned int statusCode;
	void* httpRequestHandle;
	unsigned char* body;

	ret = HTTPAPI_Init();
	if (ret == HTTPAPI_OK) {
		HTTP_HANDLE http_handle = HTTPAPI_CreateConnection(speech_URL);
		if (http_handle != NULL) {
			HTTP_HEADERS_HANDLE httpHeadersHandle = HTTPHeaders_Alloc();
			HTTP_HEADERS_HANDLE responseHeadersHandle = HTTPHeaders_Alloc();
			if (httpHeadersHandle != NULL &&responseHeadersHandle != NULL) {
				//if more than 9 minutes, need to reopen the access token
				time_t time_now;
				time(&time_now);
				double cost = difftime(time_now, SynthesizerHandle->timeStamp);
				if (cost > 9 * 60) {
					free(SynthesizerHandle->Token);
					result = getKeyValue(SynthesizerHandle->ApiKey, &SynthesizerHandle->Token);
					if (result != MSTTS_OK) {
						goto GetTokenError;
					}
					time(&SynthesizerHandle->timeStamp);
				}
				result = getHeader(&httpHeadersHandle, SynthesizerHandle->Token);
				if (result == MSTTS_OK) {
					result = getSSML(SynthesizerHandle, pszContent, eContentType, &body);
					if (result == MSTTS_OK) {
						BUFFER_HANDLE responseContent = BUFFER_new();
						if (responseContent) {
							ret = HTTPAPI_Request(http_handle, HTTPAPI_REQUEST_POST, relPath,
								httpHeadersHandle, body,
								strlen(body), &httpRequestHandle);
							if (ret == HTTPAPI_OK) {
								AUDIO_SYS_HANDLE hAudioDevice = audio_create();
								if (hAudioDevice) {
									AsyncAudio *aAudio = (AsyncAudio*)malloc(sizeof(AsyncAudio));
									if (aAudio) {
										aAudio->pBuffer = responseContent;
										aAudio->offset = 0;
										aAudio->hSpeech = hAudioDevice;

										if (audio_output_startasync(hAudioDevice, &kSilkFormat, AsyncRead, AsyncComplete, aAudio)){
											AsyncComplete(aAudio);
										}

										HTTPAPI_READEVENT_TYPE ReadEvery = HTTPAPI_START_READ;
										do {
											ret = HTTPAPI_Rsponse(&statusCode,
												responseHeadersHandle, responseContent,
												&httpRequestHandle, &ReadEvery);
											if (ret != HTTPAPI_OK || statusCode != 200) {
												result = MSTTS_HTTP_ERROR;
												break;
											}
										} while (ReadEvery != HTTPAPI_READ_END);
										//free(aAudio);
									}
									else {
										result = MSTTS_ALLOC_FAILED;
									}
								}
								else {
									result = MSTTS_ALLOC_FAILED;
								}
							}
							else {
								result = MSTTS_HTTP_ERROR;
							}
							//BUFFER_delete(responseContent);
						}
						else {
							result = MSTTS_ERROR;
						}
						free(body);
					}
					else {
						result = MSTTS_ERROR;
					}
				}
				else {
					result = MSTTS_ERROR;
				}
GetTokenError:
				if (httpHeadersHandle) {
					HTTPHeaders_Free(httpHeadersHandle);
				}
				if (responseHeadersHandle) {
					HTTPHeaders_Free(responseHeadersHandle);
				}
			}
			else {
				result = MSTTS_ALLOC_FAILED;
			}
			HTTPAPI_CloseConnection(http_handle);
		}
		else {
			result = MSTTS_CONNECTION_ERROR;
		}
		HTTPAPI_Deinit();
	}
	else {
		result = MSTTS_INIT_ERROR;
	}
	return result;
}

MSTTS_RESULT MSTTS_SetVoice(MSTTSHANDLE hSynthesizerHandle, const MSTTSVoiceInfo* pVoiceInfo){
	if (hSynthesizerHandle == NULL || pVoiceInfo->voiceName == NULL || pVoiceInfo->lang == NULL) {
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	unsigned char* voiceName = SynthesizerHandle->VoiceInfo->voiceName;
	unsigned char* lang = SynthesizerHandle->VoiceInfo->lang;

	size_t voiceNameLen = strlen(pVoiceInfo->voiceName);
	size_t langLen = strlen(pVoiceInfo->lang);

	unsigned char* newVoiceName = malloc(voiceNameLen+1);
	if (newVoiceName) {
		memset(newVoiceName, 0, voiceNameLen + 1);
		strcpy(newVoiceName, pVoiceInfo->voiceName);

		unsigned char* newLang = malloc(langLen + 1);
		if(newLang){
			memset(newLang, 0, langLen + 1);
			strcpy(newLang, pVoiceInfo->lang);

			SynthesizerHandle->VoiceInfo->voiceName = newVoiceName;
			SynthesizerHandle->VoiceInfo->lang = newLang;

			free(voiceName);
			free(lang);

			return MSTTS_OK;
		}
		else {
			result = MSTTS_ALLOC_FAILED;
		}
		free(newVoiceName);
	}
	else {
		result = MSTTS_ALLOC_FAILED;
	}

	return result;
}

void MSTTS_CloseSynthesizer(MSTTSHANDLE hSynthesizerHandle) {
	if (hSynthesizerHandle) {
		MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

		if (SynthesizerHandle->VoiceInfo) {
			MSTTSVoiceInfo* MSTTSvoicehandle = (MSTTS_HANDLE *)SynthesizerHandle->VoiceInfo;

			if (MSTTSvoicehandle->voiceName) {
				free(MSTTSvoicehandle->voiceName);
			}
			if (MSTTSvoicehandle->lang) {
				free(MSTTSvoicehandle->lang);
			}
			free(MSTTSvoicehandle);
		}

		if (SynthesizerHandle->ApiKey) {
			free(SynthesizerHandle->ApiKey);
		}
		if (SynthesizerHandle->Token) {
			free(SynthesizerHandle->Token);
		}
		free(SynthesizerHandle);
	}
}
#pragma endregion