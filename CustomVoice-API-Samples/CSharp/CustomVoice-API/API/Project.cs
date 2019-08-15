using CustomVoice_API.API.DTO;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;

namespace CustomVoice_API.API
{
    class Project
    {
        public static IEnumerable<DTO.Project> Get(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceProject_Get);
            return APIHelper.Get<IEnumerable<DTO.Project>>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string projectId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceProject_DeleteById, projectId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                Console.WriteLine($"Status Code: {response.StatusCode}");
                Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, string name, string description, string gender, string locale)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("Gender", gender);
<<<<<<< HEAD
=======
            properties.Add("ModelDeployments", "0");
            properties.Add("Models", "0");
            properties.Add("Datasets", "0");
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287

            var projectDefinition = ProjectDefinition.Create(
                name,
                description,
                locale,
                properties,
                "TextToSpeech");
<<<<<<< HEAD
            var response = APIHelper.Submit<ProjectDefinition>(subscriptionKey, hostURI + API_V3.VoiceProject_Create, projectDefinition);

            if (response.StatusCode != HttpStatusCode.OK)
=======
            var response = APIHelper.Submit<ProjectDefinition>(subscriptionKey, hostURI + API_V3.VoiceModels_Create, projectDefinition);

            if (response.StatusCode != HttpStatusCode.Accepted)
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            {
                Console.WriteLine($"Status Code: {response.StatusCode}");
                Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                return false;
            }
            return true;
        }
    }
}
