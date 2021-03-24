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

namespace QueuingMachine
{
    partial class QueuingMachine
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.Airport = new System.Windows.Forms.TabPage();
            this.GateNoComboBox = new System.Windows.Forms.ComboBox();
            this.AirPlaneComboBox = new System.Windows.Forms.ComboBox();
            this.GateNo = new System.Windows.Forms.Label();
            this.AirPlaneLabel = new System.Windows.Forms.Label();
            this.Bank = new System.Windows.Forms.TabPage();
            this.WindowNoComboBox = new System.Windows.Forms.ComboBox();
            this.CustomNoComboBox = new System.Windows.Forms.ComboBox();
            this.WindowNo = new System.Windows.Forms.Label();
            this.CustomNo = new System.Windows.Forms.Label();
            this.tabControl1 = new System.Windows.Forms.TabControl();
            this.SynthesizeLabel = new System.Windows.Forms.Label();
            this.SynthesizeRichTextBox = new System.Windows.Forms.RichTextBox();
            this.SynthesizeAndPlay = new System.Windows.Forms.Button();
            this.VoiceNameComboBox = new System.Windows.Forms.ComboBox();
            this.VoiceNameLabel = new System.Windows.Forms.Label();
            this.ProsodyRateLabel = new System.Windows.Forms.Label();
            this.ProsodyRateTrackBar = new System.Windows.Forms.TrackBar();
            this.Airport.SuspendLayout();
            this.Bank.SuspendLayout();
            this.tabControl1.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.ProsodyRateTrackBar)).BeginInit();
            this.SuspendLayout();
            // 
            // Airport
            // 
            this.Airport.Controls.Add(this.GateNoComboBox);
            this.Airport.Controls.Add(this.AirPlaneComboBox);
            this.Airport.Controls.Add(this.GateNo);
            this.Airport.Controls.Add(this.AirPlaneLabel);
            this.Airport.Location = new System.Drawing.Point(4, 22);
            this.Airport.Name = "Airport";
            this.Airport.Size = new System.Drawing.Size(370, 137);
            this.Airport.TabIndex = 2;
            this.Airport.Text = "机场";
            this.Airport.UseVisualStyleBackColor = true;
            // 
            // GateNoComboBox
            // 
            this.GateNoComboBox.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.GateNoComboBox.FormattingEnabled = true;
            this.GateNoComboBox.Items.AddRange(new object[] {
            "A29",
            "C10"});
            this.GateNoComboBox.Location = new System.Drawing.Point(70, 62);
            this.GateNoComboBox.Name = "GateNoComboBox";
            this.GateNoComboBox.Size = new System.Drawing.Size(121, 21);
            this.GateNoComboBox.TabIndex = 22;
            this.GateNoComboBox.SelectedIndex = 0;
            // 
            // AirPlaneComboBox
            // 
            this.AirPlaneComboBox.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.AirPlaneComboBox.FormattingEnabled = true;
            this.AirPlaneComboBox.Items.AddRange(new object[] {
            "MU564",
            "KN5988"});
            this.AirPlaneComboBox.Location = new System.Drawing.Point(70, 18);
            this.AirPlaneComboBox.Name = "AirPlaneComboBox";
            this.AirPlaneComboBox.Size = new System.Drawing.Size(121, 21);
            this.AirPlaneComboBox.TabIndex = 21;
            this.AirPlaneComboBox.SelectedIndex = 0;
            // 
            // GateNo
            // 
            this.GateNo.AutoSize = true;
            this.GateNo.Location = new System.Drawing.Point(13, 70);
            this.GateNo.Name = "GateNo";
            this.GateNo.Size = new System.Drawing.Size(46, 13);
            this.GateNo.TabIndex = 20;
            this.GateNo.Text = "登机口:";
            // 
            // AirPlaneLabel
            // 
            this.AirPlaneLabel.AutoSize = true;
            this.AirPlaneLabel.Location = new System.Drawing.Point(13, 21);
            this.AirPlaneLabel.Name = "AirPlaneLabel";
            this.AirPlaneLabel.Size = new System.Drawing.Size(34, 13);
            this.AirPlaneLabel.TabIndex = 19;
            this.AirPlaneLabel.Text = "航班:";
            // 
            // Bank
            // 
            this.Bank.Controls.Add(this.WindowNoComboBox);
            this.Bank.Controls.Add(this.CustomNoComboBox);
            this.Bank.Controls.Add(this.WindowNo);
            this.Bank.Controls.Add(this.CustomNo);
            this.Bank.Location = new System.Drawing.Point(4, 22);
            this.Bank.Name = "Bank";
            this.Bank.Padding = new System.Windows.Forms.Padding(3);
            this.Bank.Size = new System.Drawing.Size(370, 137);
            this.Bank.TabIndex = 0;
            this.Bank.Text = "银行";
            this.Bank.UseVisualStyleBackColor = true;
            // 
            // WindowNoComboBox
            // 
            this.WindowNoComboBox.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.WindowNoComboBox.FormattingEnabled = true;
            this.WindowNoComboBox.Items.AddRange(new object[] {
            "对公1号",
            "个人2号"});
            this.WindowNoComboBox.Location = new System.Drawing.Point(63, 75);
            this.WindowNoComboBox.Name = "WindowNoComboBox";
            this.WindowNoComboBox.Size = new System.Drawing.Size(121, 21);
            this.WindowNoComboBox.TabIndex = 18;
            this.WindowNoComboBox.SelectedIndex = 0;
            // 
            // CustomNoComboBox
            // 
            this.CustomNoComboBox.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.CustomNoComboBox.FormattingEnabled = true;
            this.CustomNoComboBox.Items.AddRange(new object[] {
            "A01",
            "B02"});
            this.CustomNoComboBox.Location = new System.Drawing.Point(63, 31);
            this.CustomNoComboBox.Name = "CustomNoComboBox";
            this.CustomNoComboBox.Size = new System.Drawing.Size(121, 21);
            this.CustomNoComboBox.TabIndex = 17;
            this.CustomNoComboBox.SelectedIndex = 0;
            // 
            // WindowNo
            // 
            this.WindowNo.AutoSize = true;
            this.WindowNo.Location = new System.Drawing.Point(6, 83);
            this.WindowNo.Name = "WindowNo";
            this.WindowNo.Size = new System.Drawing.Size(46, 13);
            this.WindowNo.TabIndex = 2;
            this.WindowNo.Text = "窗口号:";
            // 
            // CustomNo
            // 
            this.CustomNo.AutoSize = true;
            this.CustomNo.Location = new System.Drawing.Point(6, 34);
            this.CustomNo.Name = "CustomNo";
            this.CustomNo.Size = new System.Drawing.Size(46, 13);
            this.CustomNo.TabIndex = 1;
            this.CustomNo.Text = "顾客号:";
            // 
            // tabControl1
            // 
            this.tabControl1.Controls.Add(this.Bank);
            this.tabControl1.Controls.Add(this.Airport);
            this.tabControl1.Location = new System.Drawing.Point(28, 22);
            this.tabControl1.Name = "tabControl1";
            this.tabControl1.SelectedIndex = 0;
            this.tabControl1.Size = new System.Drawing.Size(378, 163);
            this.tabControl1.TabIndex = 0;
            // 
            // SynthesizeLabel
            // 
            this.SynthesizeLabel.AutoSize = true;
            this.SynthesizeLabel.Location = new System.Drawing.Point(29, 242);
            this.SynthesizeLabel.Name = "SynthesizeLabel";
            this.SynthesizeLabel.Size = new System.Drawing.Size(58, 13);
            this.SynthesizeLabel.TabIndex = 1;
            this.SynthesizeLabel.Text = "合成文字:";
            // 
            // SynthesizeRichTextBox
            // 
            this.SynthesizeRichTextBox.Location = new System.Drawing.Point(90, 203);
            this.SynthesizeRichTextBox.Name = "SynthesizeRichTextBox";
            this.SynthesizeRichTextBox.Size = new System.Drawing.Size(312, 96);
            this.SynthesizeRichTextBox.TabIndex = 2;
            this.SynthesizeRichTextBox.Text = "";
            // 
            // SynthesizeAndPlay
            // 
            this.SynthesizeAndPlay.Location = new System.Drawing.Point(327, 370);
            this.SynthesizeAndPlay.Name = "SynthesizeAndPlay";
            this.SynthesizeAndPlay.Size = new System.Drawing.Size(113, 37);
            this.SynthesizeAndPlay.TabIndex = 3;
            this.SynthesizeAndPlay.Text = "合成并播放";
            this.SynthesizeAndPlay.UseVisualStyleBackColor = true;
            this.SynthesizeAndPlay.Click += new System.EventHandler(this.SynthesizeAndPlayButton_Click);
            // 
            // VoiceNameComboBox
            // 
            this.VoiceNameComboBox.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.VoiceNameComboBox.FormattingEnabled = true;
            this.VoiceNameComboBox.Items.AddRange(new object[] {
            "Microsoft Server Speech Text to Speech Voice (zh-CN, HuihuiRUS)",
            "Microsoft Server Speech Text to Speech Voice (zh-CN, Yaoyao, Apollo)",
            "Microsoft Server Speech Text to Speech Voice (zh-CN, Kangkang, Apollo)"});
            this.VoiceNameComboBox.Location = new System.Drawing.Point(52, 331);
            this.VoiceNameComboBox.Name = "VoiceNameComboBox";
            this.VoiceNameComboBox.Size = new System.Drawing.Size(388, 21);
            this.VoiceNameComboBox.TabIndex = 18;
            this.VoiceNameComboBox.SelectedIndex = 0;
            // 
            // VoiceNameLabel
            // 
            this.VoiceNameLabel.AutoSize = true;
            this.VoiceNameLabel.Location = new System.Drawing.Point(12, 331);
            this.VoiceNameLabel.Name = "VoiceNameLabel";
            this.VoiceNameLabel.Size = new System.Drawing.Size(34, 13);
            this.VoiceNameLabel.TabIndex = 19;
            this.VoiceNameLabel.Text = "语音:";
            // 
            // ProsodyRateLabel
            // 
            this.ProsodyRateLabel.AutoSize = true;
            this.ProsodyRateLabel.Location = new System.Drawing.Point(12, 370);
            this.ProsodyRateLabel.Name = "ProsodyRateLabel";
            this.ProsodyRateLabel.Size = new System.Drawing.Size(34, 13);
            this.ProsodyRateLabel.TabIndex = 22;
            this.ProsodyRateLabel.Text = "语速:";
            // 
            // ProsodyRateTrackBar
            // 
            this.ProsodyRateTrackBar.Location = new System.Drawing.Point(73, 362);
            this.ProsodyRateTrackBar.Maximum = 20;
            this.ProsodyRateTrackBar.Minimum = 1;
            this.ProsodyRateTrackBar.Name = "ProsodyRateTrackBar";
            this.ProsodyRateTrackBar.Size = new System.Drawing.Size(129, 45);
            this.ProsodyRateTrackBar.TabIndex = 21;
            this.ProsodyRateTrackBar.Value = 10;
            this.ProsodyRateTrackBar.ValueChanged += new System.EventHandler(this.ProsodyRateTrackBar_ValueChanged);
            // 
            // QueuingMachine
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(469, 423);
            this.Controls.Add(this.ProsodyRateLabel);
            this.Controls.Add(this.ProsodyRateTrackBar);
            this.Controls.Add(this.VoiceNameLabel);
            this.Controls.Add(this.VoiceNameComboBox);
            this.Controls.Add(this.SynthesizeAndPlay);
            this.Controls.Add(this.SynthesizeRichTextBox);
            this.Controls.Add(this.SynthesizeLabel);
            this.Controls.Add(this.tabControl1);
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedSingle;
            this.Name = "QueuingMachine";
            this.Text = "叫号机";
            this.Airport.ResumeLayout(false);
            this.Airport.PerformLayout();
            this.Bank.ResumeLayout(false);
            this.Bank.PerformLayout();
            this.tabControl1.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)(this.ProsodyRateTrackBar)).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.TabPage Airport;
        private System.Windows.Forms.TabPage Bank;
        private System.Windows.Forms.Label WindowNo;
        private System.Windows.Forms.Label CustomNo;
        private System.Windows.Forms.TabControl tabControl1;
        private System.Windows.Forms.ComboBox GateNoComboBox;
        private System.Windows.Forms.ComboBox AirPlaneComboBox;
        private System.Windows.Forms.Label GateNo;
        private System.Windows.Forms.Label AirPlaneLabel;
        private System.Windows.Forms.ComboBox WindowNoComboBox;
        private System.Windows.Forms.ComboBox CustomNoComboBox;
        private System.Windows.Forms.Label SynthesizeLabel;
        private System.Windows.Forms.RichTextBox SynthesizeRichTextBox;
        private System.Windows.Forms.Button SynthesizeAndPlay;
        private System.Windows.Forms.ComboBox VoiceNameComboBox;
        private System.Windows.Forms.Label VoiceNameLabel;
        private System.Windows.Forms.Label ProsodyRateLabel;
        private System.Windows.Forms.TrackBar ProsodyRateTrackBar;
    }
}

