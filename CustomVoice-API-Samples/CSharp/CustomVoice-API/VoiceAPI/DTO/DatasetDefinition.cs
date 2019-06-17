// <copyright file="DatasetDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System.Collections.Generic;

    public sealed class DatasetDefinition
    {
        public DatasetDefinition(string name, string description, string locale, IReadOnlyDictionary<string, string> properties, string dataImportKind)
        {
            this.Name = name;
            this.Description = description;
            this.Locale = locale;
            this.Properties = properties;
            this.DataImportKind = dataImportKind;
        }

        public string Name { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public string DataImportKind { get; set; }
    }
}