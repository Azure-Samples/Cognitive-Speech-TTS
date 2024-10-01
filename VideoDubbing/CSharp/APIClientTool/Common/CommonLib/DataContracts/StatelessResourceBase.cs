// <copyright file="StatelessResourceBase.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http.DTOs.Public;

using System;

public abstract class StatelessResourceBase
{
    public string Id { get; set; }

    public string DisplayName { get; set; }

    public string Description { get; set; }

    public DateTime CreatedDateTime { get; set; }
}
