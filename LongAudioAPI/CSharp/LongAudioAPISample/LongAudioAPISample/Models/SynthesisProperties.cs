namespace LongAudioSynthesisSample.Models
{
    using System;

    public class SynthesisProperties
    {
        public string OutputFormat { get; set; }

        public bool ConcatenateResult { get; set; }

        public string TotalDuration { get; set; }

        public int BillableCharacterCount { get; set; }

        public Uri DestinationContainerUrl { get; set; }
    }
}
