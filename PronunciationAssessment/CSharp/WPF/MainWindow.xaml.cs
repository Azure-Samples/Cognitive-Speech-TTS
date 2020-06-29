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

namespace SpeechScore
{
    using MahApps.Metro.Controls;
    using Microsoft.CognitiveServices.Speech;
    using Microsoft.Win32;
    using NAudio.Wave;
    using Newtonsoft.Json;
    using System;
    using System.Collections.Generic;
    using System.ComponentModel;
    using System.IO;
    using System.Net;
    using System.Text;
    using System.Windows;
    using System.Windows.Controls;
    using System.Windows.Documents;
    using System.Windows.Media;

    /// <summary>
    /// MainWindow.xaml interactive logic
    /// </summary>
    public partial class MainWindow : MetroWindow
    {
        public WaveIn waveSource = null;
        private HttpWebRequest request;
        private Stream requestStream = null;
        private TextPointer position = null;
        private string language = "en-us";

        public MainWindow()
        {
            InitializeComponent();
        }

        /// <summary>
        /// Start Recording Callback Functions
        /// </summary>
        /// <param name="sender"></param>
        /// <param name="e"></param>
        private void waveSource_DataAvailable(object sender, WaveInEventArgs e)
        {
            if (requestStream != null)
            {
                requestStream.Write(e.Buffer, 0, e.BytesRecorded);
                requestStream.Flush();
            }
        }

        /// <summary>
        /// Recording End Callback Function
        /// </summary>
        /// <param name="sender"></param>
        /// <param name="e"></param>
        private void waveSource_RecordingStopped(object sender, StoppedEventArgs e)
        {
            if (waveSource != null)
            {
                waveSource.Dispose();
                waveSource = null;
            }
        }

        /// <summary>
        /// Highlighting
        /// </summary>
        /// <param name="color">Set Color, color.FromRgb(rgb)</param>
        /// <param name="richBox">richBox</param>
        /// <param name="keyword">Text that needs to be highlighted</param>
        /// <param name="score">The score of the word</param>
        public void ChangeColor(Color color, RichTextBox richBox, string keyword, float score)
        {
            // Set the text pointer to the initial position of the Document.
            if (position == null)
            {
                position = richBox.Document.ContentStart;
            }

            while (position != null)
            {
                //Search forward, need content for Text
                if (position.GetPointerContext(LogicalDirection.Forward) == TextPointerContext.Text)
                {
                    // Take out Run's Text
                    string text = position.GetTextInRun(LogicalDirection.Forward).ToLower();

                    // may contain more than one keyword, do an iterative search
                    int index = text.IndexOf(keyword, 0);
                    if (index != -1)
                    {
                        TextPointer start = position.GetPositionAtOffset(index);
                        TextPointer end = start.GetPositionAtOffset(keyword.Length);
                        TextRange range = richBox.Selection;
                        range.Select(start, end);

                        // high brightness
                        range.ApplyPropertyValue(TextElement.ForegroundProperty, new SolidColorBrush(color));
                        range.ApplyPropertyValue(TextElement.FontWeightProperty, FontWeights.Bold);

                        Run run = new Run(score + "", end);
                        var scoreRange = new TextRange(end,end.GetPositionAtOffset(5));
                        scoreRange.ApplyPropertyValue(TextElement.ForegroundProperty, new SolidColorBrush(color));
                        scoreRange.ApplyPropertyValue(Run.BaselineAlignmentProperty, BaselineAlignment.Superscript); //superscript

                        // Move the pointer to the end of the highlighted text as the start of the next search once the keyword is found
                        position = end.GetNextContextPosition(LogicalDirection.Forward);
                        break;
                    }

                }

                //Move the text pointer forward  
                position = position.GetNextContextPosition(LogicalDirection.Forward);
            }
        }

        private string StringFromRichTextBox(RichTextBox rtb)
        {
            var textRange = new TextRange(rtb.Document.ContentStart, rtb.Document.ContentEnd);
            // The Text property on a TextRange object returns a string
            // representing the plain text content of the TextRange.
            return textRange.Text;
        }

        private void Button_Start_Click(object sender, RoutedEventArgs e)
        {
            var referenceText =  StringFromRichTextBox(ReferenceText);
            position = null;
            if (string.IsNullOrWhiteSpace(referenceText))
            {
                MessageBox.Show("Reference text cannot be empty！");
                return;
            }

            ConnectToPronAssessmentService(referenceText);
            WriteWavHeader();

            Run r = new Run(referenceText);
            Paragraph para = new Paragraph();
            para.Inlines.Add(r);
            ReferenceText.Document.Blocks.Clear();
            ReferenceText.Document.Blocks.Add(para);

            position = null;
            StartBut.Visibility = Visibility.Collapsed;
            StopBut.Visibility = Visibility.Visible;
            waveSource = new WaveIn();
            waveSource.WaveFormat = new WaveFormat(16000, 16, 1); // 16bit, 16KHz, Mono

            waveSource.DataAvailable += new EventHandler<WaveInEventArgs>(waveSource_DataAvailable);
            waveSource.RecordingStopped += new EventHandler<StoppedEventArgs>(waveSource_RecordingStopped);

            waveSource.StartRecording();
           
            progressRing.IsActive = true;
        }

        private void Button_Stop_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                waveSource.StopRecording();
                // Close Wave (not needed under synchronous situation)
                if (waveSource != null)
                {
                    waveSource.Dispose();
                    waveSource = null;
                }

                var response = request.GetResponse();
                using (var responseStream = response.GetResponseStream())
                using (var streamReader = new StreamReader(responseStream))
                {
                    var responseJsonText = streamReader.ReadToEnd(); // The result in JSON format, with pronunciation score 
                    ScoreResult result = JsonConvert.DeserializeObject<ScoreResult>(responseJsonText);

                    if (null != result && "Success" == result.RecognitionStatus)
                    {
                        NBestItem nBestItem = result.NBest[0];
                        var pronScore = JsonConvert.SerializeObject(nBestItem);

                        PronScoreWebBrowser.InvokeScript("generatePronScoreTable", pronScore);
                        PronScoreWebBrowser.InvokeScript("generatePhoneScoreTable", pronScore);
                        PronScoreWebBrowser.Visibility = Visibility.Visible;
                        List<WordsItem> witems = result.NBest[0].Words;
                        for (int i = 0; i < witems.Count; i++)
                        {
                            WordsItem w = witems[i];
                            if (w.AccuracyScore <= 60.0)
                            {
                                ChangeColor(Colors.Red, ReferenceText, w.Word.ToLower(), w.AccuracyScore);
                            }
                            else if (w.AccuracyScore <= 70.0)
                            {
                                ChangeColor(Colors.Orange, ReferenceText, w.Word.ToLower(), w.AccuracyScore);
                            }
                            else
                            {
                                ChangeColor(Colors.Green, ReferenceText, w.Word.ToLower(), w.AccuracyScore);
                            }
                        }
                    }
                    else
                    {
                        if (null != result)
                        {
                            MessageBox.Show($"Recognition status: {result.RecognitionStatus}");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message);
            }
            finally
            {
                progressRing.IsActive = false;
                StartBut.Visibility = Visibility.Visible;
                StopBut.Visibility = Visibility.Collapsed;
            }
        }

        private void ClearBut_Click(object sender, RoutedEventArgs e)
        {
            ReferenceText.Document.Blocks.Clear();
        }

        private async void TTSBut_Click(object sender, RoutedEventArgs e)
        {
            var referenceText = StringFromRichTextBox(ReferenceText);
            if (string.IsNullOrWhiteSpace(referenceText))
            {
                MessageBox.Show("Reference text shouldn't be empty.");
                return;
            }

            if (string.IsNullOrWhiteSpace(this.SubscriptionKey.Text))
            {
                MessageBox.Show($"Please provide a valid subscription key for {this.Region.Text} region.");
                return;
            }

            var config = SpeechConfig.FromSubscription(this.SubscriptionKey.Text, this.Region.Text);

            using (var synthesizer = new SpeechSynthesizer(config))
            {
                using (var result = await synthesizer.SpeakTextAsync(referenceText))
                {
                    if (result.Reason == ResultReason.Canceled)
                    {
                        var cancellation = SpeechSynthesisCancellationDetails.FromResult(result);
                        if (cancellation.Reason == CancellationReason.Error)
                        {
                           MessageBox.Show($"CANCELED: ErrorDetails=[{cancellation.ErrorDetails}]");
                        }
                    }
                }
            }
        }

        /// <summary>  
        /// Modify registry information to be compatible with current programs  
        ///   
        /// </summary>  
        static void SetWebBrowserFeatures(int ieVersion)
        {
            // don't change the registry if running in-proc inside Visual Studio  
            if (LicenseManager.UsageMode != LicenseUsageMode.Runtime)
            {
                return;
            }

            // Acquisition procedures and names 
            var appName = System.IO.Path.GetFileName(System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName);

            // Get the value of the browser's schema
            var ieMode = GeoEmulationMode(ieVersion);

            // Set what mode (ieMode) the browser runs on the app (appName) 
            var featureControlRegKey = @"HKEY_CURRENT_USER\Software\Microsoft\Internet Explorer\Main\FeatureControl\";
            Registry.SetValue(featureControlRegKey + "FEATURE_BROWSER_EMULATION", appName, ieMode, RegistryValueKind.DWord);

            // Enable the features which are "On" for the full Internet Explorer browser  
            Registry.SetValue(featureControlRegKey + "FEATURE_ENABLE_CLIPCHILDREN_OPTIMIZATION", appName, 1, RegistryValueKind.DWord);
        }

        /// <summary>  
        /// Get the value of the browser mode by version 
        /// </summary>  
        /// <param name="browserVersion"></param>  
        /// <returns></returns>  
        static UInt32 GeoEmulationMode(int browserVersion)
        {
            UInt32 mode = 11000; // Internet Explorer 11. Webpages containing standards-based !DOCTYPE directives are displayed in IE11 Standards mode.   
            switch (browserVersion)
            {
                case 7:
                    mode = 7000; // Webpages containing standards-based !DOCTYPE directives are displayed in IE7 Standards mode.   
                    break;
                case 8:
                    mode = 8000; // Webpages containing standards-based !DOCTYPE directives are displayed in IE8 mode.   
                    break;
                case 9:
                    mode = 9000; // Internet Explorer 9. Webpages containing standards-based !DOCTYPE directives are displayed in IE9 mode.                      
                    break;
                case 10:
                    mode = 10000; // Internet Explorer 10.  
                    break;
                case 11:
                    mode = 11000; // Internet Explorer 11  
                    break;
            }

            return mode;
        }

        private void MetroWindow_Loaded(object sender, RoutedEventArgs e)
        {
            try
            {
                SetWebBrowserFeatures(10);
                PronScoreWebBrowser.Navigate(new Uri(System.IO.Path.Combine(System.Windows.Forms.Application.StartupPath, @"pronscore.html")));
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message);
            }
        }

        private void ConnectToPronAssessmentService(string referenceText)
        {
            var pronScoreParamsJson = $"{{\"ReferenceText\":\"{referenceText}\",\"GradingSystem\":\"HundredMark\",\"Dimension\":\"Comprehensive\",\"EnableMiscue\":\"True\"}}";
            var pronScoreParamsBytes = Encoding.UTF8.GetBytes(pronScoreParamsJson);
            var pronScoreParams = Convert.ToBase64String(pronScoreParamsBytes);

            request = (HttpWebRequest)HttpWebRequest.Create($"https://{this.Region.Text}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={language}");
            request.SendChunked = true;
            request.Accept = @"application/json;text/xml";
            request.Method = "POST";
            request.ProtocolVersion = HttpVersion.Version11;
            request.ContentType = @"audio/wav; codecs=audio/pcm; samplerate=16000";
            request.Headers["Ocp-Apim-Subscription-Key"] = this.SubscriptionKey.Text;
            request.Headers["Pronunciation-Assessment"] = pronScoreParams;
            request.AllowWriteStreamBuffering = false;

            requestStream = request.GetRequestStream();
        }

        private void WriteWavHeader(bool isFloatingPoint = false, ushort channelCount = 1, ushort bitDepth = 16, int sampleRate = 16000, int totalSampleCount = 0, int extraChunkSize = 0)
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
    }
}
