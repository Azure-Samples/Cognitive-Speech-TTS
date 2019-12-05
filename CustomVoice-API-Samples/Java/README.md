## Custom Voice API

This project contains samples of HTTP-based Microsoft Custom Neural Voice Batch Synthesis APIs.
 
## Build the samples

1. First, you must obtain a standard (not free) Speech API subscription key by following instructions in Microsoft Cognitive Services subscription.
2. Make sure that you have Maven installed. Under the directory with the pom file, run the command `mvn assembly:assembly` to Compile the executable jar package.
3. Run use this command: `java -jar target\CustomVoiceAPI-Java-1.0-SNAPSHOT.jar`. Related parameters, please refer to the following Usage.

#### usage

The following are the parameters required for the 5 executable commands:
* Create Voice Synthesis task
```
 [Required]
    -c,--create                     
    -h,--hosturl <arg>              i.e. https://centralindia.cris.ai
    -s,--subscriptionkey <arg>      The cris subscription key
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
    -h,--hosturl <arg>              i.e. https://centralindia.cris.ai
    -s,--subscriptionkey <arg>      The cris subscription key
```
* Get Voice Synthesis List
```
 [Required]
    -gvs,--getvoicesynthesis
    -h,--hosturl <arg>              i.e. https://centralindia.cris.ai
    -s,--subscriptionkey <arg>      The cris subscription key
```
* Get Voice Synthesis by Id
```
 [Required]
    -gvsi,--getvoicesynthesisbyid
    -h,--hosturl <arg>                  i.e. https://centralindia.cris.ai
    -s,--subscriptionkey <arg>          The cris subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```
* Delete Voice Synthesis by Id
```
 [Required]
    -dvs,--delete
    -h,--hosturl <arg>                  i.e. https://centralindia.cris.ai
    -s,--subscriptionkey <arg>          The cris subscription key
    -vsi,--voicesynthesisid <arg>       The id of the synthesis task
```

## Note:

1.The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with Notepad++), like the one en-US.txt, and should contain at least 400 billable characters (1 en-US character stands for 1 billable characters and 1 zh-CN character stands for 2 billable characters).
2.The voiceId could be acquired from the function getVoiceId() in the java file.
3.'concatenateResult' is an optional parameter, if not given, the output will be multiple wave files per line.
