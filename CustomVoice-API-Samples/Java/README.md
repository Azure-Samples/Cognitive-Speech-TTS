# Custom Voice API

This project contains samples of HTTP-based Microsoft Neural Voice Long Audio APIs.
 
## Build the samples

1. First, you must obtain a standard (not free) Speech service subscription key by following instructions in Microsoft Cognitive Services subscription.
1. Run use this command: `java -jar target\CustomVoiceAPI-Java-1.0-SNAPSHOT.jar`. Related parameters, please refer to the following Usage.

#### usage

The following are the parameters required for the 5 executable commands:
* Create Voice Synthesis task
```
 [Required]
    -c,--create                     
    -h,--hosturl <arg>              i.e. https://centralindia.customvoice.api.speech.microsoft.com
    -s,--subscriptionkey <arg>      The Speech service subscription key
    -n,--name <arg>                 The name of synthesis task
    -l,--locale <arg>               The locale information like zh-CN/en-US
    -m,--modelidlist <arg>          The id list of the model which used to synthesis, separated by ';'
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
    -h,--hosturl <arg>              i.e. https://centralindia.customvoice.api.speech.microsoft.com
    -s,--subscriptionkey <arg>      The Speech service subscription key
```
* Get Voice Synthesis List
```
 [Required]
    -gvs,--getvoicesynthesis
    -h,--hosturl <arg>              i.e. https://centralindia.customvoice.api.speech.microsoft.com
    -s,--subscriptionkey <arg>      The Speech service subscription key
```
* Get Voice Synthesis by Id
```
 [Required]
    -gvsi,--getvoicesynthesisbyid
    -h,--hosturl <arg>                  i.e. https://centralindia.customvoice.api.speech.microsoft.com
    -s,--subscriptionkey <arg>          The Speech service subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```
* Delete Voice Synthesis by Id
```
 [Required]
    -dvs,--delete
    -h,--hosturl <arg>                  i.e. https://centralindia.customvoice.api.speech.microsoft.com
    -s,--subscriptionkey <arg>          The Speech service subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```

## Note:

1. The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and shoule not contains lines more than 10000. Should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters). If billable characters number < 10000, please expect that the request probably be queued and will be done within 12 hours.If billable characters number > 10000, the request will be executed once where are available resource(not be queued).  
Billable character link: https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech#pricing-note
1. The voiceId could be acquired from the function getVoiceId() in the java file.
1. Available audio output formats are:  
  "riff-8khz-16bit-mono-pcm",  
  "riff-16khz-16bit-mono-pcm",  
  "riff-24khz-16bit-mono-pcm",  
  "riff-48khz-16bit-mono-pcm",  
  "audio-16khz-32kbitrate-mono-mp3",  
  "audio-16khz-64kbitrate-mono-mp3",  
  "audio-16khz-128kbitrate-mono-mp3",  
  "audio-24khz-48kbitrate-mono-mp3",  
  "audio-24khz-96kbitrate-mono-mp3",  
  "audio-24khz-160kbitrate-mono-mp3"
1. 'concatenateResult' is an optional parameter, if not given, the output will be multiple wave files per line.
1. Client for each subscription account is allowed to submit at most 5 requests to server per second, if hit the bar, client will get a 429 error code(too many requests).
1. Server keep at most 120 requests in queue or running for each subscription accout, if hit the bar, should wait until some requests get completed before submit new ones.
1. Server keep at most 20000 requests for each subscription account. If hit the bar, should delete some requests previously submitted before submit new ones.
