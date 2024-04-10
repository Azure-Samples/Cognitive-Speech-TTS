// <copyright file="VideoTranslationReleaseHistoryVersionMetadata.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

using System;

public class VideoTranslationReleaseHistoryVersionMetadata
{
    public string Version { get; set; }

    public DateTime Date { get; set; }

    public string Description { get; set; }
}
