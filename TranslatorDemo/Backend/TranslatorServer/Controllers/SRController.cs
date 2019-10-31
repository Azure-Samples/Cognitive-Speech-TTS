using Microsoft.AspNetCore.Mvc;
using TranslatorServer.DTO;
using Microsoft.AspNetCore.Http;
using TranslatorServer.Management;

namespace TranslatorServer.Controllers
{
    [Route("api/sr")]
    public class SRController : Controller
    {
        public SRController()
        {
            
        }


        [HttpPost("zh-cn")]
        public SRResult PostZhCnSR([FromForm] IFormCollection formCollection)
        {
            IFormFile file = formCollection.Files[0];
            return SR.GetSRResult(file, "zh-CN");
        }

        [HttpPost("en-us")]
        public SRResult PostEnUsSR([FromForm] IFormCollection formCollection)
        {
            IFormFile file = formCollection.Files[0];
            var result =  SR.GetSRResult(file, "en-US");
            return result;
        }
    }
}