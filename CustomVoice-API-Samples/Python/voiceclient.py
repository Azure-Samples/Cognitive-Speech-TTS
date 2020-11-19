import argparse
import json
import ntpath
import urllib3
import requests
import time
from json import dumps, loads, JSONEncoder, JSONDecoder
import pickle


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description='Long audio tool to submit voice synthesis requests.')
parser.add_argument('--voices', action="store_true", default=False, help='print voice list')
parser.add_argument('--voicesynthesis', action="store_true", default=False, help='print synthesis list')
parser.add_argument('--voicesynthesisbyid', action="store_true", default=False, help='print the synthesis by voice synthesis id')
parser.add_argument('--submit', action="store_true", default=False, help='submit a synthesis request')
parser.add_argument('--delete', action="store_true", default=False, help='delete a synthesis request')
parser.add_argument('--concatenateResult', action="store_true", default=False, help='If concatenate result in a single wave file')
parser.add_argument('-file', action="store",  dest="file", help='the input text script file path')
parser.add_argument('-timestart', action="store",  dest="timestart", help='the timestart filter, like 2019-11-21 15:26:21.')
parser.add_argument('-timeend', action="store",  dest="timeend", help='the timeend filter, like 2019-11-21 15:26:21.')
parser.add_argument('-status', action="store",  dest="status", help='the status filter, could be NotStarted/Running/Succeeded/Failed')
parser.add_argument('-skip', action="store", metavar='N', type=int, dest="skip", help='the skip number in query')
parser.add_argument('-top', action="store", metavar='N', type=int, dest="top", help='the top number in query')
parser.add_argument('-voiceId', action="store", nargs='+', dest="voiceId", help='the id of the voice which used to synthesis')
parser.add_argument('-synthesisId', action="store", nargs='+', dest="synthesisId", help='the id of the voice synthesis which need to be queried, or the id list of the voice synthesis which need to deleted')
parser.add_argument('-locale', action="store", dest="locale", help='the locale information like zh-CN/en-US')
parser.add_argument('-format', action="store", dest="format", default='riff-16khz-16bit-mono-pcm', help='the output audio format')
parser.add_argument('-key', action="store", dest="key", required=True, help='the Speech service subscription key, like bb82464444c548dea4dce4376f3c7d26 ')
parser.add_argument('-region', action="store", dest="region", required=True, help='the region information, could be centralindia, canadacentral or uksouth, see the following link for a list of supported regions: https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation')

args = parser.parse_args()

baseAddress = 'https://%s.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0-beta1/' % args.region

def getSubmittedSyntheses():
    url = baseAddress+"voicesynthesis/Paginated?"
    if args.status is not None:
        url = url + "&status=" + args.status
    if args.timestart is not None:
        url = url + "&timestart=" + args.timestart
    if args.timeend is not None:
        url = url + "&timeend=" + args.timeend
    if args.skip is not None:
        url = url + "&skip=" + str(args.skip)
    else:
        url = url + "&skip=0"
    if args.top is not None:
        url = url + "&top=" + str(args.top)
    else:
        url = url + "&top=100"
    url.replace(" ", "%20")
    response=requests.get(url, headers={"Ocp-Apim-Subscription-Key":args.key}, verify=False)
    if response.status_code == 200:
        syntheses = json.loads(response.text)["values"]
        return syntheses
    else:
        print("getSubmittedSyntheses request failed")
        print("response.status_code: %d" % response.status_code)
        print("response.text: %s" % response.text)
        return None

def getSubmittedSynthesis(id):
    response=requests.get(baseAddress+"voicesynthesis/"+id, headers={"Ocp-Apim-Subscription-Key":args.key}, verify=False)
    if response.status_code == 200:
        synthesis = json.loads(response.text)
        return synthesis
    else:
        print("getSubmittedSyntheses with ID request failed")
        print("response.status_code: %d" % response.status_code)
        print("response.text: %s" % response.text)
        return None

def getVoices():
    response=requests.get(baseAddress+"voicesynthesis/voices", headers={"Ocp-Apim-Subscription-Key":args.key}, verify=False)
    if response.status_code == 200:
        voices = json.loads(response.text)
        return voices
    else:
        print("getVoices request failed")
        print("response.status_code: %d" % response.status_code)
        print("response.text: %s" % response.text)
        return None

def deleteSynthesis(ids):
    for id in ids:
        print("delete voice synthesis %s " % id)
        response = requests.delete(baseAddress+"voicesynthesis/"+id, headers={"Ocp-Apim-Subscription-Key":args.key}, verify=False)
        if (response.status_code == 204):
            print("delete successful")
        else:
            print("delete failed, response.status_code: %d, response.text: %s " % (response.status_code, response.text))

def submitSynthesis():
    modelList = args.voiceId
    data={'name': 'simple test', 'description': 'desc...', 'models': json.dumps(modelList), 'locale': args.locale, 'outputformat': args.format}
    if args.concatenateResult:
        properties={'ConcatenateResult': 'true'}
        data['properties'] = json.dumps(properties)
    if args.file is not None:
        scriptfilename=ntpath.basename(args.file)
        files = {'script': (scriptfilename, open(args.file, 'rb'), 'text/plain')}
    response = requests.post(baseAddress+"voicesynthesis", data, headers={"Ocp-Apim-Subscription-Key":args.key}, files=files, verify=False)
    if response.status_code == 202:
        location = response.headers['Location']
        id = location.split("/")[-1]
        print("Submit synthesis request successful , id: %s" % (id))
        return id
    else:
        print("Submit synthesis request failed")
        print("response.status_code: %d" % response.status_code)
        print("response.text: %s" % response.text)
        return 0

if args.voices:
    voices = getVoices()
    print("There are %d voices available:" % len(voices))
    for voice in voices:
        print ("Name: %s, Description: %s, Id: %s, Locale: %s, Gender: %s, PublicVoice: %s, Created: %s" % (voice['name'], voice['description'], voice['id'], voice['locale'], voice['gender'], voice['isPublicVoice'], voice['created']))

if args.voicesynthesis:
    synthese = getSubmittedSyntheses()
    if synthese is not None:
        print("There are %d synthesis requests:" % len(synthese))
        for synthesis in synthese:
            print ("ID : %s , Name : %s, Status : %s " % (synthesis['id'], synthesis['name'], synthesis['status']))

if args.voicesynthesisbyid:
    if args.synthesisId is None:
        print ("-synthesisId is required ")
    else:
        synthesis = getSubmittedSynthesis(args.synthesisId[0])
        if synthesis is not None:
            print ("ID : %s , Name : %s, Status : %s " % (synthesis['id'], synthesis['name'], synthesis['status']))
        else:
            print ("Not found voice synthesis %s " % (args.synthesisId[0]))

if args.delete:
	deleteSynthesis(args.synthesisId)

if args.submit:
    id = submitSynthesis()
    if (id == 0):
        exit(1)

    while(1):
        print("\r\nChecking status , id : %s" % id)
        synthesis=getSubmittedSynthesis(id)
        if synthesis['status'] == "Succeeded":
            r = requests.get(synthesis['resultsUrl'])
            filename=id + ".zip"
            with open(filename, 'wb') as f:  
                f.write(r.content)
                print("Succeeded... Result file downloaded : " + filename)
            break
        elif synthesis['status'] == "Failed":
            print("Failed...")
            break
        elif synthesis['status'] == "Running":
            print("Running...")
        elif synthesis['status'] == "NotStarted":
            print("NotStarted...")
        time.sleep(10)