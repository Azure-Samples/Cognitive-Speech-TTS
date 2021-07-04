using CustomVoice_API.API.DTO;
using Newtonsoft.Json;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;

namespace CustomVoice_API.API
{
    class Dataset
    {
        public static IEnumerable<DTO.Dataset> Get(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_Get);
            return APIHelper.Get<IEnumerable<DTO.Dataset>>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.Dataset> GetByProjectId(string subscriptionKey, string hostURI, string projectId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_GetByProjectId, projectId);
            return APIHelper.Get<IEnumerable<DTO.Dataset>>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string datasetId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_DeleteById, datasetId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if(response.StatusCode != HttpStatusCode.NoContent)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            return true;
        }

        public static bool Upload(string subscriptionKey, string hostURI, string name, string description, 
            string projectId, string gender, string locale, string wavePath, string scriptPath, string datasetKind)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("Gender", gender.Substring(0, 1).ToUpper() + gender.Substring(1));
            var datasetDefinition = DatasetDefinition.Create(locale, properties, name, description, "CustomVoice", projectId);

            switch (datasetKind)
            {
                case "LongAudio":
                    return UploadDatasetWithLongAudio(subscriptionKey, hostURI, datasetDefinition, wavePath, scriptPath);
                case "AudioOnly":
                    return UploadDatasetWithAudioOnly(subscriptionKey, hostURI, datasetDefinition, wavePath);
                default:
                    return UploadDataset(subscriptionKey, hostURI, datasetDefinition, wavePath, scriptPath);
            }
        }

        private static bool UploadDataset(string subscriptionKey, string hostURI, DatasetDefinition datasetDefinition, string wavePath, string scriptPath)
        {
            string waveName = Path.GetFileName(wavePath);
            string scriptName = Path.GetFileName(scriptPath);

            using (FileStream fsscript = new FileStream(scriptPath, FileMode.Open))
            using (FileStream fswave = new FileStream(wavePath, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);

                content.Add(new StringContent(datasetDefinition.Name), "name");

                if (datasetDefinition.Description != null)
                {
                    content.Add(new StringContent(datasetDefinition.Description), "description");
                }

                if (datasetDefinition.ProjectId != null)
                {
                    content.Add(new StringContent(datasetDefinition.ProjectId), "projectId");
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

                string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_Upload);
                var response = client.PostAsync(url, content).Result;

                if (response.StatusCode != HttpStatusCode.Accepted)
                {
                    APIHelper.PrintErrorMessage(response);
                    return false;
                }

                System.Console.WriteLine(response.Headers.Location);
                return true;
            }
        }

        private static bool UploadDatasetWithLongAudio(string subscriptionKey, string hostURI, DatasetDefinition datasetDefinition, string wavePath, string scriptPath)
        {
            string scriptName = Path.GetFileName(scriptPath);
            string waveName = Path.GetFileName(wavePath);
            using (FileStream fsscript = new FileStream(scriptPath, FileMode.Open))
            using (FileStream fswave = new FileStream(wavePath, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);

                content.Add(new StringContent(datasetDefinition.Name), "name");

                if (datasetDefinition.Description != null)
                {
                    content.Add(new StringContent(datasetDefinition.Description), "description");
                }

                if (datasetDefinition.ProjectId != null)
                {
                    content.Add(new StringContent(datasetDefinition.ProjectId), "projectId");
                }

                content.Add(new StringContent(datasetDefinition.DataImportKind), "dataImportKind");
                content.Add(new StringContent(datasetDefinition.Locale), "locale");

                if (datasetDefinition.Properties != null)
                {
                    content.Add(new StringContent(JsonConvert.SerializeObject(datasetDefinition.Properties)), "properties");
                }

                var transcriptionContent = new StreamContent(fsscript);
                transcriptionContent.Headers.Add("Content-Disposition", $@"form-data; name=""transcriptions""; filename=""{scriptName}""");
                transcriptionContent.Headers.Add("Content-Type", "application/x-zip-compressed");
                transcriptionContent.Headers.Add("Content-Length", $"{fsscript.Length}");
                content.Add(transcriptionContent, "transcriptions", scriptName);

                var wavesContent = new StreamContent(fswave);
                wavesContent.Headers.Add("Content-Disposition", $@"form-data; name=""audiodata""; filename=""{waveName}""");
                wavesContent.Headers.Add("Content-Type", "application/x-zip-compressed");
                wavesContent.Headers.Add("Content-Length", $"{fswave.Length}");
                content.Add(wavesContent, "audiodata", waveName);

                string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_UploadLongAudio);
                var response = client.PostAsync(url, content).Result;

                if (response.StatusCode != HttpStatusCode.Accepted)
                {
                    APIHelper.PrintErrorMessage(response);
                    return false;
                }
                return true;
            }
        }

        private static bool UploadDatasetWithAudioOnly(string subscriptionKey, string hostURI, DatasetDefinition datasetDefinition, string wavePath)
        {
            string waveName = Path.GetFileName(wavePath);
            using (FileStream fswave = new FileStream(wavePath, FileMode.Open))
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);

                content.Add(new StringContent(datasetDefinition.Name), "name");

                if (datasetDefinition.Description != null)
                {
                    content.Add(new StringContent(datasetDefinition.Description), "description");
                }

                if (datasetDefinition.ProjectId != null)
                {
                    content.Add(new StringContent(datasetDefinition.ProjectId), "projectId");
                }

                content.Add(new StringContent(datasetDefinition.DataImportKind), "dataImportKind");
                content.Add(new StringContent(datasetDefinition.Locale), "locale");

                if (datasetDefinition.Properties != null)
                {
                    content.Add(new StringContent(JsonConvert.SerializeObject(datasetDefinition.Properties)), "properties");
                }

                var wavesContent = new StreamContent(fswave);
                wavesContent.Headers.Add("Content-Disposition", $@"form-data; name=""audiodata""; filename=""{waveName}""");
                wavesContent.Headers.Add("Content-Type", "application/x-zip-compressed");
                wavesContent.Headers.Add("Content-Length", $"{fswave.Length}");
                content.Add(wavesContent, "audiodata", waveName);

                string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceDatasets_UploadAudioOnly);
                var response =  client.PostAsync(url, content).Result;

                if (response.StatusCode != HttpStatusCode.Accepted)
                {
                    APIHelper.PrintErrorMessage(response);
                    return false;
                }
                return true;
            }
        }
    }
}
