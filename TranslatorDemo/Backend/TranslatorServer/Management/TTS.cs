using System;
using System.Globalization;
using System.IO;
using System.Net;
using System.Security;
using System.Text;

namespace TranslatorServer.Management
{
    public class TTS
    {
        const string SsmlPattern = @"<speak version=""1.0"" xmlns=""http://www.w3.org/2001/10/synthesis"" xml:lang=""{0}"">" +
            @"<voice name = ""{1}"">{2}</voice>" +
            @"</speak>";

        //Cognitive service
        const string IbizaStsUrl = Configuration.TtsIbizaStsUrl;
        const string SubscriptionKey = Configuration.TtsSubscriptionKey;
        const string Endpoint = Configuration.TtsEndpoint;
        public string AriaRUSName = Configuration.AriaRUSName;
        public string XiaoxiaoNeuralName = Configuration.XiaoxiaoNeuralName;

        private Authentication cognitiveServiceAuthentication;

        public TTS()
        {
            cognitiveServiceAuthentication = InitAuthentication(IbizaStsUrl, SubscriptionKey);
        }

        public Stream Synthesis(string script)
        {
            return Synthesis(script, "audio-16khz-32kbitrate-mono-mp3", "en-US");
        }

        public Stream Synthesis(string script, string locale)
        {
            return Synthesis(script, "audio-16khz-32kbitrate-mono-mp3", locale);
        }

        public Stream Synthesis(string script, string format, string locale)
        {
            string token = cognitiveServiceAuthentication.GetToken();
            if(locale == "zh-CN")
            {
                return GetStream(Endpoint, token, locale, XiaoxiaoNeuralName, script, format, false);
            }
            else
            {
                return GetStream(Endpoint, token, locale, AriaRUSName, script, format, false);
            }
        }

        private Stream GetStream(string endpoint, string token, string locale, string voiceName, string script, string format, bool isSSML)
        {
            WebRequest webRequest = WebRequest.Create(endpoint);
            string ImpressionGUID = Guid.NewGuid().ToString();
            webRequest.ContentType = "text/plain";
            webRequest.Headers.Add("X-MICROSOFT-OutputFormat", format);
            webRequest.Headers["Authorization"] = "Bearer " + token;
            webRequest.Headers.Add("X-FD-ClientID", ImpressionGUID);
            webRequest.Headers.Add("X-FD-ImpressionGUID", ImpressionGUID);
            ((HttpWebRequest)webRequest).UserAgent = "MicrosoftReader";

            webRequest.Method = "POST";

            if (!isSSML)
            {
                script = NeutralFormat(SsmlPattern, locale, voiceName, SecurityElement.Escape(script));
            }
            
            byte[] btBodys = Encoding.UTF8.GetBytes(script);
            webRequest.ContentLength = btBodys.Length;
            webRequest.GetRequestStream().Write(btBodys, 0, btBodys.Length);
            webRequest.Timeout = 6000000;

            HttpWebResponse httpWebResponse = (HttpWebResponse)webRequest.GetResponse();

            if(httpWebResponse.StatusCode == HttpStatusCode.OK)
            {
                return httpWebResponse.GetResponseStream();
            }
            else
            {
                return null;
            }
        }

        private Authentication InitAuthentication(string url, string subscriptionKey)
        {
            var ibizaStsUrl = new Uri(url);
            return new Authentication(ibizaStsUrl, subscriptionKey);
        }

        private string NeutralFormat(string format, params object[] arg)
        {
            if (string.IsNullOrEmpty(format))
            {
                throw new ArgumentNullException("format");
            }

            return string.Format(CultureInfo.InvariantCulture, format, arg);
        }
    }
}
