// <copyright file="Dataset.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;
    using System.Collections.Generic;
    using System.Globalization;

    public sealed class Dataset
    {
        public Dataset(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            string state,
            string dataImportKind,
            IReadOnlyDictionary<string, string> properties)
        {
            this.Id = id;
            this.Name = name;
            this.Description = description;
            this.Locale = locale.Name;
            this.CreatedDateTime = created;
            this.LastActionDateTime = lastAction;
            this.Status = state;
            this.DataImportKind = dataImportKind;
            this.Properties = properties;
        }

        public Guid Id { get; set; }

        public string Name { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public DateTime LastActionDateTime { get; set; }

        public string Status { get; set; }

        public string DataImportKind { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }
    }
}