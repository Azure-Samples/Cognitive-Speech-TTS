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
            DateTime created,
            DateTime lastAction,
            OneApiState state)
        {
            this.Id = id;
            this.ProjectKind = projectKind;
            this.Name = name;
            this.Description = description;
            this.ProjectKind = projectKind;
            this.Locale = locale.Name;
            this.Created = created;
            this.LastAction = lastAction;
            this.State = state;
        }

        public Guid Id { get; private set; }

        public string ProjectKind { get; private set; }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public DateTime Created { get; private set; }

        public DateTime LastAction { get; private set; }

        public OneApiState State { get; private set; }

        public static Project Create(
            Guid id,
            string projectKind,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            OneApiState state)
        {
            return new Project(
                id,
                projectKind,
                name,
                description,
                properties,
                locale,
                created,
                lastAction,
                state);
        }
    }
}
