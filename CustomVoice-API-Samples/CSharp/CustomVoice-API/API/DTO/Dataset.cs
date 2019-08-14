using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class Dataset
    {
        [JsonConstructor]
        private Dataset(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            OneApiState state,
            string dataImportKind)
        {
            this.Id = id;
            this.Name = name;
            this.DataImportKind = description;
            this.Properties = properties;
            this.Locale = locale.Name;
            this.Created = created;
            this.LastAction = lastAction;
            this.State = state;
            this.DataImportKind = dataImportKind;
        }

        public Guid Id { get; set; }

        public string Name { get; set; }

        public string Description { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public string Locale { get; set; }

        public DateTime Created { get; set; }

        public DateTime LastAction { get; set; }

        public OneApiState State { get; set; }

        public string DataImportKind { get; set; }

        public static Dataset Create(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            OneApiState state,
            string dataImportKind)
        {
            return new Dataset(id, name, description, properties, locale, created, lastAction, state, dataImportKind);
        }
    }
}
