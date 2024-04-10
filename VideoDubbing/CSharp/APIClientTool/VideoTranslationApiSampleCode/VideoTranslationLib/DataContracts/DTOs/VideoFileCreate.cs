// <copyright file="VideoFileCreate.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using System.Globalization;
using Microsoft.SpeechServices.DataContracts;
using Microsoft.SpeechServices.DataContracts.Deprecated;
using Microsoft.SpeechServices.VideoTranslation;

public class VideoFileCreate : StatelessResourceBase
{
    public CultureInfo Locale { get; set; }

    public int? SpeakerCount { get; set; }
}
