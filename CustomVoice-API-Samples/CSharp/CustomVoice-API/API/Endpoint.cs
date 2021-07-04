using CustomVoice_API.API.DTO;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Security;
using System.Text;

namespace CustomVoice_API.API
{
    class Endpoint
    {
        public static IEnumerable<DTO.Endpoint> Get(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceEndpoints_Get);
            return APIHelper.Get<IEnumerable<DTO.Endpoint>>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.Endpoint> GetByProjectId(string subscriptionKey, string hostURI, string projectId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceEndpoints_GetByProjectId, projectId);
            return APIHelper.Get<IEnumerable<DTO.Endpoint>>(subscriptionKey, url);
        }

        public static DTO.Endpoint GetById(string subscriptionKey, string hostURI, string endpointId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceEndpoints_DeleteById, endpointId);
            return APIHelper.Get<DTO.Endpoint>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string endpointId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceEndpoints_DeleteById, endpointId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, string name, string description,
            string local, Guid projectId, Guid modelId, bool wait = true)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("PortalAPIVersion", "3");

            System.Net.Http.HttpResponseMessage response;


            var endpointDefinition = EndpointDefinition.Create(
                name,
                description,
                local,
                new Identity(projectId),
                new List<Identity> { new Identity(modelId) },
                properties);
            var jsonString = Newtonsoft.Json.JsonConvert.SerializeObject(endpointDefinition);
            response = APIHelper.Submit(subscriptionKey, hostURI + API_V3.VoiceEndpoints_Create, jsonString);

            if (response.StatusCode != HttpStatusCode.Accepted)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            Console.WriteLine("endpoint created: " +  response.Headers.Location.ToString());

            return true;
        }

        public static void Call(string subscriptionKey, string issueTokenUrl, string endpointUrl, string voiceName, string locale, string script, string outputFile, bool isSSML)
        {
            const string SsmlPattern = @"<speak version=""1.0"" xmlns=""http://www.w3.org/2001/10/synthesis"" xmlns:mstts=""http://www.w3.org/2001/mstts"" xml:lang=""{0}"">" +
            @"<voice name = ""{1}"">{2}</voice>" +
            @"</speak>";
            string ssml = "";
            string token = APIHelper.GetToken(issueTokenUrl, subscriptionKey);

            HttpWebRequest webRequest = (HttpWebRequest)WebRequest.Create(endpointUrl);
            string ImpressionGUID = Guid.NewGuid().ToString();
            webRequest.ContentType = "application/ssml+xml";
            webRequest.Headers.Add("X-MICROSOFT-OutputFormat", "riff-16khz-16bit-mono-pcm");
            webRequest.Headers["Authorization"] = "Bearer " + token;
            webRequest.Headers.Add("X-FD-ClientID", ImpressionGUID);
            webRequest.Headers.Add("X-FD-ImpressionGUID", ImpressionGUID);
            webRequest.UserAgent = "TTSClient";
            webRequest.Method = "POST";

            if (isSSML)
            {
                ssml = script;
            }
            else
            {
                ssml = string.Format(CultureInfo.InvariantCulture, SsmlPattern, locale, voiceName, SecurityElement.Escape(script));
            }
            byte[] btBodyS = Encoding.UTF8.GetBytes(ssml);
            webRequest.ContentLength = btBodyS.Length;
            webRequest.GetRequestStream().Write(btBodyS, 0, btBodyS.Length);
            webRequest.Timeout = 6000000;

            using (var response = webRequest.GetResponse() as HttpWebResponse)
            {
                var sstream = response.GetResponseStream();
                using (FileStream fs = new FileStream(outputFile, FileMode.Create, FileAccess.Write))
                {
                    sstream.CopyTo(fs);
                }
            }
        }
    }
}
