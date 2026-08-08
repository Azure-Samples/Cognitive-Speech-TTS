// <copyright file="VoiceGeneralTaskInputFileBase.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http.DTOs.Public.VoiceGeneralTask;

using Microsoft.SpeechServices.DataContracts;
using System;

public class VoiceGeneralTaskInputFileBase : StatefulResourceBase
{
    // ID is used for client to know which file responsed.
    public Guid Id { get; set; }

    public string FileContentSha256 { get; set; }

    public Uri Url { get; set; }

    public long? Version { get; set; }
}
