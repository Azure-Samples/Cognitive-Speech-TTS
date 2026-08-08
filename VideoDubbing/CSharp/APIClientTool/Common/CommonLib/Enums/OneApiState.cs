using System;
using System.Runtime.Serialization;

namespace Microsoft.SpeechServices.CommonLib.Enums;

[DataContract]
public enum OneApiState
{
    [Obsolete("Do not use directly - used to discover deserializer issues.")]
    None = 0,

    NotStarted,

    Running,

    Succeeded,

    Failed,
}