namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using Microsoft.SpeechServices.DataContracts;
using Microsoft.SpeechServices.DataContracts.Deprecated;
using System;
using System.Globalization;

public class WebVttFileMetadata : StatelessResourceBase
{
    public CultureInfo Locale { get; set; }

    public Uri FileUrl { get; set; }
}
