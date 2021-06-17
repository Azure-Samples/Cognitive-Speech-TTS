/*
 * Speech Services API v3.0-beta1
 */

package customvoice.client;

import java.io.File;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.lang.reflect.Type;
import java.net.URLConnection;
import java.net.URLEncoder;
import java.util.Collection;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.Map.Entry;

import com.squareup.okhttp.Call;
import com.squareup.okhttp.FormEncodingBuilder;
import com.squareup.okhttp.Headers;
import com.squareup.okhttp.MediaType;
import com.squareup.okhttp.MultipartBuilder;
import com.squareup.okhttp.OkHttpClient;
import com.squareup.okhttp.Request;
import com.squareup.okhttp.RequestBody;
import com.squareup.okhttp.Response;
import com.squareup.okhttp.internal.http.HttpMethod;

import org.threeten.bp.LocalDate;
import org.threeten.bp.OffsetDateTime;

public class ApiClient {

    final String apiKeyParamName = "Ocp-Apim-Subscription-Key";
    private String basePath;
    private Map<String, String> defaultHeaderMap = new HashMap<String, String>();
    private OkHttpClient httpClient;
    private JSON json;
    private String apiKey;

    /*
     * Constructor for ApiClient
     */
    public ApiClient(String basePath) {
        httpClient = new OkHttpClient();
        this.basePath = basePath;
        json = new JSON();
    }

    /**
     * Helper method to set API key value for the first API key authentication.
     *
     * @param apiKey API key
     */
    public void setApiKey(String apiKey) {
        this.apiKey = apiKey;
    }

    /**
     * Select the Accept header's value from the given accepts array: if JSON exists
     * in the given array, use it; otherwise use all of them (joining into a string)
     *
     * @param accepts The accepts array to select from
     * @return The Accept header to use. If the given array is empty, null will be
     *         returned (not to set the Accept header explicitly).
     */
    public String selectHeaderAccept(String[] accepts) {
        if (accepts == null || accepts.length == 0) {
            return null;
        }
        for (String accept : accepts) {
            if (isJsonMime(accept)) {
                return accept;
            }
        }

        return String.join(",", accepts);
    }

    /**
     * Select the Content-Type header's value from the given array: if JSON exists
     * in the given array, use it; otherwise use the first one of the array.
     *
     * @param contentTypes The Content-Type array to select from
     * @return The Content-Type header to use. If the given array is empty, or
     *         matches "any", JSON will be used.
     */
    public String selectHeaderContentType(String[] contentTypes) {
        if (contentTypes == null || contentTypes.length == 0 || contentTypes[0].equals("*/*")) {
            return "application/json";
        }
        for (String contentType : contentTypes) {
            if (isJsonMime(contentType)) {
                return contentType;
            }
        }
        return contentTypes[0];
    }

    /**
     * Escape the given string to be used as URL query value.
     *
     * @param str String to be escaped
     * @return Escaped string
     */
    public String escapeString(String str) {
        try {
            return URLEncoder.encode(str, "utf8").replaceAll("\\+", "%20");
        } catch (UnsupportedEncodingException e) {
            return str;
        }
    }

    /**
     * Get JSON.
     *
     * @param path The sub-path of the HTTP URL
     * @return The HTTP call
     * @throws ApiException If fail to serialize the request body object
     */
    public <T> ApiResponse<T> getJson(String path, Type returnType) throws ApiException {
        String[] accepts = { "application/json" };
        com.squareup.okhttp.Call call = buildCall(path, "GET", accepts, null, null);
        return execute(call, returnType);
    }

    /**
     * Delete resource.
     *
     * @param path The sub-path of the HTTP URL
     * @return The HTTP call
     * @throws ApiException If fail to serialize the request body object
     */
    public <T> ApiResponse<T> delete(String path) throws ApiException {
        com.squareup.okhttp.Call call = buildCall(path, "DELETE", null, null, null);
        return execute(call, null);
    }

    /**
     * Post form data.
     *
     * @param path The sub-path of the HTTP URL
     * @return The HTTP call
     * @throws ApiException If fail to serialize the request body object
     */
    public <T> ApiResponse<T> post(String path, Map<String, Object> formParams, Type returnType) throws ApiException {
        final String[] localVarContentTypes = { "multipart/form-data" };
        com.squareup.okhttp.Call call = buildCall(path, "POST", null, localVarContentTypes, formParams);
        return execute(call, returnType);
    }

    /**
     * Execute HTTP call and deserialize the HTTP response body into the given
     * return type.
     *
     * @param returnType The return type used to deserialize HTTP response body
     * @param <T>        The return type corresponding to (same with) returnType
     * @param call       Call
     * @return ApiResponse object containing response status, headers and data,
     *         which is a Java object deserialized from response body and would be
     *         null when returnType is null.
     * @throws ApiException If fail to execute the call
     */
    private <T> ApiResponse<T> execute(Call call, Type returnType) throws ApiException {
        try {
            Response response = call.execute();
            T data = handleResponse(response, returnType);
            return new ApiResponse<T>(response.code(), response.headers().toMultimap(), data);
        } catch (IOException e) {
            throw new ApiException(e);
        }
    }

    /**
     * Build HTTP call with the given options.
     *
     * @param path                 The sub-path of the HTTP URL
     * @param method               The request method, one of "GET", "HEAD",
     *                             "OPTIONS", "POST", "PUT", "PATCH" and "DELETE"
     * @param localVarAccepts      The accept header parameter
     * @param localVarContentTypes The content types header parameter
     * @param formParams           The form parameters
     * @return The HTTP call
     * @throws ApiException If fail to serialize the request body object
     */
    private Call buildCall(String path, String method, String[] accepts, String[] contentTypes,
            Map<String, Object> formParams) throws ApiException {
        Map<String, String> headerParams = new HashMap<String, String>();
        String localVarAccept = selectHeaderAccept(accepts);
        if (localVarAccept != null)
            headerParams.put("Accept", localVarAccept);

        String localVarContentType = selectHeaderContentType(contentTypes);
        headerParams.put("Content-Type", localVarContentType);

        if (formParams == null)
            formParams = new HashMap<String, Object>();

        Request request = buildRequest(path, method, headerParams, formParams);
        return httpClient.newCall(request);
    }

    /**
     * Format the given parameter object into string.
     *
     * @param param Parameter
     * @return String representation of the parameter
     */
    private String parameterToString(Object param) {
        if (param == null) {
            return "";
        } else if (param instanceof Date || param instanceof OffsetDateTime || param instanceof LocalDate) {
            // Serialize to json string and remove the " enclosing characters
            String jsonStr = json.serialize(param);
            return jsonStr.substring(1, jsonStr.length() - 1);
        } else if (param instanceof Collection) {
            StringBuilder b = new StringBuilder();
            for (Object o : (Collection) param) {
                if (b.length() > 0) {
                    b.append(",");
                }
                b.append(String.valueOf(o));
            }
            return b.toString();
        } else {
            return String.valueOf(param);
        }
    }

    /**
     * Check if the given MIME is a JSON MIME. JSON MIME examples: application/json
     * application/json; charset=UTF8 APPLICATION/JSON application/vnd.company+json
     * "* / *" is also default to JSON
     * 
     * @param mime MIME (Multipurpose Internet Mail Extensions)
     * @return True if the given MIME is JSON, false otherwise.
     */
    private boolean isJsonMime(String mime) {
        String jsonMime = "(?i)^(application/json|[^;/ \t]+/[^;/ \t]+[+]json)[ \t]*(;.*)?$";
        return mime != null && (mime.matches(jsonMime) || mime.equals("*/*"));
    }

    /**
     * Deserialize response body to Java object, according to the return type and
     * the Content-Type response header.
     *
     * @param <T>        Type
     * @param response   HTTP response
     * @param returnType The type of the Java object
     * @return The deserialized Java object
     * @throws ApiException If fail to deserialize response body, i.e. cannot read
     *                      response body or the Content-Type of the response is not
     *                      supported.
     */
    private <T> T deserialize(Response response, Type returnType) throws ApiException {
        if (response == null || returnType == null) {
            return null;
        }

        String respBody;
        try {
            if (response.body() != null)
                respBody = response.body().string();
            else
                respBody = null;
        } catch (IOException e) {
            throw new ApiException(e);
        }

        if (respBody == null || "".equals(respBody)) {
            return null;
        }

        String contentType = response.headers().get("Content-Type");
        if (contentType == null) {
            // ensuring a default content type
            contentType = "application/json";
        }
        if (isJsonMime(contentType)) {
            return json.deserialize(respBody, returnType);
        } else if (returnType.equals(String.class)) {
            // Expecting string, return the raw response body.
            return (T) respBody;
        } else {
            throw new ApiException("Content type \"" + contentType + "\" is not supported for type: " + returnType,
                    response.code(), response.headers().toMultimap(), respBody);
        }
    }

    /**
     * Handle the given response, return the deserialized object when the response
     * is successful.
     *
     * @param <T>        Type
     * @param response   Response
     * @param returnType Return type
     * @throws ApiException If the response has a unsuccessful status code or fail
     *                      to deserialize the response body
     * @return Type
     */
    private <T> T handleResponse(Response response, Type returnType) throws ApiException {
        if (response.isSuccessful()) {
            if (returnType == null || response.code() == 204) {
                // returning null if the returnType is not defined,
                // or the status code is 204 (No Content)
                if (response.body() != null) {
                    try {
                        response.body().close();
                    } catch (IOException e) {
                        throw new ApiException(response.message(), e, response.code(), response.headers().toMultimap());
                    }
                }
                return null;
            } else {
                return deserialize(response, returnType);
            }
        } else {
            String respBody = null;
            if (response.body() != null) {
                try {
                    respBody = response.body().string();
                } catch (IOException e) {
                    throw new ApiException(response.message(), e, response.code(), response.headers().toMultimap());
                }
            }
            throw new ApiException(response.message(), response.code(), response.headers().toMultimap(), respBody);
        }
    }

    /**
     * Build an HTTP request with the given options.
     *
     * @param path                    The sub-path of the HTTP URL
     * @param method                  The request method, one of "GET", "HEAD",
     *                                "OPTIONS", "POST", "PUT", "PATCH" and "DELETE"
     * @param queryParams             The query parameters
     * @param collectionQueryParams   The collection query parameters
     * @param body                    The request body object
     * @param headerParams            The header parameters
     * @param formParams              The form parameters
     * @param authNames               The authentications to apply
     * @param progressRequestListener Progress request listener
     * @return The HTTP request
     * @throws ApiException If fail to serialize the request body object
     */
    private Request buildRequest(String path, String method, Map<String, String> headerParams,
            Map<String, Object> formParams) throws ApiException {
        String url = basePath + path;
        Request.Builder reqBuilder = new Request.Builder().url(url);
        headerParams.put(apiKeyParamName, apiKey);
        processHeaderParams(headerParams, reqBuilder);

        String contentType = (String) headerParams.get("Content-Type");
        // ensuring a default content type
        if (contentType == null) {
            contentType = "application/json";
        }

        RequestBody reqBody;
        if (!HttpMethod.permitsRequestBody(method)) {
            reqBody = null;
        } else if ("application/x-www-form-urlencoded".equals(contentType)) {
            reqBody = buildRequestBodyFormEncoding(formParams);
        } else if ("multipart/form-data".equals(contentType)) {
            reqBody = buildRequestBodyMultipart(formParams);
        } else {
            if ("DELETE".equals(method)) {
                // allow calling DELETE without sending a request body
                reqBody = null;
            } else {
                // use an empty request body (for POST, PUT and PATCH)
                reqBody = RequestBody.create(MediaType.parse(contentType), "");
            }
        }

        Request request = reqBuilder.method(method, reqBody).build();
        return request;
    }

    /**
     * Set header parameters to the request builder, including default headers.
     *
     * @param headerParams Header parameters in the form of Map
     * @param reqBuilder   Request.Builder
     */
    private void processHeaderParams(Map<String, String> headerParams, Request.Builder reqBuilder) {
        for (Entry<String, String> param : headerParams.entrySet()) {
            reqBuilder.header(param.getKey(), parameterToString(param.getValue()));
        }
        for (Entry<String, String> header : defaultHeaderMap.entrySet()) {
            if (!headerParams.containsKey(header.getKey())) {
                reqBuilder.header(header.getKey(), parameterToString(header.getValue()));
            }
        }
    }

    /**
     * Build a form-encoding request body with the given form parameters.
     *
     * @param formParams Form parameters in the form of Map
     * @return RequestBody
     */
    private RequestBody buildRequestBodyFormEncoding(Map<String, Object> formParams) {
        FormEncodingBuilder formBuilder = new FormEncodingBuilder();
        for (Entry<String, Object> param : formParams.entrySet()) {
            formBuilder.add(param.getKey(), parameterToString(param.getValue()));
        }
        return formBuilder.build();
    }

    /**
     * Build a multipart (file uploading) request body with the given form
     * parameters, which could contain text fields and file fields.
     *
     * @param formParams Form parameters in the form of Map
     * @return RequestBody
     */
    private RequestBody buildRequestBodyMultipart(Map<String, Object> formParams) {
        MultipartBuilder mpBuilder = new MultipartBuilder().type(MultipartBuilder.FORM);
        for (Entry<String, Object> param : formParams.entrySet()) {
            if (param.getValue() instanceof File) {
                File file = (File) param.getValue();
                Headers partHeaders = Headers.of("Content-Disposition",
                        "form-data; name=\"" + param.getKey() + "\"; filename=\"" + file.getName() + "\"");
                MediaType mediaType = MediaType.parse(guessContentTypeFromFile(file));
                mpBuilder.addPart(partHeaders, RequestBody.create(mediaType, file));
            } else {
                Headers partHeaders = Headers.of("Content-Disposition", "form-data; name=\"" + param.getKey() + "\"");
                mpBuilder.addPart(partHeaders, RequestBody.create(null, parameterToString(param.getValue())));
            }
        }
        return mpBuilder.build();
    }

    /**
     * Guess Content-Type header from the given file (defaults to
     * "application/octet-stream").
     *
     * @param file The given file
     * @return The guessed Content-Type
     */
    private String guessContentTypeFromFile(File file) {
        String contentType = URLConnection.guessContentTypeFromName(file.getName());
        if (contentType == null) {
            return "application/octet-stream";
        } else {
            return contentType;
        }
    }
}
