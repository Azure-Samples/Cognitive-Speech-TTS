using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

namespace ConsoleApp1.VoiceAPI
{
    class Authentication
    {
        private const string SubscriptionKeyHeaderName = "Ocp-Apim-Subscription-Key";

        private string subscriptionKey;
        private Uri ibizaStsUrl;

        public Authentication(Uri ibizaStsUrl, string subscriptionKey)
        {
            this.ibizaStsUrl = ibizaStsUrl;
            this.subscriptionKey = subscriptionKey;
        }

        public string RetrieveNewTokenAsync()
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
