/*
 * Speech Services API v3.0-beta1
 */

package customvoice;

import java.io.File;
import java.lang.reflect.Type;
import java.text.ParseException;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.google.gson.reflect.TypeToken;

import customvoice.client.ApiClient;
import customvoice.client.ApiException;
import customvoice.client.ApiResponse;
import customvoice.client.Configuration;
import customvoice.client.DateFormatHelper;
import customvoice.model.PaginatedEntities;
import customvoice.model.Voice;
import customvoice.model.VoiceSynthesis;

public class VoiceSynthesisApi {
	private ApiClient apiClient;

	public VoiceSynthesisApi(ApiClient apiClient) {
		this.apiClient = apiClient;
	}

	/**
	 * Creates a new synthesis.
	 * 
	 * @param name        The name information (always add this string for any voice
	 *                    synthesis). (optional)
	 * @param description Optional description information (optional)
	 * @param locale      The locale information (always add this string for any
	 *                    voice synthesis). (optional)
	 * @param model       The model GUID information (always add this string for any
	 *                    voice synthesis). (optional)
	 * @param properties  Optional properties of this voice synthesis (json
	 *                    serialized object with key/values, where all values must
	 *                    be strings) (optional)
	 * @param script      The script text file of the voice synthesis. (optional)
	 * @throws ApiException If fail to call the API, e.g. server error or cannot
	 *                      deserialize the response body
	 */
	public String createVoiceSynthesis(String name, String description, String locale, List<UUID> model,
			String outputFormat, String properties, File script) throws ApiException {
		String localVarPath = Configuration.VoiceSynthesis_BasePath;
		Map<String, Object> localVarFormParams = new HashMap<String, Object>();
		Type localVarReturnType = new TypeToken<VoiceSynthesis>() {
		}.getType();

		if (name != null)
			localVarFormParams.put("name", name);
		if (description != null)
			localVarFormParams.put("description", description);
		if (locale != null)
			localVarFormParams.put("locale", locale);
		if (model != null)
			localVarFormParams.put("model", model);
		if (properties != null)
			localVarFormParams.put("properties", properties);
		if (script != null)
			localVarFormParams.put("script", script);
		if (outputFormat != null)
			localVarFormParams.put("outputFormat", outputFormat);
		ApiResponse<Object> resp = apiClient.post(localVarPath, localVarFormParams, localVarReturnType);
		List<String> locationValues = resp.getHeaders().get("Location");
		if (locationValues != null && !locationValues.isEmpty()) {
			String[] splitLocation = locationValues.get(0).split("/");
			return splitLocation[splitLocation.length - 1];
		}
		return "No synthesis ID returned.";
	}

	/**
	 * Deletes the specified voice synthesis task.
	 * 
	 * @param id The identifier of the synthesis. (required)
	 * @return ErrorContent
	 * @throws ApiException If fail to call the API, e.g. server error or cannot
	 *                      deserialize the response body
	 */
	public void deleteVoiceSynthesis(UUID id) throws ApiException {
		// verify the required parameter 'id' is set
		if (id == null) {
			throw new ApiException("Missing the required parameter 'id' when calling deleteVoiceSynthesis(Async)");
		}

		String localVarPath = Configuration.VoiceSynthesis_BasePath + "/" + apiClient.escapeString(id.toString());
		apiClient.delete(localVarPath);
	}

	/**
	 * Gets a list of supported voices for offline synthesis.
	 * 
	 * @return List&lt;Voice&gt;
	 * @throws ApiException If fail to call the API, e.g. server error or cannot
	 *                      deserialize the response body
	 */
	public List<Voice> getSupportedVoicesForVoiceSynthesis() throws ApiException {
		String localVarPath = Configuration.VoicePath;
		Type localVarReturnType = new TypeToken<List<Voice>>() {
		}.getType();
		ApiResponse<List<Voice>> resp = apiClient.getJson(localVarPath, localVarReturnType);
		return resp.getData();
	}

	/**
	 * Gets a list of voice synthesis under the selected subscription.
	 * 
	 * @param timeStart The timeStart filter
	 * @param timeEnd   The timeEnd filter
	 * @param status    The status filter
	 * @param skip      The skip filter
	 * @param top       The top filter
	 * @return List&lt;VoiceSynthesis&gt;
	 * @throws ApiException   If fail to call the API, e.g. server error or cannot
	 *                        deserialize the response body
	 * @throws ParseException
	 */
	public List<VoiceSynthesis> getVoiceSyntheses(Date timeStart, Date timeEnd, String status, int skip, int top)
			throws ApiException, ParseException {
		String localVarPath = Configuration.PaginatedVoiceSynthesisPath + "?";
		Type localVarReturnType = new TypeToken<PaginatedEntities<VoiceSynthesis>>() {
		}.getType();

		if (timeStart != null) {
			localVarPath += "&timestart=" + DateFormatHelper.parseToString(timeStart);
		}

		if (timeEnd != null) {
			localVarPath += "&timeend=" + DateFormatHelper.parseToString(timeEnd);
		}

		if (status != null) {
			localVarPath += "&status=" + status;
		}

		if (skip != -1) {
			localVarPath += "&skip=" + skip;
		} else {
			localVarPath += "&skip=0";
		}

		if (top != -1) {
			localVarPath += "&top=" + top;
		} else {
			localVarPath += "&top=100";
		}

		localVarPath = localVarPath.replaceAll(" ", "%20");

		ApiResponse<PaginatedEntities<VoiceSynthesis>> resp = apiClient.getJson(localVarPath, localVarReturnType);

		return resp.getData().getValues();
	}

	/**
	 * Gets the voice synthesis identified by the given ID.
	 * 
	 * @param id The identifier of the synthesis. (required)
	 * @return VoiceSynthesis
	 * @throws ApiException If fail to call the API, e.g. server error or cannot
	 *                      deserialize the response body
	 */
	public VoiceSynthesis getVoiceSynthesis(UUID id) throws ApiException {
		// verify the required parameter 'id' is set
		if (id == null) {
			throw new ApiException("Missing the required parameter 'id' when calling getVoiceSynthesis(Async)");
		}

		String localVarPath = Configuration.VoiceSynthesis_BasePath + "/" + apiClient.escapeString(id.toString());
		Type localVarReturnType = new TypeToken<VoiceSynthesis>() {
		}.getType();
		ApiResponse<VoiceSynthesis> resp = apiClient.getJson(localVarPath, localVarReturnType);
		return resp.getData();
	}
}
