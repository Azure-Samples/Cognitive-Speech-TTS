package CustomVoiceAPI;

import java.io.File;
import java.util.List;
import java.util.UUID;

import io.swagger.client.ApiClient;
import io.swagger.client.ApiException;
import io.swagger.client.api.VoiceSynthesisApi;
import io.swagger.client.model.Voice;
import io.swagger.client.model.VoiceSynthesis;

public class VoiceSynthesisLib {

	private VoiceSynthesisApi voiceApi;

	public VoiceSynthesisLib(ApiClient apiClient) {
		voiceApi = new VoiceSynthesisApi(apiClient);
	}

	public List<Voice> GetVoice() throws ApiException{
		return voiceApi.getSupportedVoicesForVoiceSynthesis();
	}

	public List<VoiceSynthesis> GetVoiceSynthesis(String timeStart, String timeEnd, String status, int skip, int top) throws ApiException{
		return voiceApi.getVoiceSyntheses(timeStart, timeEnd, status, skip, top);
	}

	public VoiceSynthesis GetVoiceSynthesis(UUID id) throws ApiException{
		return voiceApi.getVoiceSynthesis(id);
	}

	public void SubmitSynthesis(String name, String description, String locale, List<UUID> model,
	String outputFormat, String properties, File script) throws ApiException{
		voiceApi.createVoiceSynthesis(name, description, locale, model, outputFormat, properties, script);
		return;
	}

	public void DeleteSynthesis(UUID id) throws ApiException{
		voiceApi.deleteVoiceSynthesis(id);
		return;
	}
}
