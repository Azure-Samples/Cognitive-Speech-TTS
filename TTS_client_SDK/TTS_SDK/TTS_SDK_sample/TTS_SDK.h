#ifndef _PUBLIC_MSTTS_CLIENT_SDK_
#define _PUBLIC_MSTTS_CLIENT_SDK_

#include <stdint.h>
#include"azure_c_shared_utility\httpapi.h"

#ifdef __cplusplus
extern "C"
{
#endif

	typedef enum MSTTS_RESULT_VALUES
	{
		MSTTS_OK,
		MSTTS_INVALID_ARG,
		MSTTS_ERROR,
		MSTTS_INIT_ERROR,
		MSTTS_CONNECTION_ERROR,
		MSTTS_GETHEADER_ERROR,
		MSTTS_HTTP_ERROR,
		MSTTS_ALLOC_FAILED
	}MSTTS_RESULT;

	typedef enum MSTTSContentType
	{
		MSTTSContentType_PlainText,
		MSTTSContentType_SSML
	}MSTTSContent;

	typedef struct tMSTTSVoiceInfo
	{
		const char* voiceName;
		const char* lang;
	}MSTTSVoiceInfo;

	typedef void* MSTTSHANDLE;

#ifdef __cplusplus
}
#endif

/*
* This is a C interface
*/
#ifdef __cplusplus
extern "C"
{
#endif

	MSTTS_RESULT MSTTS_CreateSpeechSynthesizerHandler(MSTTSHANDLE* phSynthesizerHandle, const unsigned char* ApiKey);

	MSTTS_RESULT MSTTS_SetVoice(MSTTSHANDLE hSynthesizerHandle, const MSTTSVoiceInfo* pVoiceInfo);

	MSTTS_RESULT MSTTS_Speak(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType);

	void MSTTS_CloseSynthesizer(MSTTSHANDLE hSynthesizerHandle);

#ifdef __cplusplus
}
#endif

#endif