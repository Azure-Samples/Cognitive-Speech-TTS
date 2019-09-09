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

	private VoiceSynthesisApi voiceApi;

	public VoiceSynthesisLib(String subscriptionKey, String endpoint) {
		voiceApi = new VoiceSynthesisApi(subscriptionKey, endpoint);
	}

	public Iterable<Voice> GetVoice() throws ApiException{
		// Get available voices list
		return voiceApi.getSupportedVoicesForVoiceSynthesis();
	}

	public Iterable<VoiceSynthesis> GetVoiceSynthesis() throws ApiException{
		return voiceApi.getVoiceSyntheses();
	}

	public VoiceSynthesis GetVoiceSynthesis(UUID id) throws ApiException{
		return voiceApi.getVoiceSynthesis(id);
	}

	public boolean SubmitSynthesis() throws ApiException{
		return true;
	}

	public boolean DeleteSynthesis(UUID id) throws ApiException{
		voiceApi.deleteVoiceSynthesis(id);
		return true;
	}
}
