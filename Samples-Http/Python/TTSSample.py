###
#Copyright (c) Microsoft Corporation
#All rights reserved. 
#MIT License
#Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
###
import http.client, urllib.parse, json

#Note: Sign up at http://www.projectoxford.ai to get a subscription key.  
#Search for Speech APIs from Azure Marketplace.
#Use the subscription key as Client secret below.
clientId = "Your ClientId goes here"
clientSecret = "Your Client Secret goes here"
ttsHost = "https://speech.platform.bing.com"

params = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': clientId, 'client_secret': clientSecret, 'scope': ttsHost})

print ("The body data: %s" %(params))

headers = {"Content-type": "application/x-www-form-urlencoded"}
			
AccessTokenHost = "oxford-speech.cloudapp.net"
path = "/token/issueToken"

# Connect to server to get the Oxford Access Token
conn = http.client.HTTPSConnection(AccessTokenHost)
conn.request("POST", path, params, headers)
response = conn.getresponse()
print(response.status, response.reason)

data = response.read()
conn.close()

accesstoken = data.decode("UTF-8")
print ("Oxford Access Token: " + accesstoken)

#decode the object from json
ddata=json.loads(accesstoken)
access_token = ddata['access_token']

body = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='en-us' xml:gender='Female' name='Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)'>This is a demo to call microsoft text to speach service in python.</voice></speak>"

headers = {"Content-type": "application/ssml+xml", 
			"X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm", 
			"Authorization": "Bearer " + access_token, 
			"X-Search-AppId": "07D3234E49CE426DAA29772419F436CA", 
			"X-Search-ClientID": "1ECFAE91408841A480F00935DC390960", 
			"User-Agent": "TTSForPython"}
			
#Connect to server to synthesize the wave
conn = http.client.HTTPSConnection("speech.platform.bing.com")
conn.request("POST", "/synthesize", body, headers)
response = conn.getresponse()
print(response.status, response.reason)

data = response.read()
conn.close()
print("The synthesized wave length: %d" %(len(data)))