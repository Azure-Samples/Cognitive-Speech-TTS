using Microsoft.SpeechServices.Cris.Http;
using System;
using System.Collections.Generic;
using System.Linq;

namespace ConsoleApp1
{

    class Program
    {
        //Cognitive service link
        //https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

        static void Main(string[] args)
        {
            string endpoint = "https://westus.cris.ai/";
            string ibizaStsUrl = "https://westus.api.cognitive.microsoft.com/sts/v1.0/issueToken";
            string subscriptionKey = "Your SubscriptionKey";
            CustomVoiceAPI customVoiceAPI = new CustomVoiceAPI(endpoint, ibizaStsUrl, subscriptionKey);

            //Upload Dataset
            customVoiceAPI.UpdateDataset(
                @"E:\xxx.zip",
                @"E:\xxx.txt",
                "dataset test",
                "dataset test",
                "en-US",
                "male");

            //Get Dataset
            var datasets = customVoiceAPI.GetDatasets();

            //Create Model
            Guid datasetID = new Guid("Dataset ID");
            List<DatasetIdentity> datasetIdentityList = new List<DatasetIdentity> { new DatasetIdentity(datasetID) };

            customVoiceAPI.CreateModel(
                "model test",
                "model test",
                "en-US",
                "male",
                datasetIdentityList);

            //Get Model
            var models = customVoiceAPI.GetModels();

            //Create Voice Test
            customVoiceAPI.CreateVoiceTest(
                "model ID",
                "voice test test",
                false);

            //Get Voice Test
            var voiceTests = customVoiceAPI.GetVoiceTests("Model ID");

            //Deploy Endpoint
            Guid modelID = new Guid("Model ID");
            List<ModelIdentity> modelIdentityList = new List<ModelIdentity> { new ModelIdentity(modelID) };

            customVoiceAPI.CreateEndpoint(
                "endpoint test",
                "endpoint test",
                "en-US",
                modelIdentityList);

            //Get Endpoints
            var endpoints = customVoiceAPI.GetEndpoints();

            //Call Endpoint
            customVoiceAPI.InvokeEndpoint(
                "ENdpoint Url",
                "en-US",
                "Font name",
                "test script",
                false,
                @"E:\xxx.wav");
        }

        // The voice synthesis APIs are now only availabel in DC EastUS
        private static void VoiceSynthsisAPIs()
        {
            string endpoint = "https://eastus.cris.ai/";
            string ibizaStsUrl = "https://eastus.api.cognitive.microsoft.com/sts/v1.0/issueToken";
            string subscriptionKey = "Your SubscriptionKey";

            CustomVoiceAPI customVoiceAPI = new CustomVoiceAPI(endpoint, ibizaStsUrl, subscriptionKey);

            // Get available voices list
            var voices = customVoiceAPI.GetVoices();

            // Submit a voice synthesis request
            const string Name = "Simple neural TTS batch synthesis";
            const string Description = "Simple neural TTS batch synthesis description";

            const string Locale = "en-US";
            const string LocalInputTextFile = @"TestData\en-US_small.txt";
            const string VoiceName = "Jessa";

            var voice = voices.Where(m => m.Locale == Locale && m.Name.Contains(VoiceName) && m.IsPublicVoice).FirstOrDefault();

            if (voice == null)
            {
                Console.WriteLine($"Does not have a available voice for local : {Locale} and name {VoiceName}");
                return;
            }

            customVoiceAPI.CreateVoiceSynthesis(Name, Description, Locale, LocalInputTextFile, voice.Id);

            // Get submitted synthesis request list and update a submitted synthesis request
            var syntheses = customVoiceAPI.GetSyntheses();

            var synthesis = syntheses.FirstOrDefault();
            if (synthesis != null)
            {
                customVoiceAPI.UpdateSynthesis(synthesis.Id, "Updated Name", "Updated Desc");
            }

            // Delete all pre-existing completed synthesis. If synthesis are still running or not started, they will not be deleted
            syntheses = customVoiceAPI.GetSyntheses();
            foreach (var item in syntheses)
            {
                // delete a synthesis
                customVoiceAPI.DeleteSynthesis(item.Id);
            }
        }
    }
}
