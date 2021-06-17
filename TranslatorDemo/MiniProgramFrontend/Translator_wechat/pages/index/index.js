Page({
  data: {
    recordingSrc: "",
    translationSrc: "",
    srResult: "",
    translateResult: "",
    isPlaying: false,
    voiceButtonSrcList: ["../../image/button_default.png", "../../image/button_pressed.png", "../../image/button_processing.png", "../../image/button_default.png"],
    recordState: 0,
    isPressing: 0,
    hit1: "请按住话筒录入语音",
    hit2: "最长30秒",
    items: [
      { name: '中文-->英文', value: 'zh2en', checked: 'true' },
      { name: 'English-->Chinese', value: 'en2zh' },
    ],
    translateTo: "zh2en"
  },

  onLoad: function (options) {
    var that = this;
    this.recorderManager = wx.getRecorderManager();
    this.recorderManager.onError(function () {
      that.setData({
        translationSrc: "",
        recordState: 0,
        hit1: "Recording failed.",
        hit2: "Please try again."
      })
    });
    this.recorderManager.onStop(function (res) {
      that.setData({
        recordingSrc: res.tempFilePath,
      })
      that.uploadToServer(res.tempFilePath)
      console.log(res.tempFilePath)
    });

    this.innerAudioContext = wx.createInnerAudioContext();
    this.innerAudioContext.onError((res) => {
      that.tip("Play recording failed")
      that.setData({
        isPlaying: false
      })
    })

    this.innerAudioContext.onEnded((res) => {
      that.setData({
        isPlaying: false
      })
    })
  },

  onUnload: function () {
    if(this.data.isPlaying){
      this.stopAudio()
    }
  },

  tip: function (msg) {
    wx.showModal({
      title: 'Notice',
      content: msg,
      showCancel: false
    })
  },

  radioChange(e) {
    if (e.detail.value == "zh2en") {
      this.setData({
        translateTo: e.detail.value,
        hit1: "请按住话筒录入语音",
        hit2: "最长30秒",
      });
    }
    else {
      this.setData({
        translateTo: e.detail.value,
        hit1: "Please press and hold the microphone to enter the voice",
        hit2: "For up to 30 seconds.",
      });
    }
  },

  /*Translation Speech*/
  uploadToServer: function (file) {

    var that = this;
    var inputLocaleTmp = "";
    var outputLocaleTmp = "";
    if (this.data.translateTo == "zh2en") {
      inputLocaleTmp = "zh-CN"
      outputLocaleTmp = "en-US"
    }
    else{
      inputLocaleTmp = "en-US"
      outputLocaleTmp = "zh-CN"
    }

    wx.uploadFile({
      url: '[Your backend API]',
      filePath: file,
      name: 'ms_file',
      formData: {
        inputLocale: inputLocaleTmp,
        outputLocale: outputLocaleTmp,
      },
      success(file) {
        var result = JSON.parse(file.data)
        that.setData({
          translationSrc: result.TtsResult,
          srResult: result.SrResult,
          translateResult: result.TranslateResult,
          recordState: 3,
          hit1: result.SrResult,
          hit2: result.TranslateResult
        })

        if (result.TtsResult != ""){
          that.playAudio()
        }
      },
      fail(file) {
        that.setData({
          translationSrc: "",
          recordState: 0,
          hit1: "Request failed.",
          hit2: "Please try again."
        })
        console.log(file)
      }
    })
  },

  handleStartRecord: function () {
    if(this.data.isPlaying){
      this.stopAudio()
    }

    this.recorderManager.start({
      format: 'mp3',
      sampleRate: 16000,
      numberOfChannels: 1
    });

    this.setData({
      isPressing:1,
      recordState:1
    })
  },

  handleStopRecord: function () {
    this.recorderManager.stop()
    this.setData({
      isPressing: 0,
      recordState: 2
    })
  },

  playAudio: function () {
    if(this.data.isPlaying){
      this.innerAudioContext.stop()

      this.setData({
        isPlaying: false
      })
    }
    else{
      if (this.data.translationSrc == "") {
        this.tip("Please recording first!")
        return;
      }

      this.innerAudioContext.src = this.data.translationSrc;
      this.innerAudioContext.play()

      this.setData({
        isPlaying: true
      })
    }
  },

  stopAudio: function () {
    this.innerAudioContext.stop()

    this.setData({
      isPlaying: false
    })
  },
})
