1. Install Python2 from https://www.python.org/downloads/release/python-2716/

Usage guide:

1.Check the help of the tool:
C:\Python27amd64\python.exe voiceclient.py -h

2.Get available voice list:
C:\Python27amd64\python.exe voiceclient.py --voices -region centralindia -key your_key_here

3.Submit a voice synthesis request:
C:\Python27amd64\python.exe voiceclient.py --submit -region centralindia -key your_key_here-file zh-CN.txt -locale zh-CN -voiceId voice_id_here --concatenateResult

Note:
a.The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one zh-CN.txt, and should be more than 50 lines.
b.The voiceId should pick up from MS guys or get from step2 above.
c.'concatenateResult' is a optional parameters, if not give, the output will be multiple wave files per each line.



