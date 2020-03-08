//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/Cognitive-Speech-TTS
//
// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License:
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//
using System;
using System.Net.Http;
using System.Text;
using System.IO;
using System.Threading.Tasks;
using System.Xml.Linq;
using System.Threading;

namespace TTSSample
{
    public class Authentication
    {
        private string subscriptionKey;
        private string tokenFetchUri;
        private Timer accessTokenRenewer;
        private string accessToken;

        //Access token expires every 10 minutes. Renew it every 9 minutes only.
        private const int RefreshTokenDuration = 1;

        public Authentication(string tokenFetchUri, string subscriptionKey)
        {
            if (string.IsNullOrWhiteSpace(tokenFetchUri))
            {
                throw new ArgumentNullException(nameof(tokenFetchUri));
            }

            if (string.IsNullOrWhiteSpace(subscriptionKey))
            {
                throw new ArgumentNullException(nameof(subscriptionKey));
            }

            this.tokenFetchUri = tokenFetchUri;
            this.subscriptionKey = subscriptionKey;

            this.accessToken = this.FetchTokenAsync().Result;

            // renew the token every specfied minutes
            this.accessTokenRenewer = new Timer(new TimerCallback(OnTokenExpiredCallback),
                                           this,
                                           TimeSpan.FromMinutes(RefreshTokenDuration),
                                           TimeSpan.FromMilliseconds(-1));
        }

        public string GetAccessToken()
        {
            return this.accessToken;
        }

        private async void OnTokenExpiredCallback(object stateInfo)
        {
            try
            {
                this.accessToken = await this.FetchTokenAsync().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                Console.WriteLine(string.Format("Failed renewing access token. Details: {0}", ex.Message));
            }
            finally
            {
            }
        }

        public async Task<string> FetchTokenAsync()
        {
            using (HttpClient client = new HttpClient())
            {
                client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", this.subscriptionKey);
                UriBuilder uriBuilder = new UriBuilder(this.tokenFetchUri);

                HttpResponseMessage result = await client.PostAsync(uriBuilder.Uri.AbsoluteUri, null).ConfigureAwait(false);
                return await result.Content.ReadAsStringAsync().ConfigureAwait(false);
            }
        }
    }

    // main program
    class Program
    {
        static async Task Main(string[] args)
        {
            // Prompts the user to input text for TTS conversion
            Console.Write("What would you like to convert to speech? ");
            string text;
            string input = Console.ReadLine();

            // Gets an access token
            string accessToken;

            // Add your subscription key here
            Authentication auth = new Authentication("https://southeastasia.api.cognitive.microsoft.com/sts/v1.0/issueToken", "Your Key Here");

            // reuse http client will save connection latency
            using (HttpClient client = new HttpClient())
            {
                while (true)
                {
                    Console.WriteLine("-----------------------------");

                    text = input + new Random().Next().ToString();
                    Console.WriteLine(text);
                     
                    try
                    {
                        accessToken = auth.GetAccessToken();
                        Console.WriteLine("Successfully obtained an access token. \n");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("Failed to obtain an access token.");
                        Console.WriteLine(ex.ToString());
                        Console.WriteLine(ex.Message);
                        return;
                    }

                    string host = "https://southeastasia.tts.speech.microsoft.com/cognitiveservices/v1";

                    // Create SSML document.
                    XDocument body = new XDocument(
                            new XElement("speak",
                                new XAttribute("version", "1.0"),
                                new XAttribute(XNamespace.Xml + "lang", "en-US"),
                                new XElement("voice",
                                    new XAttribute(XNamespace.Xml + "lang", "en-US"),
                                    new XAttribute(XNamespace.Xml + "gender", "Female"),
                                    new XAttribute("name", "zh-CN-XiaoxiaoNeural"), 
                                    text)));

                    DateTime dt = DateTime.Now;

                    using (HttpRequestMessage request = new HttpRequestMessage())
                    {
                        // Set the HTTP method
                        request.Method = HttpMethod.Post;
                        // Construct the URI
                        request.RequestUri = new Uri(host);
                        // Set the content type header
                        request.Content = new StringContent(body.ToString(), Encoding.UTF8, "application/ssml+xml");
                        // Set additional header, such as Authorization and User-Agent
                        request.Headers.Add("Authorization", "Bearer " + accessToken);
                        request.Headers.Add("Connection", "Keep-Alive");
                        // Update your resource name
                        request.Headers.Add("User-Agent", "YOUR_RESOURCE_NAME");
                        // Audio output format. See API reference for full list.
                        request.Headers.Add("X-Microsoft-OutputFormat", "riff-24khz-16bit-mono-pcm");
                        // Create a request
                        Console.WriteLine("Calling the TTS service. Please wait... \n");
                        using (HttpResponseMessage response = await client.SendAsync(request).ConfigureAwait(false))
                        {
                            response.EnsureSuccessStatusCode();
                            // Asynchronously read the response
                            using (Stream dataStream = await response.Content.ReadAsStreamAsync().ConfigureAwait(false))
                            {
                                Console.WriteLine("Your speech file is being written to file...");
                                using (FileStream fileStream = new FileStream(@"sample.wav", FileMode.Create, FileAccess.Write, FileShare.Write))
                                {
                                    await dataStream.CopyToAsync(fileStream).ConfigureAwait(false);
                                    fileStream.Close();
                                }
                            }
                        }
                    }

                    Console.WriteLine($"time spend {(DateTime.Now - dt).TotalMilliseconds}");
                }
            }
        }
    }
}
