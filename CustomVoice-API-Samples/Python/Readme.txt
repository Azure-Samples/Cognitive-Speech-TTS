This python script contains samples of HTTP-based Microsoft Custom Neural Voice Batch Synthesis APIs.

1. Install Python from https://www.python.org/downloads/release/

Usage guide:

1.Check the help of the tool:
python voiceclient.py -h

2.Get submitted voice synthesis list:
python voiceclient.py --syntheses -region centralindia -key your_key_here

3.Get available voice list:
python voiceclient.py --voices -region centralindia -key your_key_here

4.Submit a voice synthesis request:
python voiceclient.py --submit -region centralindia -key your_key_here -file en-US.txt -locale en-US -voiceId voice_id_here -format riff-16khz-16bit-mono-pcm --concatenateResult

5.Delete submitted voice synthesis requests:
python voiceclient.py --delete -region centralindia -key your_key_here -synthesisId id1 id2 id3 id4

Note:
a. The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters).
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
d. 'concatenateResult' is a optional parameters, if not give, the output will be multiple wave files per each line.



