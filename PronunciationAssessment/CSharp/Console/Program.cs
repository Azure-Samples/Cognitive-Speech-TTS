//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License:
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

namespace PronunciationAssessment
{
    using System;
    using System.Globalization;

    class Program
    {
        static void Main(string[] args)
        {
            var subscriptionKey = "{SubscriptionKey}"; // replace this with your subscription key
            var region = "{Region}"; // replace this with the region corresponding to your subscription key, e.g. westus, eastasia

            var referenceText = "Welcome to use Microsoft Cognitive Services pronunciation assessment API!";

            var pronAssessment = new PronunciationAssessment(CultureInfo.GetCultureInfo("en-US"), region, subscriptionKey);
            var recorder = new Recorder(pronAssessment);

            Console.WriteLine("Please press any key to start recording, and then read along below text after recording started:");
            Console.WriteLine("\r\n  " + referenceText + "\r\n");
            Console.ReadKey(true);
            recorder.Start(referenceText);
            Console.WriteLine("Recording started. Please read along above text. And after you finish reading it, press any key to stop recording.");
            Console.ReadKey(true);
            Console.WriteLine("Recording stopped.");
            Console.WriteLine("Here is the assessment result on your pronunciation:");
            recorder.Stop();
            Console.ReadKey(true);
        }
    }
}
