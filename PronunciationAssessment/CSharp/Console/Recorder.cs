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
    using NAudio.Wave;
    using Newtonsoft.Json;
    using System;

    public enum RecordingState
    {
        Recording,
        Stopping,
        Stopped
    }

    /// <summary>
    /// The recorder class
    /// </summary>
    public class Recorder
    {
        WaveInEvent waveIn = new WaveInEvent();

        RecordingState state = RecordingState.Stopped;

        PronunciationAssessment pronunciationAssessment;

        const int MaxRecordingSeconds = 30;

        int totalBytesRecorded = 0;

        public Recorder(PronunciationAssessment pronunciationAssessment, int sampleRate = 16000)
        {
            this.pronunciationAssessment = pronunciationAssessment;
            waveIn.WaveFormat = new WaveFormat(sampleRate, 1);
            waveIn.DataAvailable += WaveIn_DataAvailable;
            waveIn.RecordingStopped += WaveIn_Stopped;
        }

        public void Start(string referenceText)
        {
            pronunciationAssessment.Start(referenceText, waveIn.WaveFormat.SampleRate);
            pronunciationAssessment.WriteWavHeader(sampleRate: waveIn.WaveFormat.SampleRate);

            waveIn.StartRecording();
            state = RecordingState.Recording;
        }

        public void Stop()
        {
            waveIn.StopRecording();
            state = RecordingState.Stopping;
        }
        private void WaveIn_DataAvailable(object sender, WaveInEventArgs e)
        {
            totalBytesRecorded += e.BytesRecorded;
            pronunciationAssessment.WriteAudioChunk(e.Buffer, 0, e.BytesRecorded);

            // auto stop when recorded audio is beyond the limitation.
            if (totalBytesRecorded > waveIn.WaveFormat.AverageBytesPerSecond * MaxRecordingSeconds && state == RecordingState.Recording)
            {
                waveIn.StopRecording();
                state = RecordingState.Stopping;
                Console.WriteLine($"Recorded audio length exceeded the {MaxRecordingSeconds} seconds limit. No longer send data to server.");
                Console.WriteLine($"Press any key to stop and get the assessment result.");
            }
        }

        private void WaveIn_Stopped(object sender, StoppedEventArgs e)
        {
            state = RecordingState.Stopped;

            var finishRecordingTime = DateTime.Now;
            var rawResult = pronunciationAssessment.GetResult();
            var receiveResultTime = DateTime.Now;
            var latency = receiveResultTime.Subtract(finishRecordingTime).TotalMilliseconds;

            var resultJson = Newtonsoft.Json.Linq.JObject.Parse(rawResult);
            var formattedResult = JsonConvert.SerializeObject(resultJson, Formatting.Indented, new JsonSerializerSettings());

            Console.WriteLine(formattedResult);
            Console.WriteLine($"Total audio lenght = {(double)totalBytesRecorded / waveIn.WaveFormat.AverageBytesPerSecond} seconds.");
            Console.WriteLine($"Latency = {latency} ms.");

            totalBytesRecorded = 0;
        }
    }
}
