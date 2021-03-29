Translator Demo
===============================

This folder contains the complete Translator Demo code. Include a frontend base WeChat mini program and a backend server.

Build It
----------

You need to take a few steps to build it:

1. Apply for TTS, SR, MT related SubscriptionKey, and fill in the fields in Backend/TranslatorServer/Configuration.cs
Related Links:  [Microsoft Cognitive Services](<https://docs.microsoft.com/en-us/azure/cognitive-services/>).
2. Deploy your backend.
3. Registered [微信公众平台](<https://mp.weixin.qq.com/cgi-bin/loginpage?t=wxm2-login&lang=zh_CN>) and get the AppID. Only one AppID per account.
4. Import frontend project and fill in the AppID to complete the import.
5. Replace [Your backend API url] in frontedn project at "Microsoft Translator_wechat/pages/index/index.js" line 101.
6. You need to set up on the 微信公众平台 to activate the mini program access to the network: 开发-->开发设置-->服务器域名-->Fill in the required hosts as required.
