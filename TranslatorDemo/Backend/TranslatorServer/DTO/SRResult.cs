namespace TranslatorServer.DTO
{
    public class SRResult
    {
        public SRResult()
        {
        }

        public SRResult(string company, string spantime, string text)
        {
            this.company = company;
            this.spantime = spantime;
            this.text = text;
        }

        public string company { get; set; }
        public string spantime { get; set; }
        public string text { get; set; }
    }
}
