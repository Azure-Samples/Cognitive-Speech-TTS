#Note: The openai-python library support for Azure OpenAI is in preview.
import os
import openai
import azure.cognitiveservices.speech as speechsdk

openai.api_type = "azure"
openai.api_base = "https://docs-azure-ai-resource-aiservices.openai.azure.com/"
openai.api_version = "2023-07-01-preview"
openai.api_key = os.getenv("AI_SERVICES_KEY")
# setup speech configuration 
speech_config = speechsdk.SpeechConfig(
  subscription=os.getenv("AI_SERVICES_KEY"), 
  region="eastus2"
)

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
  engine="gpt-35-turbo-16k",
  messages = message_text,
  temperature=0.7,
  max_tokens=800,
  top_p=0.95,
  frequency_penalty=0,
  presence_penalty=0,
  stop=None
)

# Play the result on the computer's speaker
speech_config.speech_synthesis_voice_name = "en-US-JasonNeural"
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config)
speech_synthesizer.speak_text(
  completion['choices'][0]['message']['content'])