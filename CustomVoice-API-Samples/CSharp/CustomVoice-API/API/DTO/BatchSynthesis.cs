using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class BatchSynthesis
    {
        [JsonConstructor]
        private BatchSynthesis(
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            Guid id,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            Uri resultsUrl,
            Model model,
            string statusMessage)
        {
            this.Name = name;
            this.Description = description;
            this.Properties = properties;
            this.Locale = locale.Name;
            this.Id = id;
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
            this.ResultsUrl = resultsUrl;
            this.Model = model;
            this.StatusMessage = statusMessage;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public Guid Id { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public Uri ResultsUrl { get; private set; }

        public Model Model { get; private set; }

        public string StatusMessage { get; private set; }

        public static BatchSynthesis Create(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            Uri resultsUrl,
            Model model,
            string statusMessage)
        {
            return new BatchSynthesis(
                name,
                description,
                properties,
                locale,
                id,
                createdDateTime,
                lastActionDateTime,
                status,
                resultsUrl,
                model,
                statusMessage);
        }
    }
}
