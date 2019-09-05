using System;
using System.IO;
using System.Text;

namespace TranslatorServer.Utils
{
    public class LogHelper
    {
        public static void WriteLog(string sourceName, Exception ex)
        {

            WriteLog($"{sourceName}\r\n{ex.Message}\r\n{ex.Source}\r\n{ex.StackTrace}\r\n{ex.TargetSite}");
        }

        public static void WriteLog(string logInfo)
        {

            string filePath = Path.Combine(Environment.CurrentDirectory, "ErrorLog");
            if (Directory.Exists(filePath) == false)
            {
                Directory.CreateDirectory(filePath);
            }

            string fileName = $"{DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss-ffff")}_Log.log";
            string file = Path.Combine(filePath, fileName);

            File.WriteAllText(file, logInfo, Encoding.UTF8);
        }
    }
}
