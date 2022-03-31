namespace ConsoleApp1
{
    using LongAudioSynthesisSample;
    using LongAudioSynthesisSample.Models;
    using System;
    using System.Globalization;
    using System.Linq;
    using System.Threading.Tasks;

    class Program
    {
        static async Task Main(string[] args)
        {
            var hostName = "<host name>";
            var subscriptionKey = "<subscription key>";

            var synthesisClient = new LongAudioSynthesisClient(hostName, subscriptionKey);
            
            // Get a list of supported voices
            var voices = await synthesisClient.GetSupportedVoicesAsync().ConfigureAwait(false);
            
            // Get all synthesis tasks.
            var syntheses = await synthesisClient.GetAllSynthesesAsync().ConfigureAwait(false);

            // Create a new synthesis task
            var newSynthesisUri = await synthesisClient.CreateSynthesisAsync(
                new CultureInfo("en-US"),
                "en-us-JennyNeural",
                "sample long audio synthesis",
                "sample description",
                "./enUSScriptSample.txt").ConfigureAwait(false);

            var newSynthesisId = Guid.Parse(newSynthesisUri.Segments.Last());

            // Get a synthesis task.
            var synthesis = await synthesisClient.GetSynthesisAsync(newSynthesisId).ConfigureAwait(false);

            // Poll the synthesis until it completes
            var terminatedStates = new[] { "Succeeded", "Failed" };
            while (!terminatedStates.Contains(synthesis.Status))
            {
                Console.WriteLine($"Synthesis {newSynthesisId}. Status: {synthesis.Status}");
                await Task.Delay(TimeSpan.FromSeconds(30)).ConfigureAwait(false);
                synthesis = await synthesisClient.GetSynthesisAsync(newSynthesisId).ConfigureAwait(false);
            }

            // Get result of a synthesis
            var files = await synthesisClient.GetSynthesisFilesAsync(newSynthesisId).ConfigureAwait(false);
            var resultFile = files.FirstOrDefault(f => f.Kind == FileKind.LongAudioSynthesisResult);
            if (resultFile != null) 
            {
                Console.WriteLine("Please download result from this URL.");
                Console.WriteLine(resultFile.Links.ContentUrl);
            }

            // Delete a specific synthesis
            await synthesisClient.DeleteSynthesisAsync(newSynthesisId);


        }
    }
}
