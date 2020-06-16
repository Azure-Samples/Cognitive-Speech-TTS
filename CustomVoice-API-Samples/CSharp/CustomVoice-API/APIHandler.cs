using CustomVoice_API.API;
using Newtonsoft.Json;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;

namespace CustomVoice_API
{
    public class APIHandler
    {
        public static void ExecuteApi(APIKind apiKind, Action action, Dictionary<string, string> arguments)
        {
            try
            {
                switch (apiKind)
                {
                    case APIKind.project:
                        ExecuteProjectApi(action, arguments);
                        break;
                    case APIKind.dataset:
                        ExecuteDatasetApi(action, arguments);
                        break;
                    case APIKind.model:
                        ExecuteModelApi(action, arguments);
                        break;
                    case APIKind.voicetest:
                        ExecuteVoiceTestApi(action, arguments);
                        break;
                    case APIKind.endpoint:
                        ExecuteEndpointApi(action, arguments);
                        break;
                    case APIKind.batchsynthesis:
                        ExecuteBatchSynthesisApi(action, arguments);
                        break;
                    default:
                        break;

                }
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Exception: {e.Message}");
            }
        }

        private static void ExecuteProjectApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    ProjectGet(arguments);
                    break;
                case Action.delete:
                    ProjectDeleteById(arguments);
                    break;
                case Action.create:
                    ProjectCreate(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ExecuteDatasetApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    DatasetGet(arguments);
                    break;
                case Action.getbyprojectid:
                    DatasetGetByProjectId(arguments);
                    break;
                case Action.delete:
                    DatasetDeleteById(arguments);
                    break;
                case Action.uploaddataset:
                    DatasetUploadDataset(arguments);
                    break;
                case Action.uploaddatasetwithaudioonly:
                    DatasetUploadDatasetWithAudioOnly(arguments);
                    break;
                case Action.uploaddatasetwithlongaudio:
                    DatasetUploadDatasetWithLongAudio(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ExecuteModelApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    ModelGet(arguments);
                    break;
                case Action.getbyprojectid:
                    ModelGetByProjectId(arguments);
                    break;
                case Action.delete:
                    ModelDeleteById(arguments);
                    break;
                case Action.create:
                    ModelCreate(arguments);
                    break;
                case Action.copy:
                    ModelCopy(arguments);
                    break;
                case Action.update:
                    ModelUpdate(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ExecuteVoiceTestApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    VoiceTestGet(arguments);
                    break;
                case Action.getbyprojectid:
                    VoiceTestGetByProjectId(arguments);
                    break;
                case Action.delete:
                    VoiceTestDeleteById(arguments);
                    break;
                case Action.create:
                    VoiceTestCreate(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ExecuteEndpointApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    EndpointGet(arguments);
                    break;
                case Action.getbyprojectid:
                    EndpointGetByProjectId(arguments);
                    break;
                case Action.delete:
                    EndpointDeleteById(arguments);
                    break;
                case Action.create:
                    EndpointCreate(arguments);
                    break;
                case Action.call:
                    EndpointCall(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ExecuteBatchSynthesisApi(Action action, Dictionary<string, string> arguments)
        {
            switch (action)
            {
                case Action.get:
                    BatchSynthesisGet(arguments);
                    break;
                case Action.getbysynthesisid:
                    BatchSynthesisGetById(arguments);
                    break;
                case Action.getvoices:
                    BatchSynthesisGetVoices(arguments);
                    break;
                case Action.delete:
                    BatchSynthesisDeleteById(arguments);
                    break;
                case Action.create:
                    BatchSynthesisCreate(arguments);
                    break;
                default:
                    break;
            }
        }

        private static void ProjectGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];

            var result = Project.Get(subscriptionKey, hostURI);
            DisplayResult<API.DTO.Project>(result);
        }

        private static void ProjectDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];

            if (Project.DeleteById(subscriptionKey, hostURI, projectId))
            {
                Console.WriteLine("Delete project successfully");
            }
            else
            {
                Console.WriteLine("Delete project failed");
            }
        }

        private static void ProjectCreate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string gender = arguments["gender"];
            string locale = arguments["locale"];
            string description = name;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (Project.Create(subscriptionKey, hostURI, name, description, gender, locale))
            {
                Console.WriteLine("Create project successfully");
            }
            else
            {
                Console.WriteLine("Create project failed");
            }
        }

        private static void DatasetGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];

            var result = Dataset.Get(subscriptionKey, hostURI);
            DisplayResult<API.DTO.Dataset>(result);
        }

        private static void DatasetGetByProjectId(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];

            var result = Dataset.GetByProjectId(subscriptionKey, hostURI, projectId);
            DisplayResult<API.DTO.Dataset>(result);
        }

        private static void DatasetDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string datasetId = arguments["datasetid"];

            if (Dataset.DeleteById(subscriptionKey, hostURI, datasetId))
            {
                Console.WriteLine("Delete dataset successfully");
            }
            else
            {
                Console.WriteLine("Delete dataset failed");
            }
        }

        private static void DatasetUploadDataset(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string projectId = arguments["projectid"];
            string gender = arguments["gender"];
            string locale = arguments["locale"];
            string wavePath = arguments["wavepath"];
            string scriptPath = arguments["scriptpath"];
            string description = name;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (Dataset.Upload(subscriptionKey, hostURI, name, description, projectId, gender, locale, wavePath, scriptPath, "normalDataset"))
            {
                Console.WriteLine("Upload dataset successfully");
            }
            else
            {
                Console.WriteLine("Upload dataset failed");
            }
        }

        private static void DatasetUploadDatasetWithLongAudio(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string projectId = arguments["projectid"];
            string gender = arguments["gender"];
            string locale = arguments["locale"];
            string wavePath = arguments["wavepath"];
            string scriptPath = arguments["scriptpath"];
            string description = name;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (Dataset.Upload(subscriptionKey, hostURI, name, description, projectId, gender, locale, wavePath, scriptPath, "LongAudio"))
            {
                Console.WriteLine("Upload dataset successfully");
            }
            else
            {
                Console.WriteLine("Upload dataset failed");
            }
        }

        private static void DatasetUploadDatasetWithAudioOnly(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string projectId = arguments["projectid"];
            string gender = arguments["gender"];
            string locale = arguments["locale"];
            string wavePath = arguments["wavepath"];
            string description = name;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (Dataset.Upload(subscriptionKey, hostURI, name, description, projectId, gender, locale, wavePath, null, "AudioOnly"))
            {
                Console.WriteLine("Upload dataset successfully");
            }
            else
            {
                Console.WriteLine("Upload dataset failed");
            }
        }

        private static void ModelGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];

            var result = Model.Get(subscriptionKey, hostURI);
            DisplayResult<API.DTO.Model>(result);
        }

        private static void ModelGetByProjectId(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];

            var result = Model.GetByProjectId(subscriptionKey, hostURI, projectId);
            DisplayResult<API.DTO.Model>(result);
        }

        private static void ModelDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string modelId = arguments["modelid"];

            if (Model.DeleteById(subscriptionKey, hostURI, modelId))
            {
                Console.WriteLine("Delete model successfully");
            }
            else
            {
                Console.WriteLine("Delete model failed");
            }
        }

        private static void ModelCreate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string projectId = arguments["projectid"];
            string gender = arguments["gender"];
            string locale = arguments["locale"];
            string dataset = arguments["datasetidlist"];
            string description = name;
            bool isNeuralTTS = false;
            bool isMixlingual = false;
            Dictionary<string, string> neuralProperties = null;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (arguments.Keys.ToList().Contains("isneuraltts"))
            {
                isNeuralTTS = Convert.ToBoolean(arguments["isneuraltts"]);
                neuralProperties = new Dictionary<string, string>();

                if (arguments.Keys.Contains("purpose"))
                {
                    neuralProperties.Add("Purpose", arguments["purpose"]);
                }

                if (arguments.Keys.Contains("am"))
                {
                    neuralProperties.Add("Am", arguments["am"]);
                }

                if (arguments.Keys.Contains("amsteps"))
                {
                    neuralProperties.Add("AmSteps", arguments["amsteps"]);
                }

                if (arguments.Keys.Contains("amcheckpointinterval"))
                {
                    neuralProperties.Add("AmCheckpointInterval", arguments["amcheckpointinterval"]);
                }

                if (arguments.Keys.Contains("vocodersteps"))
                {
                    neuralProperties.Add("VocoderSteps", arguments["vocodersteps"]);
                }

                if (arguments.Keys.Contains("vocodercheckpointinterval"))
                {
                    neuralProperties.Add("VocoderCheckpointInterval", arguments["vocodercheckpointinterval"]);
                }
            }

            if (arguments.Keys.ToList().Contains("ismixlingual"))
            {
                isMixlingual = Convert.ToBoolean(arguments["ismixlingual"]);
            }

            var datasetList = new List<string>(dataset.Split(';')).Select(x => API.DTO.Identity.Create(new Guid(x))).ToList();
            if (Model.Create(subscriptionKey, hostURI, name, description, new Guid(projectId), gender, locale, datasetList, isNeuralTTS, isMixlingual, neuralProperties))
            {
                Console.WriteLine("Create model successfully");
            }
            else
            {
                Console.WriteLine("Create model failed");
            }
        }

        private static void ModelCopy(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            var modelId = new Guid(arguments["modelid"]);
            var targetSubscriptionKey = arguments["targetsubscriptionkey"];

            if (Model.Copy(subscriptionKey, hostURI, modelId, targetSubscriptionKey))
            {
                Console.WriteLine("Copy model succeeded");
            }
            else
            {
                Console.WriteLine("Copy model failed");
            }
        }

        private static void ModelUpdate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            var modelId = new Guid(arguments["modelid"]);
            string description = null;
            if (arguments.ContainsKey("description"))
            {
                description = arguments["description"];
            }

            var projectId = arguments.ContainsKey("projectid") && !string.IsNullOrEmpty(arguments["projectid"]) ? new Guid(arguments["projectid"]) : (Guid?)null;

            if (Model.Update(subscriptionKey, hostURI, modelId, description, projectId))
            {
                Console.WriteLine("Model updated successfully");
            }
            else
            {
                Console.WriteLine("Model update failed");
            }
        }

        private static void VoiceTestGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string modelId = arguments["modelid"];

            var result = VoiceTest.Get(subscriptionKey, hostURI, modelId);
            DisplayResult<API.DTO.VoiceTest>(result);
        }

        private static void VoiceTestGetByProjectId(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];

            var result = VoiceTest.GetByProjectId(subscriptionKey, hostURI, projectId);
            DisplayResult<API.DTO.VoiceTest>(result);
        }

        private static void VoiceTestDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string voiceTestId = arguments["voicetestid"];

            if (VoiceTest.DeleteById(subscriptionKey, hostURI, voiceTestId))
            {
                Console.WriteLine("Delete voice test successfully");
            }
            else
            {
                Console.WriteLine("Delete voice test failed");
            }
        }

        private static void VoiceTestCreate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];
            string modelId = arguments["modelid"];
            string script = arguments["script"];
            bool isSSML = false;

            if (arguments.Keys.ToList().Contains("isssml"))
            {
                isSSML = Convert.ToBoolean(arguments["isssml"]);
            }

            if (VoiceTest.Create(subscriptionKey, hostURI, new Guid(projectId), new Guid(modelId), script, isSSML))
            {
                Console.WriteLine("Create voice test successfully");
            }
            else
            {
                Console.WriteLine("Create voice test failed");
            }
        }

        private static void EndpointGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];

            var result = Endpoint.Get(subscriptionKey, hostURI);
            DisplayResult<API.DTO.Endpoint>(result);
        }

        private static void EndpointGetByProjectId(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string projectId = arguments["projectid"];

            var result = Endpoint.GetByProjectId(subscriptionKey, hostURI, projectId);
            DisplayResult<API.DTO.Endpoint>(result);
        }

        private static void EndpointDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string endpointId = arguments["endpointid"];

            if (Endpoint.DeleteById(subscriptionKey, hostURI, endpointId))
            {
                Console.WriteLine("Delete endpoint successfully");
            }
            else
            {
                Console.WriteLine("Delete endpoint failed");
            }
        }

        private static void EndpointCreate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string locale = arguments["locale"];
            string projectId = arguments["projectid"];
            string modelId = arguments["modelid"];
            string description = name;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (Endpoint.Create(subscriptionKey, hostURI, name, description, locale, new Guid(projectId), new Guid(modelId)))
            {
                Console.WriteLine("Create endpoint successfully");
            }
            else
            {
                Console.WriteLine("Create endpoint failed");
            }
        }

        private static void EndpointCall(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string issueTokenUrl = arguments["issuetokenurl"];
            string endpointUrl = arguments["endpointurl"];
            string voiceName = arguments["voicename"];
            string locale = arguments["locale"];
            string script = arguments["script"];
            string outputfile = arguments["outputfile"];
            bool isSSML = false;

            if (arguments.Keys.ToList().Contains("isssml"))
            {
                isSSML = Convert.ToBoolean(arguments["isssml"]);
            }

            Endpoint.Call(subscriptionKey, issueTokenUrl, endpointUrl, voiceName, locale, script, outputfile, isSSML);
        }

        private static void BatchSynthesisGet(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string timeStart = string.Empty;
            string timeEnd = string.Empty;
            string status = string.Empty;
            int skip = -1;
            int top = -1;
            if (arguments.Keys.ToList().Contains("timestart"))
            {
                timeStart = arguments["timestart"];
                var ret = DateTime.TryParse(timeStart, out var createdTimeStart);
                if (!ret)
                {
                    Console.WriteLine("A valid timestart should be given like '2019-11-21 15:26:21'.");
                    return;
                }
            }
            if (arguments.Keys.ToList().Contains("timeend"))
            {
                timeEnd = arguments["timeend"];
                var ret = DateTime.TryParse(timeEnd, out var createdTimeEnd);
                if (!ret)
                {
                    Console.WriteLine("A valid timeend should be given like '2019-11-21 15:26:21'.");
                    return;
                }
            }
            if (arguments.Keys.ToList().Contains("status"))
            {
                status = arguments["status"];
                var ret = API.DTO.OneApiState.TryParse(status, true, out API.DTO.OneApiState apiState);
                if (!ret)
                {
                    Console.WriteLine("status parameter missing or invalid. Should be one of 'NotStarted/Running/Succeeded/Failed'.");
                }
            }
            if (arguments.Keys.ToList().Contains("skip"))
            {
                var skipParam = arguments["skip"];
                var ret = int.TryParse(skipParam, out skip);
                if (!ret)
                {
                    Console.WriteLine("skip parameter should be an integer number.");
                }
            }
            if (arguments.Keys.ToList().Contains("top"))
            {
                var topParam = arguments["top"];
                var ret = int.TryParse(topParam, out top);
                if (!ret)
                {
                    Console.WriteLine("top parameter should be an integer number.");
                }
            }

            var result = BatchSynthesis.Get(subscriptionKey, hostURI, timeStart, timeEnd, status, skip, top);
            DisplayResult<API.DTO.BatchSynthesis>(result);
        }

        private static void BatchSynthesisGetById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string batchSynthesisId = arguments["batchsynthesisid"];

            var result = BatchSynthesis.GetById(subscriptionKey, hostURI, batchSynthesisId);
            DisplaySingleResult(result, "  ");
        }

        private static void BatchSynthesisGetVoices(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string additionalRequestHeadersStr = arguments["additionalrequestheaders"];
            Dictionary<string, string> additionalRequestHeaders = new Dictionary<string, string>();

            if (!string.IsNullOrEmpty(additionalRequestHeadersStr))
            {
                foreach (string headerStr in additionalRequestHeadersStr.Split(';'))
                {
                    var headerKeyValue = headerStr.Split(',');
                    if (headerKeyValue.Length == 2)
                    {
                        additionalRequestHeaders.Add(headerKeyValue[0], headerKeyValue[1]);
                    }
                }
            }

            var result = BatchSynthesis.Getvoices(subscriptionKey, hostURI, additionalRequestHeaders);
            DisplayResult<API.DTO.Voice>(result);
        }

        private static void BatchSynthesisDeleteById(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string batchSynthesisId = arguments["batchsynthesisid"];

            if (BatchSynthesis.DeleteById(subscriptionKey, hostURI, batchSynthesisId))
            {
                Console.WriteLine("Delete batch synthesis successfully");
            }
            else
            {
                Console.WriteLine("Delete batch synthesis failed");
            }
        }

        private static void BatchSynthesisCreate(Dictionary<string, string> arguments)
        {
            string subscriptionKey = arguments["subscriptionkey"];
            string hostURI = arguments["hosturi"];
            string name = arguments["name"];
            string inputTextPath = arguments["inputtextpath"];
            string locale = arguments["locale"];
            string models = arguments["models"];
            string description = name;
            string outputFormat = "riff-16khz-16bit-mono-pcm";
            bool isConcatenateResult = false;

            if (arguments.Keys.ToList().Contains("description"))
            {
                description = arguments["description"];
            }

            if (arguments.Keys.ToList().Contains("outputformat"))
            {
                outputFormat = arguments["outputformat"];
            }

            if (arguments.Keys.ToList().Contains("isconcatenateresult"))
            {
                isConcatenateResult = Convert.ToBoolean(arguments["isconcatenateresult"]);
            }

            var modelsList = new List<string>(models.Split(';')).Select(x => new Guid(x)).ToList();
            var synthesisId = BatchSynthesis.Create(subscriptionKey, hostURI, name, description, inputTextPath, locale, modelsList, outputFormat, isConcatenateResult);
            if (string.IsNullOrEmpty(synthesisId))
            {
                Console.WriteLine("Create batch synthesis failed");
            }
            else
            {
                Console.WriteLine($"Create batch synthesis successfully, ID : {synthesisId}");
            }
        }

        private static void DisplayResult<T>(IEnumerable<T> result)
        {
            if (result == null)
            {
                return;
            }

            Console.WriteLine("--------------------------------------------------------------------");

            foreach (var obj in result)
            {
                DisplaySingleResult(obj, "  ");
                Console.WriteLine("--------------------------------------------------------------------");
            }
        }

        private static void DisplaySingleResult(object result, string indentation)
        {
            string key;
            string value;

            if (result == null)
            {
                return;
            }

            Type type = result.GetType();
            var pros = type.GetProperties();
            foreach (var p in pros)
            {
                key = p.Name;

                if (p.PropertyType.Name.Contains("Dictionary"))
                {
                    value = p.GetValue(result) == null ? "" : JsonConvert.SerializeObject(p.GetValue(result));
                    Console.WriteLine(indentation + "{0,-30}{1}", key, value);
                }
                else if (p.PropertyType.Name.Contains("IEnumerable"))
                {
                    Console.WriteLine(indentation + "{0,-30}", key);
                    var val = p.GetValue(result);
                    foreach (dynamic item in val as IEnumerable)
                    {
                        DisplaySingleResult(item, indentation + indentation);
                    }
                }
                else if (p.PropertyType.Name.Contains("Model"))
                {
                    Console.WriteLine(indentation + "{0,-30}", key);
                    var val = p.GetValue(result);
                    DisplaySingleResult(val, indentation + indentation);
                }
                else if (p.PropertyType.Name.Contains("Identity"))
                {
                    Console.WriteLine(indentation + "{0,-30}", key);
                    var val = p.GetValue(result);
                    DisplaySingleResult(val, indentation + indentation);
                }
                else
                {
                    value = p.GetValue(result) == null ? "" : p.GetValue(result).ToString();
                    Console.WriteLine(indentation + "{0,-30}{1}", key, value);
                }
            }
        }
    }
}
