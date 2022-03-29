namespace LongAudioSynthesisSample.Models
{
    using System;

    public enum FileKind
    {
        LongAudioSynthesisScript,

        LongAudioSynthesisResult
    }

    public class SynthesisFile
    {
        public string Name { get; set; }

        public FileKind Kind { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public FileLinks Links { get; set; }
    }
}
