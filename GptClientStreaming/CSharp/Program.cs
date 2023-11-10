namespace TtsClientStreaming
{
    using System.Security;
    using System.Text;
    using Azure.AI.OpenAI;
    using Azure;
    using Microsoft.CognitiveServices.Speech;
    using Microsoft.CognitiveServices.Speech.Audio;
    using static System.Net.Mime.MediaTypeNames;


    internal class Program
    {
        private static OpenAIClient aoaiClient;
        private static SpeechSynthesizer ttsClient;
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

        public static async Task Main(string[] args)
        {
            // setup aoai and tts client
            Setup();
            Console.OutputEncoding = Encoding.UTF8;

            // streaming get gpt response
            var responseStream = await aoaiClient!.GetChatCompletionsStreamingAsync(
                deploymentOrModelName: "gpt-4",
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
                    await OnGptTokenRecieve(text);
                }
            }

            // speak the remaining text in buffer if have
            if (gptBuffer.Length > 0)
            {
                var ssml = string.Format(ssmlTemplate, SecurityElement.Escape(gptBuffer.ToString()));
                await SpeakSentence(ssml);
                gptBuffer.Clear();
            }

            // write audio buffer to file to verify
            audioBuffer.Close();
            File.WriteAllBytes("gpt.wav", audioBuffer.ToArray());
        }

        private static async Task OnGptTokenRecieve(string token)
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
                var ssml = string.Format(ssmlTemplate, SecurityElement.Escape(sentence));
                await SpeakSentence(ssml);
                ;           }
            else
            {
                gptBuffer.Append(token);
            }
        }

        private static async Task SpeakSentence(string ssml)
        {
            lock (consoleLock)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.Write($"[TTS]");
                Console.ResetColor();
            }
            await ttsClient.SpeakSsmlAsync(ssml);
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

            var config = SpeechConfig.FromSubscription(Environment.GetEnvironmentVariable("AZURE_TTS_API_KEY"), Environment.GetEnvironmentVariable("AZURE_TTS_REGION"));
            config.SetSpeechSynthesisOutputFormat(SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm);
            ttsClient = new SpeechSynthesizer(config, null);
            ttsClient.Synthesizing += TtsClientOnSynthesizing; 
        }

        // write audio data to buffer
        private static void TtsClientOnSynthesizing(object? sender, SpeechSynthesisEventArgs e)
        {
            audioBuffer.Write(e.Result.AudioData);
        }
    }
}