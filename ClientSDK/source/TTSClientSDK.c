// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#include<stdlib.h>
#include<string.h>
#include"curl/curl.h"
#include"TTSClientSDK.h"
#include"SKP_Silk_SDK_API.h"

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
#define TEMP_WAVE_DATA_LENGTH       AUDIO_SAMPLE_RATE * AUDIO_BITS / 2 * 10

typedef enum MSTTSSpeakStatusType
{
	MSTTSAudioSYS_RUNNING,
	MSTTSAudioSYS_STOP
}MSTTSSpeakStatus;

typedef struct MSTTSOUTPUT_TAG
{
	LPMSTTS_RECEIVE_WAVESAMPLES_ROUTINE pfWriteBack;  //Call back to output the wave samples, and return <0 for error code and abort speaking.
	void* pCallBackStat;                              //The call back stat for the call back.
}MSTTS_OUTPUT;

typedef struct MSTTSHANDLE_TAG
{
	unsigned char* ApiKey;          //The key to accessing the page.
	unsigned char* Token;           //Access the token.
	time_t  timeStamp;              //Record token acquisition time, token timeout will automatically request a new token.
	MSTTSSpeakStatus Speakstatus;   //Status of speak.
	MSTTSVoiceInfo* VoiceInfo;      //Voice info.
	MSTTS_OUTPUT* outputCallback;   //Output call back.
	MSTTSWAVEFORMATEX* waveFormat;  //output wave format
}MSTTS_HANDLE;

typedef struct HTTPRESPONSECONTENTHANDLE_TAG
{
	unsigned char* buffer;          //Silk buffer.
	size_t bufferSize;              //Silk buffer size.
	size_t offset;                  //The offset of the wave samples that have been output.
	uint32_t* waveSamplesSize;      //Wave samples size.
	MSTTSSpeakStatus* Speakstatus;  //Status of speak.
	MSTTS_OUTPUT* outputCallback;   //Output call back.
} HTTPRESPONSECONTENT_HANDLE;

//
//Silk decode source
//
static void* hDecoder = NULL;

static int silk_decode_frame(const SKP_uint8* inData, SKP_int nBytesIn, SKP_int16* outData,size_t* nBytesOut)
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


/*
* Call back to get the token
* Handle the responce to get the token
* Parameters:
*   data: The response data.
*   size: The size of the response data block.
*   nmemb: Number of response data blocks.
*   Token: The address of save the token.
* Return value:
*   processed data size
*/
static size_t HandleTokenData(void *data, size_t size, size_t nmemb, unsigned char** Token)
{
	unsigned char* TokenBuf = malloc(size*nmemb + 1);
	if (TokenBuf)
	{
		memset(TokenBuf, 0, size*nmemb + 1);
		strncpy(TokenBuf, data, size*nmemb);
		*Token = TokenBuf;
	}

	return size*nmemb;
}

/*
* Call back to get the wave samples
* Handle the responce to get the wave samples
* Parameters:
*   data: The response data.
*   size: The size of the response data block.
*   nmemb: Number of response data blocks.
*   responseContent: responce, type of HTTPRESPONSECONTENT_HANDLE.
* Return value:
*   processed data size
*/
static size_t HandleWaveSamples(void *ptr, size_t size, size_t nmemb, void *responseContent)
{
	HTTPRESPONSECONTENT_HANDLE *response = (HTTPRESPONSECONTENT_HANDLE *)responseContent;
	size_t		decodedBytes = 0;
	size_t      nBytes;

	if ((response != NULL) &&
		(ptr != NULL) &&
		(size * nmemb > 0))
	{
		//executed on first receipt
		if (!response->offset)
		{
			*response->Speakstatus = MSTTSAudioSYS_RUNNING;
			*response->waveSamplesSize = 0;
			if (SKP_Silk_SDK_InitDecoder(hDecoder))
			{
				return 0;
			}
		}

		//stop handle wave samples
		if (*response->Speakstatus == MSTTSAudioSYS_STOP)
		{
			return 0;
		}

		//copy the silk data to buffer
		void* newBuffer = realloc(response->buffer, response->bufferSize + (size * nmemb));
		if (newBuffer != NULL)
		{
			response->buffer = newBuffer;
			memcpy(response->buffer + response->bufferSize, ptr, size * nmemb);
			response->bufferSize += size * nmemb;
		}
		else
		{
			return 0;
		}

		//decode silk
		unsigned char *waveOutput = malloc(TEMP_WAVE_DATA_LENGTH);
		if (waveOutput)
		{
			memset(waveOutput, 0, TEMP_WAVE_DATA_LENGTH);

			uint16_t len = *(uint16_t*)(response->buffer + response->offset);
			while (response->offset + len + sizeof(uint16_t) <= response->bufferSize && TEMP_WAVE_DATA_LENGTH - decodedBytes > SILK_MAXBYTESPERBLOCK)
			{
				nBytes = TEMP_WAVE_DATA_LENGTH - decodedBytes;
				if (silk_decode_frame(
					response->buffer + response->offset + sizeof(uint16_t),
					len,
					(short*)(waveOutput + decodedBytes),
					&nBytes))
				{
					free(waveOutput);
					return 0;
				}

				response->offset += (sizeof(uint16_t) + len);
				decodedBytes += nBytes;

				//the first two bytes of silk are the data length
				len = *(uint16_t*)(response->buffer + response->offset);
			}

			*response->waveSamplesSize += decodedBytes;

			//callback WriteBack
			if (response->outputCallback->pfWriteBack)
			{
				if (response->outputCallback->pfWriteBack(response->outputCallback->pCallBackStat, waveOutput, decodedBytes) != 0)
				{
					free(waveOutput);
					return 0;
				}
			}
			free(waveOutput);
		}
		else
		{
			return 0;
		}
	}

	return size * nmemb;
}

/*
* Get the token by api key
* Parameters:
*   ApiKey: Request the token's api key.
*   KeyValue: The address of save the token.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT GetToken(const unsigned char* ApiKey, unsigned char** KeyValue)
{
	if (ApiKey == NULL || KeyValue == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	//Request the URL of the token
	const char* URL = "https://api.cognitive.microsoft.com/sts/v1.0/issueToken";
	const char* ApiKeyHeaderName = "Ocp-Apim-Subscription-Key";

	MSTTS_RESULT result = MSTTS_OK;
	long httpStatusCode;

	if (curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK)
	{
		CURL *curl = curl_easy_init();
		if (curl)
		{
			unsigned char* apiKeyHeader = malloc(strlen(ApiKeyHeaderName) + 1 + strlen(ApiKey) + 1);
			if (apiKeyHeader)
			{
				memset(apiKeyHeader, 0, strlen(ApiKeyHeaderName) + 1 + strlen(ApiKey) + 1);
				strcat(apiKeyHeader, ApiKeyHeaderName);
				strcat(apiKeyHeader, ":");
				strcat(apiKeyHeader, ApiKey);
				struct curl_slist *headers = NULL;
				headers = curl_slist_append(headers, apiKeyHeader);
				headers = curl_slist_append(headers, "Content-Length:0");
				if (headers)
				{
					if (curl_easy_setopt(curl, CURLOPT_WRITEDATA, KeyValue) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, HandleTokenData) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_URL, URL) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_POST, 1) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
#ifdef CURL_VERBOSE
					else if (curl_easy_setopt(curl, CURLOPT_VERBOSE, 1) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
#endif // CURL_VERBOSE
#ifdef NO_SSL_VERIFYPEER
					else if (curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
					else if (curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0) != CURLE_OK)
					{
						result = MSTTS_HTTP_SETOPT_ERROR;
					}
#endif
					else if (curl_easy_perform(curl) != CURLE_OK)
					{
						result = MSTTS_HTTP_PERFORM_ERROR;
					}
					else if ((curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpStatusCode) != CURLE_OK) || httpStatusCode != 200)
					{
						result = MSTTS_HTTP_GETINFO_ERROR;
					}
				}
				else
				{
					result = MSTTS_GET_HEADER_ERROR;
				}
				curl_slist_free_all(headers);
				free(apiKeyHeader);
			}
			else
			{
				result = MSTTS_MALLOC_FAILED;
			}
			curl_easy_cleanup(curl);
		}
		else
		{
			result = MSTTS_HTTP_INIT_ERROR;
		}
		curl_global_cleanup();
	}
	else
	{
		result = MSTTS_HTTP_INIT_ERROR;
	}

	return result;
}

/*
* Verify that Token is valid
* Token will expire every ten minutes,  
* and if the requested token is more than 9 minutes,
* it will be requested again.
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT CheckToken(MSTTSHANDLE hSynthesizerHandle)
{
	if (hSynthesizerHandle == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;
	MSTTS_RESULT result = MSTTS_OK;

	//if more than 9 minutes, need to reopen the access token
	time_t time_now;
	time(&time_now);
	double cost = difftime(time_now, SynthesizerHandle->timeStamp);
	if (cost > 9 * 60)
	{
		free(SynthesizerHandle->Token);
		result = GetToken(SynthesizerHandle->ApiKey, &SynthesizerHandle->Token);
		if (result == MSTTS_OK)
		{
			time(&SynthesizerHandle->timeStamp);
		}
	}

	return result;
}

/*
* Generate SSML for synthesis
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
*   pszContent: Text.
*   eContentType: Type of text or SSML.
*   body: Generates the SSML address.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT GetSSML(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType, unsigned char** body)
{
	if (hSynthesizerHandle == NULL || pszContent == NULL || body == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;
	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	if (eContentType == MSTTSContentType_SSML)
	{
		size_t len = strlen(pszContent);

		*body = malloc(len + 1);
		if (*body)
		{
			memset(*body, 0, len + 1);
			strcpy(*body, pszContent);
			result = MSTTS_OK;
		}
		else
		{
			result = MSTTS_MALLOC_FAILED;
		}
	}
	else
	{
		const unsigned char* SSMLFormat = "<speak version='1.0' xml:lang='%s'><voice xml:lang='%s' name='%s'>%s</voice></speak>";
		size_t len = strlen(SSMLFormat) +
			strlen(SynthesizerHandle->VoiceInfo->lang) +
			strlen(SynthesizerHandle->VoiceInfo->lang) +
			strlen(SynthesizerHandle->VoiceInfo->voiceName) +
			strlen(pszContent);

		*body = malloc(len + 1);
		if (*body)
		{
			memset(*body, 0, len + 1);
			snprintf(*body, len + 1, SSMLFormat,
				SynthesizerHandle->VoiceInfo->lang,
				SynthesizerHandle->VoiceInfo->lang,
				SynthesizerHandle->VoiceInfo->voiceName,
				pszContent);
			result = MSTTS_OK;
		}
		else
		{
			result = MSTTS_MALLOC_FAILED;
		}
	}

	return MSTTS_OK;
}

/*
* Create a synthesizer instance.
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
*   MSTTSApiKey: Request the token's api key.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT MSTTS_CreateSpeechSynthesizerHandler(MSTTSHANDLE* phSynthesizerHandle, const unsigned char* MSTTSApiKey)
{
	const unsigned char* cDefaultVoiceName = "Microsoft Server Speech Text to Speech Voice (zh-CN, HuihuiRUS)";
	const unsigned char* cDefaultLang = "zh-CN";

	if (MSTTSApiKey == NULL || phSynthesizerHandle == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;

	//init MSTTSVOICE_HANDLE
	MSTTSVoiceInfo* MSTTSVoiceHandle = (MSTTSVoiceInfo*)malloc(sizeof(MSTTSVoiceInfo));
	if (MSTTSVoiceHandle)
	{
		//set default lang
		unsigned char* lang = malloc(strlen(cDefaultLang) + 1);
		if (lang)
		{
			memset(lang, 0, strlen(cDefaultLang) + 1);
			strcpy(lang, cDefaultLang);
			MSTTSVoiceHandle->lang = lang;

			//set default voiceName
			unsigned char* voiceName = malloc(strlen(cDefaultVoiceName) + 1);
			if (voiceName)
			{
				memset(voiceName, 0, strlen(cDefaultVoiceName) + 1);
				strcpy(voiceName, cDefaultVoiceName);
				MSTTSVoiceHandle->voiceName = voiceName;

				MSTTSWAVEFORMATEX* waveFormat = (MSTTSWAVEFORMATEX*)malloc(sizeof(MSTTSWAVEFORMATEX));
				if (waveFormat)
				{
					waveFormat->wFormatTag = WAVE_FORMAT_PCM;
					waveFormat->nChannels = AUDIO_CHANNEL;
					waveFormat->nSamplesPerSec = AUDIO_SAMPLE_RATE;
					waveFormat->wBitsPerSample = AUDIO_BITS;
					waveFormat->nAvgBytesPerSec = AUDIO_BYTE_RATE;
					waveFormat->nBlockAlign = AUDIO_BLOCK_ALIGN;
					waveFormat->cbSize = 0;

					//init MSTTS_HANDLE
					MSTTS_HANDLE* MSTTShandle = (MSTTS_HANDLE*)malloc(sizeof(MSTTS_HANDLE));
					if (MSTTShandle)
					{

						//init ApiKey
						unsigned char* ApiKey = malloc(strlen(MSTTSApiKey) + 1);
						if (ApiKey)
						{
							memset(ApiKey, 0, strlen(MSTTSApiKey) + 1);
							strcpy(ApiKey, MSTTSApiKey);

							//init Token
							unsigned char* token;

							//Get token
							if (GetToken(ApiKey, &token) == MSTTS_OK)
							{
								MSTTShandle->ApiKey = ApiKey;
								MSTTShandle->Token = token;
								time(&MSTTShandle->timeStamp);
								MSTTShandle->Speakstatus = MSTTSAudioSYS_STOP;
								MSTTShandle->VoiceInfo = MSTTSVoiceHandle;
								MSTTShandle->outputCallback = NULL;
								MSTTShandle->waveFormat = waveFormat;	
								*phSynthesizerHandle = MSTTShandle;
								return MSTTS_OK;
							}
							else
							{
								result = MSTTS_GET_TOKEN_FAILED;
							}

							free(ApiKey);
						}
						else
						{
							result = MSTTS_MALLOC_FAILED;
						}
						free(MSTTShandle);
					}
					else
					{
						result = MSTTS_MALLOC_FAILED;
					}
					free(waveFormat);
				}
				else
				{
					result = MSTTS_MALLOC_FAILED;
				}
				free(voiceName);
			}
			else
			{
				result = MSTTS_MALLOC_FAILED;
			}
			free(lang);
		}
		else
		{
			result = MSTTS_MALLOC_FAILED;
		}
		free(MSTTSVoiceHandle);
	}
	else
	{
		result = MSTTS_MALLOC_FAILED;
	}
	return result;
}

/*
* Do text rendering.
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
*   pszContent: Text.
*   eContentType: Typr of SSML or text.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT MSTTS_Speak(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType)
{
	if (hSynthesizerHandle == NULL || pszContent == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	const char* speechURL = "https://speech.platform.bing.com/synthesize";
	const char* tokenHeaderName = "Authorization:Bearer ";

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;
	MSTTS_RESULT result = MSTTS_OK;

	if (SynthesizerHandle->outputCallback == NULL || SynthesizerHandle->outputCallback->pfWriteBack == NULL)
	{
		return MSTTS_CALLBACK_HAVE_NOT_SET;
	}

	long httpStatusCode;
	unsigned char* body;

	if (curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK)
	{
		CURL *curl = curl_easy_init();
		if (curl)
		{
			result = CheckToken(hSynthesizerHandle);
			if (result == MSTTS_OK)
			{
				unsigned char* tokenHeader = malloc(strlen(tokenHeaderName) + strlen(SynthesizerHandle->Token) + 1);
				if (tokenHeader)
				{
					memset(tokenHeader, 0, strlen(tokenHeaderName) + strlen(SynthesizerHandle->Token) + 1);
					strcat(tokenHeader, tokenHeaderName);
					strcat(tokenHeader, SynthesizerHandle->Token);

					struct curl_slist *headers = NULL;
					headers = curl_slist_append(headers, "Content-type:application/ssml+xml");
					headers = curl_slist_append(headers, "X-Microsoft-OutputFormat:raw-16khz-16bit-mono-truesilk");
					headers = curl_slist_append(headers, "X-Search-AppId:07D3234E49CE426DAA29772419F436CA");
					headers = curl_slist_append(headers, "X-Search-ClientID:1ECFAE91408841A480F00935DC390960");
					headers = curl_slist_append(headers, "User-Agent:TTSForPython");
					headers = curl_slist_append(headers, tokenHeader);
					if (headers)
					{
						if (GetSSML(SynthesizerHandle, pszContent, eContentType, &body) == MSTTS_OK)
						{
							if (!initdecoder())
							{
								HTTPRESPONSECONTENT_HANDLE *responsecontent = malloc(sizeof(HTTPRESPONSECONTENT_HANDLE));
								if (responsecontent)
								{

									responsecontent->buffer = NULL;
									responsecontent->bufferSize = 0;
									responsecontent->offset = 0;
									responsecontent->waveSamplesSize = &SynthesizerHandle->waveFormat->cbSize;
									responsecontent->Speakstatus = &SynthesizerHandle->Speakstatus;
									responsecontent->outputCallback = SynthesizerHandle->outputCallback;

									if (curl_easy_setopt(curl, CURLOPT_WRITEDATA, responsecontent) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, HandleWaveSamples) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, strlen(body)) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_URL, speechURL) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_POST, 1) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
#ifdef CURL_VERBOSE
									else if (curl_easy_setopt(curl, CURLOPT_VERBOSE, 1) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
#endif
#ifdef NO_SSL_VERIFYPEER
									else if (curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
									else if (curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0) != CURLE_OK)
									{
										result = MSTTS_HTTP_SETOPT_ERROR;
									}
#endif
									else if (curl_easy_perform(curl) != CURLE_OK)
									{
										result = MSTTS_HTTP_PERFORM_ERROR;
									}
									else if ((curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpStatusCode) != CURLE_OK) || httpStatusCode != 200)
									{
										result = MSTTS_HTTP_GETINFO_ERROR;
									}


									if (responsecontent->buffer)
									{
										free(responsecontent->buffer);
									}
									free(responsecontent);
								}
								else
								{
									result = MSTTS_MALLOC_FAILED;
								}
								audio_decoder_uninitialize();
							}
							else
							{
								result = MSTTS_SILK_INIT_ERROR;
							}
							free(body);
						}
						else
						{
							result = MSTTS_GET_SSML_ERROR;
						}
						curl_slist_free_all(headers);
					}
					else
					{
						result = MSTTS_GET_HEADER_ERROR;
					}

					free(tokenHeader);
				}
				else
				{
					result = MSTTS_MALLOC_FAILED;
				}
			}
			curl_easy_cleanup(curl);
		}
		else
		{
			result = MSTTS_HTTP_INIT_ERROR;
		}
		curl_global_cleanup();
	}
	else
	{
		result = MSTTS_HTTP_INIT_ERROR;
	}

	return result;

}

/*
* Stop speaking
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT MSTTS_Stop(MSTTSHANDLE hSynthesizerHandle)
{
	if (hSynthesizerHandle == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	SynthesizerHandle->Speakstatus = MSTTSAudioSYS_STOP;

	return MSTTS_OK;
}

/*
* Set the default voice of the current synthesizer instance,
* it will be used to speak the plain text,
* and ssml without voice name tags.
* Parameters:
*   hSynthesizerHandle: The handle of the synthesizer instance.
*   pVoiceInfo: This is the voice information in voice token file.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT MSTTS_SetVoice(MSTTSHANDLE hSynthesizerHandle, const MSTTSVoiceInfo* pVoiceInfo)
{
	if (hSynthesizerHandle == NULL || pVoiceInfo->voiceName == NULL || pVoiceInfo->lang == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_RESULT result = MSTTS_OK;

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	unsigned char* voiceName = SynthesizerHandle->VoiceInfo->voiceName;
	unsigned char* lang = SynthesizerHandle->VoiceInfo->lang;

	size_t voiceNameLen = strlen(pVoiceInfo->voiceName);
	size_t langLen = strlen(pVoiceInfo->lang);

	unsigned char* newVoiceName = malloc(voiceNameLen + 1);
	if (newVoiceName)
	{
		memset(newVoiceName, 0, voiceNameLen + 1);
		strcpy(newVoiceName, pVoiceInfo->voiceName);

		unsigned char* newLang = malloc(langLen + 1);
		if (newLang)
		{
			memset(newLang, 0, langLen + 1);
			strcpy(newLang, pVoiceInfo->lang);

			SynthesizerHandle->VoiceInfo->voiceName = newVoiceName;
			SynthesizerHandle->VoiceInfo->lang = newLang;

			free(voiceName);
			free(lang);

			return MSTTS_OK;
		}
		else
		{
			result = MSTTS_MALLOC_FAILED;
		}
		free(newVoiceName);
	}
	else
	{
		result = MSTTS_MALLOC_FAILED;
	}

	return result;
}

/*
* Set the output format for the synthesizer instance.
* All voices loaded by this instance will use the output format.
* Now, only supports raw-16khz-16bit-mono-truesilk,
* setting pWaveFormat is not implemented, just provied an interface for ecpansion.
* Parameters:
*  hSynthesizerHandle: the handle of the synthesizer instance
*  pWaveFormat: wave format to be set, if set to NULL, use TTS engine's default format.
*  pfWriteBack: Call back to output the wave samples, and return <0 for error code and abort speaking.
*  void* pCallBackStat: The call back stat for the call back.
* Return value:
*  MSTTS_RESULT
*/
MSTTS_RESULT MSTTS_SetOutput(MSTTSHANDLE hSynthesizerHandle, const MSTTSWAVEFORMATEX* pWaveFormat, LPMSTTS_RECEIVE_WAVESAMPLES_ROUTINE pfWriteBack, void* pCallBackStat)
{
	if (hSynthesizerHandle == NULL || pfWriteBack == NULL)
	{
		return MSTTS_INVALID_ARG;
	}

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	if (SynthesizerHandle->outputCallback)
	{
		SynthesizerHandle->outputCallback->pCallBackStat = pCallBackStat;
		SynthesizerHandle->outputCallback->pfWriteBack = pfWriteBack;
		return MSTTS_OK;
	}
	else
	{
		MSTTS_OUTPUT* outputCallback = (MSTTS_OUTPUT*)malloc(sizeof(MSTTS_OUTPUT));
		if (outputCallback)
		{
			outputCallback->pCallBackStat = pCallBackStat;
			outputCallback->pfWriteBack = pfWriteBack;
			SynthesizerHandle->outputCallback = outputCallback;
			return MSTTS_OK;
		}
		else
		{
			return MSTTS_MALLOC_FAILED;
		}
	}
}

/*
* Get the current synthesizer output format.
* Now only supports raw-16khz-16bit-mono format
* Parameters:
*  hSynthesizerHandle: the handle of the synthesizer instance.
* Return value:
*  MSTTS_RESULT
*/
const MSTTSWAVEFORMATEX* MSTTS_GetOutputFormat(MSTTSHANDLE hSynthesizerHandle)
{

	MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

	if (hSynthesizerHandle == NULL)
	{
		return NULL;
	}

	MSTTSWAVEFORMATEX* waveFormat = (MSTTSWAVEFORMATEX*)malloc(sizeof(MSTTSWAVEFORMATEX));
	if (waveFormat)
	{
		waveFormat->wFormatTag = SynthesizerHandle->waveFormat->wFormatTag;
		waveFormat->nChannels = SynthesizerHandle->waveFormat->nChannels;
		waveFormat->nSamplesPerSec = SynthesizerHandle->waveFormat->nSamplesPerSec;
		waveFormat->wBitsPerSample = SynthesizerHandle->waveFormat->wBitsPerSample;
		waveFormat->nAvgBytesPerSec = SynthesizerHandle->waveFormat->nAvgBytesPerSec;
		waveFormat->nBlockAlign = SynthesizerHandle->waveFormat->nBlockAlign;
		waveFormat->cbSize = SynthesizerHandle->waveFormat->cbSize;
	}

	return waveFormat;
}

/*
* Stop speaking and destroy the synthesizer.
* Parameters:
*  hSynthesizerHandle: the handle of the synthesizer instance.
*/
void MSTTS_CloseSynthesizer(MSTTSHANDLE hSynthesizerHandle)
{
	MSTTS_RESULT result = MSTTS_OK;

	if (hSynthesizerHandle)
	{
		MSTTS_HANDLE *SynthesizerHandle = (MSTTS_HANDLE *)hSynthesizerHandle;

		if (MSTTS_Stop(SynthesizerHandle) == MSTTS_OK)
		{
			if (SynthesizerHandle->VoiceInfo)
			{
				MSTTSVoiceInfo* MSTTSvoicehandle = (MSTTSVoiceInfo *)SynthesizerHandle->VoiceInfo;

				if (MSTTSvoicehandle->voiceName)
				{
					free(MSTTSvoicehandle->voiceName);
				}
				if (MSTTSvoicehandle->lang)
				{
					free(MSTTSvoicehandle->lang);
				}
				free(MSTTSvoicehandle);
			}

			if (SynthesizerHandle->outputCallback)
			{
				free(SynthesizerHandle->outputCallback);
			}
			if (SynthesizerHandle->waveFormat)
			{
				free(SynthesizerHandle->waveFormat);
			}
			if (SynthesizerHandle->ApiKey)
			{
				free(SynthesizerHandle->ApiKey);
			}
			if (SynthesizerHandle->Token)
			{
				free(SynthesizerHandle->Token);
			}
			free(SynthesizerHandle);
		}
		else
		{
			result = MSTTS_CAN_NOT_STOP;
		}
	}
	else
	{
		result = MSTTS_INVALID_ARG;
	}
	return;
}
