namespace CustomVoice_API.API.DTO
{
    class VoiceTestDefinition
    {
        private VoiceTestDefinition(
            Identity model,
            string text,
            string voiceTestKind,
            Identity project)
        {
            this.Model = model;
            this.Text = text;
            this.VoiceTestKind = voiceTestKind;
            this.Project = project;
        }

        public Identity Model { get; private set; }

        public string Text { get; private set; }

        public string VoiceTestKind { get; private set; }

        public Identity Project { get; private set; }

        public static VoiceTestDefinition Create(
            Identity model,
            string text,
            string voiceTestKind,
            Identity project)
        {
            return new VoiceTestDefinition(model, text, voiceTestKind, project);
        }
    }
}
