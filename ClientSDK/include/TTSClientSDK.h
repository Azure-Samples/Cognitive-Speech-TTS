// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#ifndef _PUBLIC_MSTTS_CLIENT_SDK_
#define _PUBLIC_MSTTS_CLIENT_SDK_

#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

	typedef enum MSTTS_RESULT_VALUES
	{
		MSTTS_OK,
		MSTTS_INVALID_ARG,
		MSTTS_GET_HEADER_ERROR,
		MSTTS_MALLOC_FAILED,
		MSTTS_HTTP_INIT_ERROR,
		MSTTS_HTTP_SETOPT_ERROR,
		MSTTS_HTTP_PERFORM_ERROR,
		MSTTS_HTTP_GETINFO_ERROR,
		MSTTS_CAN_NOT_STOP,
		MSTTS_SILK_INIT_ERROR,
		MSTTS_GET_SSML_ERROR,
		MSTTS_CALLBACK_HAVE_NOT_SET,
		MSTTS_GET_TOKEN_FAILED
	}MSTTS_RESULT;

	typedef enum MSTTSContentType
	{
		MSTTSContentType_PlainText,
		MSTTSContentType_SSML
	}MSTTSContent;

	typedef struct tMSTTSWAVEFORMATEX
	{
		uint16_t        wFormatTag;         /* format type */
		uint16_t        nChannels;          /* number of channels (i.e. mono, stereo...) */
		uint32_t        nSamplesPerSec;     /* sample rate */
		uint32_t        nAvgBytesPerSec;    /* for buffer estimation */
		uint16_t        nBlockAlign;        /* block size of data */
		uint16_t        wBitsPerSample;     /* number of bits per sample of mono data */
		uint32_t        cbSize;             /* the count in bytes of the size of */
											/* extra information (after cbSize) */
	} MSTTSWAVEFORMATEX, *PMSTTSWAVEFORMATEX;

	typedef struct tMSTTSVoiceInfo
	{
		unsigned char* voiceName;
		unsigned char* lang;
	}MSTTSVoiceInfo;

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

	typedef void* MSTTSHANDLE;
	typedef int(*LPMSTTS_RECEIVE_WAVESAMPLES_ROUTINE)(void* pCallBackStat, const char* pWaveSamples, int32_t nBytes);

	/*
	* Create a synthesizer instance.
	* Parameters:
	*   hSynthesizerHandle: The handle of the synthesizer instance.
	*   MSTTSApiKey: Request the token's api key.
	* Return value:
	*  MSTTS_RESULT
	*/
	MSTTS_RESULT MSTTS_CreateSpeechSynthesizerHandler(MSTTSHANDLE* phSynthesizerHandle, const unsigned char* ApiKey);

	/*
	* Do text rendering.
	* Parameters:
	*   hSynthesizerHandle: The handle of the synthesizer instance.
	*   pszContent: Text.
	*   eContentType: Typr of SSML or text.
	* Return value:
	*  MSTTS_RESULT
	*/
	MSTTS_RESULT MSTTS_Speak(MSTTSHANDLE hSynthesizerHandle, const char* pszContent, enum MSTTSContentType eContentType);

	/*
	* Stop speaking
	* Parameters:
	*   hSynthesizerHandle: The handle of the synthesizer instance.
	* Return value:
	*  MSTTS_RESULT
	*/
	MSTTS_RESULT MSTTS_Stop(MSTTSHANDLE hSynthesizerHandle);

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
	MSTTS_RESULT MSTTS_SetVoice(MSTTSHANDLE hSynthesizerHandle, const MSTTSVoiceInfo* pVoiceInfo);

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
	MSTTS_RESULT MSTTS_SetOutput(MSTTSHANDLE hSynthesizerHandle, const MSTTSWAVEFORMATEX* pWaveFormat, LPMSTTS_RECEIVE_WAVESAMPLES_ROUTINE pfWriteBack, void* pCallBackStat);

	/*
	* Get the current synthesizer output format.
	* Now only supports raw-16khz-16bit-mono format
	* Parameters:
	*  hSynthesizerHandle: the handle of the synthesizer instance.
	* Return value:
	*  MSTTS_RESULT
	*/
	const MSTTSWAVEFORMATEX* MSTTS_GetOutputFormat(MSTTSHANDLE hSynthesizerHandle);

	/*
	* Stop speaking and destroy the synthesizer.
	* Parameters:
	*  hSynthesizerHandle: the handle of the synthesizer instance.
	*/
	void MSTTS_CloseSynthesizer(MSTTSHANDLE hSynthesizerHandle);

#ifdef __cplusplus
}
#endif

#endif