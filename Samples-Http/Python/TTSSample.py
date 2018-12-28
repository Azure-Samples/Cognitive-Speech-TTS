'''
This sample demonstrates how to call the text-to-speech endpoint, capture
a user input, and write the respone to file. Each file is saved as .wav, and is
timestamped. For additional voices, and output formats, please use the API
reference: https://docs.microsoft.com/azure/cognitive-services/speech-service/rest-apis#text-to-speech-api
'''

# Make sure to install requests before running this script: pip install requests.

import os, requests, time

try: input = raw_input
except NameError: pass

class TextToSpeech(object):
    def __init__(self, subscription_key):
        self.subscription_key = subscription_key
        self.tts = input("What would you like to convert to speech: ")
        self.timestr = time.strftime("%Y%m%d-%H%M")
        self.access_token = None

    # This function performs the token exchange.
    def get_token(self):
        fetch_token_url = "https://westus.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        headers = {
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        response = requests.post(fetch_token_url, headers=headers)
        self.access_token = str(response.text)

    # This function calls the TTS endpoint with the access token.
    def save_audio(self):
        base_url = 'https://westus.tts.speech.microsoft.com/'
        path = 'cognitiveservices/v1'
        constructed_url = base_url + path
        headers = {
            'Authorization': 'Bearer ' + self.access_token,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
            'User-Agent': 'YOUR_RESOURCE_NAME',
            'cache-control': 'no-cache'
        }
        body = "<speak version='1.0' xml:lang='en-US'><voice xml:lang='en-US' xml:gender='Female' name='Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)'>" + self.tts + "</voice></speak>"

        response = requests.post(constructed_url, headers=headers, data=body)
        # Write the response as a wav file for playback. The file is located
        # in the same directory where this sample is run.
        if response.status_code == 200:
            with open('sample-' + self.timestr + '.wav', 'wb') as audio:
                audio.write(response.content)
                print("\nStatus code: " + str(response.status_code) + "\nYour TTS is ready for playback.\n")
        else:
            print("\nStatus code: " + str(response.status_code) + "\nSomething went wrong. Check your subscription key and headers.\n")

if __name__ == "__main__":
    # This reads from an environment variable. You can replace the value with
    # your key as a string. For example:
	# subscription_key = "YOUR_KEY_GOES_HERE"
    subscription_key = os.environ['SPEECH_SERVICE_KEY']
    app = TextToSpeech(subscription_key)
    app.get_token()
    app.save_audio()
