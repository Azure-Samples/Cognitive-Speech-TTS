namespace Microsoft.SpeechServices.DataContracts;

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

public class PaginatedResources<T>
{
    public IEnumerable<T> Value { get; set; }

    [JsonProperty(PropertyName = "@nextLink")]
    public Uri NextLink { get; set; }
}
