namespace TtsClientStreaming
{
    using System.Security;
    using System.Text;
    using Azure.AI.OpenAI;
    using Azure;
    using Microsoft.CognitiveServices.Speech;
    using Microsoft.CognitiveServices.Speech.Audio;
    using static System.Net.Mime.MediaTypeNames;
    using System.IO;
    using System.Xml.Linq;

    internal class Program
    {
        private static OpenAIClient aoaiClient;
        private static SpeechSynthesizer ttsClient;
        private static PullAudioOutputStream pullStream;
        private static StringBuilder gptBuffer = new();
        private static string ssmlTemplate = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' " +
                                             "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'>" +
                                             "<voice name='Microsoft Server Speech Text to Speech Voice (en-US, JennyNeural)'>" +
                                             "{0}" +
                                             "</voice></speak>";
        private static List<string> sentenceSaperators = new() { ".", "!", "?", ";", "。", "！", "？", "；", "\n" };
        private static object consoleLock = new();
        private static string query = "Tell me a joke about 100 words.";
        private static MemoryStream audioBuffer = new();


        public class StreamingSpeechSynthesizer
        {
            private SpeechSynthesizer ttsClient;
            private PullAudioOutputStream pullStream;
            private SpeechConfig config;
            private ManualResetEvent done = new ManualResetEvent(false);

            public StreamingSpeechSynthesizer()
            {
                config = SpeechConfig.FromSubscription(Environment.GetEnvironmentVariable("AZURE_TTS_API_KEY"), Environment.GetEnvironmentVariable("AZURE_TTS_REGION"));
                config.SetSpeechSynthesisOutputFormat(SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3);

                // create pull audio stream 
                this.pullStream = AudioOutputStream.CreatePullStream();
                var streamConfig = AudioConfig.FromStreamOutput(pullStream);
                this.ttsClient = new SpeechSynthesizer(config, streamConfig);
            }

            public async Task SpeakSentence(string text)
            {
                var ssml = string.Format(ssmlTemplate, SecurityElement.Escape(text.ToString()));
                lock (consoleLock)
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.Write($"[SentToTTS]");
                    Console.ResetColor();
                }

                await this.ttsClient.SpeakSsmlAsync(ssml);
            }

            public void Stop()
            {
                if (this.ttsClient != null)
                {
                    this.ttsClient.Dispose();
                    this.ttsClient = null;
                }


                PullAudioOutputStream stream = AudioOutputStream.CreatePullStream();
                var streamConfig = AudioConfig.FromStreamOutput(pullStream);
                var client = new SpeechSynthesizer(config, streamConfig);

                done.WaitOne();
                this.ttsClient = client;
                this.pullStream = stream;
                done.Reset();
            }

            public int ReadTts(byte[] buffer)
            {
                int filled =  (int)this.pullStream.Read(buffer);
                if (filled == 0)
                {
                    done.Set();
                }

                return filled;
            }

            ~StreamingSpeechSynthesizer()
            {
                if (this.ttsClient != null)
                {
                    this.ttsClient.Dispose();
                    this.ttsClient = null;
                }
            }

        }


        public static async Task Main(string[] args)
        {
            // setup aoai and tts client
            Setup();
            Console.OutputEncoding = Encoding.UTF8;

            StreamingSpeechSynthesizer streamingSpeechSynthesizer = new StreamingSpeechSynthesizer();

            // streaming get gpt response
            var responseStream = await aoaiClient!.GetChatCompletionsStreamingAsync(
                deploymentOrModelName: "gpt-35-turbo",
                new ChatCompletionsOptions()
                {
                    Messages =
                    {
                        new ChatMessage(ChatRole.System, @"You are an AI assistant that helps people find information."),
                        new ChatMessage(ChatRole.User, query),
                    },
                    Temperature = (float)0.7,
                    MaxTokens = 800,
                    NucleusSamplingFactor = (float)0.95,
                    FrequencyPenalty = 0,
                    PresencePenalty = 0,
                });

            // Start a new task to read out the synthesizer stream.
            Task readTask = Task.Run(() => {
                byte[] buffer = new byte[4096];
                int filledSize = 0;
                int totalSize = 0;
                while ((filledSize = streamingSpeechSynthesizer.ReadTts(buffer)) > 0)
                {
                    Console.WriteLine($"\n[READ] {filledSize} bytes received.");
                    totalSize += filledSize;

                    audioBuffer.Write(buffer, 0, (int)filledSize);
                }

                Console.WriteLine($"[READ] totally {totalSize} bytes received.");
            });


            using var streamingChatCompletions = responseStream.Value;
            await foreach (var choice in streamingChatCompletions.GetChoicesStreaming())
            {
                await foreach (var message in choice.GetMessageStreaming())
                {
                    var text = message.Content;
                    if (string.IsNullOrEmpty(text))
                    {
                        continue;
                    }

                    lock (consoleLock)
                    {
                        Console.ForegroundColor = ConsoleColor.DarkBlue;
                        Console.Write($"{text}");
                        Console.ResetColor();
                    }

                    // send to tts service to speak
                    await OnGptTokenRecieve(streamingSpeechSynthesizer, text);
                }
            }

            // speak the remaining text in buffer if have
            if (gptBuffer.Length > 0)
            {
                await streamingSpeechSynthesizer.SpeakSentence(SecurityElement.Escape(gptBuffer.ToString()));
                gptBuffer.Clear();
            }

            streamingSpeechSynthesizer.Stop();

            // write audio buffer to file to verify
            audioBuffer.Close();
            File.WriteAllBytes("gpt.mp3", audioBuffer.ToArray());
        }

        private static async Task OnGptTokenRecieve(StreamingSpeechSynthesizer streamingSpeechSynthesizer, string token)
        {
            if (string.IsNullOrEmpty(token))
            {
                return;
            }

            // if token is a sentence separator, speak the sentence in buffer
            if (sentenceSaperators.Any(token.Contains))
            {
                var sentence = gptBuffer + token;
                gptBuffer.Clear();
                await streamingSpeechSynthesizer.SpeakSentence(SecurityElement.Escape(sentence));
            }
            else
            {
                gptBuffer.Append(token);
            }
        }

   
        private static void Setup()
        {
            if (File.Exists("env.txt"))
            {
                foreach (var line in File.ReadAllLines("env.txt"))
                {
                    var parts = line.Split('=');
                    Environment.SetEnvironmentVariable(parts[0], parts[1]);
                }
            }

            aoaiClient = new OpenAIClient(
                new Uri(Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!),
                new AzureKeyCredential(Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY")!));
        }
    }
}