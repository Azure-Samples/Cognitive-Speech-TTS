# Streaming Generate TTS for GPT response
This demo shows how to do `client streaming` to generate TTS audio from GPT like response, like ChatGPT.  
Rather than creating TTS audio from the entire response and enduring extended latency, ChatGPT returns results in a streaming manner, allowing for TTS audio generation each time a complete sentence is received:  
1. Get GPT response token
2. Add the token to a string buffer
3. If token is a sentence end, generate TTS audio from the buffer
4. Repeat 1-3 until GPT response stream is finished
5. Generate TTS audio from the buffer if there is any token left

## How to run
1. Add below environment variables to your system:
```
AZURE_OPENAI_ENDPOINT=https://<my-sub>.openai.azure.com/
AZURE_OPENAI_API_KEY=my_aoai_api_key
AZURE_TTS_API_KEY=my_azure_tts_api_key
AZURE_TTS_REGION=eastus_or_other_region
```
2. Update the query if you want and dotnet run.
```
private static string query = "Tell me a joke about 100 words.";
```

```
dotnet run
```

## Example output
[TTS] means there is a TTS call after the token.  

```
Why did the tomato turn red?

[TTS]Because it saw the salad dressing!

[TTS]Now, while that joke might not be 100 words long, it's still worth a chuckle.[TTS] But if you're looking for something a bit more elaborate, here's a longer joke for you:

[TTS]A panda walks into a restaurant and orders a sandwich.[TTS] After eating the sandwich, the panda pulls out a gun, shoots the waiter, and begins to walk out of the restaurant.

[TTS]The restaurant owner, shocked by what just happened[TTS]
```

## Known issues
The sentence separator is pretty simple, which may do wrong separation for some cases.