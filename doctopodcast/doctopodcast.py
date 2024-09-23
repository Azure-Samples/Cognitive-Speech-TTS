# Description: This script converts a pdf file to a podcast using Azure OpenAI GPT-4-O and Azure TTS
import os

# setuop your AOAI endpoint, key and speech resource etc.
AOAI_KEY = os.environ.get('AOAI_GPT4O_KEY')
AOAI_ENDPOINT = "https://<your_aoai_endpoint>.openai.azure.com/"
AOAI_MODEL_NAME = "gpt-4o"
AOAI_MODEL_VERSION = "2024-02-15-preview"
speech_key = os.environ.get('SUBSCRIPTION_SPEECH_KEY')
service_region = os.environ.get('SUBSCRIPTION_SPEECH_REGION')

def printwithtime(*args):
    # show milliseconds
    import datetime
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), *args)

# download file from url
def download(url, filename):
    import requests
    response = requests.get(url)
    with open(filename, 'wb') as file:
        file.write(response.content)    

# convert pdf to text
def pdf2text(pdf_file):
    import PyPDF2
    pdf_file = open(pdf_file, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ''
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += "\n" + page.extract_text()

    return text

# generate first page image
def GenerateCoverImage(pdf_file, outimg):
    import fitz

    # open the pdf file
    pdf_document = fitz.open(pdf_file)

    # get the first page

    first_page = pdf_document[0]

    # get the image of the first page
    image = first_page.get_pixmap()

    # save the image
    image.save(outimg)

    print("Cover image generated: ", outimg)


# extract ssml from pdf with gpt
def CreatePodcastSsml(text):
    # call Azure OpenAI GPT-4
    import os
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_key = AOAI_KEY,  
        api_version = AOAI_MODEL_VERSION,
        azure_endpoint = AOAI_ENDPOINT
        )

    prompt =  """
        Create a conversational, engaging podcast script named 'AI unboxed' between two hosts from the input text. Use informal language like haha, wow etc. and keep it engaging.
        Think step by step, grasp the key points of the paper, and explain them in a conversational tone, at the end, summarize. 
        Output into SSML format like below, please don't change voice name
	    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'>
	    <voice name='en-us-andrew2:DragonHDLatestNeural'>Yeah, probably a ton of it, let's be real.</voice> 
        <voice name='en-us-emma2:DragonHDLatestNeural'>Right! So, Notebook LM is like having this super-smart research assistant who not only reads all of it for you but can also answer any question you have about that information.</voice>
        </speak>
        """
    podcasttext = ""
    trycount = 3
    while trycount > 0:
        try:
            completion = client.chat.completions.create(
                model=AOAI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=4096,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None)
            
            podcasttext = completion.choices[0].message.content 
            break
        except Exception as e:
            print(e)
            trycount -= 1
            continue

    # create ssml
    return podcasttext 

# generate audio with Azure TTS HD voices
def GenerateAudio(ssml, outaudio):
    import azure.cognitiveservices.speech as speechsdk
    import os
    # speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config = speechsdk.SpeechConfig(subscription=os.getenv("SUBSCRIPTION_KEY_DEV"), endpoint="https://dev.tts-frontend.speech-test.microsoft.com/synthesize/internal?traffictype=videodubber")

    # Creates an audio configuration that points to an audio file.
    audio_output = speechsdk.audio.AudioOutputConfig(filename=outaudio)

    # Creates a speech synthesizer using the Azure Speech Service.
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_output)

    # Synthesizes the received text to speech.
    result = speech_synthesizer.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesis was successful. Audio was written to '{}'".format(outaudio))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
        print("Did you update the subscription info?")

# generate pod cast workflow
def GeneratePodcast(url, outaudio, coverimage = None):    
    temp_pdf = 'temp.pdf'
    printwithtime("Generating podcast from pdf file: ", url)
    # download the file
    print("Downloading file")
    download(url, temp_pdf)

    # convert pdf to text
    printwithtime("Converting pdf to text")
    text = pdf2text(temp_pdf)

    # generate cover image
    printwithtime("Generating cover image")
    pdfimage = outaudio.split(".")[0] + ".png"
    GenerateCoverImage(temp_pdf, pdfimage)

    if coverimage is None:
        coverimage = pdfimage        

    # create podcast ssml
    printwithtime("Creating podcast ssml")
    ssml = CreatePodcastSsml(text)
    print(ssml)
    
    # generate podcast
    printwithtime("Generating podcast with Azure TTS")
    GenerateAudio(ssml, outaudio)

    # generate video
    printwithtime("Generating video")
    GenerateVideo(outaudio, temp_pdf, outaudio.split(".")[0] + ".mp4")

def GenerateVideo(audiofile, pdffile, outvideo):
    from moviepy.editor import ImageClip, concatenate_videoclips, AudioClip, AudioFileClip

    import fitz
    # open the pdf file
    pdf_document = fitz.open(pdffile)


    # List to store individual image clips
    clips = []

    # get audio file duration
    from pydub import AudioSegment
    audio = AudioSegment.from_file(audiofile)
    duration = audio.duration_seconds

    # number of pages
    num_pages = len(pdf_document) + 1

    if num_pages > 0:
        duration_per_page = duration / num_pages

    # Create an ImageClip from each image
    cover = "aiunboxed.png"
    if os.path.exists(cover):
        clip = ImageClip(cover, duration=duration_per_page)  # Duration of 3 seconds per image       
        clips.append(clip)

    # get cover image width and height
    cover_image = ImageClip(cover)
    cwidth, cheight = cover_image.size

    for page in pdf_document:
        # get the first page
        first_page = page

        # get the image of the first page with high resolution
        image = first_page.get_pixmap(matrix=fitz.Matrix(2, 2))        

        img = "page.png"
        # save the image
        image.save(img)

        # Create an ImageClip from each image
        clip = ImageClip(img, duration=duration_per_page)  # Duration of 3 seconds per image       

        # resize the image to cover image size
        resized_clip = clip.resize(height = cheight)
    
        clips.append(resized_clip)

    # Concatenate the clips to form the final slideshow
    slideshow = concatenate_videoclips(clips, method="compose")

    # load audio file into audio clip
    audio_clip = AudioFileClip(audiofile)

    # Add the audio to the slideshow
    slideshow = slideshow.set_audio(audio_clip)
    
    # Export the video with animations with high compression    
    slideshow.write_videofile(outvideo, codec="libx264", fps = 4, threads=4)


# helper
def GeneratePodcastFromUrl(url, outaudio = None):
    # get the file name from url
    if outaudio is None:
        outaudio  = url.split("/")[-1].split(".")[0] + ".wav"
    GeneratePodcast(url, outaudio)

# main func
if __name__ == "__main__":
    GeneratePodcastFromUrl("https://kyutai.org/Moshi.pdf")
   