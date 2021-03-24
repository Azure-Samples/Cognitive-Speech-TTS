package main

import (
	"bytes"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"time"
)

// auth token
// var token = ""

func GetToken(auth string, key string) string {
	postData := []byte("")

	req, err := http.NewRequest("POST", auth, bytes.NewBuffer(postData))
	if err != nil {
		log.Printf("New request with error %s\n", err)
	}

	token := ""
	req.Header.Set("Ocp-Apim-Subscription-Key", key)
	response, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("Do request failed with error %s\n", err)
	} else {
		defer response.Body.Close()
		data, _ := ioutil.ReadAll(response.Body)
		token = string(data)
		log.Println("token is", token)
	}

	return token
}

func GetAudioBytes(client *http.Client, endpoint string, authToken string, ssml string) {
	start := time.Now()
	postData := []byte(ssml)
	req, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(postData))
	if err != nil {
		log.Printf("New request with error %s\n", err)
		return
	}

	req.Header.Set("content-type", "application/ssml+xml")
	req.Header.Set("X-Microsoft-OutputFormat", "riff-24khz-16bit-mono-pcm")
	req.Header.Set("Authorization", "Bearer "+authToken)
	req.Header.Set("User-Agent", "GoClient")
	response, err := client.Do(req)
	if err != nil {
		log.Printf("Do request failed with error %s\n", err)
	} else {
		defer response.Body.Close()
		if response.StatusCode == 200 {
			data, _ := ioutil.ReadAll(response.Body)
			log.Println("audio byte len is", len(data))
			ioutil.WriteFile("output.wav", data, 0644)
		} else {
			log.Println("status code is", response.StatusCode)
		}
	}

	elapsed := time.Since(start)
	log.Printf("GetAudioBytes took %s", elapsed)
}

func main() {

	f, err := os.OpenFile("run.log", os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		log.Fatalf("error opening file: %v", err)
		return
	}
	defer f.Close()
	wrt := io.MultiWriter(os.Stdout, f)
	log.SetOutput(wrt)
	log.Println("Starting the application...")

	endpoint := "https://southeastasia.tts.speech.microsoft.com/cognitiveservices/v1"
	auth := "https://southeastasia.api.cognitive.microsoft.com/sts/v1.0/issueToken"
	key := "your Speech service subscription key"

	token := GetToken(auth, key)
	ticker := time.NewTicker(300 * time.Second)
	go func() {
		for range ticker.C {
			log.Println("Refreshing token")
			t := GetToken(auth, key)
			if len(t) != 0 {
				token = t
			}
		}
	}()

	tr := &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20,
	}

	for {
		time.Sleep(100 * time.Millisecond)

		client := &http.Client{
			Transport: tr,
		}

		GetAudioBytes(client, endpoint, token, "<speak version='1.0' xml:lang='en-us'><voice name='en-US-AriaNeural'>Hello world!</voice></speak>")
	}
}
