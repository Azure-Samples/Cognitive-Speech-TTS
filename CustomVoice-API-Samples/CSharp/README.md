# Custom Voice API

This folder contains samples of using HTTP REST Call for Microsoft Custom Voice REST APIs.

## The samples

Use API to construct an e2e flow: upload data, start model training, create voice test, create endpoint and so on.

## Before use

You must obtain a Speech service subscription key by following instructions in [Microsoft Cognitive Services subscription](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/get-started#create-a-speech-resource-in-azure).

## Usage

You can start quickly with console commands, or you can build your own workflow based on sample code.

### Basic

Use the following command to get available API kind and usage.

```cmd
CustomVoice-API
```

Output:

```plaintext
Custom Voice API 3.0.

Usage: CustomVoice-API [APIKind] [action] [options]

--APIKind:
     project
     dataset
     model
     voicetest
     endpoint
     batchsynthesis

For more detailed usage, please enter: CustomVoice-API [APIKind]
```



## Some parameter sets

- [HostURI](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation)

- [IssueTokenUrl](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech#how-to-get-an-access-token)

- [OutputFormat](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech#audio-outputs)

- [OutputFormatForLongAudioAPI](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/long-audio-api#audio-output-formats)

- [SSMLInputFileSampleForLongAudioAPI](https://github.com/Azure-Samples/Cognitive-Speech-TTS/blob/master/CustomVoice-API-Samples/Java/SSMLTextInputSample.txt)

## Case Study: automate model deployment, synthesis and endpoint deletion.

### create a deployment 
dotnet CustomVoice-API.Core.dll endpoint create subscriptionKey **YourSpeechKey** hostURI https://**YourRegion**.customvoice.api.speech.microsoft.com/ name batchtest locale en-us projectId **YourProjectGUID**  modelId **YourModelGuid**

it will output the new endpoint information to console like below


     endpoint created: https://eastus.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0-beta1/endpoints/YourEndpointID
     Create endpoint successfully

use the endpointID in below command. 

### query endpoint status. 
dotnet CustomVoice-API.Core.dll endpoint getbyid subscriptionKey **YourSpeechKey** hostURI https://**YourRegion**.customvoice.api.speech.microsoft.com/ endpointid **YourEndpointID**

### do some work using the endpoint. 
For example, you can synthesize a file with multiple lines with multiple threads.

### delete the endpoint 
dotnet  CustomVoice-API.Core.dll endpoint delete subscriptionKey **YourSpeechKey** hostURI https://**YourRegion**.customvoice.api.speech.microsoft.com/ endpointid **YourEndpointID**



## Contributing

We welcome contributions and are always looking for new SDKs, input, and
suggestions. Feel free to file issues on the repo and we'll address them as we can. You can also learn more about how you can help on the [Contribution
Rules & Guidelines](/CONTRIBUTING.md).

For questions, feedback, or suggestions about Microsoft Cognitive Services, feel free to reach out to us directly.

- [Cognitive Services UserVoice Forum](https://cognitive.uservoice.com)

## License

All Microsoft Cognitive Services SDKs and samples are licensed with the MIT License. For more details, see
[LICENSE](/LICENSE.md).

Sample images are licensed separately, please refer to [LICENSE-IMAGE](/LICENSE-IMAGE.md).
