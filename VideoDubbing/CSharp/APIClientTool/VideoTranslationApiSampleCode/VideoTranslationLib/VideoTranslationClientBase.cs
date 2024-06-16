namespace Microsoft.SpeechServices.VideoTranslation;
using Microsoft.SpeechServices.CommonLib.Enums;
using Microsoft.SpeechServices.CommonLib.Util;

public abstract class VideoTranslationClientBase : HttpClientBase
{
    public VideoTranslationClientBase(DeploymentEnvironment environment, string subKey)
        : base(environment, subKey)
    {
    }

    public override string RouteBase => "videotranslation";
}
