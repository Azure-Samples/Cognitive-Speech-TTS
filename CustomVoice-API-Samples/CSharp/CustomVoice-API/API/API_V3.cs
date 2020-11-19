namespace CustomVoice_API.API
{
    public class API_V3
    {
        private static string TextToSpeechBasePath_V3_beta1 => "/api/texttospeech/v3.0-beta1/";

        //Voice Project
        private static string VoiceProject_Base => TextToSpeechBasePath_V3_beta1 + "projects";
        public static string VoiceProject_Get => VoiceProject_Base;
        public static string VoiceProject_Create => VoiceProject_Base;
        public static string VoiceProject_DeleteById => VoiceProject_Base + "/{0}";

        //Voice Datasets
        private static string VoiceDataset_Base => TextToSpeechBasePath_V3_beta1 + "datasets";
        public static string VoiceDatasets_Get => VoiceDataset_Base;
        public static string VoiceDatasets_GetByProjectId => VoiceDataset_Base + "/project/{0}";
        public static string VoiceDatasets_Upload => VoiceDataset_Base + "/upload";
        public static string VoiceDatasets_UploadAudioOnly => VoiceDataset_Base + "/audioonly";
        public static string VoiceDatasets_UploadLongAudio => VoiceDataset_Base + "/longaudio";
        public static string VoiceDatasets_DeleteById => VoiceDataset_Base + "/{0}";

        //Voice Models
        private static string VoiceModels_Base => TextToSpeechBasePath_V3_beta1 + "models";
        public static string VoiceModels_Get => VoiceModels_Base;
        public static string VoiceModels_GetByProjectId => VoiceModels_Base + "/project/{0}";
        public static string VoiceModels_Create => VoiceModels_Base;
        public static string VoiceModels_DeleteById => VoiceModels_Base + "/{0}";
        public static string VoiceModels_Copy => VoiceModels_Base + "/{0}/copy";
        public static string VoiceModels_Update => VoiceModels_Base + "/{0}";

        //Voice Tests
        private static string VoiceTests_Base => TextToSpeechBasePath_V3_beta1 + "tests";
        public static string VoiceTests_GetByModelId => VoiceTests_Base + "/model/{0}";
        public static string VoiceTests_GetByProjectId => VoiceTests_Base + "/project/{0}";
        public static string VoiceTests_DeleteById => VoiceTests_Base + "/{0}";

        //Voice Endpoints
        private static string VoiceEndpoints_Base => TextToSpeechBasePath_V3_beta1 + "endpoints";
        public static string VoiceEndpoints_Get => VoiceEndpoints_Base;
        public static string VoiceEndpoints_GetByProjectId => VoiceEndpoints_Base + "/project/{0}";
        public static string VoiceEndpoints_Create => VoiceEndpoints_Base;
        public static string VoiceEndpoints_DeleteById => VoiceEndpoints_Base + "/{0}";

        //Voice Synthesis
        private static string VoiceSynthesis_Base => TextToSpeechBasePath_V3_beta1 + "voicesynthesis";
        public static string VoiceSynthesis_Get => VoiceSynthesis_Base;
        public static string VoiceSynthesis_GetPaginated => VoiceSynthesis_Base + "/Paginated";
        public static string VoiceSynthesis_Create => VoiceSynthesis_Base;
        public static string VoiceSynthesis_ById => VoiceSynthesis_Base + "/{0}";
        public static string VoiceSynthesis_GetVoice => VoiceSynthesis_Base + "/voices";
    }
}
