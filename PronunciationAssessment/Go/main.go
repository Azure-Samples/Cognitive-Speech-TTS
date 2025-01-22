//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.

// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services

// Copyright (c) Microsoft Corporation
// All rights reserved.

// MIT License:
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:

// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"os"
	"time"
)

const (
	subscriptionKey = "" // replace this with your subscription key
	region          = "" // replace this with the region corresponding to your subscription key, e.g. westus, eastasia
	locale          = "en-US"
	audioFilePath   = "../goodmorning.pcm"
	referenceText   = "Good morning."
	chunkSize       = 1024
)

// A common wave header, with zero audio length
// Since stream data doesn't contain header, but the API requires header to fetch format information,
// so you need post this header as first chunk for each query
var waveHeader16K16BitMono = []byte{
	82, 73, 70, 70, 78, 128, 0, 0, 87, 65, 86, 69, 102, 109, 116, 32, 18, 0, 0, 0, 1, 0, 1, 0,
	128, 62, 0, 0, 0, 125, 0, 0, 2, 0, 16, 0, 0, 0, 100, 97, 116, 97, 0, 0, 0, 0,
}

type PronunciationAssessmentParams struct {
	GradingSystem           string `json:"GradingSystem"`
	Dimension               string `json:"Dimension"`
	ReferenceText           string `json:"ReferenceText"`
	EnableProsodyAssessment string `json:"EnableProsodyAssessment"`
	PhonemeAlphabet         string `json:"PhonemeAlphabet"`
	EnableMiscue            string `json:"EnableMiscue"`
	NBestPhonemeCount       string `json:"NBestPhonemeCount"`
}

func getChunk(audioFile *os.File, chunkSize int) <-chan []byte {
	chunks := make(chan []byte)
	go func() {
		defer close(chunks)
		chunks <- waveHeader16K16BitMono
		buffer := make([]byte, chunkSize)
		for {
			n, err := audioFile.Read(buffer)
			if n > 0 {
				chunks <- buffer[:n]
			}
			if err == io.EOF {
				break
			}
			time.Sleep(time.Duration(chunkSize) * time.Millisecond / 32)
		}
	}()
	return chunks
}

func main() {
	// Open audio file
	audioFile, err := os.Open(audioFilePath)
	if err != nil {
		fmt.Printf("Error opening audio file: %v\n", err)
		return
	}
	defer audioFile.Close()

	// Create pronunciation assessment parameters
	params := PronunciationAssessmentParams{
		GradingSystem:           "HundredMark",
		Dimension:               "Comprehensive",
		ReferenceText:           referenceText,
		EnableProsodyAssessment: "true",
		PhonemeAlphabet:         "SAPI", // IPA or SAPI
		EnableMiscue:            "true",
		NBestPhonemeCount:       "5",
	}
	paramsJSON, _ := json.Marshal(params)
	paramsBase64 := base64.StdEncoding.EncodeToString(paramsJSON)

	// Generate session ID
	// https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-get-speech-session-id#provide-session-id-using-rest-api-for-short-audio
	sessionID := fmt.Sprintf("%x", rand.Int63())

	// Build request URL
	url := fmt.Sprintf(
		"https://%s.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?format=detailed&language=%s&X-ConnectionId=%s",
		region, locale, sessionID,
	)

	headers := map[string]string{
		"Accept":                    "application/json;text/xml",
		"Connection":                "Keep-Alive",
		"Content-Type":              "audio/wav; codecs=audio/pcm; samplerate=16000",
		"Ocp-Apim-Subscription-Key": subscriptionKey,
		"Pronunciation-Assessment":  paramsBase64,
		"Transfer-Encoding":         "chunked",
		"Expect":                    "100-continue",
	}

	// Prepare HTTP client and request
	client := &http.Client{}
	pipeReader, pipeWriter := io.Pipe()
	go func() {
		for chunk := range getChunk(audioFile, chunkSize) {
			_, err := pipeWriter.Write(chunk)
			if err != nil {
				fmt.Printf("Error writing chunk: %v\n", err)
				return
			}
		}
		pipeWriter.Close()
	}()

	req, err := http.NewRequest("POST", url, pipeReader)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return
	}

	for key, value := range headers {
		req.Header.Set(key, value)
	}

	// Send request
	startTime := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return
	}
	defer resp.Body.Close()

	// Read response
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Printf("Error reading response: %v\n", err)
		return
	}

	// Show Session ID
	fmt.Printf("Session ID: %s\n", sessionID)

	if resp.StatusCode != 200 {
		fmt.Printf("Error response code: %d\n", resp.StatusCode)
		fmt.Printf("Error message: %s\n", responseBody)
		return
	}

	latency := time.Since(startTime).Milliseconds()
	fmt.Printf("Response: %s\n", responseBody)
	fmt.Printf("Latency: %dms\n", latency)
}
