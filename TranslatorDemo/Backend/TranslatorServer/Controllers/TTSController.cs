using System.IO;
using Microsoft.AspNetCore.Mvc;
using TranslatorServer.DTO;
using TranslatorServer.Management;

namespace TranslatorServer.Controllers
{
    [Route("api/tts")]
    public class TTSController : Controller
    {
        private TTS tts { get; set; }

        public TTSController(TTS tts)
        {
            this.tts = tts;
        }

        [HttpPost]
        public Stream PostTTSStream([FromBody]TTSDefinition ttsDefinition)
        {
            return tts.Synthesis(ttsDefinition.script);
        }
    }
}
