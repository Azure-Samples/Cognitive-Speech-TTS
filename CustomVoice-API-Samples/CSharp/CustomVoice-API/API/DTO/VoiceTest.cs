using Newtonsoft.Json;
using System;

namespace CustomVoice_API.API.DTO
{
    class VoiceTest
    {
        [JsonConstructor]
        private VoiceTest(
            Guid id,
            Uri audioUri,
            Uri textUri,
            string voiceTestKind,
            Model model,
            DateTime created,
            DateTime lastAction,
            OneApiState state)
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
            this.Created = created;
            this.LastAction = lastAction;
            this.State = state;
            this.Model = model;
            this.VoiceTestKind = voiceTestKind;
        }

        public Guid Id { get; private set; }

        public DateTime Created { get; private set; }

        public DateTime LastAction { get; private set; }

        public OneApiState State { get; private set; }

        public string AudioUri { get; private set; }

        public string TextUri { get; private set; }

        public Model Model { get; private set; }

        public string VoiceTestKind { get; private set; }

        public static VoiceTest Create(
            Guid id,
            Uri audioUri,
            Uri textUri,
            string voiceTestKind,
            Model model,
            DateTime created,
            DateTime lastAction,
            OneApiState state)
        {
            return new VoiceTest(
                    id,
                    audioUri,
                    textUri,
                    voiceTestKind,
                    model,
                    created,
                    lastAction,
                    state);
        }
    }
}
