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
using System.IO;
using System.Media;
using System.Threading;
using CognitiveServicesTTS;

namespace TTSSample
{
    internal class Program
    {
        /// <summary>
        /// This method is called once the audio returned from the service.
        /// It will then attempt to play that audio file.
        /// Note that the playback will fail if the output audio format is not pcm encoded.
        /// </summary>
        /// <param name="sender">The source of the event.</param>
        /// <param name="args">The <see cref="GenericEventArgs{Stream}"/> instance containing the event data.</param>
        private static void PlayAudio(object sender, GenericEventArgs<Stream> args)
        {
            Console.WriteLine(args.EventData);

            // For SoundPlayer to be able to play the wav file, it has to be encoded in PCM.
            // Use output audio format AudioOutputFormat.Riff16Khz16BitMonoPcm to do that.
            SoundPlayer player = new SoundPlayer(args.EventData);
            player.PlaySync();
            args.EventData.Dispose();
        }

        /// <summary>
        /// Handler an error when a TTS request failed.
        /// </summary>
        /// <param name="sender">The sender.</param>
        /// <param name="e">The <see cref="GenericEventArgs{Exception}"/> instance containing the event data.</param>
        private static void ErrorHandler(object sender, GenericEventArgs<Exception> e)
        {
            Console.WriteLine("Unable to complete the TTS request: [{0}]", e.ToString());
        }

        private static void Main(string[] args)
        {
            bool useNeuralVoice = true;
            if (!useNeuralVoice)
            {

                // Note: new unified SpeechService API synthesis endpoint is per region, choose the region close to your service to minimize the latency
                // the request URI region must match with the token URI region . 
                string tokenUri = "https://westus.api.cognitive.microsoft.com/sts/v1.0/issueToken";
                string endpointUri = "https://westus.tts.speech.microsoft.com/cognitiveservices/v1";
                string key = "input your key here";

                // To use a standard voice, make sure you set the correct locale and voice name as below
                // see full list here https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support#neural-voices-preview
                // VoiceName = "Microsoft Server Speech Text to Speech Voice (en-US, Jessa24KRUS)",
                // VoiceName = "Microsoft Server Speech Text to Speech Voice (en-US, Guy24KRUS)",
                // VoiceName = "Microsoft Server Speech Text to Speech Voice (en-US, JessaRUS)",
                SpeakWithVoice(tokenUri, endpointUri, key,
                                "en-US",
                                "Microsoft Server Speech Text to Speech Voice (en-US, Jessa24KRUS)",
                                AudioOutputFormat.Riff24Khz16BitMonoPcm);
            }
            else
            {
                // To use neural voice, select a right DC, set the right proper locale and voice name
                // Neural voice is currently avaliable in eastUS, southEastAsia, westEurope
                // see https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support#neural-voices-preview
                string tokenUri = "https://eastus.api.cognitive.microsoft.com/sts/v1.0/issueToken";
                string endpointUri = "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1";
                string key = "input your key here";
                SpeakWithVoice(tokenUri, endpointUri, key,
                                "en-US",
                                "Microsoft Server Speech Text to Speech Voice (en-US, JessaNeural)",
                                AudioOutputFormat.Riff16Khz16BitMonoPcm);

                //string tokenUri = "https://southeastasia.api.cognitive.microsoft.com/sts/v1.0/issueToken";
                //string endpointUri = "https://southeastasia.tts.speech.microsoft.com/cognitiveservices/v1";
                //string key = "input your key here";
                //SpeakWithVoice(tokenUri, endpointUri, key,
                //                "zh-CN",
                //                "Microsoft Server Speech Text to Speech Voice (zh-CN, XiaoxiaoNeural)",
                //                AudioOutputFormat.Riff16Khz16BitMonoPcm,
                //                "你好， 我是晓晓!");
            }
        }

        private static void SpeakWithVoice(string tokeUri, string endpointUri, string key, string locale, string voiceName, AudioOutputFormat format, string text = "Hello, how are you doing?")
        {
            string accessToken;

            // The way to get api key:
            // Unified Speech Service key
            // Free: https://azure.microsoft.com/en-us/try/cognitive-services/?api=speech-services
            // Paid: https://go.microsoft.com/fwlink/?LinkId=872236&clcid=0x409 

            Console.WriteLine("Starting Authtentication");
            Authentication auth = new Authentication(tokeUri, key);

            try
            {
                accessToken = auth.GetAccessToken();
                Console.WriteLine("Token: {0}\n", accessToken);
            }
            catch (Exception ex)
            {
                Console.WriteLine("Failed authentication.");
                Console.WriteLine(ex.ToString());
                Console.WriteLine(ex.Message);
                return;
            }

            Console.WriteLine("Starting TTSSample request code execution.");

            string requestUri = endpointUri;
            var cortana = new Synthesize();

            cortana.OnAudioAvailable += PlayAudio;
            cortana.OnError += ErrorHandler;

            // Reuse Synthesize object to minimize latency
            cortana.Speak(CancellationToken.None, new Synthesize.InputOptions()
            {
                RequestUri = new Uri(requestUri),
                // Text to be spoken.
                Text = text,
                VoiceType = Gender.Female,

                // Refer to the documentation for complete list of supported locales.
                // Please note locale must be matched with voice locales. 
                Locale = locale,
                VoiceName = voiceName,
                OutputFormat = format,

                // For onpremise container, auth token is optional 
                AuthorizationToken = "Bearer " + accessToken,
            }).Wait();
        }
    }
}
