/*
 * Speech Services API v3.0-beta1
 */

package customvoice;

import java.io.File;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.UUID;

import org.apache.commons.cli.CommandLine;
import org.json.JSONArray;
import org.json.JSONObject;

import customvoice.client.ApiClient;
import customvoice.client.ApiException;
import customvoice.client.Configuration;
import customvoice.client.DateFormatHelper;
import customvoice.model.Voice;
import customvoice.model.VoiceSynthesis;

public class ApiHandler {
	public static void executeApi(CommandLine cli) {
		String region = cli.getOptionValue("r");
		String hostPath = String.format(Configuration.HostUri, region);
		String subscriptionKey = cli.getOptionValue("subscriptionkey");

		ApiClient apiClient = new ApiClient(hostPath);
		apiClient.setApiKey(subscriptionKey);
		VoiceSynthesisLib api = new VoiceSynthesisLib(apiClient);

		try {
			if (cli.hasOption("create")) {
				String name = cli.getOptionValue("name");
				if (name == null) {
					System.out.println("Please enter the name of voice synthesis task");
					return;
				}

				String description = cli.getOptionValue("description");
				if (description == null) {
					description = "";
				}

				String locale = cli.getOptionValue("locale");
				if (locale == null) {
					System.out.println("Please enter the locale of the model voice synthesis task used");
					return;
				}

				String modelList = cli.getOptionValue("modelidlist");
				if (modelList == null) {
					System.out
							.println("Please enter the model list of the voice synthesis task used, separated by ';'");
					return;
				}
				List<UUID> model = new ArrayList<UUID>();
				for (String id : modelList.split(";")) {
					model.add(UUID.fromString(id));
				}

				String outputFormat = cli.getOptionValue("outputformat");
				if (outputFormat == null) {
					outputFormat = "riff-16khz-16bit-mono-pcm";
				}

				String properties = "";
				if (cli.hasOption("concatenateresult")) {
					properties = "{\"ConcatenateResult\": \"true\"}";
				}

				String scriptFile = cli.getOptionValue("scriptfile");
				if (scriptFile == null) {
					System.out.println("Please enter the script file path");
					return;
				}
				File script = new File(scriptFile);

				String synthesisId = api.SubmitSynthesis(name, description, locale, model, outputFormat, properties,
						script);
				System.out.printf("Submit synthesis request successful , id: %s", synthesisId);
				return;
			} else if (cli.hasOption("getvoice")) {
				List<Voice> reslut = api.GetVoice();
				System.out.println(new JSONArray(reslut));
			} else if (cli.hasOption("getvoicesynthesis")) {
				String timeStarts = cli.getOptionValue("timestart");
				String timeEnds = cli.getOptionValue("timeend");
				String status = cli.getOptionValue("status");
				String skips = cli.getOptionValue("skip");
				int skip = -1;
				if (skips != null) {
					try {
						skip = Integer.parseInt(skips);
						if (skip < 0) {
							System.out.println(
									"Please enter a valid skip parameter, should be an integer greater or equals 0");
							return;
						}
					} catch (NumberFormatException e) {
						System.out.println(
								"Please enter a valid skip parameter, should be an integer greater or equals 0");
						return;
					}
				}
				int top = -1;
				String tops = cli.getOptionValue("top");
				if (tops != null) {
					try {
						top = Integer.parseInt(tops);
						if (top < 0) {
							System.out
									.println("Please enter a valid top parameter, should be an integer greater than 0");
							return;
						}
					} catch (NumberFormatException e) {
						System.out.println("Please enter a valid top parameter, should be an integer greater than 0");
						return;
					}
				}
				Date timeStart = null;
				if (timeStarts != null) {
					try {
						timeStart = DateFormatHelper.parseToDate(timeStarts);
					} catch (NumberFormatException e) {
						System.out.println("Please enter a valid timestart parameter, like 2020-05-01 12:00");
						return;
					}
				}
				Date timeEnd = null;
				if (timeEnds != null) {
					try {
						timeEnd = DateFormatHelper.parseToDate(timeEnds);
					} catch (NumberFormatException e) {
						System.out.println("Please enter a valid timeend parameter, like 2020-05-15");
						return;
					}
				}
				List<VoiceSynthesis> result = api.GetVoiceSynthesis(timeStart, timeEnd, status, skip, top);
				System.out.println(new JSONArray(result));
			} else if (cli.hasOption("getvoicesynthesisbyid")) {
				String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
				if (voiceSynthesisId == null) {
					System.out.println("Please enter Voice Synthesis Id");
					return;
				}
				VoiceSynthesis reslut = api.GetVoiceSynthesis(UUID.fromString(voiceSynthesisId));
				System.out.println(new JSONObject(reslut));
			} else if (cli.hasOption("delete")) {
				String voiceSynthesisId = cli.getOptionValue("voicesynthesisid");
				if (voiceSynthesisId == null) {
					System.out.println("Please enter Voice Synthesis Id");
					return;
				}
				api.DeleteSynthesis(UUID.fromString(voiceSynthesisId));
				System.out.printf("Delete successful, id : %s", voiceSynthesisId);
			} else {
				System.out.println("Please enter the action you need to perform");
			}
		} catch (Exception e) {
			System.out.println(
					"Request failed, wrong parameter or request timed out, please check the parameters and try again.");
			System.out.println("We got unexpected: " + e.getMessage());
			if (e instanceof ApiException) {
				System.out.println("Response body: " + ((ApiException) e).getResponseBody());
			}
			e.printStackTrace();
			return;
		}
	}
}
