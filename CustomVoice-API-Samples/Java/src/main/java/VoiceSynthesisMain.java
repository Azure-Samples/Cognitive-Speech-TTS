import java.io.File;
import java.io.IOException;

import org.json.JSONException;
import org.json.JSONArray;

import io.swagger.client.ApiException;
import io.swagger.client.api.VoiceSynthesisApi;
import io.swagger.client.model.Voice;
import io.swagger.client.model.VoiceSynthesis;

public class VoiceSynthesisMain {
	
	// Cognitive service link
	// https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication
	
	public static void main (String[] args) throws ApiException, IOException, InterruptedException, JSONException {
		if (args.length < 7)
		{
			System.out.println("Not enough arguments. Expected number of arguments is 7.\n"
					+ "endpoint: i.e. https://centralindia.cris.ai \n"
					+ "subscriptionKey: a standard one acquired from Azure \n"
					+ "localInputTextFile: i.e. \\Java project\\VoiceSynthsisAPIToJAVA\\en-US.txt \n"
					+ "locale: i.e. it-IT \n" + "voiceName: i.e. ElsaNeural \n"
					+ "concatenateResult: true or false. Whether you want the output file to be one part or multipart. \n"
					+ "Program exited.");
			//return;
		}
		String endpoint = args[0];
		String ibizaStsUrl = args[1];
		// the Subscription key should be a standard one, not the free one.
		String subscriptionKey = args[2];
		// The input text file could contains only plain text or only SSML or
		// mixed together(as shown in blow script)
		// The input text file encoding format should be UTF-8-BOM
		// The input text file should contains at least 50 lines of text
		String localInputTextFile = args[3];
		
		String locale = args[4];
		String voiceName = args[5];
		if (!new File(localInputTextFile).exists())
		{
			System.out.println("Input input text file does not exist. Program exited.");
			return;
		}
		
		// indicate if want concatenate the output waves with a single file or
		// not. True or false
		String concatenateResult = args[6];

		VoiceSynthesisLib api = new VoiceSynthesisLib("", "");

		Iterable<VoiceSynthesis> reslut = api.GetVoiceSynthesis();
		JSONArray jsonArray=new JSONArray(reslut);
    	
		System.out.println(jsonArray.toString());
		//VoiceSynthesisLib.VoiceSynthsisAPIs(endpoint, ibizaStsUrl, subscriptionKey, localInputTextFile, locale, voiceName, concatenateResult);
		
	}
	
}
