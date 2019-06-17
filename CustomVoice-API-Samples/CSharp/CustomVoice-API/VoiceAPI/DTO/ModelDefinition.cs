// <copyright file="ModelDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System.Collections.Generic;
    using System.Globalization;

    public sealed class ModelDefinition
    {
        public ModelDefinition(
            string name,
            string description,
            string locale,
            string modelKind,
            ModelIdentity baseModel,
            List<DatasetIdentity> datasets,
            IReadOnlyDictionary<string, string> properties)
        {
            this.Name = name;
            this.Description = description;
            this.Locale = locale;
            this.ModelKind = modelKind;
            this.BaseModel = baseModel;
            this.Datasets = datasets;
            this.Properties = properties;
        }

        public string Name { get; set; }

        public string Description { get; set; }
        
        public string Locale { get; set; }

        public string ModelKind { get; private set; }

        public ModelIdentity BaseModel { get; private set; }

        public List<DatasetIdentity> Datasets { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }
    }
}
