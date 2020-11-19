package customvoice;

import java.io.File;
import java.text.ParseException;
import java.util.Date;
import java.util.List;
import java.util.UUID;

import customvoice.client.ApiClient;
import customvoice.client.ApiException;
import customvoice.model.Voice;
import customvoice.model.VoiceSynthesis;

public class VoiceSynthesisLib {

	private VoiceSynthesisApi voiceSynthesisApi;

	public VoiceSynthesisLib(ApiClient apiClient) {
		voiceSynthesisApi = new VoiceSynthesisApi(apiClient);
	}

	public List<Voice> GetVoice() throws ApiException {
		return voiceSynthesisApi.getSupportedVoicesForVoiceSynthesis();
	}

	public List<VoiceSynthesis> GetVoiceSynthesis(Date timeStart, Date timeEnd, String status, int skip, int top)
			throws ApiException, ParseException {
		return voiceSynthesisApi.getVoiceSyntheses(timeStart, timeEnd, status, skip, top);
	}

	public VoiceSynthesis GetVoiceSynthesis(UUID id) throws ApiException {
		return voiceSynthesisApi.getVoiceSynthesis(id);
	}

	public String SubmitSynthesis(String name, String description, String locale, List<UUID> model, String outputFormat,
			String properties, File script) throws ApiException {
		return voiceSynthesisApi.createVoiceSynthesis(name, description, locale, model, outputFormat, properties,
				script);
	}

	public void DeleteSynthesis(UUID id) throws ApiException {
		voiceSynthesisApi.deleteVoiceSynthesis(id);
		return;
	}
}
