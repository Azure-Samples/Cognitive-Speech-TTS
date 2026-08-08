namespace Microsoft.SpeechServices.DataContracts.Deprecated;

using System;
using Microsoft.SpeechServices.CommonLib.Enums;

public abstract class StatefulResourceBase : StatelessResourceBase
{
    public OneApiState Status { get; set; }

    public DateTime LastActionDateTime { get; set; }
}
