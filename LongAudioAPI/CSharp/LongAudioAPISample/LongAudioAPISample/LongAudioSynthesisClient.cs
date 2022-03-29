namespace LongAudioSynthesisSample
{
    using LongAudioSynthesisSample.Models;
    using System;
    using System.Collections.Generic;
    using System.Globalization;
    using System.IO;
    using System.Linq;
    using System.Net.Http;
    using System.Net.Http.Headers;
    using System.Net.Http.Json;
    using System.Net.Mime;
    using System.Text.Json;
    using System.Text.Json.Serialization;
    using System.Threading.Tasks;

    public class LongAudioSynthesisClient
    {
        private const string OcpApimSubscriptionKey = "Ocp-Apim-Subscription-Key";
        private readonly JsonSerializerOptions serializationOption = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            Converters =
            {
                new JsonStringEnumConverter()
            }
        };

        private readonly string hostName;
        private readonly string baseUri;
        private readonly string subscriptionKey;

        private readonly HttpClient client;
        
        public LongAudioSynthesisClient(string hostName, string key)
        {
            this.hostName = hostName;
            this.subscriptionKey = key;
            this.baseUri = $"{this.hostName}/api/texttospeech/v3.0/longaudiosynthesis";

            this.client = new HttpClient();
            client.DefaultRequestHeaders.Add(OcpApimSubscriptionKey, this.subscriptionKey);
        }

        public async Task<IEnumerable<Voice>> GetSupportedVoicesAsync()
        {
            var voices = new List<Voice>();
            var uri = new Uri(this.baseUri + "/voices");
            do
            {
                var response = await this.client.GetAsync(uri).ConfigureAwait(false);

                if (!response.IsSuccessStatusCode)
                {
                    await HandleErrorResponse(response);
                    return voices;
                }

                var pagedVoices = await response.Content.ReadFromJsonAsync<PaginatedResults<Voice>>().ConfigureAwait(false);
                voices.AddRange(pagedVoices.Values);
                uri = pagedVoices.NextLink;
            }
            while (uri != null);

            return voices;
        }

        public async Task<IEnumerable<Synthesis>> GetAllSynthesesAsync()
        {
            var syntheses = new List<Synthesis>();
            var uri = new Uri(this.baseUri);
            do
            {
                var response = await this.client.GetAsync(uri).ConfigureAwait(false);

                if (!response.IsSuccessStatusCode)
                {
                    await HandleErrorResponse(response);
                    return syntheses;
                }

                var pagedSyntheses = await response.Content.ReadFromJsonAsync<PaginatedResults<Synthesis>>().ConfigureAwait(false);
                syntheses.AddRange(pagedSyntheses.Values);
                uri = pagedSyntheses.NextLink;
            }
            while (uri != null);

            return syntheses;
        }

        public async Task<Synthesis> GetSynthesisAsync(Guid id)
        {
            var uri = new Uri(this.baseUri + $"/{id}");
            var response = await this.client.GetAsync(uri).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                await HandleErrorResponse(response);
                return null;
            }

            return await response.Content.ReadFromJsonAsync<Synthesis>().ConfigureAwait(false);
        }

        public async Task DeleteSynthesisAsync(Guid id)
        {
            var uri = new Uri(this.baseUri + $"/{id}");
            var response = await this.client.DeleteAsync(uri).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                await HandleErrorResponse(response);
            }
        }

        public async Task<IEnumerable<SynthesisFile>> GetSynthesisFilesAsync(Guid id)
        {
            var uri = new Uri(this.baseUri + $"/{id}/files");
            var response = await this.client.GetAsync(uri).ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
            {
                await HandleErrorResponse(response);
                return Enumerable.Empty<SynthesisFile>();
            }

            var pagedFiles = await response.Content.ReadFromJsonAsync<PaginatedResults<SynthesisFile>>(serializationOption).ConfigureAwait(false);
            return pagedFiles.Values;
        }

        public async Task<Uri> CreateSynthesisAsync(CultureInfo locale, string voiceName, string displayName, string description, string scriptPath)
        {
            var uri = new Uri(this.baseUri);

            // Sample values
            var voices = new List<VoiceIdentity>
            {
                new VoiceIdentity(){ VoiceName = voiceName }
            };

            var formData = new MultipartFormDataContent();
            formData.Add(new StringContent(displayName), "displayName");
            formData.Add(new StringContent(description), "description");
            formData.Add(new StringContent(locale.Name), "locale");
            formData.Add(new StringContent(JsonSerializer.Serialize(voices)), "voices");

            var scriptContent = new StreamContent(File.OpenRead(scriptPath));

            scriptContent.Headers.ContentType = new MediaTypeHeaderValue(MediaTypeNames.Text.Plain);
            scriptContent.Headers.ContentDisposition = new ContentDispositionHeaderValue("form-data") { 
                Name = "script",
                FileName = Path.GetFileName(scriptPath) 
            };
            formData.Add(scriptContent, "script");

            // Optional configurations
            // formData.Add(new StringContent("riff-16khz-16bit-mono-pcm"), "outputFormat");

            var response = await this.client.PostAsync(uri, formData).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                await HandleErrorResponse(response);
                return null;
            }

            var location = response.Headers.GetValues("Location").FirstOrDefault();
            return new Uri(location);

        }

        private static async Task HandleErrorResponse(HttpResponseMessage response)
        {
            var content = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
            Console.WriteLine(content);
        }
    }
}
