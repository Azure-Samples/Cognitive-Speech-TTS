# Custom Voice API

This project contains samples of HTTP-based Microsoft Neural Voice Long Audio APIs.
 
## Before use

1. First, you must obtain a standard (not free) Speech service subscription key by following instructions in Microsoft Cognitive Services subscription.
1. Make sure that you have Maven installed. Under the directory with the pom file, run the command `mvn assembly:assembly` to Compile the executable jar package.
1. Run use this command: `java -jar target\CustomVoiceAPI-Java-1.0-SNAPSHOT.jar`. Related parameters, please refer to the following Usage.

## Usage

The following are the parameters required for the 5 executable commands:
* Create Voice Synthesis task
```
 [Required]
    -c,--create                     
    -r,--region <arg>               i.e. centralindia
    -s,--subscriptionkey <arg>      The Speech service subscription key
    -n,--name <arg>                 The name of synthesis task
    -l,--locale <arg>               The locale information like zh-CN/en-US
    -m,--modelidlist <arg>          The id list of the model (voice) which used to synthesis, separated by ';'
    -sf,--scriptfile <arg>          The input text file path
 [Optional]
    -d,--description <arg>          The description of synthesis task
    -cr,--concatenateresult         If concatenate result in a single wave file
    -of,--outputformat <arg>        The output audio format, default value:riff-16khz-16bit-mono-pcm
```
* Get supported Voices
```
 [Required]
    -gv,--getvoice
    -r,--region <arg>               i.e. centralindia
    -s,--subscriptionkey <arg>      The Speech service subscription key
```
* Get Voice Synthesis List
```
 [Required]
    -gvs,--getvoicesynthesis
    -r,--region <arg>               i.e. centralindia
    -s,--subscriptionkey <arg>      The Speech service subscription key
 [Optional]
    -sk,--skip <arg>                The skip filter of the voice synthesis
    -st,--status <arg>              The status filter of the voice synthesis query, could be NotStarted/Running/Succeeded/Failed
    -ts,--timestart <arg>           The timestart filter of the voice synthesis query, like 2020-05-01 12:00
    -te,--timeend <arg>             The timeend filter of the voice synthesis query, like 2020-05-15
    -tp,--top <arg>                 The top filter of the voice synthesis query, should be a interger value
```
* Get Voice Synthesis by id
```
 [Required]
    -gvsi,--getvoicesynthesisbyid
    -r,--region <arg>                   i.e. centralindia
    -s,--subscriptionkey <arg>          The Speech service subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```
* Delete Voice Synthesis by id
```
 [Required]
    -dvs,--delete
    -r,--region <arg>                   i.e. centralindia
    -s,--subscriptionkey <arg>          The Speech service subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```

## Note:

1. The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and shoule not contains lines more than 10000. Should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters). If billable characters number < 10000, please expect that the request probably be queued and will be done within 12 hours.If billable characters number > 10000, the request will be executed once where are available resource(not be queued).  
See [Billable character](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech#pricing-note).
1. The modelidlist could be acquired from the command "Get supported Voices", the input file should be an SSML file if mutilple model ids are set.
1. Client for each subscription account is allowed to submit at most 5 requests to server per second, if hit the bar, client will get a 429 error code(too many requests).
1. Server keep at most 120 requests in queue or running for each subscription accout, if hit the bar, should wait until some requests get completed before submit new ones.
1. Server keep at most 20000 requests for each subscription account. If hit the bar, should delete some requests previously submitted before submit new ones.

## Some parameter sets

- [SupportedRegions](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation).

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
