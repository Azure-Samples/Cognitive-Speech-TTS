namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using Microsoft.SpeechServices.CommonLib.Enums;
using Microsoft.SpeechServices.DataContracts;
using Microsoft.SpeechServices.DataContracts.Deprecated;
using System;
using System.Collections.Generic;
using System.Globalization;

public class VideoFileMetadata : StatelessResourceBase
{
    public VideoTranslationFileKind FileKind { get; set; }

    public CultureInfo Locale { get; set; }

    public int? SpeakerCount { get; set; }

    public IEnumerable<CultureInfo> TargetLocales { get; set; }

    public Uri VideoFileUri { get; set; }

    public Uri AudioFileUri { get; set; }

    public TimeSpan? Duration { get; set; }

    public Uri SnapshotImageUrl { get; set; }
}
