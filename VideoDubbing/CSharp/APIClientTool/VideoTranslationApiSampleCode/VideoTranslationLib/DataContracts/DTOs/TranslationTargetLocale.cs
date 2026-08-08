namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using System;

public class TranslationTargetLocale : TranslationTargetLocaleBase
{
    public Uri InputWebVttFileUrl { get; set; }

    public Uri OutputVideoSubtitleWebVttFileUrl { get; set; }

    public Uri OutputMetadataJsonWebVttFileUrl { get; set; }

    public Uri OutputVideoFileUrl { get; set; }

    public Uri Output24k16bitRiffAudioFileUrl { get; set; }
}
