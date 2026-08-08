namespace Microsoft.SpeechServices.DataContracts.Deprecated;

using System;
using System.ComponentModel.DataAnnotations;

public abstract class StatelessResourceBase
{
    public Uri Self { get; set; }

    [Required]
    public string DisplayName { get; set; }

    public string Description { get; set; }

    public DateTime CreatedDateTime { get; set; }

    public Guid ParseIdFromSelf()
    {
        var url = this.Self.OriginalString;
        return Guid.Parse(url.Substring(url.LastIndexOf("/") + 1, 36));
    }
}
