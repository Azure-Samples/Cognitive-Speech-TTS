using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class Model
    {
        [JsonConstructor]
        private Model(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            string modelKind,
            Model baseModel,
            IEnumerable<Dataset> datasets,
            IReadOnlyDictionary<string, string> properties,
            Identity project)
        {
            this.Id = id;
            this.Name = name;
            this.CreatedDateTime = createdDateTime;
            this.LastActionDateTime = lastActionDateTime;
            this.Status = status;
            this.Description = description;
            this.Locale = locale.Name;
            this.ModelKind = modelKind;
            this.BaseModel = baseModel;
            this.Datasets = datasets;
            this.Properties = properties;
            this.Project = project;
        }

        public Guid Id { get; private set; }

        public string Name { get; private set; }

        public DateTime CreatedDateTime { get; private set; }

        public DateTime LastActionDateTime { get; private set; }

        public OneApiState Status { get; private set; }

        public string Description { get; private set; }

        public string Locale { get; private set; }

        public string ModelKind { get; private set; }

        public Model BaseModel { get; private set; }

        public IEnumerable<Dataset> Datasets { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public Identity Project { get; private set; }

        public static Model Create(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime createdDateTime,
            DateTime lastActionDateTime,
            OneApiState status,
            string modelKind,
            Model baseModel,
            IEnumerable<Dataset> datasets,
            IReadOnlyDictionary<string, string> properties,
            Identity project)
        {
            return new Model(
                id,
                name,
                description,
                locale,
                createdDateTime,
                lastActionDateTime,
                status,
                modelKind,
                baseModel,
                datasets,
                properties,
                project);
        }
    }
}
