namespace Microsoft.SpeechServices.CommonLib.Enums;

using System;

public enum VideoTranslationMergeParagraphAudioAlignKind
{
    [Obsolete("Do not use directly - used to discover serializer issues.")]
    None = 0,

    TruncateIfExceed,

    SpeedUpIfExceed,
}
