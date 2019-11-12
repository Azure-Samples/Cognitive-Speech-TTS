using System.Collections.Generic;

namespace CustomVoice_API.API.DTO
{
    class EndpointDefinition
    {
        private EndpointDefinition(
            string name,
            string description,
            string locale,
            Identity project,
            IEnumerable<Identity> models,
            IReadOnlyDictionary<string, string> properties)
        {
            this.Locale = locale;
            this.Properties = properties;
            this.Name = name;
            this.Description = description;
            this.Models = models;
            this.Project = project;
        }

        public string Locale { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IEnumerable<Identity> Models { get; private set; }

        public Identity Project { get; private set; }

        public static EndpointDefinition Create(
            string name,
            string description,
            string locale,
            Identity project,
            IEnumerable<Identity> models,
            IReadOnlyDictionary<string, string> properties)
        {
            return new EndpointDefinition(
                name,
                description,
                locale,
                project,
                models,
                properties);
        }
    }
}
