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

namespace TTSSample
{
    public class Authentication
    {
      private string subscriptionKey;
      private string tokenFetchUri;

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
    class Program
    {
        static async Task Main(string[] args)
        {
            // Prompts the user to input text for TTS conversion
            Console.Write("What would you like to convert to speech? ");
            string text = Console.ReadLine();

            // Gets an access token
            string accessToken;
            Console.WriteLine("Attempting token exchange. Please wait...\n");

            // Add your subscription key here
            // If your resource isn't in WEST US, change the endpoint
            Authentication auth = new Authentication("https://westus.api.cognitive.microsoft.com/sts/v1.0/issueToken", "REPLACE_WITH_YOUR_KEY");
            try
            {
                accessToken = await auth.FetchTokenAsync().ConfigureAwait(false);
                Console.WriteLine("Successfully obtained an access token. \n");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Failed to obtain an access token.");
                Console.WriteLine(ex.ToString());
                Console.WriteLine(ex.Message);
                return;
            }

            string host = "https://westus.tts.speech.microsoft.com/cognitiveservices/v1";

            // Create SSML document.
            XDocument body = new XDocument(
                    new XElement("speak",
                        new XAttribute("version", "1.0"),
                        new XAttribute(XNamespace.Xml + "lang", "en-US"),
                        new XElement("voice",
                            new XAttribute(XNamespace.Xml + "lang", "en-US"),
                            new XAttribute(XNamespace.Xml + "gender", "Female"),
                            new XAttribute("name", "Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)"),
                            text)));

            using (HttpClient client = new HttpClient())
            {
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
                            Console.WriteLine("\nYour file is ready. Press any key to exit.");
                            Console.ReadLine();
                        }
                    }
                }
            }
        }
    }
}
