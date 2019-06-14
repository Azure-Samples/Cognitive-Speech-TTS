using Microsoft.SpeechServices.Cris.Http;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading.Tasks;

namespace ConsoleApp1
{

    class Program
    {
        //Cognitive service link
        //https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

        static void Main(string[] args)
        {
            //To call VoiceSynthsisAPIs method:
            //VoiceSynthsisAPIs().Wait();

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

            customVoiceAPI.UploadLongAudioDataset(
                @"E:\Audio.zip",
                @"E:\Script.zip",
                "long audio dataset",
                "long audio dataset description",
                "en-US",
                "male");

            customVoiceAPI.UploadAudioOnlyDataset(
                @"E:\Audio.zip",
                "audio only dataset",
                "audio only dataset description",
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

        private static async Task VoiceSynthsisAPIs()
        {
            string endpoint = "https://centralindia.cris.ai/";
            string ibizaStsUrl = "https://centralindia.api.cognitive.microsoft.com/sts/v1.0/issueToken";
            // the Subscription key should be a standard one, not the free one.
            string subscriptionKey = "Your SubscriptionKey";

            CustomVoiceAPI customVoiceAPI = new CustomVoiceAPI(endpoint, ibizaStsUrl, subscriptionKey);

            const string name = "Simple neural TTS batch synthesis";
            const string description = "Simple neural TTS batch synthesis description";

            // The input text file could contains only plain text or only SSML or mixed together(as shown in blow script)
            // The input text file encoding format should be UTF-8-BOM
            // The input text file should contains at least 50 lines of text
            const string localInputTextFile = @"TestData\en-US.txt";
            const string locale = "en-US";
            const string voiceName = "Jessa";
            // public voice means the voice could be used by all Subscriptions, if the voice is private(for your Subscription only), this should be set to false
            bool isPublicVoice = true;

            // you can directly set the voiceId or query the voice information by name/locale/ispublic properties from server.
            //var voiceId = new Guid("Your voice model Guid");
            var voiceId = GetVoiceId(customVoiceAPI, locale, voiceName, isPublicVoice);
            if (voiceId == Guid.Empty)
            {
                Console.WriteLine($"Does not have a available voice for locale : {locale} , name : {voiceName}, public : {isPublicVoice}");
                return;
            }

            // indicate if want concatenate the output waves with a single file or not.
            bool concatenateResult = true;

            // Submit a voice synthesis request and get a ID
            var synthesisLocation = await customVoiceAPI.CreateVoiceSynthesis(name, description, locale, localInputTextFile, voiceId, concatenateResult).ConfigureAwait(false);
            var synthesisId = new Guid(synthesisLocation.ToString().Split('/').LastOrDefault());

            Console.WriteLine("Checking status.");
            // check for the status of the submitted synthesis every 10 sec. (can also be 1, 2, 5 min depending on usage)
            bool completed = false;
            while (!completed)
            {
                var synthesis = customVoiceAPI.GetSynthesis(synthesisId);
                switch (synthesis.Status)
                {
                    case "Failed":
                    case "Succeeded":
                        completed = true;
                        // if the synthesis was successfull, download the results to local
                        if (synthesis.Status == "Succeeded")
                        {
                            var resultsUri = synthesis.ResultsUrl;
                            WebClient webClient = new WebClient();
                            var filename = $"{Path.GetTempFileName()}_{synthesis.Id}_.zip";
                            webClient.DownloadFile(resultsUri, filename);
                            Console.WriteLine($"Synthesis succeeded. Results: {filename}");
                        }
                        break;

                    case "Running":
                        break;

                    case "NotStarted":
                        break;
                }

                Console.WriteLine(string.Format("Syntheses status: {0}", synthesis.Status));
                await Task.Delay(TimeSpan.FromSeconds(10)).ConfigureAwait(false);
            }

            Console.WriteLine("Press any key...");
            Console.ReadKey();

            // Get submitted synthesis request list and update a submitted synthesis request
            /*
            var syntheses = customVoiceAPI.GetSyntheses();

            var synthesis = syntheses.FirstOrDefault();
            if (synthesis != null)
            {
                customVoiceAPI.UpdateSynthesis(synthesis.Id, "Updated Name", "Updated Desc");
            }
            */

            // Delete all pre-existing completed synthesis. If synthesis are still running or not started, they will not be deleted
            /*
            syntheses = customVoiceAPI.GetSyntheses();
            foreach (var item in syntheses)
            {
                // delete a synthesis
                customVoiceAPI.DeleteSynthesis(item.Id);
            }
            */
        }

        private static Guid GetVoiceId(CustomVoiceAPI api, string locale, string voiceName, bool publicVoice)
        {
            // Get available voices list
            var voices = api.GetVoices();
            Voice voice = null;
            if (publicVoice)
            {
                voice = voices.Where(m => m.Locale == locale && m.Name.Contains(voiceName) && m.IsPublicVoice).FirstOrDefault();
            }
            else
            {
                voice = voices.Where(m => m.Locale == locale && m.Name.Contains(voiceName)).FirstOrDefault();
            }
            if (voice == null)
            {
                Console.WriteLine($"Does not have a available voice for locale : {locale} , name : {voiceName}, public : {publicVoice}");
                return Guid.Empty;
            }
            return voice.Id;
        }
    }
}
