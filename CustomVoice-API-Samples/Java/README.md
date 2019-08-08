## Custom Voice API

This project contains samples of HTTP-based Microsoft Custom Voice Synthesis APIs.
 
## Build the samples

1. First, you must obtain a standard (not free) Speech API subscription key by following instructions in Microsoft Cognitive Services subscription.
2. To run the sample, make sure that you manually include all the jar files inside the lib folder to the project. 
3. You need to pass in arguments of endpoint, ibizaStsUrl, subscriptionKey, localInputTextFile, locale, voiceName and concatenateResult to the VoiceSynthsisAPIToJAVA.java file based on the information of the region, your subscription key, your designated voice and your desirable format of output wav file.

## Note:

1.The input text file should be Unicode format with 'UTF-8-BOM' (you can check the text format with your preferred advanced text editor), like the one zh-CN.txt, and should be more than 50 lines.
2.The voiceId should pick up from MS guys or from the function getVoiceId in the java file.
3.'concatenateResult' is an optional parameter, if not given, the output will be multiple wave files per line.
