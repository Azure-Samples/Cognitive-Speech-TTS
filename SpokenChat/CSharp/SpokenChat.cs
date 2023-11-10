using Azure.AI.OpenAI;
using Azure;
using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;

// Azure OpenAI setup
var apiBase = "OPEN_AI_ENDPOINT"; // Add your endpoint here
var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY"); // Add your OpenAI API key here
var deploymentId = "DEPLOYMENT_NAME"; // Add your deployment ID here

// setup speech configuration 
var speechConfig = SpeechConfig.FromSubscription(
  Environment.GetEnvironmentVariable("OPENAI_API_KEY"), "eastus");

// Azure Cognitive Search setup
var searchEndpoint = "SEARCH_ENDPOINT"; // Add your Azure Cognitive Search endpoint here
var searchKey = Environment.GetEnvironmentVariable("SEARCH_KEY"); // Add your Azure Cognitive Search admin key here
var searchIndexName = "speechdoc"; // Add your Azure Cognitive Search index name here
var client = new OpenAIClient(new Uri(apiBase), new AzureKeyCredential(apiKey!));

// Get the text from the microphone
speechConfig.SpeechRecognitionLanguage = "en-US";
using var audioConfig = AudioConfig.FromDefaultMicrophoneInput();
using var recognizer = new SpeechRecognizer(speechConfig, audioConfig);
Console.WriteLine("Say something...");
var speechResult = await recognizer.RecognizeOnceAsync();

var chatCompletionsOptions = new ChatCompletionsOptions()
{
    Messages =
    {
        new ChatMessage(ChatRole.User, speechResult.Text)
    },
    // The addition of AzureChatExtensionsOptions enables the use of Azure OpenAI capabilities that add to
    // the behavior of Chat Completions, here the "using your own data" feature to supplement the context
    // with information from an Azure Cognitive Search resource with documents that have been indexed.
    AzureExtensionsOptions = new AzureChatExtensionsOptions()
    {
        Extensions =
        {
            new AzureCognitiveSearchChatExtensionConfiguration()
            {
                SearchEndpoint = new Uri(searchEndpoint),
                IndexName = searchIndexName,
                SearchKey = new AzureKeyCredential(searchKey!),
            }
        }
    }
};

var response = await client.GetChatCompletionsAsync(
    deploymentId,
    chatCompletionsOptions);

var message = response.Value.Choices[0].Message;
// The final, data-informed response still appears in the ChatMessages as usual
Console.WriteLine($"{message.Role}: {message.Content}");
// Responses that used extensions will also have Context information that includes special Tool messages
// to explain extension activity and provide supplemental information like citations.
Console.WriteLine($"Citations and other information:");
foreach (var contextMessage in message.AzureExtensionsContext.Messages)
{
    // Note: citations and other extension payloads from the "tool" role are often encoded JSON documents
    // and need to be parsed as such; that step is omitted here for brevity.
    Console.WriteLine($"{contextMessage.Role}: {contextMessage.Content}");
}

// Set a voice name for synthesis
speechConfig.SpeechSynthesisVoiceName = "en-US-AmberNeural";
using var synthesizer = new SpeechSynthesizer(speechConfig);
await synthesizer.SpeakTextAsync(response.Value.Choices[0].Message.Content);
