#include<stdio.h>
#include"iconv\iconv.h"
#include"TTS_SDK.h"
#include<time.h>
#include<windows.h>
#include"azure_c_shared_utility\httpapi.h"
#include"azure_c_shared_utility\audio_sys.h"

const unsigned char* ApiKey = "f2c0453f2e0e448584f76e3d25989df1";

const char* text = "安琪说，她最大的遗憾就是没有长成一个坏女生。\
微胖女孩的凌乱美安琪是一个微胖的女孩，脸上长着点点雀斑煞是可爱，头发不长不短，可是她扎起马尾以后，我就成了班上仅存的一枚短发女生。\
她并不在意自己的发型，刘海三七分，挡住视线了就剪。后面的头发扎得很低，因为头发尚短的缘故，我从后面看她，不论哪个角度都觉得她的发型像中年大妈。\
她说她喜欢凌乱美，就像韩剧里女主角的飘飘长发被风扬起来的样子，带有一种不可言语的凄美，再配上那黛玉妹妹似的忧愁眼神，活生生一个乱世佳人的模样。\
只是，安琪眼中的凌乱美未免理解得有些肤浅了吧，不梳头发叫凌乱美？安琪，我只想说，你只做到了前面两个字。\
安琪的五官并不出色但属于端正的范畴，可她还是会为自己的容貌感到不自信甚至是自卑，她偶尔会发发牢骚说自己又矮又胖又丑，\
这个时候我会摸摸她的头告诉她：“这世间不可能人人都是倾国倾城的绝色佳人，总有人长得好看，有人长得不那么好看，但是上帝在关上一扇门时也会善意地打开一扇窗。”\
她说她喜欢凌乱美，就像韩剧里女主角的飘飘长发被风扬起来的样子，带有一种不可言语的凄美，再配上那黛玉妹妹似的忧愁眼神，\
活生生一个乱世佳人的模样。只是，安琪眼中的凌乱美未免理解得有些肤浅了吧，不梳头发叫凌乱美？安琪，我只想说，你只做到了前面两个字。\
安琪的五官并不出色但属于端正的范畴，可她还是会为自己的容貌感到不自信甚至是自卑，她偶尔会发发牢骚说自己又矮又胖又丑，\
这个时候我会摸摸她的头告诉她：“这世间不可能人人都是倾国倾城的绝色佳人，总有人长得好看，有人长得不那么好看，但是上帝在关上一扇门时也会善意地打开一扇窗。”\
老实说，我也不知道自己在絮絮叨叨些什么，但是我相信她会懂的。所以，即使班长在口香糖的包装纸上写了“你最近怎么越来越胖了”\
这样令人有拿鞋底拍他的冲动的话递给她时，乐观豁达的安琪还是会微笑着在背面写上“你这么说就是以前我很瘦喽”，然后递给欠揍的班长。";

int conversion(const unsigned char* inbuf, unsigned char* outbuf, size_t outlen, const char* tocode, const char* fromcode) {
	int inlen = strlen(inbuf);
	iconv_t cd = iconv_open(tocode, fromcode);
	char *tmpOutbuf = (char *)malloc(inlen * 4);
	memset(tmpOutbuf, 0, inlen * 4);
	char *in = inbuf;
	char *out = tmpOutbuf;
	size_t tmpOutlen = inlen * 4;
	iconv(cd, &in, (size_t *)&inlen, &out, &tmpOutlen);
	tmpOutlen = strlen(tmpOutbuf);

	if (tmpOutlen >= outlen) {
		free(tmpOutbuf);
		iconv_close(cd);
		return -1;
	}
	else {
		strcpy(outbuf, tmpOutbuf);
		free(tmpOutbuf);
		iconv_close(cd);
		return 0;
	}
}

void main() {

	MSTTS_RESULT result;
	MSTTSHANDLE MSTTShandle;
	
	result = MSTTS_CreateSpeechSynthesizerHandler(&MSTTShandle, ApiKey);

	//MSTTS_RESULT MSTTS_SetVoice(MSTTSHANDLE hSynthesizerHandle, const MSTTSVoiceInfo* pVoiceInfo);

	unsigned char* bodyText = malloc(10000);
	if (bodyText == NULL) {
		printf("malloc failed");
		return;
	}
	memset(bodyText, 0, 10000);
	conversion(text, bodyText, 10000, "utf-8", "GBK");

	result = MSTTS_Speak(MSTTShandle, bodyText, MSTTSContentType_PlainText);

	MSTTS_CloseSynthesizer(MSTTShandle);

	free(bodyText);

	getch();
}
