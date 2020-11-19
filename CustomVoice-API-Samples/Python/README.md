# Custom Voice API

This python script contains samples of HTTP-based Microsoft Neural Voice Long Audio APIs.

## Before use

1. First, you must obtain a standard (not free) Speech service subscription key by following instructions in Microsoft Cognitive Services subscription.
1. Install Python from https://www.python.org/downloads/release/
1. Install python modules needed with 'pip install urllib3 requests'

## Usage

* Check the help of the tool:
```
python voiceclient.py -h
```
* Get submitted voice synthesis list with filter and paged:
```
python voiceclient.py --voicesynthesis -region centralindia -key your_key_here -status Succeeded -timestart "2020-01-01" -timeend "2020-01-23" -skip 0 -top 100
```
* Get single submitted voice synthesis by ID:
```
python voiceclient.py --voicesynthesisbyid -region centralindia -key your_key_here -synthesisId id
```

* Get available voice list:
```
python voiceclient.py --voices -region centralindia -key your_key_here
```
* Submit a voice synthesis request:
```
python voiceclient.py --submit -region centralindia -key your_key_here -file en-US.txt -locale en-US -voiceId voiceId1 voiceId2 -format riff-16khz-16bit-mono-pcm --concatenateResult
```
* Delete submitted voice synthesis requests:
```
python voiceclient.py --delete -region centralindia -key your_key_here -synthesisId id1 id2 id3 id4
```

## Note:

1. The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and shoule not contains lines more than 10000. Should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters). If billable characters number < 10000, please expect that the request probably be queued and will be done within 12 hours.If billable characters number > 10000, the request will be executed once where are available resource(not be queued).
See [Billable character](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech#pricing-note).
1. The voiceId should pick up from MS guys or get from the command "Get available voice list", the input file should be an SSML file if mutilple voice ids are set.
1. 'concatenateResult' is an optional parameter. If this parameter isn't set, the audio outputs will be generated per paragraph.
1. Client for each subscription account is allowed to submit at most 5 requests to server per second, if hit the bar, client will get a 429 error code(too many requests).
1. Server keep at most 120 requests in queue or running for each subscription accout, if hit the bar, should wait until some requests get completed before submit new ones.
1. Server keep at most 20000 requests for each subscription account. If hit the bar, should delete some requests previously submitted before submit new ones.

## Some parameter sets

- [SupportedRegions](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation)

- [OutputFormats](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/long-audio-api#audio-output-formats)

- [SSMLInputFileSample](https://github.com/Azure-Samples/Cognitive-Speech-TTS/blob/master/CustomVoice-API-Samples/Java/SSMLTextInputSample.txt)

# Contributing

We welcome contributions and are always looking for new SDKs, input, and
suggestions. Feel free to file issues on the repo and we'll address them as we can. You can also learn more about how you can help on the [Contribution
Rules & Guidelines](/CONTRIBUTING.md).

For questions, feedback, or suggestions about Microsoft Cognitive Services, feel free to reach out to us directly.

- [Cognitive Services UserVoice Forum](https://cognitive.uservoice.com)

# License

All Microsoft Cognitive Services SDKs and samples are licensed with the MIT License. For more details, see
[LICENSE](/LICENSE.md).

Sample images are licensed separately, please refer to [LICENSE-IMAGE](/LICENSE-IMAGE.md).