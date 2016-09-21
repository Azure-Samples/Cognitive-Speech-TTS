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

using AxWMPLib;
using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace QueuingMachine
{
    public partial class QueuingMachine : Form
    {
        private AxWindowsMediaPlayer mediaPlayer;
        public QueuingMachine()
        {
            InitializeComponent();
            if (mediaPlayer == null)
            {
                mediaPlayer = new AxWindowsMediaPlayer();
                mediaPlayer.CreateControl();
                mediaPlayer.Visible = false;
            }
        }

        private void SynthesizeAndPlayButton_Click(object sender, EventArgs e)
        {
            // generate the synthesis text
            if (tabControl1.SelectedTab == tabControl1.TabPages["Bank"])
             {
                 SynthesizeRichTextBox.Text = "请顾客" + CustomNoComboBox.Text + "到" + WindowNoComboBox.Text + "窗口办理业务";
             }
            else
            {
                SynthesizeRichTextBox.Text = "从北京到上海的航班" + AirPlaneComboBox.Text + "马上就要起飞了, 请还没登机的乘客到登机口" + GateNoComboBox.Text + "办理登机手续";
            }

            mediaPlayer.Ctlcontrols.stop();
            mediaPlayer.close();
            SynthesizePlay();
            
        }

        /// <summary>
        /// Create the media player
        /// </summary>
        private void CreateMediaPlayer()
        {
            if (mediaPlayer == null)
            {
                mediaPlayer = new AxWindowsMediaPlayer();
                mediaPlayer.CreateControl();
                mediaPlayer.Visible = false;
            }
        }


        /// <summary>
        /// Call to Path.GetTempFileName() with exception handling.
        /// </summary>
        /// <returns>Temporary file path.</returns>
        private string GetTempFileName(string extension)
        {
            string filePath = string.Empty;
            try
            {
                filePath = Path.GetTempPath();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Trace.WriteLine(ex.Message);
            }

            return Path.Combine(filePath, "QueuingMachine_Synthesize." + extension);
        }

        private void SynthesizePlay()
        {
            byte[] waveData = null;

            try
            {
                waveData = TtsService.TtsAudioOutput("zh-CN", VoiceNameComboBox.Text, AudioFormat.Wave, SynthesizeRichTextBox.Text, (float)ProsodyRateTrackBar.Value / 10);
            }
            catch(Exception e)
            {
                MessageBox.Show(e.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            Task task = Task.Factory.StartNew(() => PlayWave(waveData));
        }

        private void PlayWave(byte[] waveData)
        {
            string waveLocalPath = GetTempFileName("wav");
            
            using (FileStream fs = new FileStream(waveLocalPath, FileMode.Create, FileAccess.Write))
            {
                MemoryStream stream = new MemoryStream(waveData);
                stream.CopyTo(fs);
            }

            mediaPlayer.URL = waveLocalPath;
            mediaPlayer.Ctlcontrols.play();
            mediaPlayer.settings.rate = 1.0;
            mediaPlayer.settings.volume = 50;
        }

        private void ProsodyRateTrackBar_ValueChanged(object sender, EventArgs e)
        {
            ProsodyRateLabel.Text = "语速(" + (ProsodyRateTrackBar.Value / 10.0) + "):";
        }
    }
}
