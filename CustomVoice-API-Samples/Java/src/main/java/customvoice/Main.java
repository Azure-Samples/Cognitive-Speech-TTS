package customvoice;

import java.io.IOException;

import org.apache.commons.cli.CommandLine;
import org.apache.commons.cli.CommandLineParser;
import org.apache.commons.cli.DefaultParser;
import org.apache.commons.cli.HelpFormatter;
import org.apache.commons.cli.Option;
import org.apache.commons.cli.Options;
import org.apache.commons.cli.ParseException;

import customvoice.client.ApiException;

public class Main {

	// Cognitive service link
	// https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-apis#authentication

	public static void main(String[] args) throws ApiException, IOException, InterruptedException {
		CommandLine cli = null;
		CommandLineParser cliParser = new DefaultParser();
		HelpFormatter helpFormatter = new HelpFormatter();

		Options options = SetArgsOptions();

		try {
			cli = cliParser.parse(options, args);
		} catch (ParseException e) {
			helpFormatter.printHelp(">>>>>> parameter options", options);
			return;
		}

		ApiHandler.executeApi(cli);
		return;
	}

	private static Options SetArgsOptions() {
		Options options = new Options();

		Option opt1 = new Option("c", "create", false, "Creates a new synthesis task");
		opt1.setRequired(false);
		options.addOption(opt1);
		Option opt2 = new Option("gv", "getvoice", false, "Gets a list of supported voices for synthesis");
		opt2.setRequired(false);
		options.addOption(opt2);
		Option opt3 = new Option("gvs", "getvoicesynthesis", false, "Gets a list of voice synthesis");
		opt3.setRequired(false);
		options.addOption(opt3);
		Option opt4 = new Option("gvsi", "getvoicesynthesisbyid", false, "Gets voice synthesis by Id");
		opt4.setRequired(false);
		options.addOption(opt4);
		Option opt5 = new Option("dvs", "delete", false, "Deletes the specified voice synthesis task.");
		opt5.setRequired(false);
		options.addOption(opt5);
		Option opt6 = new Option("r", "region", true,
				"i.e. centralindia, see the following link for a list of supported regions https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/regions#speech-to-text-text-to-speech-and-translation");
		opt6.setRequired(true);
		options.addOption(opt6);
		Option opt7 = new Option("s", "subscriptionkey", true, "The Speech service subscription key");
		opt7.setRequired(true);
		options.addOption(opt7);
		Option opt8 = new Option("n", "name", true, "The name of synthesis task");
		opt8.setRequired(false);
		options.addOption(opt8);
		Option opt9 = new Option("d", "description", true, "The description of synthesis task");
		opt9.setRequired(false);
		options.addOption(opt9);
		Option opt10 = new Option("l", "locale", true, "The locale information like zh-CN/en-US");
		opt10.setRequired(false);
		options.addOption(opt10);
		Option opt11 = new Option("m", "modelidlist", true,
				"The id list of the model which used to synthesis, separated by ';'");
		opt11.setRequired(false);
		options.addOption(opt11);
		Option opt12 = new Option("vsi", "voicesynthesisid", true, "The id of the synthesis task");
		opt12.setRequired(false);
		options.addOption(opt12);
		Option opt13 = new Option("of", "outputformat", true,
				"The output audio format, like: riff-16khz-16bit-mono-pcm");
		opt13.setRequired(false);
		options.addOption(opt13);
		Option opt14 = new Option("sf", "scriptfile", true, "The input text file path");
		opt14.setRequired(false);
		options.addOption(opt14);
		Option opt15 = new Option("cr", "concatenateresult", false, "If concatenate result in a single wave file");
		opt15.setRequired(false);
		options.addOption(opt15);
		Option opt16 = new Option("ts", "timestart", true,
				"The timestart filter of the voice synthesis query, like 2020-05-01 12:00");
		opt16.setRequired(false);
		options.addOption(opt16);
		Option opt17 = new Option("te", "timeend", true,
				"The timeend filter of the voice synthesis query, like 2020-05-15");
		opt17.setRequired(false);
		options.addOption(opt17);
		Option opt18 = new Option("st", "status", true,
				"The status filter of the voice synthesis query, could be NotStarted/Running/Succeeded/Failed");
		opt18.setRequired(false);
		options.addOption(opt18);
		Option opt19 = new Option("sk", "skip", true,
				"The skip filter of the voice synthesis query, should be a integer value");
		opt19.setRequired(false);
		options.addOption(opt19);
		Option opt20 = new Option("tp", "top", true,
				"The top filter of the voice synthesis query, should be a integer value");
		opt20.setRequired(false);
		options.addOption(opt20);

		return options;
	}
}
