using CustomVoice_API.API.DTO;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;

namespace CustomVoice_API.API
{
    class Model
    {
        public static IEnumerable<DTO.Model> Get(string subscriptionKey, string hostURI)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceModels_Get);
            return APIHelper.Get<IEnumerable<DTO.Model>>(subscriptionKey, url);
        }

        public static IEnumerable<DTO.Model> GetByProjectId(string subscriptionKey, string hostURI, string projectId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceModels_GetByProjectId, projectId);
            return APIHelper.Get<IEnumerable<DTO.Model>>(subscriptionKey, url);
        }

        public static bool DeleteById(string subscriptionKey, string hostURI, string modelId)
        {
            string url = string.Format(CultureInfo.InvariantCulture, hostURI + API_V3.VoiceModels_DeleteById, modelId);
            var response = APIHelper.Delete(subscriptionKey, url);
            if (response.StatusCode != HttpStatusCode.NoContent)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }

            return true;
        }

        public static bool Create(string subscriptionKey, string hostURI, string name, string description,
            Guid projectId, string gender, string locale,  List<Identity> dataset,  bool isNeuralTTS, bool isMixlingual,
            IDictionary<string, string> neuralProperties)
        {
            var properties = new Dictionary<string, string>();
            properties.Add("Gender", gender.Substring(0, 1).ToUpper() + gender.Substring(1));

            if (isMixlingual)
            {
                locale = "zh-CN";
                properties.Add("IsMixLingual", "true");
            }
            else
            {
                properties.Add("IsMixLingual", "false");
            }

            if (isNeuralTTS)
            {
                properties.Add("VoiceModelKind", "NeuralTts");
                foreach (var neuralProperty in neuralProperties)
                {
                    properties.Add(neuralProperty.Key, neuralProperty.Value);
                }
            }

            var modelDefinition = ModelDefinition.Create(
                name,
                description,
                properties,
                locale,
                "CustomVoice",
                null,
                dataset,
                new Identity(projectId));
            var response = APIHelper.Submit<ModelDefinition>(subscriptionKey, hostURI + API_V3.VoiceModels_Create, modelDefinition);

            if (response.StatusCode != HttpStatusCode.Accepted)
            {
                APIHelper.PrintErrorMessage(response);
                return false;
            }
            return true;
        }
    }
}
