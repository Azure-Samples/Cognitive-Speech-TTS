#include<stdio.h>
#include<time.h>
#include"TTS_SDK.h"
#include"iconv\iconv.h"
#include"azure_c_shared_utility\httpheaders.h"
#include"azure_c_shared_utility\httpapi.h"

void printHEADER(HTTP_HEADERS_HANDLE responseHeadersHandle) {
	if (responseHeadersHandle == NULL) {
		printf("Parameter is invalid");
		return ;
	}

	size_t headersCount;
	HTTP_HEADERS_RESULT result = HTTPHeaders_GetHeaderCount(responseHeadersHandle, &headersCount);
	printf("\r\n");
	printf("HEADER:\r\n");
	for (int i = 0; i < headersCount; i++) {
		unsigned char *destination = NULL;
		result = HTTPHeaders_GetHeader(responseHeadersHandle, i, &destination);
		printf("%s\r\n", destination);
	}
	printf("\r\n");
}

void printBUFFER(BUFFER_HANDLE responseContent)
{
	if (responseContent == NULL) {
		printf("Parameter is invalid");
		return ;
	}

	size_t ContentSize;
	unsigned char* data;

	int resualt = BUFFER_size(responseContent, &ContentSize);
	data = malloc(ContentSize + 1);
	if (data == NULL)
	{
		printf("malloc returned NULL.");
		return ;
	}
	memset(data, 0, ContentSize + 1);
	unsigned char *content = NULL;
	resualt = BUFFER_content(responseContent, &content);
	strncpy(data, content, ContentSize);

	printf("\r\n");
	printf("BUFFER: %s\r\n", data);
	printf("\r\n");

	free(data);
}

MSTTS_RESULT getKeyValue(const unsigned char* ApiKey, unsigned char* KeyValue) {
	if (ApiKey == NULL || KeyValue == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	const char* ApiKey_header = "Ocp-Apim-Subscription-Key";
	const char* URL = "api.cognitive.microsoft.com";
	const char* relativePath = "/sts/v1.0/issueToken";

	HTTPAPI_RESULT httpResult;
	HTTP_HEADERS_RESULT headerResult;
	unsigned int httpStatusCode;

	//init HTTPAPI
	httpResult = HTTPAPI_Init();
	if (httpResult != HTTPAPI_OK){
		return httpResult;
	}

	//init HTTP handle
	HTTP_HANDLE httpHandle = HTTPAPI_CreateConnection(URL);

	//init HTTP header handle
	HTTP_HEADERS_HANDLE requestHeadersHandle = HTTPHeaders_Alloc();
	HTTP_HEADERS_HANDLE responseHeadersHandle = HTTPHeaders_Alloc();
	//add apiKey to header
	headerResult = HTTPHeaders_AddHeaderNameValuePair(requestHeadersHandle, ApiKey_header, ApiKey);

	//init buffer
	BUFFER_HANDLE responseContent = BUFFER_new();

	//send request
	httpResult = HTTPAPI_ExecuteRequest(httpHandle, HTTPAPI_REQUEST_POST, relativePath,
		requestHeadersHandle, NULL, 0, &httpStatusCode, responseHeadersHandle, responseContent);
	if (httpResult != HTTPAPI_OK) {
		return httpResult;
	}

#ifdef __DEBUG__
	printHEADER(responseHeadersHandle);
	printBUFFER(responseContent);
#endif

	size_t ContentSize;
	int resualt = BUFFER_size(responseContent, &ContentSize);
	unsigned char *content = NULL;
	resualt = BUFFER_content(responseContent, &content);
	strncpy(KeyValue, content, ContentSize);

	HTTPAPI_CloseConnection(httpHandle);
	HTTPHeaders_Free(requestHeadersHandle);
	HTTPHeaders_Free(responseHeadersHandle);
	BUFFER_delete(responseContent);
	HTTPAPI_Deinit();

	return MSTTS_OK;
}

MSTTS_HANDLE MSTTS_init(unsigned char* MSTTS_ApiKey) {
	if (MSTTS_ApiKey == NULL) {
		printf("Parameter is invalid");
		return NULL;
	}

	//init MSTTSVOICE_HANDLE
	MSTTSVOICE_HANDLE MSTTSvoicehandle = (MSTTS_VOICE_HANDLE*)malloc(sizeof(MSTTS_VOICE_HANDLE));
	if (MSTTSvoicehandle == NULL) {
		printf("malloc failed");
		return NULL;
	}
	unsigned char* lang = malloc(langLength);
	if (lang == NULL) {
		printf("malloc failed");
		return NULL;
	}
	memset(lang, 0, langLength);
	strcpy(lang, "zh-CN");
	MSTTSvoicehandle->lang = lang;
	MSTTSvoicehandle->gender = Famale;
	unsigned char* voiceName = malloc(voiceNameLength);
	if (voiceName == NULL) {
		printf("malloc failed");
		return NULL;
	}
	memset(voiceName, 0, voiceNameLength);
	strcpy(voiceName, "Microsoft Server Speech Text to Speech Voice (zh-CN, Yaoyao, Apollo)");
	MSTTSvoicehandle->voiceName = voiceName;

	//init MSTTSDATA_HANDLE
	MSTTSDATA_HANDLE MSTTSdatahandle = (MSTTSDATAHANDLE*)malloc(sizeof(MSTTSDATAHANDLE));
	if (MSTTSdatahandle == NULL) {
		printf("malloc failed");
		return NULL;
	}
	MSTTSdatahandle->outputFormat = riff_16khz_16bit_mono_pcm;
	MSTTSdatahandle->VoiceInfo = MSTTSvoicehandle;

	//init MSTTS_HANDLE
	MSTTS_HANDLE MSTTShandle = (MSTTSHANDLE*)malloc(sizeof(MSTTSHANDLE));
	if (MSTTShandle == NULL) {
		printf("malloc failed");
		return NULL;
	}
	//init ApiKey
	unsigned char* ApiKey = malloc(ApiKeyLength);
	if (ApiKey == NULL) {
		printf("malloc failed");
		return NULL;
	}
	memset(ApiKey, 0, ApiKeyLength);
	strcpy(ApiKey, MSTTS_ApiKey);

	//init Token
	unsigned char* token = malloc(tokenLength);
	if (token == NULL) {
		printf("malloc failed");
		return NULL;
	}
	memset(token, 0, tokenLength);

	//Get token
	getKeyValue(ApiKey, token);

	MSTTShandle->ApiKey = ApiKey;
	MSTTShandle->MSTTSData = MSTTSdatahandle;
	MSTTShandle->Token = token;
	time(&MSTTShandle->timeStamp);

	return MSTTShandle;
}

const unsigned char* getGender(MSTTSGender Gender) {
	switch (Gender) {
	case Male:
		return "Male";
	case Famale:
		return "Famale";
	default:
		return "Famale";
	}
}

MSTTS_RESULT getSSML(MSTTS_HANDLE MSTTShandle, const char* pszContent, enum MSTTSContentType eContentType, unsigned char* body, size_t bodyDataLength) {
	if (MSTTShandle == NULL || pszContent == NULL || body == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	if (strlen(pszContent) > MAX_BodyLength) {
		printf("The text length exceeds the allowed maximum");
		return MSTTS_INVALID_ARG;
	}

	if (eContentType == MSTTSContentType_SSML) {
		snprintf(body, bodyDataLength, "<speak version='1.0' xml:lang='%s'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>",
			MSTTShandle->MSTTSData->VoiceInfo->lang,
			MSTTShandle->MSTTSData->VoiceInfo->lang,
			getGender(MSTTShandle->MSTTSData->VoiceInfo->gender),
			MSTTShandle->MSTTSData->VoiceInfo->voiceName,
			pszContent);
	}
	else {
		snprintf(body, bodyDataLength, "<speak version='1.0' xml:lang='%s'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>", 
			MSTTShandle->MSTTSData->VoiceInfo->lang,
			MSTTShandle->MSTTSData->VoiceInfo->lang,
			getGender(MSTTShandle->MSTTSData->VoiceInfo->gender),
			MSTTShandle->MSTTSData->VoiceInfo->voiceName,
			pszContent);
	}

	return MSTTS_OK;
}

const unsigned char* getWaveFormat(MSTTSWaveFormat WaveFormat) {
	switch(WaveFormat){
		case ssml_16khz_16bit_mono_tts:
			return "ssml-16khz-16bit-mono-tts";
		case raw_16khz_16bit_mono_pcm:
			return "raw-16khz-16bit-mono-pcm";
		case audio_16khz_16kbps_mono_siren:
			return "audio-16khz-16kbps-mono-siren";
		case riff_16khz_16kbps_mono_siren:
			return "riff-16khz-16kbps-mono-siren";
		case riff_16khz_16bit_mono_pcm:
			return "riff-16khz-16bit-mono-pcm";
		case audio_16khz_128kbitrate_mono_mp3:
			return "audio-16khz-128kbitrate-mono-mp3";
		case audio_16khz_64kbitrate_mono_mp3:
			return "audio-16khz-64kbitrate-mono-mp3";
		case audio_16khz_32kbitrate_mono_mp3:
			return "audio-16khz-32kbitrate-mono-mp3";
		default:
			return "riff-16khz-16bit-mono-pcm";
	}
}

MSTTS_RESULT getHeader(HTTP_HEADERS_HANDLE* httpHeadersHandle, unsigned char* KeyValue, MSTTSWaveFormat WaveFormat) {
	if (KeyValue == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "Content-type", "application/ssml+xml");
	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Microsoft-OutputFormat", getWaveFormat(WaveFormat));
	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Search-AppId", "07D3234E49CE426DAA29772419F436CA");
	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "X-Search-ClientID", "1ECFAE91408841A480F00935DC390960");
	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "User-Agent", "TTSForPython");
	unsigned char* Token = malloc(1000);
	if (Token == NULL) {
		printf("malloc failed");
		return MSTTS_ALLOC_FAILED;
	}
	memset(Token, 0, 1000);
	strcpy(Token, "Bearer ");
	strcat(Token, KeyValue);
	HTTPHeaders_AddHeaderNameValuePair(*httpHeadersHandle, "Authorization", Token);

	return MSTTS_OK;
}

MSTTS_RESULT MSTTS_Synthesizer(MSTTS_HANDLE MSTTShandle, const char* pszContent, MSTTSContent eContentType, unsigned char* wavStream, size_t wavStreamLength) {
	if (MSTTShandle == NULL || pszContent == NULL || wavStream == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	const char* speech_URL = "speech.platform.bing.com";
	const char* relPath = "/synthesize";

	unsigned char* body = malloc(MAX_BodyLength);
	if (body == NULL) {
		printf("malloc failed");
		return MSTTS_ALLOC_FAILED;
	}
	getSSML(MSTTShandle, pszContent, eContentType, body, MAX_BodyLength);


	HTTPAPI_RESULT ret = HTTPAPI_Init();
	HTTP_HANDLE http_handle = HTTPAPI_CreateConnection(speech_URL);

	unsigned int statusCode;

	HTTP_HEADERS_HANDLE httpHeadersHandle = HTTPHeaders_Alloc();
	HTTP_HEADERS_HANDLE responseHeadersHandle = HTTPHeaders_Alloc();
	BUFFER_HANDLE responseContent = BUFFER_new();

	//if more than 9 minutes, need to reopen the access token
	time_t time_now;
	time(&time_now);
	double cost = difftime(time_now, MSTTShandle->timeStamp);
	if (cost > 9 * 60) {
		memset(MSTTShandle->Token, 0, tokenLength);
		getKeyValue(MSTTShandle->ApiKey, MSTTShandle->Token);
	}

	getHeader(&httpHeadersHandle, MSTTShandle->Token, MSTTShandle->MSTTSData->outputFormat);

	printHEADER(httpHeadersHandle);

	ret = HTTPAPI_ExecuteRequest(http_handle, HTTPAPI_REQUEST_POST, relPath,
		httpHeadersHandle, body, strlen(body), &statusCode, responseHeadersHandle, responseContent);

	size_t ContentSize;
	int resualt = BUFFER_size(responseContent, &ContentSize);
	if (wavStreamLength <= ContentSize) {
		printf("wavStream space is too small");
		return MSTTS_INVALID_ARG;
	}
	memset(wavStream, 0, wavStreamLength);
	unsigned char *content = NULL;
	resualt = BUFFER_content(responseContent, &content);
	strncpy(wavStream, content, ContentSize);
	
#ifdef __DEBUG__
	printHEADER(httpHeadersHandle);
	printHEADER(responseHeadersHandle);
	printBUFFER(responseContent);
#endif

	free(body);
	HTTPAPI_CloseConnection(http_handle);
	HTTPHeaders_Free(httpHeadersHandle);
	HTTPHeaders_Free(responseHeadersHandle);
	BUFFER_delete(responseContent);

	HTTPAPI_Deinit();

	return MSTTS_OK;
}

MSTTS_RESULT MSTTS_setVoice(MSTTS_HANDLE MSTTShandle, MSTTSVOICE_HANDLE voiceData) {
	if (MSTTShandle == NULL || voiceData->voiceName == NULL || voiceData->lang == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	size_t voiceNameLen = strlen(voiceData->voiceName);
	if (voiceNameLen >= voiceNameLength) {
		free(MSTTShandle->MSTTSData->VoiceInfo->voiceName);
		MSTTShandle->MSTTSData->VoiceInfo->voiceName = malloc(voiceNameLen + 1);
		if (MSTTShandle->MSTTSData->VoiceInfo->voiceName == NULL) {
			printf("malloc failed");
			return MSTTS_ALLOC_FAILED;
		}
		memset(MSTTShandle->MSTTSData->VoiceInfo->voiceName, 0 , voiceNameLen + 1);
		strcpy(MSTTShandle->MSTTSData->VoiceInfo->voiceName, voiceData->voiceName);
	}
	else {
		memset(MSTTShandle->MSTTSData->VoiceInfo->voiceName, 0, voiceNameLength);
		strcpy(MSTTShandle->MSTTSData->VoiceInfo->voiceName, voiceData->voiceName);
	}

	size_t langLen = strlen(voiceData->lang);
	if (langLen >= langLength) {
		free(MSTTShandle->MSTTSData->VoiceInfo->lang);
		MSTTShandle->MSTTSData->VoiceInfo->lang = malloc(langLen + 1);
		if (MSTTShandle->MSTTSData->VoiceInfo->lang == NULL) {
			printf("malloc failed");
			return MSTTS_ALLOC_FAILED;
		}
		memset(MSTTShandle->MSTTSData->VoiceInfo->lang, 0, langLen + 1);
		strcpy(MSTTShandle->MSTTSData->VoiceInfo->lang, voiceData->lang);
	}
	else {
		memset(MSTTShandle->MSTTSData->VoiceInfo->lang, 0, langLength);
		strcpy(MSTTShandle->MSTTSData->VoiceInfo->lang, voiceData->lang);
	}
	
	MSTTShandle->MSTTSData->VoiceInfo->gender = voiceData->gender;

	return MSTTS_OK;
}

const MSTTSVOICE_HANDLE MSTTS_getVoice(MSTTS_HANDLE MSTTShandle) {
	if (MSTTShandle == NULL) {
		printf("Parameter is invalid");
		return NULL;
	}

	return MSTTShandle->MSTTSData->VoiceInfo;
}

MSTTS_RESULT MSTTS_setOutput(MSTTS_HANDLE MSTTShandle, MSTTSWaveFormat waveFormat) {
	if (MSTTShandle == NULL) {
		printf("Parameter is invalid");
		return MSTTS_INVALID_ARG;
	}

	if (waveFormat == NULL) {
		MSTTShandle->MSTTSData->outputFormat = riff_16khz_16bit_mono_pcm;
	}
	else{
		MSTTShandle->MSTTSData->outputFormat = waveFormat;
	}
	
	return MSTTS_OK;
}

MSTTSWaveFormat MSTTS_getOutput(MSTTS_HANDLE MSTTShandle) {
	if (MSTTShandle == NULL) {
		printf("Parameter is invalid");
		return ;
	}

	return MSTTShandle->MSTTSData->outputFormat;
}

void MSTTS_close(MSTTS_HANDLE MSTTShandle) {
	//MSTTShandle
	if (MSTTShandle != NULL) {
		//MSTTShandle->ApiKey
		if (MSTTShandle->ApiKey != NULL) {
			free(MSTTShandle->ApiKey);
		}
		//MSTTShandle->Token
		if (MSTTShandle->Token != NULL) {
			free(MSTTShandle->Token);
		}
		//MSTTShandle->MSTTSData
		if (MSTTShandle->MSTTSData != NULL) {
			//MSTTShandle->MSTTSData->VoiceInfo
			if (MSTTShandle->MSTTSData->VoiceInfo != NULL) {
				//MSTTShandle->MSTTSData->VoiceInfo->voiceName
				if (MSTTShandle->MSTTSData->VoiceInfo->voiceName != NULL) {
					free(MSTTShandle->MSTTSData->VoiceInfo->voiceName);
				}
				//MSTTShandle->MSTTSData->VoiceInfo->lang
				if (MSTTShandle->MSTTSData->VoiceInfo->lang != NULL) {
					free(MSTTShandle->MSTTSData->VoiceInfo->lang);
				}
				free(MSTTShandle->MSTTSData->VoiceInfo);
			}
			free(MSTTShandle->MSTTSData);
		}
		free(MSTTShandle);
	}
}