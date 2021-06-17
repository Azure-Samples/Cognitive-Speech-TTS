using Microsoft.AspNetCore.Http;
using TranslatorServer.DTO;
using Newtonsoft.Json.Linq;
using SoxSharp;
using System;
using System.IO;
using System.Net;
using TranslatorServer.Utils;
using System.Globalization;
using System.Text;

namespace TranslatorServer.Management
{
    public class SR
    {
        private const string requestUri = Configuration.SrRequestUri;
        private const string host = Configuration.SrHost;
        private const string subscriptionKey = Configuration.SrSubscriptionKey;

        public static SRResult GetSRResult(IFormFile file, string language)
        {
            SRResult result = new SRResult();
            string sourcePath = "";
            string targetPath = "";
            if (file == null)
            {
                return null;
            }

            try
            {
                string filePath = Path.Combine(Environment.CurrentDirectory, "TemplateDictation");
                if (Directory.Exists(filePath) == false)
                {
                    Directory.CreateDirectory(filePath);
                }

                (sourcePath, targetPath) = Mp3ToWave(file, filePath);
                result = MicrosoftSRResult(targetPath, language);
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog($"{language}SR", ex);
                result = new SRResult("error", "0", ex.Message);
            }
            finally
            {
                if (System.IO.File.Exists(sourcePath) == true)
                {
                    System.IO.File.Delete(sourcePath);
                }

                if (System.IO.File.Exists(targetPath) == true)
                {
                    System.IO.File.Delete(targetPath);
                }
            }

            return result;
        }

        private static (string, string) Mp3ToWave(IFormFile file, string filePath)
        {
            var sourcePath = Path.Combine(filePath, $"{Guid.NewGuid()}.mp3");
            var targetPath = Path.Combine(filePath, $"{Guid.NewGuid()}.wav");

            using (FileStream fs = System.IO.File.Create(sourcePath))
            {
                file.CopyTo(fs);
                fs.Flush();
            }

            using (Sox sox = new Sox("offlineTool\\sox-14-4-2\\sox.exe"))
            {
                sox.Process(sourcePath, targetPath);
            }

            return (sourcePath, targetPath);
        }

        private static SRResult MicrosoftSRResult(string audioFile, string language)
        {
            SRResult result = new SRResult();
            string retString = "";
            HttpWebRequest request = null;
            request = (HttpWebRequest)HttpWebRequest.Create(string.Format(CultureInfo.InvariantCulture, requestUri, language));
            request.SendChunked = true;
            request.Accept = @"application/json;text/xml";
            request.Method = "POST";
            request.ProtocolVersion = HttpVersion.Version11;
            request.Host = host;
            request.ContentType = @"audio/wav; codecs=audio/pcm; samplerate=16000";
            request.Headers["Ocp-Apim-Subscription-Key"] = subscriptionKey;
            request.AllowWriteStreamBuffering = false;

            using (var fs = new FileStream(audioFile, FileMode.Open, FileAccess.Read))
            {
                /*
                * Open a request stream and write 1024 byte chunks in the stream one at a time.
                */
                byte[] buffer = null;
                int bytesRead = 0;
                using (Stream requestStream = request.GetRequestStream())
                {
                    /*
                    * Read 1024 raw bytes from the input audio file.
                    */
                    buffer = new Byte[checked((uint)Math.Min(2048, (int)fs.Length))];
                    while ((bytesRead = fs.Read(buffer, 0, buffer.Length)) != 0)
                    {
                        requestStream.Write(buffer, 0, bytesRead);
                    }

                    // Flush
                    requestStream.Flush();
                }
            }

            DateTime beforeDT = System.DateTime.Now;
            using (var response = request.GetResponse() as HttpWebResponse)
            {
                DateTime afterDT = System.DateTime.Now;
                TimeSpan ts = afterDT.Subtract(beforeDT);
                result.company = "Microsoft";
                result.spantime = ((double)ts.TotalMilliseconds / 1000).ToString("f2");

                if(response.StatusCode == HttpStatusCode.OK)
                {
                    Stream myResponseStream = response.GetResponseStream();
                    StreamReader myStreamReader = new StreamReader(myResponseStream, Encoding.UTF8);
                    retString = myStreamReader.ReadToEnd();
                    var jObject = JObject.Parse(retString);
                    var text = jObject["DisplayText"];
                    if(text == null)
                    {
                        result.text = null;
                    }
                    else
                    {
                        result.text = text.ToString().Trim();
                    } 
                }
                else
                {
                    return null;
                }
            }
            
            return result;
        }
    }
}
