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

		try{
			if (cli.hasOption("create")){
				String name = cli.getOptionValue("name");
				if(name == null){
					System.out.println("Please enter the name of voice synthesis task");
					return ;
				}
	
				String description = cli.getOptionValue("description");
				if(description == null){
					description = "";
				}
	
				String locale = cli.getOptionValue("locale");
				if(locale == null){
					System.out.println("Please enter the locale of the model voice synthesis task used");
					return ;
				}
	
				String modelList = cli.getOptionValue("modelidlist");
				if(modelList == null){
					System.out.println("Please enter the model list of the voice synthesis task used, separated by ';'");
					return ;
				}
				List<UUID> model = new ArrayList<UUID>();
				for (String id : modelList.split(";")) {
					model.add(UUID.fromString(id));
				}
	
				String outputFormat = cli.getOptionValue("outputformat");
				if(outputFormat == null){
					outputFormat = "riff-16khz-16bit-mono-pcm";
				}
	
				String properties = ""; 
				if(cli.hasOption("concatenateresult")){
					properties="{\"ConcatenateResult\": \"true\"}";
				}
	
				String scriptFile = cli.getOptionValue("scriptfile");
				if(scriptFile == null){
					System.out.println("Please enter the script file path");
					return ;
				}
				File script = new File(scriptFile);
				
				api.SubmitSynthesis(name, description, locale, model, outputFormat, properties, script);
			}
			else if(cli.hasOption("getvoice")){
				List<Voice> reslut = api.GetVoice();
				System.out.println(new JSONArray(reslut));
			}
			else if(cli.hasOption("getvoicesynthesis")){
				String timeStart = cli.getOptionValue("timestart");
				String timeEnd = cli.getOptionValue("timeend");
				String status = cli.getOptionValue("status");
				String skips = cli.getOptionValue("skip");
				int skip = -1;
				if(skips != null)
				{
					try
					{
						skip = Integer.parseInt(skips);
						if(skip < 0)
						{
							System.out.println("Please enter a valid skip parameter, should be a ingeter greater or equals 0");
							return ;
						}
					}
					catch (NumberFormatException e)
					{
						System.out.println("Please enter a valid skip parameter, should be a ingeter greater or equals 0");
						return ;
					}
				}
				int top = -1;
				String tops = cli.getOptionValue("top");
				if(tops != null)
				{
					try
					{
						top = Integer.parseInt(tops);
						if(top < 0)
						{
							System.out.println("Please enter a valid top parameter, should be a ingeter greater than 0");
							return ;
						}
					}
					catch (NumberFormatException e)
					{
						System.out.println("Please enter a valid top parameter, should be a ingeter greater than 0");
						return ;
					}
				}
				List<VoiceSynthesis> result = api.GetVoiceSynthesis(timeStart, timeEnd, status, skip, top);
				System.out.println(new JSONArray(result));
			}
			else if(cli.hasOption("getvoicesynthesisbyid")){
				String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
				if(voiceSynthesisId == null){
					System.out.println("Please enter Voice Synthesis Id");
					return ;
				}
				VoiceSynthesis reslut = api.GetVoiceSynthesis(UUID.fromString(voiceSynthesisId));
				System.out.println(new JSONObject(reslut));
			}
			else if(cli.hasOption("delete")){
				String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
				if(voiceSynthesisId == null){
					System.out.println("Please enter Voice Synthesis Id");
					return ;
				}
				api.DeleteSynthesis(UUID.fromString(voiceSynthesisId));
			}
			else{
				System.out.println("Please enter the action you need to perform");
			}
		}
		catch (Exception e) {
			System.out.println("Request failed, wrong parameter or request timed out, please check the parameters and try again.");
			System.out.println("We got unexpected:" + e.getMessage());
			e.printStackTrace();
			return ;
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
		Option opt16 = new Option("ts","timestart",true,"The timestart filter of the voice synthesis query, like 2019-11-21 15:26:21");
		opt16.setRequired(false);
		options.addOption(opt16);
		Option opt17 = new Option("te","timeend",true,"The timeend filter of the voice synthesis query, like 2019-11-21 15:26:21");
		opt17.setRequired(false);
		options.addOption(opt17);
		Option opt18 = new Option("st","status",true,"The status filter of the voice synthesis query, could be NotStarted/Running/Succeeded/Failed");
		opt18.setRequired(false);
		options.addOption(opt18);
		Option opt19 = new Option("sk","skip",true,"The skip filter of the voice synthesis query, should be a interger value");
		opt19.setRequired(false);
		options.addOption(opt19);
		Option opt20 = new Option("tp","top",true,"The top filter of the voice synthesis query, should be a interger value");
		opt20.setRequired(false);
		options.addOption(opt20);

		return options;
	}
}
