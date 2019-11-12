using System;
using System.Net;
using System.Net.Http;

namespace TranslatorServer.Management
{
    public class Authentication
    {
        private const string SubscriptionKeyHeaderName = "Ocp-Apim-Subscription-Key";

        private string subscriptionKey;
        private Uri ibizaStsUrl;
        private DateTime dateTime;
        private string token;

        public Authentication(Uri ibizaStsUrl, string subscriptionKey)
        {
            this.ibizaStsUrl = ibizaStsUrl;
            this.subscriptionKey = subscriptionKey;
            this.dateTime = DateTime.Now;
            this.token = RetrieveNewTokenAsync();
        }

        public string GetToken()
        {
            DateTime now = DateTime.Now;
            TimeSpan duration = now - dateTime;
            if (duration.TotalMinutes > 9)
            {
                dateTime = now;
                token = RetrieveNewTokenAsync(); 
            }

            return token;
        }

        private string RetrieveNewTokenAsync()
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add(SubscriptionKeyHeaderName, this.subscriptionKey);
                var response = client.PostAsync(this.ibizaStsUrl, new StringContent(string.Empty)).Result;

                if (response.IsSuccessStatusCode)
                {
                    return response.Content.ReadAsStringAsync().Result;
                }
                else
                {
                    throw new WebException(response.ReasonPhrase);
                }
            }
        }
    }
}
