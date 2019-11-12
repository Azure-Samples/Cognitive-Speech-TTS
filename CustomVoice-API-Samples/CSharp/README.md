Custom Voice API
===============================

This folder contains samples of using HTTP REST Call for Microsoft Custom Voice REST APIs.

The samples
===========

Use API to construct an e2e flow: upload data, start modeling, create voice test, create endpoint and so on.

Before use
----------------

You must obtain a Speech API subscription key by following instructions in [Microsoft Cognitive Services subscription](<https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/get-started#create-a-speech-resource-in-azure>).



Usage
----------------

You can start quickly with console commands, or you can build your own workflow based on sample code.

#### For console Usage

Enter the following commands at the level you can see the parameter description and command sample:

```
> CustomVoice-API
```
```
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
```
> CustomVoice-API project
```
```
CustomVoice-API project:

All Dataset, Model, VoiceTest, Endpoint are bound in the project.
We need to specify Locale and Gender when creating Project.
The data bound to each Project must be a unique locale and gender.

Usage: CustomVoice-API project [action] [options]

--action
 Get
     Gets the list of projects for the authenticated subscription.
 create
     Creates a new project.
 Delete
     Deletes the project identified by the given ID

For more detailed usage, please enter: CustomVoice-API project [action]
```
```
> CustomVoice-API project get
```
```
CustomVoice-API project get:

Gets the list of projects for the authenticated subscription.

Usage: CustomVoice-API project get [options]

--options
 [Required]
     subscriptionkey
     hosturi
 [Optional]

Sample command : CustomVoice-API project get subscriptionKey [YourSubscriptionKey] hostURI https://Westus.cris.ai/
```

#### Some parameters sets

- [HostURI](<https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation>)

- [IssueTokenUrl](<https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech#how-to-get-an-access-token>)

- [OutputFormat](<https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech#audio-outputs>)

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
