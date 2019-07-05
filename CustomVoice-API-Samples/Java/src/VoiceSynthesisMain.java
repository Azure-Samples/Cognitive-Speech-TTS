import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.MalformedURLException;
import java.net.URI;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;
import java.util.UUID;

import org.json.JSONException;
import org.json.JSONObject;

import io.swagger.client.ApiException;
import io.swagger.client.ApiResponse;
import io.swagger.client.api.VoiceSynthesisApi;
import io.swagger.client.model.Voice;
import io.swagger.client.model.VoiceSynthesis;
import io.swagger.client.model.VoiceSynthesis.StatusEnum;
import com.squareup.okhttp.Response;

public class VoiceSynthesisMain {

	//Cognitive service link
    //https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

	public static void main(String[] args) throws ApiException, IOException, InterruptedException, JSONException {
		if(args.length<7) {
			System.out.println("Not enough arguments. Expected number of arguments is 7.\n"
					+ "endpoint: i.e. https://centralindia.cris.ai \n"
					+ "ibizaStsUrl: i.e. https://centralindia.api.cognitive.microsoft.com/sts/v1.0/issueToken \n"
					+ "subscriptionKey: a standard one acquired from Azure \n"
					+ "localInputTextFile: i.e. \\Java project\\VoiceSynthsisAPIToJAVA\\en-US.txt \n"
					+ "locale: i.e. it-IT \n"
					+ "voiceName: i.e. ElsaNeural \n"
					+ "concatenateResult: true or false. Whether you want the output file to be one part or multipart. \n"
					+ "Program exited.");
			return;
		}
		String endpoint =  args[0];
        String ibizaStsUrl =  args[1];
        // the Subscription key should be a standard one, not the free one.
        String subscriptionKey = args[2];
        // The input text file could contains only plain text or only SSML or mixed together(as shown in blow script)
        // The input text file encoding format should be UTF-8-BOM
        // The input text file should contains at least 50 lines of text
        String localInputTextFile = args[3];
        
        String locale = args[4];
        String voiceName = args[5];
        if(!new File(localInputTextFile).exists()) {
        	System.out.println("Input input text file does not exist. Program exited.");
        	return;
        }
        
        // indicate if want concatenate the output waves with a single file or not. True or false
        String concatenateResult = args[6];
		VoiceSynthsisAPIs(endpoint, ibizaStsUrl, subscriptionKey, localInputTextFile, locale, voiceName, concatenateResult);

	}
	
	
	private static void VoiceSynthsisAPIs(String endpoint, String ibizaStsUrl, String subscriptionKey, String
			localInputTextFile, String locale, String voiceName, String concatenateResult) 
					throws ApiException, IOException, InterruptedException, JSONException
    {
		


        final String name = "Simple neural TTS batch synthesis";
        final String description = "Simple neural TTS batch synthesis description";

        // public voice means the voice could be used by all Subscriptions, if the voice is private(for your Subscription only), this should be set to false
        boolean isPublicVoice = true;

        // you can directly set the voiceId or query the voice information by name/locale/ispublic properties from server.
        //var voiceId = new Guid("Your voice model Guid");
        
        VoiceSynthesisApi voiceApi=new VoiceSynthesisApi(subscriptionKey, endpoint);
        
        UUID voiceId = GetVoiceId( voiceApi, locale, voiceName, isPublicVoice);
        
        if (voiceId.getLeastSignificantBits()==0L && voiceId.getMostSignificantBits()==0L)
        {
            System.out.println("Does not have a available voice for locale :"+locale+ ", name : "+voiceName+", public : "+isPublicVoice);
            return;
        }

        File file=new File(localInputTextFile);
        // Submit a voice synthesis request and get a ID
        //URI synthesisLocation = customVoiceAPI.CreateVoiceSynthesis(name, description, locale, localInputTextFile, voiceId, concatenateResult);
        
        JSONObject properties = new JSONObject(); 
        
        properties.put("ConcatenateResult", concatenateResult); 
        
        Response res=voiceApi.NewcreateVoiceSynthesisWithHttpInfo(name, description, locale, voiceId.toString(), properties.toString(),file);
        List<String> synthesisLocation=res.headers("Location");
        if(synthesisLocation==null ||synthesisLocation.size()==0) {
        	System.out.println("No synthesis location returned from server. Program exited.");
        }
        String[] seq=synthesisLocation.get(0).toString().split("/");
        UUID synthesisId = UUID.fromString(seq.length>0?seq[seq.length-1]:"");

        System.out.println("Checking status.");
        // check for the status of the submitted synthesis every 10 sec. (can also be 1, 2, 5 min depending on usage)
        boolean completed = false;
        while (!completed)
        {
            //var synthesis = customVoiceAPI.s(synthesisId);
        	VoiceSynthesis synthesis=voiceApi.getVoiceSynthesis(synthesisId);
        	
            switch (synthesis.getStatus().toString())
            {
                case "Failed":
                case "Succeeded":
                    completed = true;
                    // if the synthesis was successfull, download the results to local
                    if (synthesis.getStatus().toString() == "Succeeded")
                    {
                        String resultsUri = synthesis.getResultsUrl();
                        System.out.println(resultsUri);
                        URL url=new URL(resultsUri);
                        //WebClient webClient = new WebClient();
                        //String filename = Path.GetTempFileName()+"_"+synthesis.Id+"_.zip";
                        //webClient.DownloadFile(resultsUri, filename);
                        
                        File filename=File.createTempFile("_"+synthesis.getId()+"_", ".zip");
                        try (BufferedInputStream inputStream = new BufferedInputStream(url.openStream());  
                        		  FileOutputStream fileOS = new FileOutputStream(filename)) {
                        		    byte data[] = new byte[1024];
                        		    int byteContent;
                        		    while ((byteContent = inputStream.read(data, 0, 1024)) != -1) {
                        		        fileOS.write(data, 0, byteContent);
                        		    }
                        		} catch (IOException e) {
                        		    // handles IO exceptions
                        		}
                        System.out.println("Synthesis succeeded. Results: "+filename);
                    }
                    break;

                case "Running":
                    break;

                case "NotStarted":
                    break;
            }

            System.out.println("Syntheses status: "+ synthesis.getStatus());
            //await Task.Delay(TimeSpan.FromSeconds(10)).ConfigureAwait(false);
            Thread.sleep(10*1000L);
        }

        System.out.println("Press any key...");
        Scanner input=new Scanner(System.in);
        input.nextLine();
    }
	
	 private static UUID GetVoiceId( VoiceSynthesisApi voiceApi, String locale, String voiceName, boolean publicVoice) throws ApiException
     {
         // Get available voices list
		 //VoiceSynthesisApi voiceApi=new VoiceSynthesisApi();
         Iterable<Voice> voices = voiceApi.getSupportedVoicesForVoiceSynthesis();
         Voice voice = null;
         List<Voice> list=new ArrayList<>();
         
         
         if (publicVoice)
         {
        	 for(Voice v:voices)
             {
            	 if( v.getName().contains(voiceName) &&v.getLocale().equals(locale) && v.isIsPublicVoice())
            		 list.add(v);
             }
        	 voice=(list.size()>0)?list.get(0):null;
        	 
         }
         else
         {
        	 for(Voice v:voices)
             {
            	 if(v.getLocale().equals(locale) && v.getName().contains(voiceName))
            		 list.add(v);
             }
        	 voice=(list.size()>0)?list.get(0):null;
         }
         if (voice == null)
         {
             System.out.println("Does not have a available voice for locale : "+locale+", name : "+ voiceName+", public : "+publicVoice);
             return new UUID( 0L , 0L );
         }
         return voice.getId();
     }
	
	
	

}
