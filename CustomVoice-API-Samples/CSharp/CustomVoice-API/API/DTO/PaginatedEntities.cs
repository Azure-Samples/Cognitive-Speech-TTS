using Newtonsoft.Json;
using System;
using System.Collections.Generic;

namespace CustomVoice_API.API.DTO
{
    public class PaginatedEntities<T>
    {
        public IEnumerable<T> Values { get; set; }

        [JsonProperty(PropertyName = "@nextLink")]
        public Uri NextLink { get; set; }
    }
}
