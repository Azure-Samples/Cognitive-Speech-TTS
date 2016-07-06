HTTP Samples for Text To Speech
===============================

This folder contains samples of using HTTP REST Call for Microsoft Cognitive Services (formerly Project Oxford)
Text To Speech REST APIs.

The samples
===========

Many languages are demonstrated, including Android, C#, Java, Node.js, PHP, Python, and Ruby.

Build the samples
----------------

1. First, you must obtain a Speech API subscription key by following instructions in [Microsoft Cognitive Services subscription](<https://www.microsoft.com/cognitive-services/en-us/sign-up>).

2. You need to find the line with the string "Your Client Secret goes here" in the source files of
a particular language, and replace it with your subscription key for Speech.

3. For Android sample, follow this instruction to find the string:
In Android Studio -\> "Project" panel -\> "Android" view, open file
    "app/res/values/strings.xml", and find the line
    "Please\_add\_the\_subscription\_key\_here;". Replace the
    "Please\_add\_the\_subscription\_key\_here" value with your subscription key
    string from the first step. If you cannot find the file "strings.xml", it is
    in folder "Sample\app\src\main\res\values\string.xml".

Run the samples
--------------

Follow the requirements of your language, and run the sample accordingly.

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
