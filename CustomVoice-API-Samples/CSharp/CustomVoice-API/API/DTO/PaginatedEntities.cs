using Newtonsoft.Json;
using System;
using System.Collections.Generic;

namespace Skype.Azure.Runners.CustomVoice.CRISVoiceAPI.DTO
{
    public class PaginatedEntities<T>
    {
        public IEnumerable<T> Values { get; set; }

        [JsonProperty(PropertyName = "@nextLink")]
        public Uri NextLink { get; set; }
    }
}
