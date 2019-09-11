## Custom Voice API

This project contains samples of HTTP-based Microsoft Custom Voice Synthesis APIs.
 
## Build the samples

1. First, you must obtain a standard (not free) Speech API subscription key by following instructions in Microsoft Cognitive Services subscription.
2. Make sure that you have Maven installed. Under the directory with the pom file, run the command 'mvn clean install' to install all project dependencies.
3. Run the VoiceSynthsisMain.java file. Please refer to the instructions for use.

#### usage

Must choose one to determine the action to perform:
```
 -c,--create                     Creates a new synthesis task
 -gv,--getvoice                  Gets a list of supported voices for    
                                 synthesis
 -gvs,--getvoicesynthesis        Gets a list of voice synthesis
 -gvsi,--getvoicesynthesisbyid   Gets voice synthesis by Id
 -dvs,--delete                   Deletes the specified voice synthesis  
                                 task.
```

The following is the request parameter:
```
 -h,--hosturl <arg>              i.e. https://centralindia.cris.ai      
 -s,--subscriptionkey <arg>      The cris subscription key
```

The following is the request parameter:
```
 -vsi,--voicesynthesisid <arg>   The id of the synthesis task
 -n,--name <arg>                 The name of synthesis task
 -d,--description <arg>          The description of synthesis task  
 -l,--locale <arg>               The locale information like zh-CN/en-US
 -m,--modelidlist <arg>          The id list of the model which used to 
                                 synthesis, separated by ';'
 -of,--outputformat <arg>        The output audio format, like:
                                 riff-16khz-16bit-mono-pcm
 -sf,--scriptfile <arg>          The input text file path
 -cr,--concatenateresult         If concatenate result in a single wave 
                                 file
 
```

## Note:

1.The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with your preferred advanced text editor), like the one zh-CN.txt, and should be more than 50 lines.
2.The voiceId could be acquired from the function getVoiceId() in the java file.
3.'concatenateResult' is an optional parameter, if not given, the output will be multiple wave files per line.
