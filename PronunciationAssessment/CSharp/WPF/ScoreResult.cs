namespace SpeechScore
{
    using System.Collections.Generic;

    public class ScoreResult
    {
        public string RecognitionStatus { get; set; }
        public int Offset { get; set; }
        public int Duration { get; set; }
        public List<NBestItem> NBest { get; set; }
    }

    public class NBestItem
    {
        public double Confidence { get; set; }
        public string Lexical { get; set; }
        public string ITN { get; set; }
        public string MaskedITN { get; set; }
        public string Display { get; set; }
        public float PronScore { get; set; }
        public float AccuracyScore { get; set; }
        public float FluencyScore { get; set; }
        public float CompletenessScore { get; set; }
        public List<WordsItem> Words { get; set; }
    }

    public class WordsItem
    {
        public string Word { get; set; }
        public float AccuracyScore { get; set; }
        public string ErrorType { get; set; }
        public int Offset { get; set; }
        public int Duration { get; set; }
        public List<PhonemesItem> Phonemes { get; set; }
    }

    public class PhonemesItem
    {
        public string Phoneme { get; set; }
        public float AccuracyScore { get; set; }
        public int Offset { get; set; }
        public int Duration { get; set; }
    }
}
