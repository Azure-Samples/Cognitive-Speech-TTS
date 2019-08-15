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
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status,
=======
            OneApiState state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            string endpointKind,
            IEnumerable<Model> models,
            int concurrentRecognitions,
            bool isContentLoggingEnabled,
            IReadOnlyDictionary<string, Uri> endpointUrls)
        {
            this.Id = id;
            this.Name = name;
            this.Created = created;
            this.LastAction = lastAction;
<<<<<<< HEAD
            this.Status = status;
=======
            this.State = state;
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            this.Description = description;
            this.Locale = locale.Name;
            this.EndpointKind = endpointKind;
            this.Models = models;
            this.ConcurrentRecognitions = concurrentRecognitions;
            this.IsContentLoggingEnabled = isContentLoggingEnabled;
            this.Properties = properties;
            this.EndpointUrls = endpointUrls.ToDictionary(kv => kv.Key, kv => kv.Value.ToString());
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public Guid Id { get; private set; }

        public DateTime Created { get; private set; }

        public DateTime LastAction { get; private set; }

<<<<<<< HEAD
        public OneApiState Status { get; private set; }
=======
        public OneApiState State { get; private set; }
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287

        public string EndpointKind { get; private set; }

        public IEnumerable<Model> Models { get; private set; }

        public int ConcurrentRecognitions { get; private set; }

        public bool IsContentLoggingEnabled { get; private set; }

        public IReadOnlyDictionary<string, string> EndpointUrls { get; private set; }

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
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status)
=======
            OneApiState state)
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
        {
            return new Endpoint(
                name,
                description,
                properties,
                locale,
                id,
                created,
                lastAction,
<<<<<<< HEAD
                status,
=======
                state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
                endpointKind,
                models,
                concurrentRecognitions,
                isContentLoggingEnabled,
                endpointUrls);
        }
    }
}
