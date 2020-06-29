# Pronunciation Assessment - Windows Presentation Foundation (C#) Samples

This sample shows how to call pronunciation assessment REST API in CSharp, with GUI based speech recording.

## Prerequisites

Here's what you'll need to run these samples:

* DotNET framework 4.6.1 or above
* Visual Studio 2019
* An Azure subscription with Speech Services enabled. [Get one for free!](https://docs.microsoft.com/azure/cognitive-services/speech-service/get-started)
* A working microphone as audio input device
* A working speaker or headset as audio output device

## Code sample

To use this sample, follow these instructions:

* Clone this repository.
* Open `PronunciationAssessment.sln` in Visual Studio.
* Follow the [instructions](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/quickstarts/setup-platform?tabs=dotnet%2Cwindows%2Cjre%2Cbrowser&pivots=programming-language-csharp#choose-target-architecture) to choose target architecture
* Build the solution.
* Press F5 to start the application.
* On the application window, choose the region and fill your subscription key.
* Type some text into the text box at the center of the window, or leave the default text as it is.
* Click the button with `speaker` icon to listen to the standard pronunciation of the text.
* Click the button with `microphone` icon and then read along the text in the central text box.
* After you finish reading the text, click `stop` button (which was changed from the `microphone` button). Then you should see the pronuncation assessment result in scores, on sentence, word, and phoneme levels.

## Resources

* [REST API reference](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-speech-to-text)
