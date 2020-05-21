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
    using System.IO;
    using System.Net;
    using System.Text;

    /// <summary>
    /// Pronunciation assessment with streaming
    /// </summary>
    public class PronunciationAssessment
    {
        string locale;
        string region;
        string subscriptionKey;

        HttpWebRequest request;
        Stream requestStream;

        public PronunciationAssessment(CultureInfo locale, string region, string subscriptionKey)
        {
            this.locale = locale.Name.ToLower();
            this.region = region;
            this.subscriptionKey = subscriptionKey;
        }

        public int Start(string referenceText, int samplingRate = 16000)
        {
            int ret = 0;
            try
            {
                var pronAssessmentParamsJson = $"{{\"ReferenceText\":\"{referenceText}\",\"GradingSystem\":\"HundredMark\",\"Granularity\":\"Phoneme\",\"Dimension\":\"Comprehensive\"}}";
                var pronAssessmentParamsBytes = Encoding.UTF8.GetBytes(pronAssessmentParamsJson);
                var pronAssessmentParams = Convert.ToBase64String(pronAssessmentParamsBytes);
                string url = $"https://{this.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={this.locale}";
                request = (HttpWebRequest)HttpWebRequest.Create(url);

                request.SendChunked = true;
                request.Accept = @"application/json;text/xml";
                request.Method = "POST";
                request.ProtocolVersion = HttpVersion.Version11;
                request.ContentType = $"audio/wav; codecs=audio/pcm; samplerate={samplingRate}";
                request.Headers["Ocp-Apim-Subscription-Key"] = this.subscriptionKey;
                request.Headers["Pronunciation-Assessment"] = pronAssessmentParams;
                request.AllowWriteStreamBuffering = false;

                requestStream = request.GetRequestStream();
            }
            catch (Exception)
            {
                ret = -1;
            }

            return ret;

        }

        public void WriteWavHeader(bool isFloatingPoint = false, ushort channelCount = 1, ushort bitDepth = 16, int sampleRate = 16000, int totalSampleCount = 0, int extraChunkSize = 0)
        {
            var stream = this.requestStream;

            // RIFF header.
            // Chunk ID.
            stream.Write(Encoding.ASCII.GetBytes("RIFF"), 0, 4);

            // Chunk size.
            stream.Write(BitConverter.GetBytes(((bitDepth / 8) * totalSampleCount) + 36 + extraChunkSize), 0, 4);

            // Format.
            stream.Write(Encoding.ASCII.GetBytes("WAVE"), 0, 4);

            // Sub-chunk 1.
            // Sub-chunk 1 ID.
            stream.Write(Encoding.ASCII.GetBytes("fmt "), 0, 4);

            // Sub-chunk 1 size.
            stream.Write(BitConverter.GetBytes(16), 0, 4);

            // Audio format (floating point (3) or PCM (1)). Any other format indicates compression.
            stream.Write(BitConverter.GetBytes((ushort)(isFloatingPoint ? 3 : 1)), 0, 2);

            // Channels.
            stream.Write(BitConverter.GetBytes(channelCount), 0, 2);

            // Sample rate.
            stream.Write(BitConverter.GetBytes(sampleRate), 0, 4);

            // Bytes rate.
            stream.Write(BitConverter.GetBytes(sampleRate * channelCount * (bitDepth / 8)), 0, 4);

            // Block align.
            stream.Write(BitConverter.GetBytes((ushort)channelCount * (bitDepth / 8)), 0, 2);

            // Bits per sample.
            stream.Write(BitConverter.GetBytes(bitDepth), 0, 2);

            // Sub-chunk 2.
            // Sub-chunk 2 ID.
            stream.Write(Encoding.ASCII.GetBytes("data"), 0, 4);

            // Sub-chunk 2 size.
            stream.Write(BitConverter.GetBytes((bitDepth / 8) * totalSampleCount), 0, 4);
        }

        public int WriteAudioChunk(byte[] buffer, int offset, int length)
        {
            int ret = 0;
            try
            {
                requestStream.Write(buffer, offset, length);
                requestStream.Flush();
            }
            catch (Exception)
            {
                ret = -1;
            }

            return ret;
        }

        public string GetResult()
        {
            var result = string.Empty;
            var response = request.GetResponse();
            using (var responseStream = response.GetResponseStream())
            using (var streamReader = new StreamReader(responseStream))
            {
                result = streamReader.ReadToEnd(); // The result in JSON format, with pronunciation score
            }

            return result;
        }
    }
}
