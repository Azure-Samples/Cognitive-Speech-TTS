//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/Cognitive-Speech-TTS
//
// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License:
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
//
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED ""AS IS"", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
// LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
// WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

package com.microsoft.cognitiveservices.pronunciationassessment;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.util.Base64;

import javax.net.ssl.HttpsURLConnection;

public class Sample {
	public static void main(String[] args) throws Exception {
		
		String subscriptionKey = "{SubscriptionKey}"; // replace this with your subscription key
		String region = "{Region}"; // replace this with the region corresponding to your subscription key, e.g. westus, eastasia
		
		// a common wave header, with zero audio length
		// since stream data doesn't contain header, but the API requires header to fetch format information, so you need post this header as first chunk for each query
		final byte[] WaveHeader16K16BitMono = new byte[] { 82, 73, 70, 70, 78, (byte)128, 0, 0, 87, 65, 86, 69, 102, 109, 116, 32, 18, 0, 0, 0, 1, 0, 1, 0, (byte)128, 62, 0, 0, 0, 125, 0, 0, 2, 0, 16, 0, 0, 0, 100, 97, 116, 97, 0, 0, 0, 0 };
		
		// build pronunciation assessment parameters
		String referenceText = "Good morning.";
		String pronAssessmentParamsJson = "{\"ReferenceText\":\"" + referenceText + "\",\"GradingSystem\":\"HundredMark\",\"Dimension\":\"Comprehensive\"}";
		byte[] pronAssessmentParamsBase64 = Base64.getEncoder().encode(pronAssessmentParamsJson.getBytes("utf-8"));
		String pronAssessmentParams = new String(pronAssessmentParamsBase64, "utf-8");
		
		// build request (when re-run below code in short time, the connect can be cached and reused behind, with lower connecting time cost)
		URL url = new URL("https://" + region + ".stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-us");
		HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
		connection.setRequestMethod("POST");
		connection.setDoOutput(true);
		connection.setChunkedStreamingMode(0);
		connection.setRequestProperty("Accept", "application/json;text/xml");
		connection.setRequestProperty("Content-Type", "audio/wav; codecs=audio/pcm; samplerate=16000");
		connection.setRequestProperty("Ocp-Apim-Subscription-Key", subscriptionKey);
		connection.setRequestProperty("Pronunciation-Assessment", pronAssessmentParams);
		
		// send request with chunked data
		File file = new File("../../goodmorning.pcm");
		FileInputStream fileStream = new FileInputStream(file);
		byte[] audioChunk = new byte[1024];
		
		OutputStream outputStream = connection.getOutputStream();
		outputStream.write(WaveHeader16K16BitMono);
		int chunkSize = fileStream.read(audioChunk);
		while (chunkSize > 0)
		{
			Thread.sleep(chunkSize / 32); // to simulate human speaking rate
			outputStream.write(audioChunk, 0, chunkSize);
			chunkSize = fileStream.read(audioChunk);
		}

		fileStream.close();
		outputStream.flush();
		outputStream.close();
		
		long uploadFinishTime = System.currentTimeMillis();
		
		// receive response
		byte[] responseBuffer = new byte[connection.getContentLength()];
		InputStream inputStream = connection.getInputStream();
		inputStream.read(responseBuffer);
		String result = new String(responseBuffer, "utf-8"); // the result is a JSON, you can parse it with a JSON library 

		System.out.println("Pronunciation assessment result:\n");
		System.out.println(result);
		
		long getResponseTime = System.currentTimeMillis();
		System.out.println("\nLatency: " + (getResponseTime - uploadFinishTime) + "ms");
	}
}
