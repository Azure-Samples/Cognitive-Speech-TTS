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
require 'ruby_speech'

# A note to fix an SSL error
puts "if encounter the Error: SSL_connect returned=1 errno=0 state=SSLv3 read server certificate B: certificate verify failed, find the fix in https://gist.github.com/fnichol/867550\n"

# Note: The way to get api key:
# Free: https://www.microsoft.com/cognitive-services/en-us/subscriptions?productId=/products/Bing.Speech.Preview
# Paid: https://portal.azure.com/#create/Microsoft.CognitiveServices/apitype/Bing.Speech/pricingtier/S0
apiKey = "Your api key goes here"

post_data = ""

#print (post_data)
url = URI.parse("https://api.cognitive.microsoft.com/sts/v1.0/issueToken")
http = Net::HTTP.new(url.host, url.port)
http.use_ssl = true


headers = {
  'Ocp-Apim-Subscription-Key' => apiKey
}

# get the Access Token
puts "get the Access Token"
resp = http.post(url.path, post_data, headers)
puts "Access Token: ", resp.body, "\n"

accessToken = resp.body

ttsServiceUri = "https://speech.platform.bing.com:443/synthesize"
url = URI.parse(ttsServiceUri)
http = Net::HTTP.new(url.host, url.port)
http.use_ssl = true

headers = {
	'content-type' => 'application/ssml+xml',
	'X-Microsoft-OutputFormat' => 'riff-16khz-16bit-mono-pcm',
	'Authorization' => 'Bearer ' + accessToken,
	'X-Search-AppId' => '07D3234E49CE426DAA29772419F436CA',
	'X-Search-ClientID' => '1ECFAE91408841A480F00935DC390960',
	'User-Agent' => 'TTSRuby'
}

# SsmlTemplate = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>"
data = RubySpeech::SSML.draw do
  voice gender: :female, name: 'Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)', language: 'en-US' do
    string 'This is a demo to call microsoft text to speech service in ruby'
  end
end

# get the wave data
puts "get the wave data"
resp = http.post(url.path, data.to_s, headers)

puts "wave data length: ", resp.body.length