// <copyright file="VoiceAPIHelper.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System.Collections.Generic;
    using System.IO;
    using System.Net.Http;
    using System.Text;
    using System.Threading;
    using Newtonsoft.Json;

    public static class VoiceAPIHelper
    {
        public static IEnumerable<T> Get<T>(string token, string endpoint)
        {
            var response = GetData(token, endpoint);

            using (var responseStream = response.Content.ReadAsStreamAsync().Result)
            using (var streamReader = new StreamReader(responseStream))
            {
                string responseJson = streamReader.ReadToEnd();
                var items = JsonConvert.DeserializeObject<IEnumerable<T>>(responseJson);
                return items;
            }
        }

        public static HttpResponseMessage Submit<T>(T definition, string endpoint, string token)
        {
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", token);
                return client.PostAsJsonAsync(endpoint, definition, CancellationToken.None).Result;
            }
        }

        public static HttpResponseMessage SubmitDataset(DatasetDefinition datasetDefinition, string wave, string script, string endpoint, string token)
        {
            string waveName = Path.GetFileName(wave);
            string scriptName = Path.GetFileName(script);

            using (FileStream fsscript = new FileStream(script, FileMode.Open))
            using (FileStream fswave = new FileStream(wave, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", token);

                content.Add(new StringContent(datasetDefinition.Name), "name");

                if (datasetDefinition.Description != null)
                {
                    content.Add(new StringContent(datasetDefinition.Description), "description");
                }

                content.Add(new StringContent(datasetDefinition.DataImportKind), "dataImportKind");
                content.Add(new StringContent(datasetDefinition.Locale), "locale");

                if (datasetDefinition.Properties != null)
                {
                    content.Add(new StringContent(JsonConvert.SerializeObject(datasetDefinition.Properties)), "properties");
                }

                var transcriptionContent = new StreamContent(fsscript);
                transcriptionContent.Headers.Add("Content-Disposition", $@"form-data; name=""transcriptions""; filename=""{scriptName}""");
                transcriptionContent.Headers.Add("Content-Type", "text/plain");
                transcriptionContent.Headers.Add("Content-Length", $"{fsscript.Length}");
                content.Add(transcriptionContent, "transcriptions", scriptName);

                var wavesContent = new StreamContent(fswave);
                wavesContent.Headers.Add("Content-Disposition", $@"form-data; name=""audiodata""; filename=""{waveName}""");
                wavesContent.Headers.Add("Content-Type", "application/x-zip-compressed");
                wavesContent.Headers.Add("Content-Length", $"{fswave.Length}");
                content.Add(wavesContent, "audiodata", waveName);

                return client.PostAsync(endpoint, content).Result;
            }
        }

        public static HttpResponseMessage SubmitVoiceSynthesis(VoiceSynthesisDefinition voiceSynthesisDefinition, string inputTextPath, string endpoint, string token)
        {
            string scriptName = Path.GetFileName(inputTextPath);

            using (FileStream fsscript = new FileStream(inputTextPath, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", token);

                content.Add(new StringContent(voiceSynthesisDefinition.Name), "name");

                if (voiceSynthesisDefinition.Description != null)
                {
                    content.Add(new StringContent(voiceSynthesisDefinition.Description), "description");
                }

                content.Add(new StringContent(voiceSynthesisDefinition.Model.Id.ToString()), "model");
                content.Add(new StringContent(voiceSynthesisDefinition.Locale), "locale");

                if (voiceSynthesisDefinition.Properties != null)
                {
                    content.Add(new StringContent(JsonConvert.SerializeObject(voiceSynthesisDefinition.Properties)), "properties");
                }

                var scriptContent = new StreamContent(fsscript);
                scriptContent.Headers.Add("Content-Disposition", $@"form-data; name=""script""; filename=""{scriptName}""");
                scriptContent.Headers.Add("Content-Type", "text/plain");
                scriptContent.Headers.Add("Content-Length", $"{fsscript.Length}");
                content.Add(scriptContent, "script", scriptName);

                return client.PostAsync(endpoint, content).Result;
            }
        }

        public static HttpResponseMessage Delete(string token, string endpoint)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", token);
                return client.DeleteAsync(endpoint, CancellationToken.None).Result;
            }
        }

        public static HttpResponseMessage PatchVoiceSynthesis(VoiceSynthesisUpdate definition, string token, string endpoint)
        {
            using (var client = new HttpClient())
            using (var content = new StringContent(JsonConvert.SerializeObject(definition), Encoding.UTF8, "application/json"))
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", token);
                return client.PatchAsync(endpoint, content).Result;
            }
        }

        public static HttpResponseMessage GetData(string subKey, string endpoint)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subKey);
                return client.GetAsync(endpoint, CancellationToken.None).Result;
            }
        }
    }
}
