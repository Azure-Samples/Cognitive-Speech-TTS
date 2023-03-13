function ttsPlayer({ ttsPlayerConfig, sourceLocation, voice, style, isFlat, divNames, xPaths, requestId, ssmlTemplate, styles, isLogging, isDebugging }) {

    let logClickTime;

    const imagesSrc = {
        azure: `${ttsPlayerConfig.playerLibPath}/images/azure-icon.svg`,
        azureText: `${ttsPlayerConfig.playerLibPath}/images/azure-text-icon.svg`,
        listenButtonHover: `${ttsPlayerConfig.playerLibPath}/images/listen-hover-icon.svg`,
        listenButton: `${ttsPlayerConfig.playerLibPath}/images/listen-icon.svg`,
        pause: `${ttsPlayerConfig.playerLibPath}/images/pause.svg`,
        play: `${ttsPlayerConfig.playerLibPath}/images/play.svg`,
    };

    function createFlatPlayer() {
        const audioPlayerBox = document.createElement("div");
        audioPlayerBox.id = "audio-player-box";
        audioPlayerBox.className = "audio-player-box";
        if (styles?.audioPlayerBox) {
            for (let i in styles.audioPlayerBox) {
                audioPlayerBox.style[i] = styles.audioPlayerBox[i]
            }
        }
        commonPlayer.applyCommonPlayerArea(audioPlayerBox);
        return audioPlayerBox;
    }
    function createFloatPlayer() {
        const floatingPlayer = document.createElement("div");
        floatingPlayer.className = "float-player-switch";
        const listenButton = document.createElement("button");
        listenButton.className = "listen-button";
        listenButton.title = "listen to the article";
        floatingPlayer.append(listenButton);
        const listenIcon = document.createElement("img");
        listenIcon.id = "listen-icon";
        listenIcon.onmouseover = elementEvents.floating_ListenButton_OnMouseOver;
        listenIcon.onmouseleave = elementEvents.floating_ListenButton_OnMouseLeave;
        listenIcon.onclick = _ => elementEvents.floating_ListenButton_OnClick();
        listenIcon.src = imagesSrc.listenButton;
        listenIcon.alt = "play";
        listenButton.append(listenIcon);

        const audioPlayerBox = document.createElement("div");
        audioPlayerBox.id = "audio-player-box";
        audioPlayerBox.className = "audio-player-box-float";
        audioPlayerBox.style = "display:none";
        if (styles?.audioPlayerBox) {
            for (let i in styles.audioPlayerBox) {
                audioPlayerBox.style[i] = styles.audioPlayerBox[i]
            }
        }
        commonPlayer.applyCommonPlayerArea(audioPlayerBox);
        floatingPlayer.append(audioPlayerBox);
        return floatingPlayer;
    }

    function onLoad() {
        const playerUI = isFlat ? createFlatPlayer() : createFloatPlayer();
        const parentElement = document.getElementById(ttsPlayerConfig.playerParentDivId);
        parentElement.append(playerUI);
    }

    const commonPlayer = {
        applyCommonPlayerArea: function (audioPlayerBox) {
            const playerBox = document.createElement("div");
            playerBox.className = "player-area";
            audioPlayerBox.append(playerBox);
            const audioTag = document.createElement("audio");
            const cachedAudioSource = document.createElement("source");
            const synthesisAudioSource = document.createElement("source");
            cachedAudioSource.id = "cached-audio-source";
            synthesisAudioSource.id = "synthesis-audio-source";
            cachedAudioSource.type = "audio/mp3";
            synthesisAudioSource.type = "audio/mp3";
            audioTag.append(cachedAudioSource);
            audioTag.append(synthesisAudioSource);
            audioTag.id = "tts-player-audio-control";
            audioTag["data-isAvailable"] = false;
            audioTag.autoPlay = false;
            audioTag.preload = "";
            playerBox.append(audioTag);
            const playButton = document.createElement("button");
            playButton.className = "audio-view-button";
            playButton.id = "play-or-pause-button";
            playButton.onclick = _ => elementEvents.playButton_OnClick();
            const playerIcon = document.createElement("img");
            playerIcon.id = "audio-player-icon";
            playerIcon.src = imagesSrc.play;
            playerIcon.alt = "play";
            playButton.append(playerIcon);
            playerBox.append(playButton);
            const audioTip = document.createElement("div");
            audioTip.id = "player-tip";
            audioTip.className = "player-tip";
            audioTip.innerText = "Listen to the article";
            playerBox.append(audioTip);
            const playerProgress = document.createElement("div");
            playerProgress.id = "player-progress";
            playerProgress.className = "player-progress";
            playerBox.append(playerProgress);
            const cachedAudioPlayedDuration = document.createElement("span");
            cachedAudioPlayedDuration.id = "cached-audio-played-duration";
            cachedAudioPlayedDuration.className = "audio-time";
            cachedAudioPlayedDuration.innerText = "00:00";
            playerProgress.append(cachedAudioPlayedDuration);
            const seekBar = document.createElement("input");
            seekBar.id = "player-seek-bar";
            seekBar.className = "seek-bar";
            seekBar.type = "range";
            seekBar.value = "0";
            if (styles?.seekBar) {
                for (let i in styles.seekBar) {
                    seekBar.style[i] = styles.seekBar[i]
                }
            }
            playerProgress.append(seekBar);
            const totalDuration = document.createElement("span");
            totalDuration.id = "total-duration";
            totalDuration.className = "audio-time";
            totalDuration.innerText = "00:00";
            playerProgress.append(totalDuration);
            const noCachedAudioPlayedDuration = document.createElement("div");
            noCachedAudioPlayedDuration.className = "no-cached-audio-time";
            noCachedAudioPlayedDuration.id = "no-cached-audio-played-duration";
            noCachedAudioPlayedDuration.innerText = "00:00";
            playerBox.append(noCachedAudioPlayedDuration);

            const labelContent = document.createElement("div");
            labelContent.className = "label-content";
            audioPlayerBox.append(labelContent);
            const playerLogo = document.createElement("div");
            playerLogo.className = "player-logo";
            labelContent.append(playerLogo);
            const logoText = document.createElement("span");
            logoText.innerText = "Powered by";
            playerLogo.append(logoText);
            const space = document.createElement("div");
            space.className = "space";
            playerLogo.append(space);
            const azureLogo = document.createElement("img");
            azureLogo.src = imagesSrc.azure;
            azureLogo.alt = "azure logo";
            playerLogo.append(azureLogo);
            playerLogo.append(space);
            const azureTextLogo = document.createElement("img");
            azureTextLogo.src = imagesSrc.azureText;
            azureTextLogo.alt = "azure text logo";
            playerLogo.append(azureTextLogo);
        }
    }

    const apiHelper = {
        buildSynthesisUrl: function (playerId, sourceLocation, voice, cacheMode, style, divNames, xPaths, requestId, ssmlTemplate) {
            const _requestId = requestId ? requestId : util.createUUID();
            sourceLocation = encodeURIComponent(sourceLocation);
            divNames = divNames ? `&divClassNames=${encodeURIComponent(divNames)}` : "";
            if (xPaths instanceof Array) {
                for (let i in xPaths) {
                    typeof xPaths[i] === "string" && (xPaths[i] = xPaths[i].trim());
                }

                xPaths = xPaths ? `&xpaths=${encodeURIComponent(JSON.stringify(xPaths))?.replace(/\(/g, '%28')?.replace(/\)/g, "%29")}` : "";
            }
            else {
                xPaths = xPaths ? xPaths : "";
            }

            style = style ? style : "general";
            ssmlTemplate = ssmlTemplate ? `&ssmlTemplate=${ssmlTemplate}` : "";
            return `https://${ttsPlayerConfig.environment}/api/texttospeech/v3.0-beta1/TTSWebPagePlayerSynthesis/synthesis-content?playerId=${playerId}&sourceLocation=${sourceLocation}&voice=${voice}&style=${style}&cacheMode=${cacheMode}&requestId=${_requestId}${divNames}${xPaths}${ssmlTemplate}`;
        },

        setAudioSrcAttrFromDebugging: function () {
            const playerId = ttsPlayerConfig.playerId;
            const audioControlId = "tts-player-audio-control";
            switch (ttsPlayerConfig.cacheMode) {
                case "ProductionScenario": {
                    this.buildUrlAndSetAudioSrcAttr();
                    break;
                }
                case "TryHitCache": {
                    const synthesisContentUrl = this.buildSynthesisUrl(playerId, sourceLocation, voice, "TryHitCache", style, divNames, xPaths, requestId, ssmlTemplate);
                    elementAttrFunc.audioControl_SetSrcAttr(audioControlId, "", synthesisContentUrl);
                    break;
                }
                case "OnlyCache": {
                    const synthesisContentUrl = this.buildSynthesisUrl(playerId, sourceLocation, voice, "OnlyCache", style, divNames, xPaths, requestId, ssmlTemplate);
                    elementAttrFunc.audioControl_SetSrcAttr(audioControlId, synthesisContentUrl, "");
                    break;
                }
            }
        },

        buildUrlAndSetAudioSrcAttr: function () {
            const playerId = ttsPlayerConfig.playerId;
            const audioControlId = "tts-player-audio-control";
            const cachedAudioUrl = this.buildSynthesisUrl(
                playerId, sourceLocation, voice, "OnlyCache", style, divNames, xPaths, requestId, ssmlTemplate);
            const synthesisContentUrl = this.buildSynthesisUrl(
                playerId, sourceLocation, voice, "TryHitCache", style, divNames, xPaths, requestId, ssmlTemplate);
            elementAttrFunc.audioControl_SetSrcAttr(audioControlId, cachedAudioUrl, synthesisContentUrl);
        }
    }

    const elementAttrFunc = {
        playOrPauseButton_SetPlayIcon: function () {
            const playOrPauseButton = document.getElementById("play-or-pause-button");
            const oldPlayIcon = playOrPauseButton.getElementsByTagName("img")[0] || playOrPauseButton.getElementsByClassName("loading")[0];
            if (oldPlayIcon.alt !== "play") {
                const newPlayIcon = document.createElement("img");
                newPlayIcon.id = "audio-player-icon";
                newPlayIcon.src = imagesSrc.play;
                newPlayIcon.alt = "play";
                playOrPauseButton.replaceChild(newPlayIcon, oldPlayIcon);
            }
        },

        playOrPauseButton_SetPauseIcon: function () {
            const playOrPauseButton = document.getElementById("play-or-pause-button");
            const oldPlayIcon = playOrPauseButton.getElementsByTagName("img")[0] || playOrPauseButton.getElementsByClassName("loading")[0];
            if (oldPlayIcon.alt !== "pause") {
                const newPlayIcon = document.createElement("img");
                newPlayIcon.id = "audio-player-icon";
                newPlayIcon.src = imagesSrc.pause;
                newPlayIcon.alt = "pause";
                playOrPauseButton.replaceChild(newPlayIcon, oldPlayIcon);
            }
        },

        playOrPauseButton_SetLoadingIcon: function () {
            const playOrPauseButton = document.getElementById("play-or-pause-button");
            const oldPlayIcon = playOrPauseButton.getElementsByTagName("img")[0];
            const loadingIcon = document.createElement("div");
            loadingIcon.className = "loading";
            playOrPauseButton.replaceChild(loadingIcon, oldPlayIcon);
        },

        progressArea_ShowCachedAudioPlayedDuration: function (playedDuration) {
            const playedDurationElement = document.getElementById("cached-audio-played-duration");
            playedDurationElement.innerText = util.formatTime(playedDuration);
        },

        progressArea_ShowNoCachedAudioPlayedDuration: function (isShow, playedDuration) {
            const playedDurationElement = document.getElementById("no-cached-audio-played-duration");
            if (playedDuration) playedDurationElement.innerText = util.formatTime(playedDuration);
            playedDurationElement.style.display = isShow ? "inline" : "none";
        },

        progressArea_ShowCachedAudioTotalDuration: function (totalDuration) {
            const durationElement = document.getElementById("total-duration");
            durationElement.innerText = util.formatTime(totalDuration);
        },

        progressArea_ShowTip: function (isShow) {
            const playerTip = document.getElementById("player-tip");
            isShow ? playerTip.style.display = "inline" : playerTip.style.display = "none";
        },

        progressArea_ShowCachedAudioSeekBar: function (isShow) {
            const playerProgress = document.getElementById("player-progress");
            playerProgress.style.display = isShow ? "flex" : "none";
        },

        progressArea_HideTipAndShowCachedAudioSeekBar: function () {
            this.progressArea_ShowTip(false);
            this.progressArea_ShowCachedAudioSeekBar(true);
        },

        audioControl_SetSrcAttr: function (audioControlId, cachedUrl, synthesisContentUrl) {
            let audioControl = document.getElementById(audioControlId);
            let cachedAudioSource = document.getElementById("cached-audio-source");
            let synthesisAudioSource = document.getElementById("synthesis-audio-source");
            if (cachedUrl) cachedAudioSource.src = cachedUrl;
            if (synthesisContentUrl) synthesisAudioSource.src = synthesisContentUrl;
            audioControl["data-isAvailable"] = true;
            elementEvents.initializeAudioControlAndSeekBar(audioControlId);
            audioControl.load();
            audioControl.play();
        },

    }

    const elementEvents = {
        floating_ListenButton_OnMouseOver: function (e) {
            e.currentTarget.src = imagesSrc.listenButtonHover;
        },

        floating_ListenButton_OnMouseLeave: function (e) {
            const audioPlayerBox = document.getElementById("audio-player-box");
            if (audioPlayerBox.style.display === "none") {
                e.currentTarget.src = imagesSrc.listenButton;
            }
        },

        floating_ListenButton_OnClick: function () {
            const audioPlayerBox = document.getElementById("audio-player-box");
            if (audioPlayerBox.style.display === "none") {
                audioPlayerBox.style.display = "block";
                const playIcon = document.getElementById("audio-player-icon");
                if (playIcon.alt !== "pause") elementEvents.playButton_OnClick();
            } else {
                audioPlayerBox.style.display = "none";
            }
        },

        playButton_OnClick: function () {
            const playIcon = document.getElementById("audio-player-icon");
            if (!playIcon) return;
            const audioControl = document.getElementById("tts-player-audio-control");
            if (playIcon.alt === "play") {
                if (audioControl["data-isAvailable"]) {
                    elementAttrFunc.playOrPauseButton_SetPauseIcon();
                    audioControl.play();
                } else {
                    elementAttrFunc.playOrPauseButton_SetLoadingIcon();
                    console.time("fetch-audio-data-time")
                    logClickTime = new Date().getTime();
                    isDebugging ? apiHelper.setAudioSrcAttrFromDebugging() : apiHelper.buildUrlAndSetAudioSrcAttr();
                }
            } else if (playIcon.alt === "pause") {
                elementAttrFunc.playOrPauseButton_SetPlayIcon();
                audioControl.pause();
            }
        },

        initializeAudioControlAndSeekBar: function (audioControlId) {
            const audioControl = document.getElementById(audioControlId);
            const cachedAudioSourceId = document.getElementById("cached-audio-source");
            if (cachedAudioSourceId) {
                cachedAudioSourceId.onerror = error => {
                    const synthesisAudioSourceId = document.getElementById("synthesis-audio-source");
                    if (synthesisAudioSourceId) {
                        synthesisAudioSourceId.onerror = error => {
                            elementAttrFunc.playOrPauseButton_SetPlayIcon();
                            audioControl["data-isAvailable"] = false;
                            console.error(`Error: ${JSON.stringify(error)}  Href: ${audioControl.src}`);
                        }
                    }
                    // Add code to log error here.
                    console.error(`Error: ${JSON.stringify(error)}  Href: ${audioControl.src}`);
                }
            }
            const seekBar = document.getElementById("player-seek-bar");
            if (audioControl) {
                let isDragging = false;
                audioControl.onpause = _ => {
                    audioControl.pause();
                    elementAttrFunc.playOrPauseButton_SetPlayIcon();
                };
                audioControl.oncanplay = _ => {
                    if (isLogging) console.timeEnd('fetch-audio-data-time');
                    const fetchAudioTime = Math.floor(new Date().getTime() - logClickTime);
                    const logUrl = `https://${ttsPlayerConfig.environment}/api/texttospeech/v3.0-beta1/TTSWebPagePlayerSynthesis/log?playerId=${ttsPlayerConfig.playerId}&&value=${fetchAudioTime}&&voice=${voice}&&logKind=PlayFirstByteLatency&&requestId=${util.createUUID()}`
                    fetch(logUrl, { method: "POST" }).catch(e => {
                        console.error(e)
                    })
                }
                audioControl.ontimeupdate = _ => {
                    if (audioControl.currentTime && seekBar && !isDragging) {
                        elementAttrFunc.playOrPauseButton_SetPauseIcon();
                        if (audioControl.duration && audioControl.duration !== Infinity) {
                            const percent = (audioControl.currentTime / audioControl.duration) * 100;
                            seekBar.value = percent.toString();
                            seekBar.style.backgroundSize = `${percent}% 100%`;
                            if (audioControl.currentTime === audioControl.duration) {
                                elementAttrFunc.playOrPauseButton_SetPlayIcon();
                            }
                            elementAttrFunc.progressArea_ShowCachedAudioPlayedDuration(audioControl.currentTime);
                            elementAttrFunc.progressArea_ShowCachedAudioTotalDuration(audioControl.duration);
                            elementAttrFunc.progressArea_HideTipAndShowCachedAudioSeekBar();
                            elementAttrFunc.progressArea_ShowNoCachedAudioPlayedDuration(false, audioControl.currentTime);
                        } else {
                            elementAttrFunc.progressArea_ShowTip(false);
                            elementAttrFunc.progressArea_ShowNoCachedAudioPlayedDuration(true, audioControl.currentTime);
                        }
                    }
                };
                audioControl.onerror = error => {
                    elementAttrFunc.playOrPauseButton_SetPlayIcon();
                    audioControl["data-isAvailable"] = false;
                    // Add code to log error here.
                    console.error(`Error: ${JSON.stringify(error)}  Href: ${audioControl.src}`);
                };
                if (seekBar) {
                    seekBar.onmousedown = _ => {
                        isDragging = true;
                    };
                    seekBar.onmouseup = _ => {
                        isDragging = false;
                    };
                    seekBar.onmouseleave = _ => {
                        isDragging = false;
                    };
                    seekBar.oninput = _ => {
                        if (audioControl) {
                            const percentagePosition = seekBar.valueAsNumber;
                            seekBar.style.backgroundSize = `${percentagePosition}% 100%`;
                            seekBar.value = percentagePosition.toString();
                        }
                    };
                    seekBar.onchange = _ => {
                        if (audioControl && !isDragging) {
                            const percentagePosition = seekBar.valueAsNumber;
                            seekBar.style.backgroundSize = `${percentagePosition}% 100%`;
                            seekBar.value = percentagePosition.toString();
                            const time = audioControl.duration * (percentagePosition / 100);
                            audioControl.currentTime = time;
                            audioControl.play();
                        }
                    }
                }
                audioControl.play();
            }
        }

    }

    const util = {
        formatTime: function (time) {
            const pad = (value) => String(value).padStart(2, "0");
            time = !time || time < 0 ? 0 : time;
            const hours = Math.floor(time / 60 / 60);
            const minutes = Math.floor(time / 60) % 60;
            const seconds = Math.floor(time % 60);

            if (hours > 0) return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
            else return `${pad(minutes)}:${pad(seconds)}`;
        },
        createUUID: function () {
            return 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'.replace(/[x]/g, function (c) {
                const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
    }

    onLoad();
}