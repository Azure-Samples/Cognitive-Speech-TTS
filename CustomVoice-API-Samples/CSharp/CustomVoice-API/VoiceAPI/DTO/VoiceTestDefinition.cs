// <copyright file="VoiceTestDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    public sealed class VoiceTestDefinition
    {
        public VoiceTestDefinition(
            ModelIdentity model,
            string text,
            string voiceTestKind)
        {
            this.Model = model;
            this.Text = text;
            this.VoiceTestKind = voiceTestKind;
        }

        public ModelIdentity Model { get; private set; }

        public string Text { get; private set; }

        public string VoiceTestKind { get; private set; }
    }
}
