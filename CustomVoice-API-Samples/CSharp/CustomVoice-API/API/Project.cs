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
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, string name, string description, string gender, string locale)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("Gender", gender.Substring(0, 1).ToUpper() + gender.Substring(1));

            var projectDefinition = ProjectDefinition.Create(
                name,
                name,
                description,
                locale,
                properties,
                "TextToSpeech");

            var jsonString = Newtonsoft.Json.JsonConvert.SerializeObject(projectDefinition);

            var response = APIHelper.Submit(subscriptionKey, hostURI + API_V3.VoiceProject_Create, jsonString);


            if (response.StatusCode != HttpStatusCode.Accepted && response.StatusCode != HttpStatusCode.Created)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            System.Console.WriteLine(response.Headers.Location);
            return true;
        }
    }
}
