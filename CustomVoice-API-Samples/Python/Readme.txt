1. Install Python from https://www.python.org/downloads/release/

Usage guide:

1.Check the help of the tool:
python voiceclient.py -h

2.Get available voice list:
python voiceclient.py --voices -region centralindia -key your_key_here

3.Submit a voice synthesis request:
python voiceclient.py --submit -region centralindia -key your_key_here -file zh-CN.txt -locale zh-CN -voiceId voice_id_here -format riff-16khz-16bit-mono-pcm --concatenateResult

Note:
a.The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one zh-CN.txt, and should be more than 50 lines.
b.The voiceId should pick up from MS guys or get from step2 above.
c Available audio output formats are:
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
d.'concatenateResult' is a optional parameters, if not give, the output will be multiple wave files per each line.



