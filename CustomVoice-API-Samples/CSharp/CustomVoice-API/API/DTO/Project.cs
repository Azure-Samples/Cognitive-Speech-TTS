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
            string self,
            string projectKind,
            string displayName,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime)
        {
            this.Self = self;
            this.Properties = properties;
            this.DisplayName = displayName;
            this.Description = description;
            this.ProjectKind = projectKind;
            this.Locale = locale.Name;
            this.CreatedDateTime = createdDateTime;         
        }

        public string Self { get; private set; }

        public string ProjectKind { get; private set; }

        public string DisplayName { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public static Project Create(
            string self,
            string projectKind,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            OneApiState status)
        {
            return new Project(
                self,
                projectKind,
                name,
                description,
                properties,
                locale,
                createdDateTime);
        }
    }
}