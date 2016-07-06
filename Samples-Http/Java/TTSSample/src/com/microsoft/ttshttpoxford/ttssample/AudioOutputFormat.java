//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/ProjectOxford-ClientSDK
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

package com.microsoft.ttshttpoxford.ttssample;

/// <summary>
/// Voice output formats.
/// </summary>
public class AudioOutputFormat {

        /// <summary>
        /// raw-8khz-8bit-mono-mulaw request output audio format type.
        /// </summary>
        public static final String Raw8Khz8BitMonoMULaw = "raw-8khz-8bit-mono-mulaw";
        /// <summary>
        /// raw-16khz-16bit-mono-pcm request output audio format type.
        /// </summary>
        public static final String Raw16Khz16BitMonoPcm = "raw-16khz-16bit-mono-pcm";
        /// <summary>
        /// riff-8khz-8bit-mono-mulaw request output audio format type.
        /// </summary>
        public static final String Riff8Khz8BitMonoMULaw = "riff-16khz-16bit-mono-pcm";
        /// <summary>
        /// riff-16khz-16bit-mono-pcm request output audio format type.
        /// </summary>
        public static final String Riff16Khz16BitMonoPcm = "riff-16khz-16bit-mono-pcm";
        /// <summary>
        /// ssml-16khz-16bit-mono-silk request output audio format type.
        /// It is a SSML with audio segment, with audio compressed by SILK codec
        /// </summary>
        public static final String Ssml16Khz16BitMonoSilk = "ssml-16khz-16bit-mono-silk";
        /// <summary>
        /// ssml-16khz-16bit-mono-tts request output audio format type.
        /// It is a SSML with audio segment, and it needs tts engine to play out
        /// </summary>
        public static final String Ssml16Khz16BitMonoTts = "ssml-16khz-16bit-mono-tts";
}
