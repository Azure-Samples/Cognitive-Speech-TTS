using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace CustomVoice_API.API.DTO
{
    class Endpoint
    {
        [JsonConstructor]
        private Endpoint(
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            Guid id,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            string endpointKind,
            IEnumerable<Model> models,
            int concurrentRecognitions,
            bool isContentLoggingEnabled,
            IReadOnlyDictionary<string, Uri> endpointUrls,
            Identity project)
        {
            this.Id = id;
            this.Name = name;
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
            this.Description = description;
            this.Locale = locale.Name;
            this.EndpointKind = endpointKind;
            this.Models = models;
            this.ConcurrentRecognitions = concurrentRecognitions;
            this.IsContentLoggingEnabled = isContentLoggingEnabled;
            this.Properties = properties;
            this.EndpointUrls = endpointUrls.ToDictionary(kv => kv.Key, kv => kv.Value.ToString());
            this.Project = project;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public Guid Id { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public string EndpointKind { get; private set; }

        public IEnumerable<Model> Models { get; private set; }

        public int ConcurrentRecognitions { get; private set; }

        public bool IsContentLoggingEnabled { get; private set; }

        public IReadOnlyDictionary<string, string> EndpointUrls { get; private set; }

        public Identity Project { get; private set; }

        public static Endpoint Create(
            Guid id,
            string endpointKind,
            IEnumerable<Model> models,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            int concurrentRecognitions,
            bool isContentLoggingEnabled,
            CultureInfo locale,
            IReadOnlyDictionary<string, Uri> endpointUrls,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            Identity project)
        {
            return new Endpoint(
                name,
                description,
                properties,
                locale,
                id,
                createdDateTime,
                lastActionDateTime,
                status,
                endpointKind,
                models,
                concurrentRecognitions,
                isContentLoggingEnabled,
                endpointUrls,
                project);
        }
    }
}
