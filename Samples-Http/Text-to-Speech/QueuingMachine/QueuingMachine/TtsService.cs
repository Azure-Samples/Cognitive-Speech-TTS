//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/Cognitive-Speech-TTS
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

using System;
using System.Text;
using System.Net;
using System.IO;

namespace QueuingMachine
{
    public enum AudioFormat
    {
        /// <summary>
        /// pcm wav
        /// </summary>
        Wave,
        
        /// <summary>
        /// tts silk
        /// </summary>
        Silk,

        /// <summary>
        /// mp3 format
        /// </summary>
        Mp3
    };

    public class TtsService
    {

        // Note: The way to get api key:
        // Free: https://www.microsoft.com/cognitive-services/en-us/subscriptions?productId=/products/Bing.Speech.Preview
        // Paid: https://portal.azure.com/#create/Microsoft.CognitiveServices/apitype/Bing.Speech/pricingtier/S0
        private static Authentication auth = new Authentication("Your api key goes here");

        public static byte[] TtsAudioOutput(string lang, string voiceName, AudioFormat format, string text, float prosodyRate = 1.0f)
        {
            byte[] output = null;

            string accessToken = auth.GetAccessToken();
            string uri = "https://speech.platform.bing.com/synthesize";

            HttpWebRequest webRequest = (HttpWebRequest)WebRequest.Create(uri);
            string ImpressionGUID = Guid.NewGuid().ToString();

            webRequest.ContentType = "application/ssml+xml";
            webRequest.UserAgent = "QueuingMachine";
            string formatName = (format == AudioFormat.Silk) ? "ssml-16khz-16bit-mono-silk" : "riff-16khz-16bit-mono-pcm";
            webRequest.Headers.Add("X-MICROSOFT-OutputFormat", formatName);
            webRequest.Headers.Add("X-Search-AppId", "07D3234E49CE426DAA29772419F436CA");
            webRequest.Headers.Add("X-Search-ClientID", "1ECFAE91408841A480F00935DC390960");

            webRequest.Headers.Add("Authorization", "Bearer " + accessToken);
            webRequest.Method = "POST";

            string bodyTemplate = "<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xmlns:mstts=\"http://www.w3.org/2001/mstts\" xmlns:emo=\"http://www.w3.org/2009/10/emotionml\" xml:lang=\"{0}\">{1}<emo:emotion><emo:category name=\"CALM\" value=\"1.0\"/><prosody rate=\"{2:F1}\">{3}</prosody></emo:emotion></voice></speak>";
            string voiceTag = "<voice name=\"" + voiceName + "\">";
            string deviceLanguage = lang;
            string encodedXml = text.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;").Replace("'", "&apos;");

            if(prosodyRate < 0.1f)
            {
                prosodyRate = 0.1f;
            }else if(prosodyRate > 2.0f)
            {
                prosodyRate = 2.0f;
            }

            string body = string.Format(bodyTemplate, deviceLanguage, voiceTag, prosodyRate, encodedXml);
            byte[] bytes = Encoding.UTF8.GetBytes(body);
            webRequest.ContentLength = bytes.Length;
            using (Stream outputStream = webRequest.GetRequestStream())
            {
                outputStream.Write(bytes, 0, bytes.Length);
            }

            WebResponse webResponse = webRequest.GetResponse();
            using (Stream stream = webResponse.GetResponseStream())
            { 
                using (MemoryStream ms = new MemoryStream())
                {
                    int count = 0;
                    do
                    {
                        byte[] buf = new byte[1024];
                        count = stream.Read(buf, 0, 1024);
                        ms.Write(buf, 0, count);
                    } while (stream.CanRead && count > 0);
                    output = ms.ToArray();
                }
            }
            return output;
        }
    }
}
