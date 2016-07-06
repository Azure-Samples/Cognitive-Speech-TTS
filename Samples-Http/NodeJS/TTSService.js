/**
Copyright (c) Microsoft Corporation
All rights reserved. 
MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
**/
var util = require('util'),
  https = require('https');
 

 exports.Synthesize = function Synthesize(){

	// Note: Sign up at http://www.projectoxford.ai to get a subscription key.  
	// Search for Speech APIs from Azure Marketplace.  
    // Use the subscription key as Client secret below.
	var clientId = "Your ClientId goes here";
	var clientSecret = "Your Client Secret goes here";
	var speechHost = "https://speech.platform.bing.com";
	var post_data = "grant_type=client_credentials&client_id=" + encodeURIComponent(clientId) + "&client_secret=" + encodeURIComponent(clientSecret) + "&scope=" + encodeURI(speechHost);

	var AccessTokenUri = "https://oxford-speech.cloudapp.net/token/issueToken";

	var post_option = {
		hostname: 'oxford-speech.cloudapp.net',
		port: 443,
		path: '/token/issueToken',
		method: 'POST'
	};

	post_option.headers = {
		'content-type' : 'application/x-www-form-urlencoded',
		'Content-Length' : post_data.length	
	};

	var post_req = https.request(post_option, function(res){
	  var _data="";
	   res.on('data', function(buffer){
		 _data += buffer;
		 });
		 
		 // end callback
		res.on('end', function(){
		console.log("json string result: ",_data);
		OxfordAccessToken = eval ('(' + _data + ')');
		
		// call tts service
		var https = require('https');


	var ttsServiceUri = "https://speech.platform.bing.com/synthesize";

	var post_option = {
		hostname: 'speech.platform.bing.com',
		port: 443,
		path: '/synthesize',
		method: 'POST'
	};

	var SsmlTemplate = "<speak version='1.0' xml:lang='en-us'><voice xml:lang='%s' xml:gender='%s' name='%s'>%s</voice></speak>";
	var post_data = util.format(SsmlTemplate, 'en-US', 'Female', 'Microsoft Server Speech Text to Speech Voice (en-US, ZiraRUS)', 'This is a demo to call microsoft text to speach service in javascript.');
	console.log('\n\ntts post_data: ' + post_data + '\n');
	
	post_option.headers = {
		'content-type' : 'application/ssml+xml',
		'Content-Length' : post_data.length,
		'X-Microsoft-OutputFormat' : 'riff-16khz-16bit-mono-pcm',
		'Authorization': 'Bearer ' + OxfordAccessToken.access_token,
		'X-Search-AppId': '07D3234E49CE426DAA29772419F436CA',
		'X-Search-ClientID': '1ECFAE91408841A480F00935DC390960',
		"User-Agent": "TTSNodeJS"
	};

	var post_req = https.request(post_option, function(res){
	  var _data="";
	   res.on('data', function(buffer){
		   //get the wave
		 _data += buffer;
		 });
		 
		 // end callback
		res.on('end', function(){

		console.log('wave data.length: ' + _data.length);
		});

		post_req.on('error', function(e) {
		console.log('problem with request: ' + e.message);
		});
	});
	
	 post_req.write(post_data);
	 post_req.end();
	 
		});

		post_req.on('error', function(e) {
		console.log('problem with request: ' + e.message);
		OxfordAccessToken = null;
		//return OxfordAccessToken;
		});
	});
	
	 post_req.write(post_data);
	 post_req.end();
}