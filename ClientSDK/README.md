Client SDK for Text To Speech
===============================

TTSClient SDK is a C library providing common functionality for Microsoft Cognitive Services (formerly Project Oxford)
Text To Speech REST APIs.

The samples
===========

Now supports Linux and Windows.

Build the samples
----------------

TTSClient SDK depends on curl, openssl and silk. They are stored in 3rdparty.

Build the samples
----------------

1. First, you must obtain a Speech API subscription key by following instructions in [Microsoft Cognitive Services subscription](<https://www.microsoft.com/cognitive-services/en-us/sign-up>).

2. You need to find the line with the string "Your api key" in the source files of
a particular language, and replace it with your subscription key for Speech.

3. You can run the script directly to build a project, it depends on CMAKE.

Contributing
============
We welcome contributions and are always looking for new SDKs, input, and
suggestions. Feel free to file issues on the repo and we'll address them as we can. You can also learn more about how you can help on the [Contribution
Rules & Guidelines](</CONTRIBUTING.md>).

For questions, feedback, or suggestions about Microsoft Cognitive Services, feel free to reach out to us directly.

-   [Cognitive Services UserVoice Forum](<https://cognitive.uservoice.com>)

License
=======

All Microsoft Cognitive Services SDKs and samples are licensed with the MIT License. For more details, see
[LICENSE](</LICENSE.md>).

Sample images are licensed separately, please refer to [LICENSE-IMAGE](</LICENSE-IMAGE.md>).
