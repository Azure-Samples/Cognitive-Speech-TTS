# Microsoft Bing Speech API: Text-to-Speech Samples
This repo contains sample in various languages for using Text-to-Speech in the Microsoft Bing Speech API, an offering within [Microsoft Cognitive Services](https://www.microsoft.com/cognitive-services), formerly known as Project Oxford.
* [Learn about the Bing Speech API](https://www.microsoft.com/cognitive-services/en-us/speech-api)
* [Read the documentation](https://www.microsoft.com/cognitive-services/en-us/speech-api/documentation/overview)
* [Find more SDKs & Samples](https://www.microsoft.com/cognitive-services/en-us/SDK-Sample?api=bing%20speech)


## The Sample

### Requirements
 * Android OS must be Android 4.1 or higher (API Level 16 or higher)
 * The speech client library contains native code. To use this sample in an emulator, make sure that your build variant matches the architecture (x86 or arm) of your emulator. However, due to the need of audio, using a physical device is recommended.

### Build the sample
1.  First, you must obtain a Speech API subscription key by [following the instructions on our website](<https://www.microsoft.com/cognitive-services/en-us/sign-up>).

2.  Start Android Studio and open project by File \> Import Project. Choose subfolder "Sample" in the Speech \> TextToSpeech \> Android folder.

3.  In Android Studio -\> "Project" panel -\> "Android" view, open file
    "app/res/values/strings.xml", and find the line
    "Please\_add\_the\_subscription\_key\_here;". Replace the
    "Please\_add\_the\_subscription\_key\_here" value with your subscription key
    string from the first step. If you cannot find the file "string.xml", it is
    in folder "Sample\app\src\main\res\values\string.xml".

4.  In Android Studio, select menu "Build \> Make Project" to build the sample, and "Run" to launch this sample app.

### Run the sample
In Android Studio, select menu "Run", and "Run app" to launch this sample app.

<img src="SampleScreenshots/SampleRunning1.png" width="50%"/>


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
