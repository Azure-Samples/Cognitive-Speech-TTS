var authorizationToken;
var start = false;
var stopf = false;

function gettoken(){
    var request = new XMLHttpRequest();
    request.open('POST', '/gettoken', true);

    // Callback function for when request completes
    request.onload = () => {
        // Extract JSON data from request
        const data = JSON.parse(request.responseText);
        authorizationToken = data.at;
    }
    
    //send request
    request.send();
    return false;
}

var textdone, textleft;
var totalscore = 0;
var totalscorep;
var pointsdiv;
var authorizationToken, phrases;
var region = "centralindia";
var language = "en-IN";
var SpeechSDK;
var recognizer;
var id=0;
var storyi = 0;
var story;
var cursentence = "";
var cursentencewordsleft = [];
var cursentencewordsdone = [];
var nomatchflag = 0;

var reco;
var buttonmic;

var soundContext = undefined;
try {
    var AudioContext = window.AudioContext // our preferred impl
        || window.webkitAudioContext       // fallback, mostly when on Safari
        || false;                          // could not find.

    if (AudioContext) {
        soundContext = new AudioContext();
    } else {
        alert("Audio context not supported");
    }
}
catch (e) {
    window.console.log("no sound context found, no audio output. " + e);
}

function initvars(){
    authorizationToken = "";
    phrases = [];
    region = "centralindia";
    language = "en-IN";
    recognizer = undefined;
    start = false;
    stopf = false;
    storyi = 0;
    story = "";
    cursentence = "";
    cursentencewordsleft = [];
    cursentencewordsdone = [];
    nomatchflag = 0;
    reco = undefined;

    soundContext = undefined;
    try {
        var AudioContext = window.AudioContext // our preferred impl
            || window.webkitAudioContext       // fallback, mostly when on Safari
            || false;                          // could not find.

        if (AudioContext) {
            soundContext = new AudioContext();
        } else {
            alert("Audio context not supported");
        }
    }
    catch (e) {
        window.console.log("no sound context found, no audio output. " + e);
    }
}

function getstory(id){
    console.log("getting story "+id.toString());
    var request = new XMLHttpRequest();
    request.open('POST', '/getstory', true);

    // Callback function for when request completes
    request.onload = ()=>{
        const data = JSON.parse(request.responseText);
        //console.log(data);
        if(data.code == 200) {
            story = data.story;
            //console.log(story);
            document.getElementById("textleft").innerHTML = story[0];
            document.getElementById("textdone").innerHTML = "";
        }
        else{
            console.log("You have completed all stories");
            document.getElementById("textleft").innerHTML = "--- THE END ---";
        }
    }
    // Add data to send with request
    const data = new FormData();
    data.append("id",id);  

    //send request
    request.send(data);
    
    return false;     
}
getstory(id);

document.addEventListener("DOMContentLoaded", function () {
    buttonmic = document.getElementById("buttonmic");
    textdone = document.getElementById("textdone");
    textleft = document.getElementById("textleft");
    pointsdiv = document.getElementById("pointsdiv");
    totalscorep = document.getElementById("totalscorep");

    function score(points){
        totalscore += points;
        var newpoint = document.createElement("p");
        newpoint.innerHTML = (points>=0) ? "+"+points.toString() : points.toString() ;
        newpoint.className = "points";
        if(pointsdiv.childElementCount >=5){
            pointsdiv.removeChild(pointsdiv.childNodes[0]);  
        }
        pointsdiv.appendChild(newpoint);
        totalscorep.innerHTML = totalscore.toString() ;
        
    }

    function getnextsentence(){
        console.log("getnextsentence");
        if(storyi < story.length){
            cursentence = story[storyi];
            textleft.innerHTML = cursentence;
            textdone.innerHTML = "";
            storyi++;
            cursentencewordsleft = cursentence.split(" ");
            cursentencewordsdone = [];
        }
    }
    
    function match(word){
        if(word.toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()"'?!]/g,"") == cursentencewordsleft[0].toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()"'?!]/g,"")){
            cursentencewordsdone.push(cursentencewordsleft.shift());
            console.log("MATCH = " + word);
            textdone.innerHTML = cursentencewordsdone.join(" ") + " ";
            textleft.innerHTML = cursentencewordsleft.join(" ");
            score(2);
        }
        else if(nomatchflag > 0)
        {
            if(word.toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()"'?!]/g,"") == cursentencewordsleft[1].toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()"'?!]/g,"")){
                console.log("GOT A SKIP AND MATCH for " + word + " at nomatchflag ="+ nomatchflag.toString());
                nomatchflag = 0;
                cursentencewordsdone.push(cursentencewordsleft.shift());
                cursentencewordsdone.push(cursentencewordsleft.shift());
                textdone.innerHTML = cursentencewordsdone.join(" ") + " ";
                textleft.innerHTML = cursentencewordsleft.join(" ");
                score(1);
            }
            else
            {
                console.log("SKIP BUT NO MATCH!");
            }
        }
        else{
            nomatchflag = 1;
            score(-1);
            console.log("NOMATCH for " + cursentencewordsleft[0].toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()"'?!]/g,"").italics() + ". Instead, received "+word.italics());
            console.log(cursentencewordsleft);
            console.log(cursentencewordsdone);
            console.log("NOMATCH END -----------------");
        }
    
        if(cursentencewordsleft.length == 0)
        {
            if(storyi<story.length){
                getnextsentence()
            }
            else{
                console.log("FINISHED STORY");
                stoppingfunction();
            }   
        }
    }

    function stoppingfunction(){
        start = false;
        stopf = true;
        buttonmic.innerHTML = "<span class='fa fa-step-forward'></span>Next";
        buttonmic.className = "blue-button";
        reco.stopContinuousRecognitionAsync(
            function () {
                reco.close();
                reco = undefined;
            },
            function (err) {
                reco.close();
                reco = undefined;
            });
    }

    // Starts continuous speech recognition.
    buttonmic.addEventListener("click", function () {
        if(stopf){
            this.innerHTML = "<span class='fa fa-microphone'></span>Start";
            this.className = "green-button";
            
            initvars();
            gettoken();
            id++;
            getstory(id);
        }
        else if(start){
            stoppingfunction();
        }
        else{
            start = true;
            this.innerHTML = "<span class='fa fa-stop'></span>Stop";
            this.className = "red-button";

            getnextsentence();
            var prevwords = [];

            var audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
            
            var speechConfig;
            if (authorizationToken) {
                speechConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(authorizationToken, region);
            } else {
                console.log("authToken problem");
            }

            speechConfig.speechRecognitionLanguage = language;
            reco = new SpeechSDK.SpeechRecognizer(speechConfig, audioConfig);
            var phraseListGrammar = SpeechSDK.PhraseListGrammar.fromRecognizer(reco);
            phraseListGrammar.addPhrase(story);

            // Before beginning speech recognition, setup the callbacks to be invoked when an event occurs.

            // The event recognizing signals that an intermediate recognition result is received.
            // You will receive one or more recognizing events as a speech phrase is recognized, with each containing
            // more recognized speech. The event will contain the text for the recognition since the last phrase was recognized.
            reco.recognizing = function (s, e) {
                //window.console.log(e);
                var curwords = e.result.text.split(" ");
                //console.log(curwords);
                for(var i=prevwords.length; i<curwords.length; i++){
                    var curword = curwords[i];
                    match(curword);
                }
                prevwords = curwords;            
            };

            // The event recognized signals that a final recognition result is received.
            // This is the final event that a phrase has been recognized.
            // For continuous recognition, you will get one recognized event for each phrase recognized.
            reco.recognized = function (s, e) {
                //window.console.log(e);
                prevwords = [];
            };

            // Starts recognition
            reco.startContinuousRecognitionAsync();
        }
    });

    function Initialize(onComplete) {
        if (!!window.SpeechSDK) {
            document.getElementById('warning').style.display = 'none';
            onComplete(window.SpeechSDK);
        }
    }

    Initialize(function (speechSdk) {
        SpeechSDK = speechSdk;

        // in case we have a function for getting an authorization token, call it.
        if (typeof gettoken === "function") {
            gettoken();
            //console.log("got access token");
        }
    });
});