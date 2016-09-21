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
package com.microsoft.ttshttpoxford.ttssample;

import android.support.v7.app.ActionBarActivity;
import android.os.Bundle;
import android.text.method.ScrollingMovementMethod;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import com.microsoft.speech.tts.*;

public class TTSHttpOxfordMainActivity extends ActionBarActivity {

    private TextView status;
    private EditText txtContent;
    private Button btnSynthesize;
    private String textToSynthesize;
    private Synthesizer m_syn;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_tts_main);
        status = (TextView)findViewById(R.id.status);
        status.setMovementMethod(new ScrollingMovementMethod());
        txtContent = (EditText)findViewById(R.id.txtContent);
        txtContent.setMovementMethod(new ScrollingMovementMethod());
        btnSynthesize = (Button)findViewById(R.id.btnSynthesize);

        // Note: The way to get api key:
        // Free: https://www.microsoft.com/cognitive-services/en-us/subscriptions?productId=/products/Bing.Speech.Preview
        // Paid: https://portal.azure.com/#create/Microsoft.CognitiveServices/apitype/Bing.Speech/pricingtier/S0
        m_syn = new Synthesizer("Your api key");
        Voice v = new Voice("en-US", "Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)", Voice.Gender.Female, true);
        m_syn.SetVoice(v, null);
        btnSynthesize.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                textToSynthesize = txtContent.getText().toString().trim();
                if(textToSynthesize == null || textToSynthesize.isEmpty()){
                    status.setText("The text to synthesize is empty!");
                }else{
                    status.setText("Synthesize...");
                    m_syn.SpeakToAudio(textToSynthesize);
                }
            }
        });
    }
}
