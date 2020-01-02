---
page_type: sample
description: "Samples in various languages for using Text-to-Speech."
languages:
- csharp
- python
- nodejs
- javascript
- php
- swift
- java
- ruby
products:
- azure
- azure-cognitive-services
---

# Microsoft Speech Service API: Text-to-Speech Samples

Microsoft Text to speech service now is offically supported by [Speech SDK](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/speech-sdk) now.  It is recommended way to use TTS in your service or apps.  It supports both REST and Websocket connection to the service. This repo still contains sample in various languages for using Text-to-Speech.  We will also support the common development questions using the issues tracker.  

[Speech Service](<https://azure.microsoft.com/en-us/services/cognitive-services/directory/speech/>) is generally avaliable since [2018.9](<https://azure.microsoft.com/en-us/updates/azure-cognitive-services-speech-service-is-now-generally-available/>). Please be sure you have a subscription key for the new Speech Service, not a subcription key from the retiring Bing Speech. 

Microsoft also offers [Neural TTS GA](<https://azure.microsoft.com/en-us/blog/microsoft-s-new-neural-text-to-speech-service-helps-machines-speak-like-people/>) which can be invoked following the samples in this repo as well. What you need is to use a neural TTS endpoint.  

Neural TTS uses Deep Neural Networks in matching patterns of stress and intonation in spoken language called prosody. So, it does prosody prediction and voice synthesis simultaneously. While traditional TTS break down prosody into separate linguistic analysis and the predictions are governed by independent models, that results in obscure voice synthesis. And therefore, Neural TTS perform much better than traditional TTS.

Recommend to run the CSharp example first which is always kept up to date. 

# Useful Links
- [Azure TTS wiki](https://github.com/Azure-Samples/Cognitive-Speech-TTS/wiki)
- [Azure Speech Document](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech)
- [Create Custom Neural Voice](https://speech.microsoft.com/customvoice)
- [Speech SDK](https://github.com/Azure-Samples/cognitive-services-speech-sdk)
- [Azure Speech Containers](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/speech-container-howto?tabs=stt%2Ccsharp)

## Contributing
We welcome contributions. Feel free to file issues and pull requests on the repo and we'll address them as we can. Learn more about how you can help on our [Contribution Rules & Guidelines](</CONTRIBUTING.md>). 

You can reach out to us anytime with questions and suggestions using our communities below:
 - **Support questions:** [StackOverflow](<https://stackoverflow.com/questions/tagged/microsoft-cognitive>)
 - **Feedback & feature requests:** [Cognitive Services UserVoice Forum](<https://cognitive.uservoice.com>)

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.


## License
All Microsoft Cognitive Services SDKs and samples are licensed with the MIT License. For more details, see
[LICENSE](</LICENSE.md>).

Sample images are licensed separately, please refer to [LICENSE-IMAGE](</LICENSE-IMAGE.md>).


## Developer Code of Conduct
Developers using Cognitive Services, including this client library & sample, are expected to follow the “Developer Code of Conduct for Microsoft Cognitive Services”, found at [http://go.microsoft.com/fwlink/?LinkId=698895](http://go.microsoft.com/fwlink/?LinkId=698895).
