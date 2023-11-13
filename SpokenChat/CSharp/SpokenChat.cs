// Note: The Azure OpenAI client library for .NET is in preview.
// Install the .NET library via NuGet: dotnet add package Azure.AI.OpenAI --prerelease
using Azure;
using Azure.AI.OpenAI;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;

// setup speech configuration 
var speechConfig = SpeechConfig.FromSubscription(
  Environment.GetEnvironmentVariable("AI_SERVICES_KEY"), "eastus2");

// Get the text from the microphone
speechConfig.SpeechRecognitionLanguage = "en-US";
using var audioConfig = AudioConfig.FromDefaultMicrophoneInput();
using var recognizer = new SpeechRecognizer(speechConfig, audioConfig);
Console.WriteLine("Say something...");
var speechResult = await recognizer.RecognizeOnceAsync();

OpenAIClient client = new OpenAIClient(
  new Uri("https://docs-azure-ai-resource-aiservices.openai.azure.com/"),
  new AzureKeyCredential(Environment.GetEnvironmentVariable("AI_SERVICES_KEY")));

  Response<ChatCompletions> responseWithoutStream = await client.GetChatCompletionsAsync(
  "gpt-35-turbo-16k",
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
  });


ChatCompletions response = responseWithoutStream.Value;
// Set a voice name for synthesis
speechConfig.SpeechSynthesisVoiceName = "en-US-JasonNeural";
using var synthesizer = new SpeechSynthesizer(speechConfig);
await synthesizer.SpeakTextAsync(response.Value.Choices[0].Message.Content);