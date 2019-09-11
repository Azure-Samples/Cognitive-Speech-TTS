package CustomVoiceAPI;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.io.File;
import java.io.IOException;

import org.apache.commons.cli.*;
import org.json.JSONArray;
import org.json.JSONObject;

import io.swagger.client.ApiClient;
import io.swagger.client.ApiException;
import io.swagger.client.model.Voice;
import io.swagger.client.model.VoiceSynthesis;

public class VoiceSynthesisMain {
	
	// Cognitive service link
	// https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

	public static void main (String[] args) throws ApiException, IOException, InterruptedException {
		CommandLine cli = null;
		CommandLineParser cliParser = new DefaultParser();
		HelpFormatter helpFormatter = new HelpFormatter();

		Options options = SetArgsOptions();

		try {
			cli = cliParser.parse(options, args);
        } catch (ParseException e) {
			helpFormatter.printHelp(">>>>>> parameter options", options);
			return ;
        }

		String hostPath = cli.getOptionValue("hosturl");
		String subscriptionKey = cli.getOptionValue("subscriptionkey");

		ApiClient apiClient = new ApiClient(hostPath);
		apiClient.setApiKey(subscriptionKey);
		VoiceSynthesisLib api = new VoiceSynthesisLib(apiClient);

        if (cli.hasOption("create")){
			String name = cli.getOptionValue("name");
			if(name == null){
				System.out.println("Please enter the name of voice synthesis task");
			}

			String description = cli.getOptionValue("description");
			if(description == null){
				description = "";
			}

			String locale = cli.getOptionValue("locale");
			if(locale == null){
				System.out.println("Please enter the locale of the model voice synthesis task used");
			}

			String modelList = cli.getOptionValue("modelidlist");
			if(modelList == null){
				System.out.println("Please enter the model list of the voice synthesis task used, separated by ';'");
			}
			List<UUID> model = new ArrayList<UUID>();
			for (String id : modelList.split(";")) {
				model.add(UUID.fromString(id));
			}

			String outputFormat = cli.getOptionValue("outputformat");
			if(locale == null){
				outputFormat = "riff-16khz-16bit-mono-pcm";
			}

			String properties = ""; 
			if(cli.hasOption("concatenateresult")){
				properties="{\"ConcatenateResult\": \"true\"}";
			}

			String scriptFile = cli.getOptionValue("scriptfile");
			if(scriptFile == null){
				System.out.println("Please enter the script file path");
			}
			File script = new File(scriptFile);
			
			api.SubmitSynthesis(name, description, locale, model, outputFormat, properties, script);
        }
        else if(cli.hasOption("getvoice")){
			List<Voice> reslut = api.GetVoice();
			System.out.println(new JSONArray(reslut));
        }
        else if(cli.hasOption("getvoicesynthesis")){
			List<VoiceSynthesis> reslut = api.GetVoiceSynthesis();
			System.out.println(new JSONArray(reslut));
        }
        else if(cli.hasOption("getvoicesynthesisbyid")){
			String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
			if(voiceSynthesisId == null){
				System.out.println("Please enter Voice Synthesis Id");
			}
			VoiceSynthesis reslut = api.GetVoiceSynthesis(UUID.fromString(voiceSynthesisId));
			System.out.println(new JSONObject(reslut));
		}
		else if(cli.hasOption("delete")){
			String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
			if(voiceSynthesisId == null){
				System.out.println("Please enter Voice Synthesis Id");
			}
			api.DeleteSynthesis(UUID.fromString(voiceSynthesisId));
		}
		else{
			System.out.println("Please enter the action you need to perform");
		}

		return;
	}

	private static Options SetArgsOptions(){
		Options options = new Options();

		Option opt1 = new Option("c","create",false,"Creates a new synthesis task");
		opt1.setRequired(false);
		options.addOption(opt1);
		Option opt2 = new Option("gv","getvoice",false,"Gets a list of supported voices for synthesis");
		opt2.setRequired(false);   
		options.addOption(opt2);
		Option opt3 = new Option("gvs","getvoicesynthesis",false,"Gets a list of voice synthesis");
		opt3.setRequired(false);
		options.addOption(opt3);
		Option opt4 = new Option("gvsi","getvoicesynthesisbyid",false,"Gets voice synthesis by Id");
		opt4.setRequired(false);
		options.addOption(opt4);
		Option opt5 = new Option("dvs","delete",false,"Deletes the specified voice synthesis task.");
		opt5.setRequired(false);
		options.addOption(opt5);
		Option opt6 = new Option("h","hosturl",true,"i.e. https://centralindia.cris.ai");
		opt6.setRequired(true);  
		options.addOption(opt6);
		Option opt7 = new Option("s","subscriptionkey",true,"The cris subscription key");
		opt7.setRequired(true);
		options.addOption(opt7);
		Option opt8 = new Option("n","name",true,"The name of synthesis task");
		opt8.setRequired(false);
		options.addOption(opt8);
		Option opt9 = new Option("d","description",true,"The description of synthesis task");
		opt9.setRequired(false);
		options.addOption(opt9);
		Option opt10 = new Option("l","locale",true,"The locale information like zh-CN/en-US");
		opt10.setRequired(false);
		options.addOption(opt10);
		Option opt11 = new Option("m","modelidlist",true,"The id list of the model which used to synthesis, separated by ';'");
		opt11.setRequired(false);
		options.addOption(opt11);
		Option opt12 = new Option("vsi","voicesynthesisid",true,"The id of the synthesis task");
		opt12.setRequired(false);
		options.addOption(opt12);
		Option opt13 = new Option("of","outputformat",true,"The output audio format, like: riff-16khz-16bit-mono-pcm");
		opt13.setRequired(false);
		options.addOption(opt13);
		Option opt14 = new Option("sf","scriptfile",true,"The input text file path");
		opt14.setRequired(false);
		options.addOption(opt14);
		Option opt15 = new Option("cr","concatenateresult",false,"If concatenate result in a single wave file");
		opt15.setRequired(false);
		options.addOption(opt15);

		return options;
	}
}
