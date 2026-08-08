namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using Microsoft.SpeechServices.Cris.Http.DTOs.Public;
using Microsoft.SpeechServices.Cris.Http.DTOs.Public.VideoTranslation;
using Microsoft.SpeechServices.DataContracts;
using System;
using System.Globalization;

// For query target locale list.
public class VideoFileTargetLocale : VideoFileTargetLocaleBrief
{
    public Uri EditingMetadataJsonWebvttFileUri { get; set; }
}
