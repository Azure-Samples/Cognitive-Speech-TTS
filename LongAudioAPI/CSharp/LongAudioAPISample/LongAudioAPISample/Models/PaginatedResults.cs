namespace LongAudioSynthesisSample.Models
{
    using System;
    using System.Collections.Generic;
    using System.Text.Json.Serialization;

    public class PaginatedResults<T>
    {
        public IEnumerable<T> Values { get; set; }

        [JsonPropertyName("@nextLink")]
        public Uri NextLink { get; set; }
    }
}
