This python script contains samples of HTTP-based Microsoft Neural Voice Long Audio APIs.

1. First, you must obtain a standard (not free) Speech service subscription key by following instructions in Microsoft Cognitive Services subscription.
2. Install Python from https://www.python.org/downloads/release/
3. Install python modules needed with 'pip install urllib3 requests'

Usage guide:

1.Check the help of the tool:
python voiceclient.py -h

2.Get submitted voice synthesis list with filter and paged:
python voiceclient.py --voicesynthesis -region centralindia -key your_key_here -status Succeeded -timestart "2020-01-01" -timeend "2020-01-23" -skip 0 -top 100

2.Get submitted voice synthesis by ID:
python voiceclient.py --voicesynthesisbyid -region centralindia -key your_key_here -synthesisId id

3.Get available voice list:
python voiceclient.py --voices -region centralindia -key your_key_here

4.Submit a voice synthesis request:
python voiceclient.py --submit -region centralindia -key your_key_here -file en-US.txt -locale en-US -voiceId voice_id_here -format riff-16khz-16bit-mono-pcm --concatenateResult

5.Delete submitted voice synthesis requests:
python voiceclient.py --delete -region centralindia -key your_key_here -synthesisId id1 id2 id3 id4

Note:
a. The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and shoule not contains lines more than 10000. Should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters). If billable characters number < 10000, please expect that the request probably be queued and will be done within 12 hours.If billable characters number > 10000, the request will be executed once where are available resource(not be queued).
Billable character link : https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech#pricing-note
b. The voiceId should pick up from MS guys or get from step2 above.
c. Available audio output formats are:
	"riff-8khz-16bit-mono-pcm",
	"riff-16khz-16bit-mono-pcm",
	"riff-24khz-16bit-mono-pcm",
	"riff-48khz-16bit-mono-pcm",
	"audio-16khz-32kbitrate-mono-mp3",
	"audio-16khz-64kbitrate-mono-mp3",
	"audio-16khz-128kbitrate-mono-mp3",
	"audio-24khz-48kbitrate-mono-mp3",
	"audio-24khz-96kbitrate-mono-mp3",
	"audio-24khz-160kbitrate-mono-mp3",
d. 'concatenateResult' is a optional parameters, if not give, the output will be multiple wave files per line.
e. Client for each subscription account is allowed to submit at most 5 requests to server per second, if hit the bar, client will get a 429 error code(too many requests).
f. Server keep at most 120 requests in queue or running for each subscription accout, if hit the bar, should wait until some requests get completed before submit new ones.
g. Server keep at most 20000 requests for each subscription account. If hit the bar, should delete some requests previously submitted before submit new ones.


