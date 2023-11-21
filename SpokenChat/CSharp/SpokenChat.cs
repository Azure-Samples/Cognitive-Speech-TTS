// Note: The Azure OpenAI client library for .NET is in preview.
// Install the .NET library via NuGet: dotnet add package Azure.AI.OpenAI --prerelease
using Azure;
using Azure.AI.OpenAI;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using System.Linq;
using System.Text;

// setup speech configuration 
var speechConfig = SpeechConfig.FromSubscription(
    Environment.GetEnvironmentVariable("AI_SERVICES_KEY"), "eastus2");

// Speech to text from the microphone
speechConfig.SpeechRecognitionLanguage = "en-US";
using var audioConfig = AudioConfig.FromDefaultMicrophoneInput();
using var recognizer = new SpeechRecognizer(speechConfig, audioConfig);
Console.WriteLine("Say something...");
var speechResult = await recognizer.RecognizeOnceAsync();

OpenAIClient client = new OpenAIClient(
    new Uri("https://docs-azure-ai-resource-aiservices.openai.azure.com/"),
    new AzureKeyCredential(Environment.GetEnvironmentVariable("AI_SERVICES_KEY")));


using var responseWithoutStream = await client.GetChatCompletionsStreamingAsync(
    new ChatCompletionsOptions()
    {
        Messages =
        {
            new ChatMessage(ChatRole.System, @"You are an AI assistant that helps people find information."),
            new ChatMessage(ChatRole.User, speechResult.Text)
        },
        Temperature = (float)0.7,
        MaxTokens = 800,


        NucleusSamplingFactor = (float)0.95,
        FrequencyPenalty = 0,
        PresencePenalty = 0,
        DeploymentName = "gpt-35-turbo"
    });

// Sentence end symbols for splitting the response into sentences.
List<string> sentenceSaperators = new() { ".", "!", "?", ";", "。", "！", "？", "；", "\n" };
StringBuilder gptBuffer = new();

// Set a voice name for synthesis
speechConfig.SpeechSynthesisVoiceName = "en-US-JasonNeural";
using var synthesizer = new SpeechSynthesizer(speechConfig);
await foreach (var message in responseWithoutStream.EnumerateValues())
{
    var text = message.ContentUpdate;
    if (string.IsNullOrEmpty(text))
    {
        continue;
    }

    gptBuffer.Append(text);
    Console.Write(text);

    if (sentenceSaperators.Any(text.Contains))
    {
        var sentence = gptBuffer.ToString().Trim();
        if (!string.IsNullOrEmpty(sentence))
        {
            await synthesizer.SpeakTextAsync(sentence);
            gptBuffer.Clear();
        }
    }
}
