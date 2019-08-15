using System.Collections.Generic;

namespace CustomVoice_API.API.DTO
{
    class ModelDefinition
    {
        private ModelDefinition(
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            string locale,
            string modelKind,
            Identity baseModel,
            IEnumerable<Identity> datasets,
            string text,
            Identity project)
        {
            this.Name = name;
            this.Description = description;
            this.Properties = properties;
            this.Locale = locale;
            this.ModelKind = modelKind;
            this.BaseModel = baseModel;
            this.Datasets = datasets;
            this.Text = text;
            this.Project = project;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public string ModelKind { get; private set; }

        public Identity BaseModel { get; private set; }

        public IEnumerable<Identity> Datasets { get; private set; }

        public string Text { get; private set; }

        public Identity Project { get; private set; }

        public static ModelDefinition Create(
           string name,
           string description,
           IReadOnlyDictionary<string, string> properties,
           string locale,
           string modelKind,
           Identity baseModel,
           IEnumerable<Identity> datasets,
           Identity project)
        {
            return new ModelDefinition(name, description, properties, locale, modelKind, baseModel, datasets, null, project);
        }

        

       

    }
}
