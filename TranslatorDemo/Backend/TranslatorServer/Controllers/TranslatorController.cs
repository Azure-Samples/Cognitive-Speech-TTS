using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using TranslatorServer.Utils;
using TranslatorServer.DTO;
using TranslatorServer.Management;
using System.Collections.Generic;
using System.Linq;
using System;
using System.IO;

namespace TranslatorServer.Controllers
{
    [Route("api/translator")]
    public class TranslatorController : Controller
    {
        private TTS tts { get; set; }

        public TranslatorController(TTS tts)
        {
            this.tts = tts;
        }

        [HttpGet("{lang}/{script}")]
        // Async call to the Translator Text API
        public IEnumerable<TranslationResult> TranslateTextRequest(string lang, string script)
        {
            return Translator.TranslateTextRequest(script, lang);
        }

        [HttpPost("speech")]
        // Async call to the Translator Text API
        public Dictionary<string, string> TranslateSpeechRequest([FromForm] IFormCollection formCollection, string inputLocale, string outputLocale)
        {
            IFormFile file = formCollection.Files[0];
            return TranslateSpeech(file, inputLocale, outputLocale);
        }

        private Dictionary<string, string> TranslateSpeech(IFormFile file, string inputLocale, string outputLocale)
        {
            Dictionary<string, string> result = new Dictionary<string, string>();
            result.Add("SrResult", "");
            result.Add("TranslateResult", "");
            result.Add("TtsResult", "");
            string script = "";

            try
            {
                if(inputLocale == null || inputLocale == "" || outputLocale == null || outputLocale == "")
                {
                    result["SrResult"] = "Request error, Please try again";
                    return result;
                }

                var srResult = SR.GetSRResult(file, inputLocale);
                if (srResult == null)
                {
                    result["SrResult"] = "Speech recognition failed, please try again";
                    return result;
                }
                if (srResult.text == null)
                {
                    result["SrResult"] = "Recording is too short, please try again";
                    return result;
                }
                if (srResult.text == "" || srResult.text == null)
                {
                    result["SrResult"] = "Speech is not recognized, please read clearly";
                    return result;
                }

                var translatorResult = Translator.TranslateTextRequest(srResult.text, outputLocale);
                if (translatorResult == null)
                {
                    result["SrResult"] = "Translation failed, please try again";
                    return result;
                }

                script = GetTranslateFirstText(translatorResult);
                if (script == null)
                {
                    result["SrResult"] = "Translation failed, please try again";
                    return result;
                }

                var stream = tts.Synthesis(script, outputLocale);
                if (stream == null)
                {
                    result["SrResult"] = "Text to speech failed, please try again";
                    return result;
                }

                string blobPath = BlobHelper.GetBlobPath("TranslatorResult", "translator", $"{Guid.NewGuid().ToString()}.wav");
                var audioLink = BlobHelper.SaveToBlob(blobPath, stream);
                if (audioLink == null)
                {
                    result["SrResult"] = "Save to blob failed, please try again";
                    return result;
                }

                result["SrResult"] = srResult.text;
                result["TranslateResult"] = script;
                result["TtsResult"] = audioLink;
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog($"TranslateSpeechRequest", ex);
                result["SrResult"] = ex.Message;
                result["TranslateResult"] = ex.StackTrace;
            }

            return result;
        }

        private string GetTranslateFirstText(IEnumerable<TranslationResult> result)
        {
            var Translate = new List<TranslationResult>(result);
            return Translate.FirstOrDefault().Translations.FirstOrDefault().Text;
        }
    }
}
