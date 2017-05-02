#ifndef _PUBLIC_MSTTS_CLIENT_SDK_
#define _PUBLIC_MSTTS_CLIENT_SDK_

#include <stdint.h>
#include"azure_c_shared_utility\httpapi.h"

#ifdef __cplusplus
extern "C"
{
#endif

#define ApiKeyLength 50
#define tokenLength 500
#define langLength 10
#define voiceNameLength 100
#define MAX_BodyLength 4096

	typedef enum MSTTS_RESULT_VALUES
	{
		MSTTS_OK,
		MSTTS_INVALID_ARG,
		MSTTS_ERROR,
		MSTTS_ALLOC_FAILED
	}MSTTS_RESULT;

	typedef enum MSTTSContentType
	{
		MSTTSContentType_PlainText,
		MSTTSContentType_SSML
	}MSTTSContent;

	typedef enum MSTTSFormatType
	{
		ssml_16khz_16bit_mono_tts,
		raw_16khz_16bit_mono_pcm,
		audio_16khz_16kbps_mono_siren,
		riff_16khz_16kbps_mono_siren,
		riff_16khz_16bit_mono_pcm,
		audio_16khz_128kbitrate_mono_mp3,
		audio_16khz_64kbitrate_mono_mp3,
		audio_16khz_32kbitrate_mono_mp3
	}MSTTSWaveFormat;

	typedef enum MSTTSGenderType
	{
		Male,
		Famale
	}MSTTSGender;

	typedef struct MSTTS_VOICE_HANDLE_TAG
	{
		MSTTSGender gender;
		unsigned char* voiceName;
		unsigned char* lang;
	}MSTTS_VOICE_HANDLE;

	typedef struct MSTTS_VOICE_HANDLE_TAG* MSTTSVOICE_HANDLE;

	typedef struct MSTTSDATAHANDLE_TAG
	{
		MSTTSWaveFormat outputFormat;
		MSTTSVOICE_HANDLE VoiceInfo;
	}MSTTSDATAHANDLE;

	typedef struct MSTTSDATAHANDLE_TAG* MSTTSDATA_HANDLE;

	typedef struct MSTTSHANDLE_TAG
	{
		MSTTSDATA_HANDLE MSTTSData;
		unsigned char* ApiKey;
		unsigned char* Token;
		time_t  timeStamp;
	}MSTTSHANDLE;

	typedef struct MSTTSHANDLE_TAG* MSTTS_HANDLE;

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

	/*
	* Create a synthesizer instance, return the instance handle.
	* Return value:
	*  > 0: handle of the new synthesizer instance.
	*  NULL: failed to create the instance, error code.
	*/
	MSTTS_HANDLE MSTTS_init(unsigned char* ApiKey);

	/*
	* Do text synthesis.
	* Parameters:
	*   MSTTShandle: The handle of the synthesizer instance.
	*   pszContent: The content to speak, can be plain text or ssml depending to nContentType.
	*	eContentType: 0: plain text, 1: SSML.
	*	wavStream: the syntheticed data stream.
	*	wavStreamLength: the length of the data stream 
	* Return value:
	*	MSTTS_OK if initialization is successful or an error
	* 		code in case it fails.
	*/
	MSTTS_RESULT MSTTS_Synthesizer(MSTTS_HANDLE MSTTShandle, const char* pszContent, MSTTSContent eContentType, unsigned char* wavStream, size_t wavStreamLength);

	/*
	* Set the default voice of the current synthesizer instance,
	* it will be used to speak the plain text,
	* and ssml without voice name tags.
	* Parameters:
	*   MSTTShandle: The handle of the synthesizer instance.
	*   voiceData: This is the voice information in voice token file.
	* Return value:
	*	MSTTS_OK if initialization is successful or an error
	* 		code in case it fails.
	*/
	MSTTS_RESULT MSTTS_setVoice(MSTTS_HANDLE MSTTShandle, MSTTSVOICE_HANDLE voiceData);

	/*
	* Get the current synthesizer voice data.
	* Parameters:
	*  MSTTShandle: the handle of the synthesizer instance.
	* Return value:
	*  The pointer of the voice data structure.
	*/
	const MSTTSVOICE_HANDLE MSTTS_getVoice(MSTTS_HANDLE MSTTShandle);

	/*
	* Set the output format for the synthesizer instance.
	* All voices loaded by this instance will use the output format.
	* Return error code if failed to set or can support the format.
	* Parameters:
	*  MSTTShandle: the handle of the synthesizer instance
	*  waveFormat: wave format to be set, if set to NULL, use TTS engine's default format.
	* Return value:
	*	MSTTS_OK if initialization is successful or an error
	* 		code in case it fails.
	*/
	MSTTS_RESULT MSTTS_setOutput(MSTTS_HANDLE MSTTShandle, MSTTSWaveFormat waveFormat);

	/*
	* Get the current synthesizer output format.
	* Parameters:
	*  MSTTShandle: the handle of the synthesizer instance.
	* Return value:
	*  The enum of the wave format structure.
	*/
	MSTTSWaveFormat MSTTS_getOutput(MSTTS_HANDLE MSTTShandle);

	/*
	* Destroy the MSTTShandle.
	* Parameters:
	*  MSTTShandle: the handle of the synthesizer instance.
	*/
	void MSTTS_close(MSTTS_HANDLE MSTTShandle);

#ifdef __cplusplus
}
#endif

#endif