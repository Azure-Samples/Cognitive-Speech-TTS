<!--
Copyright (c) Microsoft Corporation
All rights reserved. 
MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
-->
<!DOCTYPE html>
<html>
<body>

<?php

$AccessTokenUri = "https://oxford-speech.cloudapp.net:443/token/issueToken";

// Note: Sign up at http://www.projectoxford.ai to get a subscription key.  
// Search for Speech APIs from Azure Marketplace.  
// Use the subscription key as Client secret below.
$clientId = "Your ClientId goes here";
$clientSecret = "Your Client Secret goes here";
$ttsHost = "https://speech.platform.bing.com";

$data = array('grant_type' => 'client_credentials', 'client_id' => $clientId,
'client_secret' => $clientSecret, 'scope' => $ttsHost);
$data = http_build_query($data);
//echo "post data: ". $data;

// use key 'http' even if you send the request to https://...
$options = array(
    'http' => array(
        'header'  => "Content-type: application/x-www-form-urlencoded\r\n" .
        "content-length: ".strlen($data)."\r\n",
        'method'  => 'POST',
        'content' => $data,
    ),
);
$context  = stream_context_create($options);

//get the Oxford Access Token in json
$result = file_get_contents($AccessTokenUri, false, $context);

if (!$result) {
    throw new Exception("Problem with $AccessTokenUri, $php_errormsg");
  }
else{
   echo "Oxford Access Token: ". $result. "\n";
  
   // decode the json to get the Oxford Access Token object.
   $OxfordAcessToken = json_decode($result);
   $access_token = $OxfordAcessToken->{'access_token'};

   $ttsServiceUri = "https://speech.platform.bing.com:443/synthesize";

   //$SsmlTemplate = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>";
   $data = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='en-US' xml:gender='Female' name='Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)'>This is a demo to call microsoft text to speach service in php.</voice></speak>";
   echo "tts post data: ". $data . "\n";
   $options = array(
    'http' => array(
        'header'  => "Content-type: application/ssml+xml\r\n" .
                    "X-Microsoft-OutputFormat: riff-16khz-16bit-mono-pcm\r\n" .
                    "Authorization: "."Bearer ".$access_token."\r\n" .
                    "X-Search-AppId: 07D3234E49CE426DAA29772419F436CA\r\n" .
                    "X-Search-ClientID: 1ECFAE91408841A480F00935DC390960\r\n" .
                    "User-Agent: TTSPHP\r\n" .
                    "content-length: ".strlen($data)."\r\n",
        'method'  => 'POST',
        'content' => $data,
        ),
    );

    $context  = stream_context_create($options);

    // get the wave data
    $result = file_get_contents($ttsServiceUri, false, $context);
    if (!$result) {
        throw new Exception("Problem with $AccessTokenUri, $php_errormsg");
      }
    else{
        echo "Wave data length: ". strlen($result);
    }
}

?>  

</body>
</html>
