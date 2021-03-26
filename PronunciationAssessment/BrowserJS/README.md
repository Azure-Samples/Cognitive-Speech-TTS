To run on local (in terminal):
 
1. git clone the code
2. open the application.py file and enter your subscription_key and region values
3. Download and extract the [Speech SDK for JavaScript](https://aka.ms/csspeech/jsbrowserpackage)  microsoft.cognitiveservices.speech.sdk.bundle.js file, and place it in a folder accessible to your HTML file - static folder 

In cmd line, type the following commands:

1. cd pronunciationdash
\\activate your virtualenv\\
2. pip install -r requirements.txt
3. set FLASK_APP=application.py
4. set FLASK_ENV=development
5. flask run
