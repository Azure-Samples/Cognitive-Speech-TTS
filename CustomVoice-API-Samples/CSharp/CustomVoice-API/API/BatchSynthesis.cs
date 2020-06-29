using CustomVoice_API.API.DTO;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;

namespace CustomVoice_API.API
{
    class BatchSynthesis
    {
        private const string OneAPIOperationLocationHeaderKey = "Location";

        public static IEnumerable<DTO.BatchSynthesis> Get(string subscriptionKey, string hostURI, string timeStart, string timeEnd, string status, int skip, int top)
        {
            string url = string.Format($@"{hostURI}{API_V3.VoiceSynthesis_GetPaginated}?");
            if(!string.IsNullOrEmpty(timeStart))
            {
                url += string.Format($@"&timestart={timeStart}");
            }
            if (!string.IsNullOrEmpty(timeEnd))
            {
                url += string.Format($@"&timeend={timeEnd}");
            }
            if (!string.IsNullOrEmpty(status))
            {
                url += string.Format($@"&status={status}");
            }
            if (skip != -1)
            {
                url += string.Format($@"&skip={skip}");
            }
            else
            {
                url += string.Format($@"&skip=0");
            }
            if (top != -1)
            {
                url += string.Format($@"&top={top}");
            }
            else
            {
                url += string.Format($@"&top=100");
            }
            var encodedUrl = Uri.EscapeUriString(url);
            return APIHelper.GetListPaged<DTO.BatchSynthesis>(subscriptionKey, encodedUrl);
        }

        public static DTO.BatchSynthesis GetById(string subscriptionKey, string hostURI, string batchSynthesisId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_ById, batchSynthesisId);
            return APIHelper.Get<DTO.BatchSynthesis>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.Voice> Getvoices(string subscriptionKey, string hostURI, Dictionary<string, string> additionalRequestHeaders)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_GetVoice);
            return APIHelper.Get<IEnumerable<DTO.Voice>>(subscriptionKey, url, additionalRequestHeaders);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string batchSynthesisId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceSynthesis_ById, batchSynthesisId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            return true;
        }

        public static string Create(string subscriptionKey, string hostURI, string name, string description,
            string inputTextPath, string locale, IEnumerable<Guid> models, string outputFormat, bool isConcatenateResult)
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

        private static string Create(string subscriptionKey, string hostURI, BatchSynthesisDefinition batchSynthesisDefinition)
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

                string url = hostURI + API_V3.VoiceSynthesis_Create;
                var response = client.PostAsync(url, content).Result;

                if (response.StatusCode != HttpStatusCode.Accepted)
                {
                    APIHelper.PrintErrorMessage(response);
                    return null;
                }

                var returnUrl = GetLocationFromPostResponse(response);
                if (returnUrl != null)
                {
                    return new Guid(returnUrl.ToString().Split('/').LastOrDefault()).ToString();
                }
                return null;
            }
        }

        private static Uri GetLocationFromPostResponse(HttpResponseMessage response)
        {
            IEnumerable<string> headerValues;
            if (response.Headers.TryGetValues(OneAPIOperationLocationHeaderKey, out headerValues))
            {
                if (headerValues.Any())
                {
                    return new Uri(headerValues.First());
                }
            }

            return response.Headers.Location;
        }
    }
}
