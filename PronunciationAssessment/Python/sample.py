#
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.
#
# Microsoft Cognitive Services: https://www.microsoft.com/cognitive-services
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License:
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import base64
import requests
import time
import uuid

subscription_key = "{SubscriptionKey}"  # replace this with your subscription key
region = "{Region}"  # replace this with the region corresponding to your subscription key, e.g. westus, eastasia

# A common wave header, with zero audio length
# Since stream data doesn't contain header, but the API requires header to fetch format information,
# so you need post this header as first chunk for each query
WaveHeader16K16BitMono = bytes(
    [
        82,
        73,
        70,
        70,
        78,
        128,
        0,
        0,
        87,
        65,
        86,
        69,
        102,
        109,
        116,
        32,
        18,
        0,
        0,
        0,
        1,
        0,
        1,
        0,
        128,
        62,
        0,
        0,
        0,
        125,
        0,
        0,
        2,
        0,
        16,
        0,
        0,
        0,
        100,
        97,
        116,
        97,
        0,
        0,
        0,
        0,
    ]
)


# A generator which reads audio data chunk by chunk.
# The audio_source can be any audio input stream which provides read() method,
# e.g. audio file, microphone, memory stream, etc.
def get_chunk(audio_source, chunk_size=1024):
    yield WaveHeader16K16BitMono
    while True:
        time.sleep(chunk_size / 32000)  # to simulate human speaking rate
        chunk = audio_source.read(chunk_size)
        if not chunk:
            global upload_finish_time
            upload_finish_time = time.time()
            break
        yield chunk


# Build pronunciation assessment parameters
locale = "en-US"
audio_file = open("../goodmorning.pcm", "rb")
reference_text = "Good morning."
enable_prosody_assessment = True
phoneme_alphabet = "SAPI"  # IPA or SAPI
enable_miscue = True
nbest_phoneme_count = 5
pron_assessment_params_json = (
    '{"GradingSystem":"HundredMark","Dimension":"Comprehensive","ReferenceText":"%s","EnableProsodyAssessment":"%s",'
    '"PhonemeAlphabet":"%s","EnableMiscue":"%s","NBestPhonemeCount":"%s"}'
    % (reference_text, enable_prosody_assessment, phoneme_alphabet, enable_miscue, nbest_phoneme_count)
)
pron_assessment_params_base64 = base64.b64encode(bytes(pron_assessment_params_json, "utf-8"))
pron_assessment_params = str(pron_assessment_params_base64, "utf-8")

# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-get-speech-session-id#provide-session-id-using-rest-api-for-short-audio
session_id = uuid.uuid4().hex

# Build request
url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
url = f"{url}?format=detailed&language={locale}&X-ConnectionId={session_id}"
headers = {
    "Accept": "application/json;text/xml",
    "Connection": "Keep-Alive",
    "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
    "Ocp-Apim-Subscription-Key": subscription_key,
    "Pronunciation-Assessment": pron_assessment_params,
    "Transfer-Encoding": "chunked",
    "Expect": "100-continue",
}

print(f"II URL: {url}")
print(f"II Config: {pron_assessment_params_json}")

# Send request with chunked data
response = requests.post(url=url, data=get_chunk(audio_file), headers=headers)
get_response_time = time.time()
audio_file.close()

# Show Session ID
print(f"II Session ID: {session_id}")

if response.status_code != 200:
    print(f"EE Error code: {response.status_code}")
    print(f"EE Error message: {response.text}")
    exit()
else:
    print(f"II Response: {response.json()}")

latency = get_response_time - upload_finish_time
print(f"II Latency: {int(latency * 1000)}ms")
