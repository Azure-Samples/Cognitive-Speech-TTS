using System;
using System.Collections.Generic;
using System.Linq;

namespace CustomVoice_API
{
    public class APIArguments
    {
        internal const string SubscriptionKey = "subscriptionKey";
        internal const string HostUri = "hostURI";
        internal const string Name = "name";
        internal const string Description = "description";
        internal const string Gender = "gender";
        internal const string Locale = "locale";
        internal const string ProjectId = "projectId";
        internal const string WavePath = "wavePath";
        internal const string ScriptPath = "scriptPath";
        internal const string DatasetId = "datasetId";
        internal const string DatasetIdList = "datasetIdList";
        internal const string ModelId = "modelId";
        internal const string EndpointId = "endpointId";
        internal const string BatchSynthesisId = "batchSynthesisId";
        internal const string VoiceTestId = "voiceTestId";
        internal const string HostUriValue = "https://<region>.customvoice.api.speech.microsoft.com/";
        internal const string AdditionalRequestHeaders = "additionalRequestHeaders";

        public static Dictionary<string, string> GetApiKindAndAction(string[] args)
        {
            if (args.Length <= 0)
            {
                return null;
            }

            var arguments = new Dictionary<string, string>();

            for (int i = 0; i < args.Length; i++)
            {
                if (i == 0)
                {
                    arguments.Add("apikind", args[i].ToLower());
                }
                else if (i == 1)
                {
                    arguments.Add("action", args[i].ToLower());
                    break;
                }
            }

            return arguments;
        }

        public static Dictionary<string, string> GetArguments(string[] args)
        {
            if (args.Length <= 0)
            {
                return null;
            }

            var arguments = new Dictionary<string, string>();
            string argumentName = "";

            for (int i = 2; i < args.Length; i++)
            {
                if (argumentName == "")
                {
                    argumentName = args[i].Replace("-", "").ToLower();
                }
                else
                {
                    arguments.Add(argumentName, args[i]);
                    argumentName = "";
                }
            }
            return arguments;
        }

        public static bool NoAPIKind(Dictionary<string, string> ApiKindAndAction)
        {
            if (ApiKindAndAction == null || !ApiKindAndAction.Keys.Contains("apikind") || !Enum.IsDefined(typeof(APIKind), ApiKindAndAction["apikind"]))
            {
                return true;
            }

            return false;
        }

        public static bool NoAction(Dictionary<string, string> ApiKindAndAction)
        {
            if (ApiKindAndAction == null || !ApiKindAndAction.Keys.Contains("action") || !Enum.IsDefined(typeof(Action), ApiKindAndAction["action"]))
            {
                return true;
            }

            return false;
        }

        public static bool ParametersNoMatch(Dictionary<string, string> arguments, List<string> requiredParameters)
        {
            if (requiredParameters.Except(arguments.Keys).Count() > 0)
            {
                return true;
            }

            return false;
        }

        public static Dictionary<string, List<string>> GetParameters(APIKind apiKind, Action action)
        {
            Dictionary<string, List<string>> result = new Dictionary<string, List<string>>();
            List<string> RequiredParameters = null;
            List<string> OptionalParameters = null;

            switch ($"{apiKind}-{action}")
            {
                case nameof(APIKind.project) + "-" + nameof(Action.create):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, Gender, Locale };
                        OptionalParameters = new List<string>() { Description };
                        break;
                    }
                case nameof(APIKind.project) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.project) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.uploaddataset):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, ProjectId, Gender, Locale, WavePath, ScriptPath };
                        OptionalParameters = new List<string>() { Description };
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.uploaddatasetwithlongaudio):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, ProjectId, Gender, Locale, WavePath, ScriptPath };
                        OptionalParameters = new List<string>() { Description };
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.uploaddatasetwithaudioonly):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, ProjectId, Gender, Locale, WavePath };
                        OptionalParameters = new List<string>() { Description };
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.getbyprojectid):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.dataset) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, DatasetId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.create):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, ProjectId, Gender, Locale, DatasetIdList };
                        OptionalParameters = new List<string>() { Description, "isNeuralTTS", "isMixlingual", "purpose", "am", "amSteps", "amCheckpointInterval", "vocoderSteps", "vocoderCheckpointInterval", };
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.getbyprojectid):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ModelId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.update):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ModelId };
                        OptionalParameters = new List<string>() { ProjectId, Description };
                        break;
                    }
                case nameof(APIKind.voicetest) + "-" + nameof(Action.create):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId, ModelId, "script" };
                        OptionalParameters = new List<string>() { "isSSML" };
                        break;
                    }
                case nameof(APIKind.voicetest) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ModelId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.voicetest) + "-" + nameof(Action.getbyprojectid):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.voicetest) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, VoiceTestId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.endpoint) + "-" + nameof(Action.create):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, Locale, ProjectId, ModelId };
                        OptionalParameters = new List<string>() { Description };
                        break;
                    }
                case nameof(APIKind.endpoint) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.endpoint) + "-" + nameof(Action.getbyprojectid):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ProjectId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.batchsynthesis) + "-" + nameof(Action.getbysynthesisid):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, BatchSynthesisId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.endpoint) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, EndpointId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.endpoint) + "-" + nameof(Action.call):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, "issuetokenurl", "endpointUrl", "voiceName", Locale, "script", "outputFile" };
                        OptionalParameters = new List<string>() { "isSSML" };
                        break;
                    }
                case nameof(APIKind.batchsynthesis) + "-" + nameof(Action.create):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, Name, "inputTextPath", Locale, "models" };
                        OptionalParameters = new List<string>() { Description, "outputFormat", "isConcatenateResult" };
                        break;
                    }
                case nameof(APIKind.batchsynthesis) + "-" + nameof(Action.get):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>() { "timestart", "timeend", "status", "skip", "top" };
                        break;
                    }
                case nameof(APIKind.batchsynthesis) + "-" + nameof(Action.getvoices):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri };
                        OptionalParameters = new List<string>() { AdditionalRequestHeaders };
                        break;
                    }
                case nameof(APIKind.batchsynthesis) + "-" + nameof(Action.delete):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, BatchSynthesisId };
                        OptionalParameters = new List<string>();
                        break;
                    }
                case nameof(APIKind.model) + "-" + nameof(Action.copy):
                    {
                        RequiredParameters = new List<string>() { SubscriptionKey, HostUri, ModelId, "targetSubscriptionKey" };
                        OptionalParameters = new List<string>();
                        break;
                    }
                default:
                    {
                        return null;
                    }
            }

            result.Add("Required", RequiredParameters.Select(x => x.ToLower()).ToList());
            result.Add("Optional", OptionalParameters.Select(x => x.ToLower()).ToList());
            return result;
        }
    }
}
