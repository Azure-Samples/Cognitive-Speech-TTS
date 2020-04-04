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
# Microsoft TTS News 
* 2020.04 [Introducing new voice styles in Azure Cognitive Services](https://techcommunity.microsoft.com/t5/azure-ai/introducing-new-voice-styles-in-azure-cognitive-services/ba-p/1248368)
* 2020.03 [Cognitive Services adds Brazilian Portuguese to Neural Text to Speech](https://techcommunity.microsoft.com/t5/azure-ai/cognitive-services-adds-brazilian-portuguese-to-neural-text-to/ba-p/1210471)
* 2020.03 [科技宝藏 | 微软听听文档，AI语音全线升级！ ](https://mp.weixin.qq.com/s?__biz=MzA5Mzk3NDcyNw==&mid=2247486058&idx=1&sn=8db9d8a3d61ab5027865593e0aef3f24&chksm=9054f3c2a7237ad455a00c0dab6baa639f84d1387525e8153f2b6c8736a5857d1de316616b60&mpshare=1&scene=1&srcid=0320zDDQqoIu4bz0ILj2eq41&sharer_sharetime=1584690411522&sharer_shareid=67fac6419876a8c72f83d82f53762097#rd)
* 2019.12 [NeurIPS2019: FastSpeech: New text-to-speech model improves on speed, accuracy, and controllability](https://www.microsoft.com/en-us/research/blog/fastspeech-new-text-to-speech-model-improves-on-speed-accuracy-and-controllability/)
* 2019.11 [Play My Emails in Outlook and get time back in your day](https://techcommunity.microsoft.com/t5/outlook-blog/play-my-emails-in-outlook-and-get-time-back-in-your-day/ba-p/930243)
* 2019.11 [Azure custom neural voice public preview](https://venturebeat.com/2019/11/04/azure-cognitive-services-gets-speech-search-language-and-security-updates-at-ignite-2019/)
* 2019.08 [Bringing cloud powered voices to Microsoft Edge Insiders](https://blogs.windows.com/msedgedev/2019/08/14/cloud-powered-voices-microsoft-edge-chromium/)
* 2019.06 [Inclusive Classroom round up for Microsoft Education at ISTE 2019](https://techcommunity.microsoft.com/t5/education-blog/inclusive-classroom-round-up-for-microsoft-education-at-iste/ba-p/679764)
* 2019.05 [Azure Neural text-to-speech GA](https://azure.microsoft.com/en-us/blog/a-deep-dive-into-what-s-new-with-azure-cognitive-services/)
* 2019.05 [ICML 2019 | 微软提出极低资源下语音合成与识别新方法，小语种也不怕没数据了](https://mp.weixin.qq.com/s?__biz=MzAwMTA3MzM4Nw==&mid=2649447754&idx=1&sn=8ad44ffc9aad1079f8d58585d5aa58e0&chksm=82c0b4ceb5b73dd8334086200cf17685c565a97b7cf09ef046d1d6ddb40ba71a3a1159a6f6c9&mpshare=1&scene=1&srcid=0405pPt16EzzJE7aSoSgcjjf&sharer_sharetime=1586043580069&sharer_shareid=3bf44cb83f7345f6bb40f678c7ccccf4#rd)
* 2019.01 [AAAI 2019: Neural Speech Synthesis with Transformer Network](https://mp.weixin.qq.com/s?__biz=MzAwMTA3MzM4Nw==&mid=2649446094&idx=1&sn=86dac8a999f6fd40af07ae1b31348355&chksm=82c0bf4ab5b7365cabf27c3fc03ee5d656d858a1ca0db5c77deceba96e486ee1af682cdc30f2&mpshare=1&scene=1&srcid=0405UlO9Hg4LROWMdTaSEFoE&sharer_sharetime=1586043448061&sharer_shareid=3bf44cb83f7345f6bb40f678c7ccccf4#rd)
* 2018.12 [Microsoft previews neural network text-to-speech](https://azure.microsoft.com/en-us/blog/microsoft-previews-neural-network-text-to-speech/)
* 2018.09 [Microsoft’s new neural text-to-speech service helps machines speak like people](https://azure.microsoft.com/en-us/blog/microsoft-s-new-neural-text-to-speech-service-helps-machines-speak-like-people/)


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
