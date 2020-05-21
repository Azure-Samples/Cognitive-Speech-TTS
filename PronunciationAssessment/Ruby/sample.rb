###
#Copyright (c) Microsoft Corporation
#All rights reserved. 
#MIT License
#Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
###
require 'json'
require 'base64'
require 'uri'
require 'net/http'

# Note: new unified SpeechService API key and issue token uri is per region
# New unified SpeechService key
# Free: https://azure.microsoft.com/en-us/try/cognitive-services/?api=speech-services
# Paid: https://go.microsoft.com/fwlink/?LinkId=872236
apiKey = ENV["MYKEY"]
region = "westus"

wavheader = [82, 73, 70, 70, 78, 128, 0, 0, 87, 65, 86, 69, 102, 109, 116, 32, 18, 0, 0, 0, 1, 0, 1, 0, 128, 62, 0, 0, 0, 125, 0, 0, 2, 0, 16, 0, 0, 0, 100, 97, 116, 97, 0, 0, 0, 0].pack("C*").force_encoding("ASCII-8BIT")
pcmdata = File.open("../goodmorning.pcm", "rb") { |f| f.read }
data = wavheader + pcmdata

pronAssessmentParams = {
	:ReferenceText => "Good morning.",
	:GradingSystem => "HundredMark",
	:Granularity => "FullText",
	:Dimension => "Comprehensive"
}
pronAssessmentParamsJson = JSON.generate(pronAssessmentParams)
pronAssessmentParamsBase64 = Base64.strict_encode64(pronAssessmentParamsJson)

headers = {
	'Accept': 'application/json;text/xml',
	'Connection': 'Keep-Alive',
	'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
	'Ocp-Apim-Subscription-Key': apiKey,
	'Pronunciation-Assessment': pronAssessmentParamsBase64,
	'Transfer-Encoding': 'chunked',
	'Expect': '100-continue'
}

url = URI.parse("https://#{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-us")
req = Net::HTTP.new(url.host, url.port)
req.use_ssl = true
res = req.post(url, data, headers)
if res.message == "OK"
	puts res.body
else
	puts res.message
end
