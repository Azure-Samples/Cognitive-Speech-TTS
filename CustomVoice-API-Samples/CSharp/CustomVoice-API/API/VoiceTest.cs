using CustomVoice_API.API.DTO;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;

namespace CustomVoice_API.API
{
    class VoiceTest
    {
        public static IEnumerable<DTO.VoiceTest> Get(string subscriptionKey, string hostURI, string modelId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceTests_GetByModelId, modelId);
            return APIHelper.Get<IEnumerable<DTO.VoiceTest>>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.VoiceTest> GetByProjectId(string subscriptionKey, string hostURI, string projectId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceTests_GetByProjectId, projectId);
            return APIHelper.Get<IEnumerable<DTO.VoiceTest>>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string voiceTestId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceTests_DeleteById, voiceTestId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                Console.WriteLine($"Status Code: {response.StatusCode}");
                Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, Guid projectId, Guid modelId, string script, bool isSSML)
        {
            string TextKind = "Text";
            if (isSSML)
            {
                TextKind = "SSML";
            }

            var voiceTestDefinition = VoiceTestDefinition.Create(
                new Identity(modelId),
                script,
                TextKind,
                new Identity(projectId));

            var response = APIHelper.Submit<VoiceTestDefinition>(subscriptionKey, hostURI + API_V3.VoiceTests_Create, voiceTestDefinition);

            if (response.StatusCode != HttpStatusCode.Accepted)
            {
                Console.WriteLine($"Status Code: {response.StatusCode}");
                Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
                return false;
            }
            return true;
        }
    }
}
