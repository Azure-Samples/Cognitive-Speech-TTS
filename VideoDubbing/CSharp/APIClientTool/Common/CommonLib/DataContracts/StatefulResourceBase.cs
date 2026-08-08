// <copyright file="StatefulResourceBase.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http.DTOs.Public;

using System;
using Microsoft.SpeechServices.Common.Client;
using Microsoft.SpeechServices.CommonLib.Enums;

public abstract class StatefulResourceBase : StatelessResourceBase
{
    public OneApiState Status { get; set; }

    public DateTime LastActionDateTime { get; set; }
}
