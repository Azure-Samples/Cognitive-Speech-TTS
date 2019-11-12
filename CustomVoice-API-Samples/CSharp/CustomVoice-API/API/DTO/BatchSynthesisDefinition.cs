using System;
using System.Collections.Generic;


namespace CustomVoice_API.API.DTO
{
    class BatchSynthesisDefinition
    {
        private BatchSynthesisDefinition(
            string name,
            string description,
            string inputTextPath,
            IReadOnlyDictionary<string, string> properties,
            string locale,
            IEnumerable<Guid> models,
            string outputFormat)
        {
            this.Name = name;
            this.Description = description;
            this.InputTextPath = inputTextPath;
            this.Properties = properties;
            this.Locale = locale;
            this.Models = models;
            this.OutputFormat = outputFormat;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public IEnumerable<Guid> Models { get; private set; }

        public string OutputFormat { get; private set; }

        public string InputTextPath { get; private set; }

        public static BatchSynthesisDefinition Create(
            string name,
            string description,
            string inputTextPath,
            IReadOnlyDictionary<string, string> properties,
            string locale,
            IEnumerable<Guid> models,
            string outputFormat)
        {
            return new BatchSynthesisDefinition(name, description, inputTextPath, properties, locale, models, outputFormat);
        }
    }
}
