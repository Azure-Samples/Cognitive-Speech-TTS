import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;
import java.util.UUID;

import org.json.JSONException;
import org.json.JSONObject;

import com.squareup.okhttp.Response;

import io.swagger.client.ApiException;
import io.swagger.client.api.VoiceSynthesisApi;
import io.swagger.client.model.Voice;
import io.swagger.client.model.VoiceSynthesis;

public class VoiceSynthesisLib {
	public static void VoiceSynthsisAPIs(String endpoint, String ibizaStsUrl, String subscriptionKey,
			String localInputTextFile, String locale, String voiceName, String concatenateResult) throws ApiException,
			IOException, JSONException, InterruptedException {

		final String name = "Simple neural TTS batch synthesis";
		final String description = "Simple neural TTS batch synthesis description";

		// public voice means the voice could be used by all Subscriptions, if
		// the voice is private(for your Subscription only), this should be set
		// to false
		boolean isPublicVoice = true;

		// you can directly set the voiceId or query the voice information by
		// name/locale/ispublic properties from server.
		// var voiceId = new Guid("Your voice model Guid");

		VoiceSynthesisApi voiceApi = new VoiceSynthesisApi(subscriptionKey, endpoint);

		UUID FemaleVoiceId = GetVoiceId(voiceApi, locale, voiceName, isPublicVoice);

		if (FemaleVoiceId.getLeastSignificantBits() == 0L && FemaleVoiceId.getMostSignificantBits() == 0L) {
			System.out.println("1Does not have a available voice for locale :" + locale + ", name : " + voiceName
					+ ", public : " + isPublicVoice);
			return;
		}
		List<UUID> modelIds = new ArrayList<>();
		modelIds.add(FemaleVoiceId);

		String outputFormat = "riff-16khz-16bit-mono-pcm";
		/*
		 * Available output format: "riff-8khz-16bit-mono-pcm",
		 * "riff-16khz-16bit-mono-pcm", "riff-24khz-16bit-mono-pcm",
		 * "riff-48khz-16bit-mono-pcm", "audio-16khz-32kbitrate-mono-mp3",
		 * "audio-16khz-64kbitrate-mono-mp3", "audio-16khz-128kbitrate-mono-mp3",
		 * "audio-24khz-48kbitrate-mono-mp3", "audio-24khz-96kbitrate-mono-mp3",
		 * "audio-24khz-160kbitrate-mono-mp3",
		 */

		File file = new File(localInputTextFile);
		// Submit a voice synthesis request and get a ID
		// URI synthesisLocation = customVoiceAPI.CreateVoiceSynthesis(name,
		// description, locale, localInputTextFile, voiceId, concatenateResult);

		JSONObject properties = new JSONObject();

		properties.put("ConcatenateResult", concatenateResult);

		Response res = voiceApi.NewcreateVoiceSynthesisWithHttpInfo(name, description, locale, modelIds, outputFormat,
				properties.toString(), file);
		List<String> synthesisLocation = res.headers("Location");
		if (synthesisLocation == null || synthesisLocation.size() == 0) {
			System.out.println("No synthesis location returned from server. Program exited.");
		}
		String[] seq = synthesisLocation.get(0).toString().split("/");
		UUID synthesisId = UUID.fromString(seq.length > 0 ? seq[seq.length - 1] : "");

		System.out.println("Checking status.");
		// check for the status of the submitted synthesis every 10 sec. (can
		// also be 1, 2, 5 min depending on usage)
		boolean completed = false;
		while (!completed) {
			// var synthesis = customVoiceAPI.s(synthesisId);
			VoiceSynthesis synthesis = voiceApi.getVoiceSynthesis(synthesisId);

			switch (synthesis.getStatus().toString()) {
			case "Failed":
			case "Succeeded":
				completed = true;
				// if the synthesis was successfull, download the results to
				// local
				if (synthesis.getStatus().toString() == "Succeeded") {
					String resultsUri = synthesis.getResultsUrl();
					System.out.println(resultsUri);
					URL url = new URL(resultsUri);
					// WebClient webClient = new WebClient();
					// String filename =
					// Path.GetTempFileName()+"_"+synthesis.Id+"_.zip";
					// webClient.DownloadFile(resultsUri, filename);

					File filename = File.createTempFile("_" + synthesis.getId() + "_", ".zip");
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
					System.out.println("Synthesis succeeded. Results: " + filename);
				}
				break;

			case "Running":
				break;

			case "NotStarted":
				break;
			}

			System.out.println("Syntheses status: " + synthesis.getStatus());
			// await Task.Delay(TimeSpan.FromSeconds(10)).ConfigureAwait(false);
			Thread.sleep(10 * 1000L);
		}

		System.out.println("Press any key...");
		Scanner input = new Scanner(System.in);
		input.nextLine();
	}

	public static UUID GetVoiceId(VoiceSynthesisApi voiceApi, String locale, String voiceName, boolean publicVoice)
			throws ApiException {
		// Get available voices list
		// VoiceSynthesisApi voiceApi=new VoiceSynthesisApi();
		Iterable<Voice> voices = voiceApi.getSupportedVoicesForVoiceSynthesis();
		Voice voice = null;
		List<Voice> list = new ArrayList<>();

		if (publicVoice) {
			for (Voice v : voices) {
				if (v.getName().contains(voiceName) && v.getLocale().equals(locale) && v.isIsPublicVoice())
					list.add(v);
			}
			voice = (list.size() > 0) ? list.get(0) : null;

		} else {
			for (Voice v : voices) {
				if (v.getLocale().equals(locale) && v.getName().contains(voiceName))
					list.add(v);
			}
			voice = (list.size() > 0) ? list.get(0) : null;
		}
		if (voice == null) {
			System.out.println("Does not have a available voice for locale : " + locale + ", name : " + voiceName
					+ ", public : " + publicVoice);
			return new UUID(0L, 0L);
		}
		return voice.getId();
	}
}
