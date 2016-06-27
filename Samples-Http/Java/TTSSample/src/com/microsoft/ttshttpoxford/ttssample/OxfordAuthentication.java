//
// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.
//
// Microsoft Cognitive Services (formerly Project Oxford): https://www.microsoft.com/cognitive-services
//
// Microsoft Cognitive Services (formerly Project Oxford) GitHub:
// https://github.com/Microsoft/ProjectOxford-ClientSDK
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

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.net.URLEncoder;
import java.util.Timer;
import java.util.TimerTask;

import javax.net.ssl.HttpsURLConnection;

/*
     * This class demonstrates how to get a valid O-auth token from
     * Azure Data Market.
     */
public class OxfordAuthentication
{
    public static final String AccessTokenUri = "https://oxford-speech.cloudapp.net/token/issueToken";

    private String clientId;
    private String clientSecret;
    private String request;
    private OxfordAccessToken token;
    private Timer accessTokenRenewer;

    //Access token expires every 10 minutes. Renew it every 9 minutes only.
    private final int RefreshTokenDuration = 9 * 60 * 1000;
    private final String charsetName = "utf-8";
    private TimerTask nineMinitesTask = null;

    public OxfordAuthentication(String clientId, String clientSecret)
    {
        this.clientId = clientId;
        this.clientSecret = clientSecret;

            /*
             * If clientid or client secret has special characters, encode before sending request
             */
        try{
        this.request = String.format("grant_type=client_credentials&client_id=%s&client_secret=%s&scope=%s",
                URLEncoder.encode(clientId,charsetName),
                URLEncoder.encode(clientSecret, charsetName),
                URLEncoder.encode("https://speech.platform.bing.com",charsetName));

        }catch (Exception e){
            e.printStackTrace();
        }
        this.token = HttpPost(AccessTokenUri, this.request);

        // renew the token every specified minutes
        accessTokenRenewer = new Timer();
        nineMinitesTask = new TimerTask(){
            public void run(){
                RenewAccessToken();
            }
        };

        accessTokenRenewer.schedule(nineMinitesTask, 0, RefreshTokenDuration);
    }

    public OxfordAccessToken GetAccessToken()
    {
        return this.token;
    }

    private void RenewAccessToken()
    {
        OxfordAccessToken newAccessToken = HttpPost(AccessTokenUri, this.request);
        //swap the new token with old one
        //Note: the swap is thread unsafe
        System.out.println("new access token: " + newAccessToken.access_token);
        this.token = newAccessToken;
    }

    private OxfordAccessToken HttpPost(String AccessTokenUri, String requestDetails)
    {
        InputStream inSt = null;
        HttpsURLConnection webRequest = null;

        //Prepare OAuth request
        try{
            webRequest = HttpsConnection.getHttpsConnection(AccessTokenUri);
            webRequest.setDoInput(true);
            webRequest.setDoOutput(true);
            webRequest.setConnectTimeout(5000);
            webRequest.setReadTimeout(5000);
            webRequest.setRequestProperty("content-type", "application/x-www-form-urlencoded");
            webRequest.setRequestMethod("POST");

            byte[] bytes = requestDetails.getBytes();
            webRequest.setRequestProperty("content-length", String.valueOf(bytes.length));
            webRequest.connect();

            DataOutputStream dop = new DataOutputStream(webRequest.getOutputStream());
            dop.write(bytes);
            dop.flush();
            dop.close();

            inSt = webRequest.getInputStream();
            InputStreamReader in = new InputStreamReader(inSt);
            BufferedReader bufferedReader = new BufferedReader(in);
            StringBuffer strBuffer = new StringBuffer();
            String line = null;
            while ((line = bufferedReader.readLine()) != null) {
                strBuffer.append(line);
            }

            bufferedReader.close();
            in.close();
            inSt.close();
            webRequest.disconnect();

            // parse the access token from the json format
            String result = strBuffer.toString();
            
            OxfordAccessToken token = new OxfordAccessToken();
            token.access_token = Util.getJsonValue(result, "access_token");
            token.token_type = Util.getJsonValue(result, "token_type");
            token.expires_in = Util.getJsonValue(result, "expires_in");
            token.scope = Util.getJsonValue(result, "scope");

            return token;
        }catch (Exception e){
            e.printStackTrace();
        }

        return null;
    }
}
