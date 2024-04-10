namespace Microsoft.SpeechServices.VideoTranslation;

using System;
using System.Collections.Generic;
using Microsoft.SpeechServices.CommonLib.Enums;

public static class VideoTranslationConstant
{
    public readonly static TimeSpan UploadVideoOrAudioFileTimeout = TimeSpan.FromMinutes(10);

    public readonly static IEnumerable<DeploymentEnvironment> SupportedEnvironments = new[]
    {
        DeploymentEnvironment.Local,
        DeploymentEnvironment.Develop,
        DeploymentEnvironment.DevelopEUS,
        DeploymentEnvironment.CanaryUSCX,
        DeploymentEnvironment.ProductionEUS,

        // This region doesn't support GPT.
        DeploymentEnvironment.ProductionWEU,
    };
}
