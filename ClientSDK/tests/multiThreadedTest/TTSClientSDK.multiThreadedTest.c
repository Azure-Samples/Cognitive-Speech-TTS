// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#include<stdio.h>
#include<stdlib.h>
#include<pthread.h>
#include<string.h>
#include<windows.h>
#include"TTSClientSDK.h"

//Note: The way to get api key :
//Free : https://www.microsoft.com/cognitive-services/en-us/subscriptions?productId=/products/Bing.Speech.Preview
//Paid : https://portal.azure.com/#create/Microsoft.CognitiveServices/apitype/Bing.Speech/pricingtier/S0
const unsigned char* ApiKey = "Your api key";

const char* text = "This is the Microsoft TTS Client SDK test program. It tested multithreaded operations. It will generate two wav files, one is complete, one is stopped";

typedef struct _wave_pcm_hdr
{
	char         riff[4];
	int          size_8;
	char         wave[4];
	char         fmt[4];
	int          fmt_size;
	short int    format_tag;
	short int    channels;
	int          samples_per_sec;
	int          avg_bytes_per_sec;
	short int    block_align;
	short int    bits_per_sample;
	char         data[4];
	int          data_size;
} wave_pcm_hdr;

wave_pcm_hdr default_wav_hdr =
{
	{ 'R', 'I', 'F', 'F' },
	0,
	{ 'W', 'A', 'V', 'E' },
	{ 'f', 'm', 't', ' ' },
	16,
	1,
	1,
	16000,
	32000,
	2,
	16,
	{ 'd', 'a', 't', 'a' },
	0
};

int pfWriteBack(void* pCallBackStat, const char* pWaveSamples, int32_t nBytes)
{
	FILE *fp;
	fp = fopen((char*)pCallBackStat, "ab");
	fwrite(pWaveSamples, sizeof(char), nBytes, fp);
	fclose(fp);
	return 0;
}

int addWaveHeader(char* targetFile, char* soourceFile, const MSTTSWAVEFORMATEX* waveFormat)
{
	int rc;
	unsigned char buf[1024];
	wave_pcm_hdr wav_hdr = default_wav_hdr;
	wav_hdr.size_8 = waveFormat->cbSize + (sizeof(wav_hdr) - 8);
	wav_hdr.fmt_size = 16;
	wav_hdr.format_tag = waveFormat->wFormatTag;
	wav_hdr.channels = waveFormat->nChannels;
	wav_hdr.samples_per_sec = waveFormat->nSamplesPerSec;
	wav_hdr.avg_bytes_per_sec = waveFormat->nAvgBytesPerSec;
	wav_hdr.block_align = waveFormat->nBlockAlign;
	wav_hdr.bits_per_sample = waveFormat->wBitsPerSample;
	wav_hdr.data_size = waveFormat->cbSize;

	FILE *sourceFp, *targetFp;
	sourceFp = fopen(soourceFile, "rb");
	targetFp = fopen(targetFile, "wb");

	fwrite(&wav_hdr, sizeof(wav_hdr), 1, targetFp);

	while ((rc = fread(buf, sizeof(unsigned char), 1024, sourceFp)) != 0)
	{
		fwrite(buf, sizeof(unsigned char), rc, targetFp);
	}

	fclose(targetFp);
	fclose(sourceFp);
	return 0;
}

int runSpeechSynthesizer(MSTTSHANDLE* handle, char* fileName) {
	MSTTS_RESULT result;
	MSTTSHANDLE MSTTShandle;
	const MSTTSWAVEFORMATEX* waveFormat = NULL;

	result = MSTTS_CreateSpeechSynthesizerHandler(&MSTTShandle, ApiKey);
	if (result != MSTTS_OK)
	{
		printf("Creat speech synthesizer handler error\r\n");
		return 0;
	}

	*handle = MSTTShandle;

	result = MSTTS_SetOutput(MSTTShandle, waveFormat, pfWriteBack, fileName);
	if (result != MSTTS_OK)
	{
		printf("set output callback error\r\n");
		return 0;
	}

	//MSTTSVoiceInfo must set the correct match voice information
	//Otherwise MSTTS_Speak will return MSTTS_HTTP_GETINFO_ERROR
	//You can view the language you can set up at the following URL
	//https://docs.microsoft.com/zh-cn/azure/cognitive-services/Speech/API-Reference-REST/BingVoiceOutput
	MSTTSVoiceInfo* pVoiceInfo = (MSTTSVoiceInfo*)malloc(sizeof(MSTTSVoiceInfo));
	pVoiceInfo->lang = "en-US";
	pVoiceInfo->voiceName = "Microsoft Server Speech Text to Speech Voice (en-US, BenjaminRUS)";

	result = MSTTS_SetVoice(MSTTShandle, (const MSTTSVoiceInfo*)pVoiceInfo);
	if (result != MSTTS_OK)
	{
		printf("set voice error\r\n");
		return 0;
	}

	result = MSTTS_Speak(MSTTShandle, text, MSTTSContentType_PlainText);
	//If result == MSTTS_HTTP_PERFORM_BREAK
	//Means that HTTP reception stops
	if (result == MSTTS_HTTP_PERFORM_BREAK) {
		printf("speak stoped\r\n");
	}

	if (result != MSTTS_OK && result != MSTTS_HTTP_PERFORM_BREAK)
	{
		printf("speak error\r\n");
		return 0;
	}

	waveFormat = MSTTS_GetOutputFormat(MSTTShandle);
	if (waveFormat == NULL)
	{
		printf("get wave format error\r\n");
		return 0;
	}

	char* targetFileName = (char*)malloc(strlen(fileName) + 1 + 4);
	memset(targetFileName, 0, strlen(fileName) + 1 + 4);
	strcat(targetFileName, fileName);
	strcat(targetFileName, ".wav");

	if (!addWaveHeader(targetFileName, fileName, waveFormat))
	{
		printf("Generate wav file success\r\n");
	}

	free(targetFileName);

	MSTTS_CloseSynthesizer(MSTTShandle);

	return 0;
}


void* tprocess1(void* args) {
	
	runSpeechSynthesizer(args, "./tprocess1.pcm");
	return NULL;
}

void* tprocess2(void* args) {
	
	runSpeechSynthesizer(args, "./tprocess2.pcm");
	return NULL;
}


int main() {
	pthread_t t1;
	pthread_t t2;
	MSTTSHANDLE MSTTShandle_p1 = NULL;
	MSTTSHANDLE MSTTShandle_p2 = NULL;

	pthread_create(&t1, NULL, tprocess1, &MSTTShandle_p1);
	Sleep(500);
	pthread_create(&t2, NULL, tprocess2, &MSTTShandle_p2);
	Sleep(1200);

	//will stop SpeechSynthesizer in tprocess2
	MSTTS_Stop(MSTTShandle_p2);
	pthread_join(t1, NULL);
	pthread_join(t2, NULL);
	getch();
	return 0;
}
