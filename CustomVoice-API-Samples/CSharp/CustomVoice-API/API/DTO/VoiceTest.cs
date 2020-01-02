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
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            Identity project)
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
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
            this.Model = model;
            this.VoiceTestKind = voiceTestKind;
            this.Project = project;
        }

        public Guid Id { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public string AudioUri { get; private set; }

        public string TextUri { get; private set; }

        public Model Model { get; private set; }

        public string VoiceTestKind { get; private set; }

        public Identity Project { get; private set; }

        public static VoiceTest Create(
            Guid id,
            Uri audioUri,
            Uri textUri,
            string voiceTestKind,
            Model model,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            Identity project)
        {
            return new VoiceTest(
                    id,
                    audioUri,
                    textUri,
                    voiceTestKind,
                    model,
                    createdDateTime,
                    lastActionDateTime,
                    status,
                    project);
        }
    }
}
