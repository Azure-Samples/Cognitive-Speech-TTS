// <copyright file="VideoTranslationFeatureMetadata.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using Microsoft.SpeechServices.CommonLib.Enums;
using System.Collections.Generic;
using System.Globalization;

public class VideoTranslationFeatureMetadata
{
    // Use this instead of enum to avoid exception.
    public string FeatureKind { get; set; }

    public string Version { get; set; }

    public string Description { get; set; }

    public List<CultureInfo> SupportedSourceLocales { get; set; }

    public List<CultureInfo> SupportedTargetLocales { get; set; }
}
