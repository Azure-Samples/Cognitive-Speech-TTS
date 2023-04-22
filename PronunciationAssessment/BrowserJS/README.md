![image](https://user-images.githubusercontent.com/31500515/112596487-e4513100-8e31-11eb-9cd1-d08c93887409.png)
This Pronunciation Assessment Browser sample code allows you to test the Azure Speech Service Pronunciation Assessment feature in your own browser. You can simply enter your reference text or choose a random Tongue Twister and click on the record button to test your voice.
![image](https://user-images.githubusercontent.com/31500515/112596145-6c830680-8e31-11eb-9d88-26eca37df10e.png)
You can also play the Learn Pronunciation button to hear back the correct Pronunciation for the text.

Note: This is a Python Flask app and JavaScript based sample. It uses the en-US locale for Pronunciation Assessment and the en-GB LibbyNeural voice for TTS playback. You can change the TTS voice by editing the code.

Bonus - you can also test the read along experience on localhost/readalong
![image](https://user-images.githubusercontent.com/31500515/112596985-8e30bd80-8e32-11eb-9fb2-385105e7ab96.png)

Instructions on how to run this sample:

To run on local (in terminal):

1. git clone the code
2. open the application.py file and enter your subscription_key and region values for your Azure Speech Service resource.
3. Download and extract the [Speech SDK for JavaScript](https://aka.ms/csspeech/jsbrowserpackage)  microsoft.cognitiveservices.speech.sdk.bundle.js file, and place it in a folder accessible to your HTML file - static folder

In cmd line, type the following commands:

1. cd BrowserJS
   \\activate your virtualenv\\
2. pip install -r requirements.txt
3. set FLASK_APP=application.py  
4. set FLASK_ENV=development   
5. flask run

Note: For Ubuntu, change `set` to `export`

3. `export FLASK_APP=application.py`
4. `export FLASK_ENV=development`

