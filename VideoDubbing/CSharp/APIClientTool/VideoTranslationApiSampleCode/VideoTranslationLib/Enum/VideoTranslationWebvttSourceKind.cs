// <copyright file="VideoTranslationWebvttSourceKind.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.VideoTranslation.Enums;

public enum VideoTranslationWebvttSourceKind
{
    None = 0,

    // In this kind, NOT associate with target locale with current translation.
    FileUpload,

    // 1. In this kind, will associate with target local with current translation.
    // 2. If no user editting file, translate without webvtt file instead of response error.
    TargetLocale,
}
