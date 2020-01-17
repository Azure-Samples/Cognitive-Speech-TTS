using System.Collections.Generic;

namespace CustomVoice_API.API.DTO
{
    class DatasetDefinition
    {
        private DatasetDefinition(
            string locale,
            IReadOnlyDictionary<string, string> properties,
            string name,
            string description,
            string dataImportKind,
            string projectId)
        {
            this.Locale = locale;
            this.Properties = properties;
            this.Name = name;
            this.Description = description;
            this.DataImportKind = dataImportKind;
            this.ProjectId = projectId;
        }

        public string Locale { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public string DataImportKind { get; private set; }

        public string ProjectId { get; private set; }

        public static DatasetDefinition Create(
            string locale,
            IReadOnlyDictionary<string, string> properties,
            string name,
            string description,
            string dataImportKind,
            string projectId)
        {
            return new DatasetDefinition(
                    locale,
                    properties,
                    name,
                    description,
                    dataImportKind,
                    projectId);
        }
    }
}
