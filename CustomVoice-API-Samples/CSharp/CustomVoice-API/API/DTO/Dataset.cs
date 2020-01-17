using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    public class Dataset
    {
        [JsonConstructor]
        private Dataset(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            string dataImportKind,
            Identity project)
        {
            this.Id = id;
            this.Name = name;
            this.Description = description;
            this.Properties = properties;
            this.Locale = locale.Name;
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
            this.DataImportKind = dataImportKind;
            this.Project = project;
        }

        public Guid Id { get; private set; }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public string DataImportKind { get; private set; }

        public Identity Project { get; private set; }

        public static Dataset Create(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            string dataImportKind,
            Identity project)
        {
            return new Dataset(id, name, description, properties, locale, createdDateTime, lastActionDateTime, status, dataImportKind, project);
        }
    }
}
