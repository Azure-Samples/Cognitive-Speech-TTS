Contributing to Microsoft Cognitive Services Client Libraries
===============================================

So, you want to contribute on a client SDK for one of the Microsoft Cognitive Services.
Here's what you need to know.

1.  Each SDK must include both a client library and a sample showing the API in
    action

2.  When building an SDK, it's important you support the most common development
    platforms and that we are consistent from project to project. We require you
    to build the following, using the associated coding guidelines, in priority
    order:

    -   .NET (Coding guidelines below)

    -   Android [(Coding guidelines for
        Java)](<http://source.android.com/source/code-style.html>)

    -   iOS Objective-C [(Coding guidelines for
        Cocoa)](<https://developer.apple.com/library/mac/documentation/Cocoa/Conceptual/CodingGuidelines/CodingGuidelines.html>)

    -   Optional: Client Javascript ([Coding guidelines for
        npm](<https://docs.npmjs.com/misc/coding-style>))

3.  Samples are important for illustrating how to actually call into the API.
    Samples should be as visual and reusable as possible.

    Do:

    -   Create a UI sample when possible.

    -   Make your sample user friendly. Expect that developers will want to try
        different mainline scenarios and key APIs.

    -   Create code that's easy for other developers to copy/paste into their
        own solutions

    Consider:

    -   Adding UI to allow devs to quickly copy/paste subscription keys, instead
        of updating them in the code or using a config file. The
        FaceAPI-WPF-Samples.sln provides an example.

    Don't:

    -   Leave your subscription key in the source of samples. You do not want
        your key to be abused by others.

4.  Always create a README.md for your top-level API root and for each platform.

    -   Use the existing README.md files as a reference for what information is
        useful here. In general, you want to describe the functionality of the
        API as well as specifics for how to build and run the project(s).
