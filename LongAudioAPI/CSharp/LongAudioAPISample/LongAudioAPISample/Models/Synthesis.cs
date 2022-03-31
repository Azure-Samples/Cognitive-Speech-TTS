namespace LongAudioSynthesisSample.Models
{
    using System;

    public class Synthesis
    {
        public Guid Id { get; set; }

        public string DisplayName { get; set; }

        public string Description { get; set; }

        public string Status { get; set; }

        public string Locale { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public DateTime LastActionDateTime { get; set; }

        public SynthesisProperties Properties { get; set; }
    }
}
