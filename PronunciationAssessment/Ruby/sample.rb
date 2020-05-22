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
api_key = ENV["MYKEY"]
region = ENV["MYREGION"]

read_pipe, write_pipe = IO.pipe

waveheader = [82, 73, 70, 70, 78, 128, 0, 0, 87, 65, 86, 69, 102, 109, 116, 32, 18, 0, 0, 0, 1, 0, 1, 0, 128, 62, 0, 0, 0, 125, 0, 0, 2, 0, 16, 0, 0, 0, 100, 97, 116, 97, 0, 0, 0, 0].pack("C*").force_encoding("ASCII-8BIT")
write_pipe.write(waveheader)

offset = 0
chunk_size=1024
chunk_data = IO.binread("../goodmorning.pcm", chunk_size, offset)
while chunk_data
    sleep(chunk_size / 32000) # to simulate human speaking rate
    write_pipe.write(chunk_data)
    offset += chunk_size
    chunk_data = IO.binread("../goodmorning.pcm", chunk_size, offset)
    if not chunk_data
        $upload_finish_time = Time.now
    end
end

pron_assessment_params = {
    :ReferenceText => "Good morning.",
    :GradingSystem => "HundredMark",
    :Dimension => "Comprehensive"
}
pron_assessment_params_json = JSON.generate(pron_assessment_params)
pron_assessment_params_base64 = Base64.strict_encode64(pron_assessment_params_json)

headers = {
    'Accept': 'application/json;text/xml',
    'Connection': 'Keep-Alive',
    'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
    'Ocp-Apim-Subscription-Key': api_key,
    'Pronunciation-Assessment': pron_assessment_params_base64,
    'Transfer-Encoding': 'chunked',
    'Expect': '100-continue'
}

url = URI.parse("https://#{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-us")
req = Net::HTTP.new(url.host, url.port)
req.use_ssl = true

request_thread = Thread.new do
    res = req.post(url, read_pipe.read, headers)
    $get_response_time = Time.now
    if res.message == "OK"
        puts JSON.pretty_generate(JSON.parse(res.body))
    else
        puts res.message
    end
end

write_pipe.close

request_thread.join

puts ($get_response_time - $upload_finish_time) * 1000
