#include<stdio.h>
#include"iconv\iconv.h"
#include"TTS_SDK.h"
#include<time.h>
#include"azure_c_shared_utility\httpheaders.h"
#include"azure_c_shared_utility\httpapi.h"

const unsigned char* ApiKey = "f2c0453f2e0e448584f76e3d25989df1";

const char* text = "����˵���������ź�����û�г���һ����Ů����\
΢��Ů����������������һ��΢�ֵ�Ů�������ϳ��ŵ��ȸ��ɷ�ǿɰ���ͷ���������̣�������������β�Ժ��Ҿͳ��˰��Ͻ����һö�̷�Ů���������������Լ��ķ��ͣ��������߷֣���ס�����˾ͼ��������ͷ�����úܵͣ���Ϊͷ���ж̵�Ե�ʣ��ҴӺ��濴���������ĸ��Ƕȶ��������ķ�����������衣\
��˵��ϲ�������������񺫾���Ů���ǵ�ƮƮ�������������������ӣ�����һ�ֲ�������������������������������Ƶ��ǳ����񣬻�����һ���������˵�ģ����ֻ�ǣ��������е�������δ��������Щ��ǳ�˰ɣ�����ͷ��������������������ֻ��˵����ֻ������ǰ�������֡�\
��������ٲ�����ɫ�����ڶ����ķ��룬�������ǻ�Ϊ�Լ�����ò�е��������������Ա�����ż���ᷢ����ɧ˵�Լ��ְ������ֳ����ʱ���һ���������ͷ���������������䲻�������˶��������ǵľ�ɫ���ˣ������˳��úÿ������˳��ò���ô�ÿ��������ϵ��ڹ���һ����ʱҲ������ش�һ�ȴ�����\
��˵��ϲ�������������񺫾���Ů���ǵ�ƮƮ�������������������ӣ�����һ�ֲ�������������������������������Ƶ��ǳ����񣬻�����һ���������˵�ģ����ֻ�ǣ��������е�������δ��������Щ��ǳ�˰ɣ�����ͷ��������������������ֻ��˵����ֻ������ǰ�������֡�\
��������ٲ�����ɫ�����ڶ����ķ��룬�������ǻ�Ϊ�Լ�����ò�е��������������Ա�����ż���ᷢ����ɧ˵�Լ��ְ������ֳ����ʱ���һ���������ͷ���������������䲻�������˶��������ǵľ�ɫ���ˣ������˳��úÿ������˳��ò���ô�ÿ��������ϵ��ڹ���һ����ʱҲ������ش�һ�ȴ�����\
��ʵ˵����Ҳ��֪���Լ�������߶߶Щʲô���������������ᶮ�ġ����ԣ���ʹ�೤�ڿ����ǵİ�װֽ��д�ˡ��������ôԽ��Խ���ˡ�������������Ь�������ĳ嶯�Ļ��ݸ���ʱ���ֹۻ��İ������ǻ�΢Ц���ڱ���д�ϡ�����ô˵������ǰ�Һ���ඡ���Ȼ��ݸ�Ƿ��İ೤��";

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
	MSTTS_HANDLE MSTTShandle = MSTTS_init(ApiKey); 
	if (MSTTShandle == NULL) {
		printf("init MSTTS failed");
		return 0;
	}

	unsigned char* bodyText = malloc(MAX_BodyLength);
	if (bodyText == NULL) {
		printf("malloc failed");
		return 0;
	}
	memset(bodyText, 0, MAX_BodyLength);
	conversion(text, bodyText, MAX_BodyLength, "utf-8", "GBK");

	unsigned char* wavStream = malloc(102400);
	if (wavStream == NULL) {
		printf("malloc failed");
		return 0;
	}
	memset(wavStream, 0 , 10240000);
	MSTTS_Synthesizer(MSTTShandle, bodyText, MSTTSContentType_PlainText, wavStream, 102400);

	MSTTS_close(MSTTShandle);

	free(bodyText);
	free(wavStream);

	getch();
}
