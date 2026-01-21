namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using System.Collections.Generic;
using System.Globalization;

public class TranslationBrief : TranslationBase
{
    public IReadOnlyDictionary<CultureInfo, TranslationTargetLocaleBase> TargetLocales { get; set; }
}
