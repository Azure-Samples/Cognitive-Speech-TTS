Contributing to Microsoft Cognitive Services Client Libraries & Samples
===============================================
So, you want to contribute on a client library or sample for one of the Microsoft Cognitive Services.
Here's what you need to know.

1.  Each SDK should include both a client library and a sample showing the API in
    action

2.  When working on an SDK, it's important that we are consistent from project to project, so we ask you to follow the coding guidelines below:

    -   Windows [(Coding guidelines for C#)](https://msdn.microsoft.com/en-us/library/ff926074.aspx) -- also reference our [common Windows code](https://github.com/Microsoft/Cognitive-common-windows) for building samples

    -   Android [(Coding guidelines for
        Java)](<http://source.android.com/source/code-style.html>)

    -   iOS Objective-C [(Coding guidelines for
        Cocoa)](<https://developer.apple.com/library/mac/documentation/Cocoa/Conceptual/CodingGuidelines/CodingGuidelines.html>)

    -   Optional: Client Javascript ([Coding guidelines for
        npm](<https://docs.npmjs.com/misc/coding-style>))

3.  Samples are important for illustrating how to actually call into the API.
    Samples should be as visual and reusable as possible.

    - Do:

        -   Create a UI sample when possible.

        -   Make your sample user friendly. Expect that developers will want to try
        different mainline scenarios and key APIs.

        -   Create code that's easy for other developers to copy/paste into their
        own solutions

    - Consider:

        -   Adding UI to allow devs to quickly copy/paste subscription keys, instead
        of updating them in the code or using a config file. The
        FaceAPI-WPF-Samples.sln provides an example.

    - Don't:

        -   Leave your subscription key in the source of samples. You do not want your key to be abused by others.

Happy coding!
