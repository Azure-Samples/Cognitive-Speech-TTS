using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class Project
    {
        [JsonConstructor]
        private Project(
            Guid id,
            string projectKind,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status)
        {
            this.Id = id;
            this.Properties = properties;
            this.Name = name;
            this.Description = description;
            this.ProjectKind = projectKind;
            this.Locale = locale.Name;
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
        }

        public Guid Id { get; private set; }

        public string ProjectKind { get; private set; }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public static Project Create(
            Guid id,
            string projectKind,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status)
        {
            return new Project(
                id,
                projectKind,
                name,
                description,
                properties,
                locale,
                createdDateTime,
                lastActionDateTime,
                status);
        }
    }
}
