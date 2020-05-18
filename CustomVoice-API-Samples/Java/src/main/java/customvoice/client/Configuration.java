/*
 * Speech Services API v3.0-beta1
 */

package customvoice.client;

public class Configuration {
    private static String TextToSpeech_BasePath_V3_beta1 = "/api/texttospeech/v3.0-beta1/";

    public static String VoiceSynthesis_BasePath = TextToSpeech_BasePath_V3_beta1 + "voicesynthesis";

    public static String VoicePath = VoiceSynthesis_BasePath + "/voices";

    public static String PaginatedVoiceSynthesisPath = VoiceSynthesis_BasePath + "/Paginated";

    public static String HostUri = "https://%s.customvoice.api.speech.microsoft.com";
}
