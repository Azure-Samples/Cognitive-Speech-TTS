using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using CustomVoice_API.API.DTO;
using Newtonsoft.Json;

namespace CustomVoice_API.API
{
    class APIHelper
    {
        public static T Get<T>(string subscriptionKey, string url)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                var response = client.GetAsync(url, CancellationToken.None).Result;

                if (response.StatusCode != HttpStatusCode.OK)
                {
                    PrintErrorMessage(response);
                    return default(T);
                }

                using (var responseStream = response.Content.ReadAsStreamAsync().Result)
                using (var streamReader = new StreamReader(responseStream))
                {
                    string responseJson = streamReader.ReadToEnd();
                    var items = JsonConvert.DeserializeObject<T>(responseJson);
                    return items;
                }
            }
        }

        public static T Get<T>(string subscriptionKey, string url, Dictionary<string, string> additionalRequestHeaders)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                foreach (var pair in additionalRequestHeaders)
                {
                    client.DefaultRequestHeaders.Add(pair.Key, pair.Value);
                }

                var response = client.GetAsync(url, CancellationToken.None).Result;

                if (response.StatusCode != HttpStatusCode.OK)
                {
                    PrintErrorMessage(response);
                    return default(T);
                }

                using (var responseStream = response.Content.ReadAsStreamAsync().Result)
                using (var streamReader = new StreamReader(responseStream))
                {
                    string responseJson = streamReader.ReadToEnd();
                    var items = JsonConvert.DeserializeObject<T>(responseJson);
                    return items;
                }
            }
        }

        public static IEnumerable<T> GetListPaged<T>(string subscriptionKey, string url)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                var response = client.GetAsync(url, CancellationToken.None).Result;

                if (response.StatusCode != HttpStatusCode.OK)
                {
                    PrintErrorMessage(response);
                    return null;
                }

                using (var responseStream = response.Content.ReadAsStreamAsync().Result)
                using (var streamReader = new StreamReader(responseStream))
                {
                    string responseJson = streamReader.ReadToEnd();
                    var result = JsonConvert.DeserializeObject<PaginatedEntities<T>>(responseJson);
                    return result.Values;
                }
            }
        }

        public static HttpResponseMessage Submit<T>(string subscriptionKey, string url, T definition)
        {
            using (var client = new HttpClient())
            using (var content = new MultipartFormDataContent())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                return client.PostAsJsonAsync(url, definition, CancellationToken.None).Result;
            }
        }

        public static HttpResponseMessage Delete(string subscriptionKey, string url)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                return client.DeleteAsync(url, CancellationToken.None).Result;
            }
        }

        public static HttpResponseMessage Patch<T>(string subscriptionKey, string url, T payload)
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", subscriptionKey);
                var method = new HttpMethod("PATCH");
                using (var request = new HttpRequestMessage(method, url)
                {
                    Content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json")
                })
                {
                    return client.SendAsync(request).Result;
                }
            }
        }

        public static string GetToken(string issueTokenUrl, string subscriptionKey)
        {
            var ibizaStsUrl = new Uri(issueTokenUrl);
            var authentication = new Authentication(ibizaStsUrl, subscriptionKey);
            return authentication.RetrieveNewTokenAsync();
        }

        public static void PrintErrorMessage(HttpResponseMessage response)
        {
            Console.WriteLine($"Status Code: {response.StatusCode}");
            Console.WriteLine($"Status ReasonPhrase: {response.ReasonPhrase}");
            var content = response.Content.ReadAsStringAsync().Result;
            Console.WriteLine(content);
        }

        public static Uri GetLocationFromPostResponseAsync(HttpResponseMessage response)
        {
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            const string OneAPIOperationLocationHeaderKey = "Location";
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
    }
}
