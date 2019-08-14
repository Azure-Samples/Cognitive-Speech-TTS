using System;

namespace CustomVoice_API
{
    class Program
    {
        static void Main(string[] args)
        {
            APIKind apikind;
            Action action;
            var ApiKindAndAction = APIArguments.GetApiKindAndAction(args);

            /*No specified or error specified APIKind*/
            if (APIArguments.NoAPIKind(ApiKindAndAction))
            {
                ArgumentsDescription.PrintAPIUsage();
                return;
            }
            apikind = (APIKind)Enum.Parse(typeof(APIKind), ApiKindAndAction["apikind"]);

            /*No specified or error specified APIKind*/
            if (APIArguments.NoAction(ApiKindAndAction))
            {
                ArgumentsDescription.PrintAPIKindUsage(apikind);
                return;
            }
            action = (Action)Enum.Parse(typeof(Action), ApiKindAndAction["action"]);

            var parameters = APIArguments.GetParameters(apikind, action);
            if(parameters == null)
            {
                Console.WriteLine($"{apikind} does not support {action} operation");
                ArgumentsDescription.PrintAPIKindUsage(apikind);
                return;
            }

            var arguments = APIArguments.GetArguments(args);
            if (APIArguments.ParametersNoMatch(arguments, parameters["Required"]))
            {
                Console.WriteLine($"Missing required parameters.");
                ArgumentsDescription.PrintAPIActionUsage(apikind, action, parameters);
                return;
            }

            APIHandler.ExecuteApi(apikind, action, arguments);
        }
    }
}
