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

package com.microsoft.cognitiveservices.ttssample;

import java.io.File;
import java.io.FileOutputStream;

import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioInputStream;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.SourceDataLine;

public class TTSSample {

	public static void main(String[] args) {
		String textToSynthesize = "This is a demo to call microsoft text to speech service in java.";
		String outputFormat = AudioOutputFormat.Riff16Khz16BitMonoPcm;
        String deviceLanguage = "en-US";
        String genderName = Gender.Female;
        String voiceName = "Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)";

        try{
        	byte[] audioBuffer = TTSService.Synthesize(textToSynthesize, outputFormat, deviceLanguage, genderName, voiceName);
        	
        	// write the pcm data to the file
        	String outputWave = ".\\output.pcm";
        	File outputAudio = new File(outputWave);
        	FileOutputStream fstream = new FileOutputStream(outputAudio);
            fstream.write(audioBuffer);
            fstream.flush();
            fstream.close();
            
            
            // specify the audio format 
           	AudioFormat audioFormat = new AudioFormat(
           			AudioFormat.Encoding.PCM_SIGNED,
               		16000,
               		16,
               		1,
               		1 * 2,
               		16000,
               		false);
           	
               AudioInputStream audioInputStream = AudioSystem.getAudioInputStream(new File(outputWave));
               
               DataLine.Info dataLineInfo = new DataLine.Info(SourceDataLine.class,
                       audioFormat, AudioSystem.NOT_SPECIFIED);
               SourceDataLine sourceDataLine = (SourceDataLine) AudioSystem
                       .getLine(dataLineInfo);
               sourceDataLine.open(audioFormat);
               sourceDataLine.start();
               System.out.println("start to play the wave:");
               /*
                * read the audio data and send to mixer
                */
               int count;
               byte tempBuffer[] = new byte[4096];
               while ((count = audioInputStream.read(tempBuffer, 0, tempBuffer.length)) >0) {
                       sourceDataLine.write(tempBuffer, 0, count);
               }
        
               sourceDataLine.drain();
               sourceDataLine.close();
               audioInputStream.close();
               
        }catch(Exception e){
        	e.printStackTrace();
        }
   }

}
