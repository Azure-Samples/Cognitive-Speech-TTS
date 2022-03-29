namespace LongAudioSynthesisSample.Models
{
    using System;
    using System.Globalization;

    public class Voice
    {
        public Guid Id { get; set; }
    
        public string VoiceName { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public string Gender { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public VoiceProperties Properties { get; set; }
    }
}
