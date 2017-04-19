#include<stdio.h>
#include<stdlib.h>
#include"TTSClientSDK.h"


const unsigned char* ApiKey = "f2c0453f2e0e448584f76e3d25989df1";

const char* text = "This is the Microsoft TTS Client SDK test program";

typedef struct _wave_pcm_hdr
{
	char            riff[4];
	int				size_8;
	char            wave[4];
	char            fmt[4];
	int				fmt_size;
	short int       format_tag;
	short int       channels;
	int				samples_per_sec;
	int				avg_bytes_per_sec;
	short int       block_align;
	short int       bits_per_sample;
	char            data[4];
	int				data_size;
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

int pfWriteBack(void* pCallBackStat, const char* pWaveSamples, int32_t nBytes) {
	FILE *fp;
	fp = fopen("./TTSSample.pcm", "ab");
	fwrite(pWaveSamples, sizeof(char), nBytes, fp);
	fclose(fp);
	return 0;
}

int addWaveHeader(char* targetFile, char* soourceFile, const MSTTSWAVEFORMATEX* waveFormat) {
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

	while ((rc = fread(buf, sizeof(unsigned char), 1024, sourceFp)) != 0) {
		fwrite(buf, sizeof(unsigned char), rc, targetFp);
	}

	fclose(targetFp);
	fclose(sourceFp);
	return 0;
}

int main() {

	MSTTS_RESULT result;
	MSTTSHANDLE MSTTShandle;
	const MSTTSWAVEFORMATEX* waveFormat = NULL;

	result = MSTTS_CreateSpeechSynthesizerHandler(&MSTTShandle, ApiKey);
	if (result != MSTTS_OK) {
		printf("Creat speech synthesizer handler error\r\n");
		return 0;
	}

	result = MSTTS_SetOutput(MSTTShandle, waveFormat, pfWriteBack, NULL);
	if (result != MSTTS_OK) {
		printf("set output callback error\r\n");
		return 0;
	}

	result = MSTTS_Speak(MSTTShandle, text, MSTTSContentType_PlainText);
	if (result != MSTTS_OK) {
		printf("speak error\r\n");
		return 0;
	}

	waveFormat = MSTTS_GetOutputFormat(MSTTShandle);
	if (waveFormat == NULL) {
		printf("get wave format error\r\n");
		return 0;
	}

	if (!addWaveHeader("./TTSSample.wav", "./TTSSample.pcm", waveFormat)) {
		printf("Generate wav file success\r\n");
	}

	MSTTS_CloseSynthesizer(MSTTShandle);

	return 0;

}
