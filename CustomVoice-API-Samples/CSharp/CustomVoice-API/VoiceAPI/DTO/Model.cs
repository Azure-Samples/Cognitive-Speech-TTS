// <copyright file="Model.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;
    using System.Collections.Generic;
    using System.Globalization;

    public sealed class Model
    {
        public Model(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            string state,
            string modelKind,
            Model baseModel,
            List<Dataset> datasets,
            IReadOnlyDictionary<string, string> properties)
        {
            this.Id = id;
            this.Name = name;
            this.Description = description;
            this.Locale = locale.Name;
            this.CreatedDateTime = created;
            this.LastActionDateTime = lastAction;
            this.Status = state;
            this.ModelKind = modelKind;
            this.BaseModel = baseModel;
            this.Datasets = datasets;
            this.Properties = properties;
        }

        public Guid Id { get; set; }

        public string Name { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public DateTime LastActionDateTime { get; set; }

        public string Status { get; set; }

        public string ModelKind { get; private set; }

        public Model BaseModel { get; set; }

        public List<Dataset> Datasets { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }
    }
}