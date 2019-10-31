using TranslatorServer.DTO;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;

namespace TranslatorServer.Management
{
    public class Translator
    {
        private const string host = Configuration.MtHost;
        private const string subscriptionKey = Configuration.MtSubscriptionKey;

        public static IEnumerable<TranslationResult> TranslateTextRequest(string inputText, string lang)
        {
            string route = "";
            object[] body = new object[] { new { Text = inputText } };
            var requestBody = JsonConvert.SerializeObject(body);

            if (lang == "zh-CN")
            {
                route = Configuration.MtZhRoute;
            }
            if (lang == "en-US")
            {
                route = Configuration.MtEnRoute;
            }

            using (var client = new HttpClient())
            using (var request = new HttpRequestMessage())
            {
                // Build the request.
                request.Method = HttpMethod.Post;
                request.RequestUri = new Uri(host + route);
                request.Content = new StringContent(requestBody, Encoding.UTF8, "application/json");
                request.Headers.Add("Ocp-Apim-Subscription-Key", subscriptionKey);

                // Send the request and get response.
                HttpResponseMessage response = client.SendAsync(request).Result;
                // Read response as a string.
                string result = response.Content.ReadAsStringAsync().Result;
                var deserializedOutput = JsonConvert.DeserializeObject<IEnumerable<TranslationResult>>(result);

                return deserializedOutput;
            }
        }
    }
}
