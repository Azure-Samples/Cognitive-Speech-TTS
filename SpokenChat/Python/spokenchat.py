import openai, os, requests
import azure.cognitiveservices.speech as speechsdk

# Azure OpenAI setup
# Azure OpenAI on your own data is only supported by the 2023-08-01-preview API version
openai.api_type = "azure"
openai.api_version = "2023-08-01-preview"
openai.api_base = 'OPEN_AI_ENDPOINT' # Add your endpoint here
openai.api_key = os.getenv("OPENAI_API_KEY") # Add your OpenAI API key here
deployment_id = "DEPLOYMENT_NAME" # Add your deployment ID here

# Azure Cognitive Search setup
search_endpoint = "SEARCH_ENDPOINT"; # Add your Azure Cognitive Search endpoint here
search_key = os.getenv("SEARCH_KEY"); # Add your Azure Cognitive Search admin key here
search_index_name = "speechdoc"; # Add your Azure Cognitive Search index name here

# setup speech configuration 
speech_config = speechsdk.SpeechConfig(
  subscription=os.getenv("OPENAI_API_KEY"),
  region="eastus"
)

def setup_byod(deployment_id: str) -> None:
    """Sets up the OpenAI Python SDK to use your own data for the chat endpoint.

    :param deployment_id: The deployment ID for the model to use with your own data.

    To remove this configuration, simply set openai.requestssession to None.
    """

    class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):

        def send(self, request, **kwargs):
            request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
            return super().send(request, **kwargs)

    session = requests.Session()

    # Mount a custom adapter which will use the extensions endpoint for any call using the given `deployment_id`
    session.mount(
        prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
        adapter=BringYourOwnDataAdapter()
    )

    openai.requestssession = session

setup_byod(deployment_id)

# Get the text from the microphone
audio_config = speechsdk.audio.AudioConfig(
  use_default_microphone=True)
speech_config.speech_recognition_language="en-US"
speech_recognizer = speechsdk.SpeechRecognizer(
  speech_config, 
  audio_config)

print("Say something...")
speech_result = speech_recognizer.recognize_once_async().get()

message_text = [{"role": "user", "content": speech_result.text}]

completion = openai.ChatCompletion.create(
    messages=message_text,
    deployment_id=deployment_id,
    dataSources=[  # camelCase is intentional, as this is the format the API expects
        {
            "type": "AzureCognitiveSearch",
            "parameters": {
                "endpoint": search_endpoint,
                "key": search_key,
                "indexName": search_index_name,
            }
        }
    ]
)
print(completion)

# Play the result on the computer's speaker
speech_config.speech_synthesis_voice_name = "en-US-AmberNeural"
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config)
speech_synthesizer.speak_text(
  completion['choices'][0]['message']['content'])
