using CustomVoice_API.API.DTO;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;

namespace CustomVoice_API.API
{
    class BatchSynthesis
    {
        public static IEnumerable<DTO.BatchSynthesis> Get(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_Get);
            return APIHelper.Get<IEnumerable<DTO.BatchSynthesis>>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.Voice> Getvoices(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_GetVoice);
            return APIHelper.Get<IEnumerable<DTO.Voice>>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string batchSynthesisId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_DeleteById, batchSynthesisId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                Console.WriteLine($"Status Code: {response.StatusCode}");
                Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, string name, string description,
            string inputTextPath, string locale, IEnumerable<Identity> models, string outputFormat, bool isConcatenateResult)
        {
            var properties = new Dictionary<string, string>();
            if (isConcatenateResult)
            {
                properties.Add("ConcatenateResult", "true");
            }
           
            var batchSynthesisDefinition = BatchSynthesisDefinition.Create(name,
            description,
            inputTextPath,
            properties,
            locale,
            models,
            outputFormat);

            return Create(subscriptionKey, hostURI, batchSynthesisDefinition);
        }

        private static bool Create(string subscriptionKey, string hostURI, BatchSynthesisDefinition batchSynthesisDefinition)
        {
            string scriptName = Path.GetFileName(batchSynthesisDefinition.InputTextPath);

            using (FileStream fsscript = new FileStream(batchSynthesisDefinition.InputTextPath, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);

                content.Add(new StringContent(batchSynthesisDefinition.Name), "name");

                if (!string.IsNullOrEmpty(batchSynthesisDefinition.OutputFormat))
                {
                    content.Add(new StringContent(batchSynthesisDefinition.OutputFormat), "outputformat");
                }

                if (batchSynthesisDefinition.Description != null)
                {
                    content.Add(new StringContent(batchSynthesisDefinition.Description), "description");
                }

                content.Add(new StringContent(JsonConvert.SerializeObject(batchSynthesisDefinition.Models)), "models");
                content.Add(new StringContent(batchSynthesisDefinition.Locale), "locale");

                if (batchSynthesisDefinition.Properties != null)
                {
                    content.Add(new StringContent(JsonConvert.SerializeObject(batchSynthesisDefinition.Properties)), "properties");
                }

                var scriptContent = new StreamContent(fsscript);
                scriptContent.Headers.Add("Content-Disposition", $@"form-data; name=""script""; filename=""{scriptName}""");
                scriptContent.Headers.Add("Content-Type", "text/plain");
                scriptContent.Headers.Add("Content-Length", $"{fsscript.Length}");
                content.Add(scriptContent, "script", scriptName);

                string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_Create);
                var response = client.PostAsync(url, content).Result;

                if (response.StatusCode != HttpStatusCode.Accepted)
                {
                    Console.WriteLine($"Status Code: {response.StatusCode}");
                    Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                    return false;
                }
                return true;
            }
        }
    }
}
