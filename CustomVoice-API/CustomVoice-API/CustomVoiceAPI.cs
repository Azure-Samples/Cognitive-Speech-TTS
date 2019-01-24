using System.Collections.Generic;
using Microsoft.SpeechServices.Cris.Http;
using System;
using System.Globalization;
using System.Net;
using System.Text;
using System.Security;
using ConsoleApp1.VoiceAPI;
using System.IO;

namespace ConsoleApp1
{
    public class CustomVoiceAPI
    {
        public string endpoint { get; private set; } = null;
        public string ibizaStsUrl { get; private set; } = null;

        private string GetDatasetsUrl => endpoint + @"api/texttospeech/v2.0/datasets";
        private string GetModelsUrl => endpoint + @"api/texttospeech/v2.0/models";
        private string GetEndpointsUrl => endpoint + @"api/texttospeech/v2.0/endpoints";
        private string GetVoiceTestsUrl => endpoint + @"api/texttospeech/v2.0/tests/model/{0}";
        private string CreateDatasetUrl => endpoint + "api/texttospeech/v2.0/datasets/upload";
        private string CreateModelUrl => endpoint + "api/texttospeech/v2.0/models";
        private string CreateEndpointUrl => endpoint + "api/texttospeech/v2.0/endpoints";
        private string CreateVoiceTestUrl => endpoint + "api/texttospeech/v2.0/tests";
        private string DeleteDatasetsUrl => endpoint + "api/texttospeech/v2.0/datasets/{0}";
        private string DeleteModelsUrl => endpoint + "api/texttospeech/v2.0/models/{0}";
        private string DeleteEndpointsUrl => endpoint + "api/texttospeech/v2.0/endpoints/{0}";
        private string DeleteVoiceTestsUrl => endpoint + "api/texttospeech/v2.0/tests/{0}";

        public CustomVoiceAPI(string endpoint, string ibizaStsUrl)
        {
            this.endpoint = endpoint;
            this.ibizaStsUrl = ibizaStsUrl;
        }
        //Get Dataset
        public List<Dataset> GetDatasets(string SubscriptionKey)
        {
            return VoiceAPIHelper.Get<Dataset>(SubscriptionKey, GetDatasetsUrl);
        }

        //Get Model
        public List<Model> GetModels(string SubscriptionKey)
        {
            return VoiceAPIHelper.Get<Model>(SubscriptionKey, GetModelsUrl);
        }

        //Get Endpoint
        public List<Endpoint> GetEndpoints(string SubscriptionKey)
        {
            return VoiceAPIHelper.Get<Endpoint>(SubscriptionKey, GetEndpointsUrl);
        }

        //Get VoiceTest
        public List<VoiceTest> GetVoiceTests(string SubscriptionKey, string modelID)
        {
            return VoiceAPIHelper.Get<VoiceTest>(SubscriptionKey, string.Format(CultureInfo.InvariantCulture, GetVoiceTestsUrl, modelID));
        }

        //Create Dataset
        public void UpdateDataset(string SubscriptionKey, string waveUpload, string scriptUpload, string name, string description, string locale, string gender)
        {
            var properties = new Dictionary<string, string>
            {
                { "Gender", gender }
            };
            var datasetDefinition = new DatasetDefinition(name, description, locale, properties, "CustomVoice");
            var submitResponse = VoiceAPIHelper.SubmitDataset(datasetDefinition, waveUpload, scriptUpload, CreateDatasetUrl, SubscriptionKey);
        }

        //Create Models
        public void CreateModel(string SubscriptionKey, string name, string description, string locale, string gender, List<DatasetIdentity> DatasetIds)
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
            var submitResponse = VoiceAPIHelper.Submit<ModelDefinition>(modelDefinition, CreateModelUrl, SubscriptionKey);
        }

        //Create Endpoint
        public void CreateEndpoint(string SubscriptionKey, string name, string description, string locale, List<ModelIdentity> ModelIds)
        {
            var endpointDefinition = new EndpointDefinition(name,
                description,
                locale,
                ModelIds,
                null,
                0,
                false);
            var submitResponse = VoiceAPIHelper.Submit<EndpointDefinition>(endpointDefinition, CreateEndpointUrl, SubscriptionKey);
        }

        //Create Voice Test
        public void CreateVoiceTest(string SubscriptionKey, string ModelId, string script, bool isSSML)
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

            var submitResponse = VoiceAPIHelper.Submit<VoiceTestDefinition>(testDefinition, CreateVoiceTestUrl, SubscriptionKey);
        }

        //Invoked Endpoint
        public void InvokeEndpoint(string subscriptionKey, string endpointUrl, string local, string voiceName, string script, bool isSSML, string outputFile)
        {
            const string SsmlPattern = @"<speak version=""1.0"" xmlns=""http://www.w3.org/2001/10/synthesis"" xmlns:mstts=""http://www.w3.org/2001/mstts"" xml:lang=""{0}"">" +
            @"<voice name = ""{1}"">{2}</voice>" +
            @"</speak>";

            var authentication = new Authentication(new Uri(this.ibizaStsUrl), subscriptionKey);
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
    }
}
