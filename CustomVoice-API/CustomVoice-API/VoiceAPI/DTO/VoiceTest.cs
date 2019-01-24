// <copyright file="VoiceTest.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;

    public sealed class VoiceTest
    {
        public VoiceTest(
            Guid id,
            Uri audioUri,
            Uri textUri,
            string voiceTestKind,
            Model model,
            DateTime created,
            DateTime lastAction,
            string state)
        {
            if (audioUri != null)
            {
                this.AudioUri = audioUri.ToString();
            }

            if (textUri != null)
            {
                this.TextUri = textUri.ToString();
            }

            this.Id = id;
            this.CreatedDateTime = created;
            this.LastActionDateTime = lastAction;
            this.Status = state;
            this.Model = model;
            this.VoiceTestKind = voiceTestKind;
        }

        public Guid Id { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public DateTime LastActionDateTime { get; set; }

        public string Status { get; set; }

        public string AudioUri { get; private set; }

        public string TextUri { get; private set; }

        public Model Model { get; private set; }

        public string VoiceTestKind { get; private set; }

    }
}