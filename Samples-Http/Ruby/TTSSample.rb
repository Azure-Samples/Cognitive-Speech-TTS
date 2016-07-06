###
#Copyright (c) Microsoft Corporation
#All rights reserved. 
#MIT License
#Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
###
require 'net/http'
require 'net/https'
require 'uri'
require 'json'

# A note to fix an SSL error
puts "if encounter the Error: SSL_connect returned=1 errno=0 state=SSLv3 read server certificate B: certificate verify failed, find the fix in https://gist.github.com/fnichol/867550\n"

# Note: Sign up at http://www.projectoxford.ai to get a subscription key.  
# Search for Speech APIs from Azure Marketplace.  
# Use the subscription key as Client secret below.
clientId = "Your ClientId goes here"
clientSecret = "Your Client Secret goes here"
speechHost = "https://speech.platform.bing.com"
post_data = "grant_type=client_credentials&client_id=" + URI.encode(clientId) + "&client_secret=" + URI.encode(clientSecret) + "&scope=" + URI.encode(speechHost)

#print (post_data)
url = URI.parse("https://oxford-speech.cloudapp.net:443/token/issueToken")
http = Net::HTTP.new(url.host, url.port)
http.use_ssl = true


headers = {
  'content-type' => 'application/x-www-form-urlencoded'
}

# get the Oxford Access Token in json
resp = http.post(url.path, post_data, headers)
puts "Oxford Access Token: ", resp.body, "\n"

# decode the json to get the Oxford Access Token object.
OxfordAccessToken = JSON.parse(resp.body)

ttsServiceUri = "https://speech.platform.bing.com:443/synthesize"
url = URI.parse(ttsServiceUri)
http = Net::HTTP.new(url.host, url.port)
http.use_ssl = true

headers = {
	'content-type' => 'application/ssml+xml',
	'X-Microsoft-OutputFormat' => 'riff-16khz-16bit-mono-pcm',
	'Authorization' => 'Bearer ' + OxfordAccessToken["access_token"],
	'X-Search-AppId' => '07D3234E49CE426DAA29772419F436CA',
	'X-Search-ClientID' => '1ECFAE91408841A480F00935DC390960',
	'User-Agent' => 'TTSRuby'
}

# SsmlTemplate = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>"
data = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='en-US' xml:gender='Female' name='Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)'>This is a demo to call microsoft text to speach service in php.</voice></speak>"

# get the wave data
resp = http.post(url.path, data, headers)

puts "wave data length: ", resp.body.length