using System.Collections.Generic;
using Microsoft.SpeechServices.Cris.Http;
using System;
using System.Globalization;
using System.Net;
using System.Text;
using System.Security;
using ConsoleApp1.VoiceAPI;
using System.IO;
using System.Threading.Tasks;
using System.Net.Http;
using Newtonsoft.Json;
using System.Linq;

namespace ConsoleApp1
{
    public class CustomVoiceAPI
    {
        public string endpoint { get; private set; } = null;
        public string ibizaStsUrl { get; private set; } = null;
        public string subscriptionKey { get; private set; } = null;

        private string GetDatasetsUrl => endpoint + @"api/texttospeech/v2.0/datasets";
        private string GetModelsUrl => endpoint + @"api/texttospeech/v2.0/models";
        private string GetEndpointsUrl => endpoint + @"api/texttospeech/v2.0/endpoints";
        private string GetVoiceTestsUrl => endpoint + @"api/texttospeech/v2.0/tests/model/{0}";
        private string CreateDatasetUrl => endpoint + "api/texttospeech/v2.0/datasets/upload";
        private string CreateLongAudioDatasetUrl => endpoint + "api/texttospeech/v2.1/datasets/longaudio";
        private string CreateAudioOnlyDatasetUrl => endpoint + "api/texttospeech/v2.1/datasets/audioonly";
        private string CreateModelUrl => endpoint + "api/texttospeech/v2.0/models";
        private string CreateEndpointUrl => endpoint + "api/texttospeech/v2.0/endpoints";
        private string CreateVoiceTestUrl => endpoint + "api/texttospeech/v2.0/tests";
        private string DeleteDatasetsUrl => endpoint + "api/texttospeech/v2.0/datasets/{0}";
        private string DeleteModelsUrl => endpoint + "api/texttospeech/v2.0/models/{0}";
        private string DeleteEndpointsUrl => endpoint + "api/texttospeech/v2.0/endpoints/{0}";
        private string DeleteVoiceTestsUrl => endpoint + "api/texttospeech/v2.0/tests/{0}";
        private string GetVoicesUrl => endpoint + "api/texttospeech/v3.0-beta1/voicesynthesis/voices";
        private string DeleteSynthesisUrl => endpoint + "api/texttospeech/v3.0-beta1/voicesynthesis/{0}";
        private string VoiceSynthesisUrl => endpoint + "api/texttospeech/v3.0-beta1/voicesynthesis/";

        private const string OneAPIOperationLocationHeaderKey = "Operation-Location";

        public CustomVoiceAPI(string endpoint, string ibizaStsUrl, string subscriptionKey)
        {
            this.endpoint = endpoint;
            this.ibizaStsUrl = ibizaStsUrl;
            this.subscriptionKey = subscriptionKey;
        }
        //Get Dataset
        public IEnumerable<Dataset> GetDatasets()
        {
            return VoiceAPIHelper.Get<Dataset>(this.subscriptionKey, GetDatasetsUrl);
        }

        //Get Model
        public IEnumerable<Model> GetModels()
        {
            return VoiceAPIHelper.Get<Model>(this.subscriptionKey, GetModelsUrl);
        }

        //Get Endpoint
        public IEnumerable<Endpoint> GetEndpoints()
        {
            return VoiceAPIHelper.Get<Endpoint>(this.subscriptionKey, GetEndpointsUrl);
        }

        //Get VoiceTest
        public IEnumerable<VoiceTest> GetVoiceTests(string modelID)
        {
            return VoiceAPIHelper.Get<VoiceTest>(this.subscriptionKey, string.Format(CultureInfo.InvariantCulture, GetVoiceTestsUrl, modelID));
        }

        //Create Dataset
        public void UpdateDataset(string waveUpload, string scriptUpload, string name, string description, string locale, string gender)
        {
            var properties = new Dictionary<string, string>
            {
                { "Gender", gender }
            };
            var datasetDefinition = new DatasetDefinition(name, description, locale, properties, "CustomVoice");
            var submitResponse = VoiceAPIHelper.SubmitDataset(datasetDefinition, waveUpload, scriptUpload, CreateDatasetUrl, this.subscriptionKey);
        }

        //Create Long Audio Dataset
        public void UploadLongAudioDataset(string waveZipUpload, string scriptZipUpload, string name, string description, string locale, string gender)
        {
            var properties = new Dictionary<string, string>
            {
                { "Gender", gender }
            };
            var datasetDefinition = new DatasetDefinition(name, description, locale, properties, "CustomVoice");
            var submitResponse = VoiceAPIHelper.SubmitLongAudioDataset(datasetDefinition, waveZipUpload, scriptZipUpload, CreateLongAudioDatasetUrl, this.subscriptionKey);
        }

        //Create Audio Only Dataset
        public void UploadAudioOnlyDataset(string waveZipUpload, string name, string description, string locale, string gender)
        {
            var properties = new Dictionary<string, string>
            {
                { "Gender", gender }
            };
            var datasetDefinition = new DatasetDefinition(name, description, locale, properties, "CustomVoice");
            var submitResponse = VoiceAPIHelper.SubmitAudioOnlyDataset(datasetDefinition, waveZipUpload, CreateLongAudioDatasetUrl, this.subscriptionKey);
        }

        //Create Models
        public void CreateModel(string name, string description, string locale, string gender, List<DatasetIdentity> DatasetIds)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("Gender", gender);
            var modelDefinition = new ModelDefinition(name,
                description,
                locale,
                "CustomVoice",
                null,
                DatasetIds,
                properties);
            var submitResponse = VoiceAPIHelper.Submit<ModelDefinition>(modelDefinition, CreateModelUrl, this.subscriptionKey);
        }

        //Create Endpoint
        public void CreateEndpoint(string name, string description, string locale, List<ModelIdentity> ModelIds)
        {
            var endpointDefinition = new EndpointDefinition(name,
                description,
                locale,
                ModelIds,
                null,
                0,
                false);
            var submitResponse = VoiceAPIHelper.Submit<EndpointDefinition>(endpointDefinition, CreateEndpointUrl, this.subscriptionKey);
        }

        //Create Voice Test
        public void CreateVoiceTest(string ModelId, string script, bool isSSML)
        {
            VoiceTestDefinition testDefinition;

            if (isSSML)
            {
                testDefinition = new VoiceTestDefinition(new ModelIdentity(new Guid(ModelId)),
                script,
                "SSML");
            }
            else
            {
                testDefinition = new VoiceTestDefinition(new ModelIdentity(new Guid(ModelId)),
                script,
                "Text");
            }

            var submitResponse = VoiceAPIHelper.Submit<VoiceTestDefinition>(testDefinition, CreateVoiceTestUrl, this.subscriptionKey);
        }

        //Invoked Endpoint
        public void InvokeEndpoint(string endpointUrl, string local, string voiceName, string script, bool isSSML, string outputFile)
        {
            const string SsmlPattern = @"<speak version=""1.0"" xmlns=""http://www.w3.org/2001/10/synthesis"" xmlns:mstts=""http://www.w3.org/2001/mstts"" xml:lang=""{0}"">" +
            @"<voice name = ""{1}"">{2}</voice>" +
            @"</speak>";

            var authentication = new Authentication(new Uri(this.ibizaStsUrl), this.subscriptionKey);
            string token = authentication.RetrieveNewTokenAsync();

            WebRequest webRequest = WebRequest.Create(endpointUrl);
            string ImpressionGUID = Guid.NewGuid().ToString();
            webRequest.ContentType = "application/ssml+xml";
            webRequest.Headers.Add("X-MICROSOFT-OutputFormat", "riff-16khz-16bit-mono-pcm");
            webRequest.Headers["Authorization"] = "Bearer " + token;
            webRequest.Headers.Add("X-FD-ClientID", ImpressionGUID);
            webRequest.Headers.Add("X-FD-ImpressionGUID", ImpressionGUID);
            webRequest.Method = "POST";

            string ssml;
            if (isSSML)
            {
                ssml = script;
            }
            else
            {
                ssml = NeutralFormat(SsmlPattern, local, voiceName, SecurityElement.Escape(script));
            }
            byte[] btBodys = Encoding.UTF8.GetBytes(ssml);
            webRequest.ContentLength = btBodys.Length;
            webRequest.GetRequestStream().Write(btBodys, 0, btBodys.Length);
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

        public string NeutralFormat(string format, params object[] arg)
        {
            if (string.IsNullOrEmpty(format))
            {
                throw new ArgumentNullException("format");
            }

            return string.Format(CultureInfo.InvariantCulture, format, arg);
        }

        public IEnumerable<Voice> GetVoices()
        {
            return VoiceAPIHelper.Get<Voice>(this.subscriptionKey, GetVoicesUrl);
        }

        public IEnumerable<Synthesis> GetSyntheses()
        {
            return VoiceAPIHelper.Get<Synthesis>(this.subscriptionKey, VoiceSynthesisUrl);
        }

        public Synthesis GetSynthesis(Guid id)
        {
            return VoiceAPIHelper.GetVoiceSynthesis(this.subscriptionKey, string.Format(CultureInfo.InvariantCulture, DeleteSynthesisUrl, id.ToString()));
        }

        public void DeleteSynthesis(Guid id)
        {
            VoiceAPIHelper.Delete(this.subscriptionKey, string.Format(CultureInfo.InvariantCulture, DeleteSynthesisUrl, id.ToString()));
        }

        public void UpdateSynthesis(Guid id, string newName, string newDesc)
        {
            VoiceAPIHelper.PatchVoiceSynthesis(VoiceSynthesisUpdate.Create(newName, newDesc), this.subscriptionKey, string.Format(CultureInfo.InvariantCulture, DeleteSynthesisUrl, id.ToString()));
        }

        public async Task<Uri> CreateVoiceSynthesis(string name, string description, string locale, string inputTextPath, Guid modelId, bool concatenateResult)
        {
            Console.WriteLine("Creating batch synthesiss.");
            var properties = new Dictionary<string, string>();
            if (concatenateResult)
            {
                properties.Add("ConcatenateResult", "true");
            }
            var model = ModelIdentity.Create(modelId);
            var voiceSynthesisDefinition = VoiceSynthesisDefinition.Create(name, description, locale, model, properties);
            using (var submitResponse = VoiceAPIHelper.SubmitVoiceSynthesis(voiceSynthesisDefinition, inputTextPath, VoiceSynthesisUrl, this.subscriptionKey))
            {
                return await GetLocationFromPostResponseAsync(submitResponse).ConfigureAwait(false);
            }
        }

        private static async Task<Uri> GetLocationFromPostResponseAsync(HttpResponseMessage response)
        {
            if (!response.IsSuccessStatusCode)
            {
                throw await CreateExceptionAsync(response).ConfigureAwait(false);
            }

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

        private static async Task<FailedHttpClientRequestException> CreateExceptionAsync(HttpResponseMessage response)
        {
            switch (response.StatusCode)
            {
                case HttpStatusCode.Forbidden:
                    return new FailedHttpClientRequestException(response.StatusCode, "No permission to access this resource.");
                case HttpStatusCode.Unauthorized:
                    return new FailedHttpClientRequestException(response.StatusCode, "Not authorized to see the resource.");
                case HttpStatusCode.NotFound:
                    return new FailedHttpClientRequestException(response.StatusCode, "The resource could not be found.");
                case HttpStatusCode.UnsupportedMediaType:
                    return new FailedHttpClientRequestException(response.StatusCode, "The file type isn't supported.");
                case HttpStatusCode.BadRequest:
                    {
                        var content = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                        var shape = new { Message = string.Empty };
                        var result = JsonConvert.DeserializeAnonymousType(content, shape);
                        if (result != null && !string.IsNullOrEmpty(result.Message))
                        {
                            return new FailedHttpClientRequestException(response.StatusCode, result.Message);
                        }

                        return new FailedHttpClientRequestException(response.StatusCode, response.ReasonPhrase);
                    }

                default:
                    return new FailedHttpClientRequestException(response.StatusCode, response.ReasonPhrase);
            }
        }
    }
}
