using Microsoft.SpeechServices.Cris.Http;
using System;
using System.Collections.Generic;

namespace ConsoleApp1
{

    class Program
    {
        //Cognitive service link
        //https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

        private static string endpoint = "https://westus.cris.ai/";
        private static string ibizaStsUrl = "https://westus.api.cognitive.microsoft.com/sts/v1.0/issueToken";
        private static string SubscriptionKey = "Your SubscriptionKey";

        static void Main(string[] args)
        {
            CustomVoiceAPI customVoiceAPI = new CustomVoiceAPI(endpoint, ibizaStsUrl);
            
            //Upload Dataset
            customVoiceAPI.UpdateDataset(
                SubscriptionKey,
                @"E:\xxx.zip",
                @"E:\xxx.txt",
                "dataset test",
                "dataset test",
                "en-US",
                "male");

            //Get Dataset
            var datasets = customVoiceAPI.GetDatasets(SubscriptionKey);

            //Create Model
            Guid datasetID = new Guid("Dataset ID");
            List<DatasetIdentity> datasetIdentityList = new List<DatasetIdentity> { new DatasetIdentity(datasetID) };

            customVoiceAPI.CreateModel(
                SubscriptionKey,
                "model test",
                "model test",
                "en-US",
                "male",
                datasetIdentityList);

            //Get Model
            var models = customVoiceAPI.GetModels(SubscriptionKey);

            //Create Voice Test
            customVoiceAPI.CreateVoiceTest(
                SubscriptionKey,
                "model ID",
                "voice test test",
                false);

            //Get Voice Test
            var voiceTests = customVoiceAPI.GetVoiceTests(SubscriptionKey, "Model ID");

            //Deploy Endpoint
            Guid modelID = new Guid("Model ID");
            List<ModelIdentity> modelIdentityList = new List<ModelIdentity> { new ModelIdentity(modelID) };

            customVoiceAPI.CreateEndpoint(
                SubscriptionKey,
                "endpoint test",
                "endpoint test",
                "en-US",
                modelIdentityList);

            //Get Endpoints
            var endpoints = customVoiceAPI.GetEndpoints(SubscriptionKey);

            //Call Endpoint
            customVoiceAPI.InvokeEndpoint(
                SubscriptionKey,
                "ENdpoint Url",
                "en-US",
                "Font name",
                "test script",
                false,
                @"E:\xxx.wav");
        }
    }
}
