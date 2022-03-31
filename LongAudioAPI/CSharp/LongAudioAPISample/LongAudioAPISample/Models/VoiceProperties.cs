namespace LongAudioSynthesisSample.Models
{
    using System.Collections.Generic;

    public class VoiceStyle
    {
        public string Name { get; set; }
    }

    public class VoiceSpeaker
    {
        public int Id { get; set; }
    }

    public class VoiceRole
    {
        public string Name { get; set; }
    }

    public class VoiceProperties
    {
        public bool PublicAvailable { get; set; }

        public IEnumerable<VoiceSpeaker> Speakers { get; set; }

        public IEnumerable<VoiceRole> Roles { get; set; }

        public IEnumerable<VoiceStyle> Styles { get; set; }
    }
}
