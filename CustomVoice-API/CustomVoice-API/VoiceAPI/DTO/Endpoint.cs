// <copyright file="Endpoint.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;
    using System.Collections.Generic;
    using System.Globalization;
    using System.Linq;

    public sealed class Endpoint
    {
        public Endpoint(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
            string state,
            string endpointKind,
            List<Model> models,
            int scaleUnits,
            bool isContentLoggingEnabled,
            IReadOnlyDictionary<string, string> properties,
            IReadOnlyDictionary<string, Uri> endpointUrls)
        {
            this.Id = id;
            this.Name = name;
            this.Description = description;
            this.Locale = locale.Name;
            this.CreatedDateTime = created;
            this.LastActionDateTime = lastAction;
            this.Status = state;
            this.EndpointKind = endpointKind;
            this.Models = models;
            this.ScaleUnits = scaleUnits;
            this.IsContentLoggingEnabled = isContentLoggingEnabled;
            this.Properties = properties;
            this.EndpointUrls = endpointUrls.ToDictionary(kv => kv.Key, kv => kv.Value.ToString());
        }

        public Guid Id { get; set; }

        public string Name { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public DateTime CreatedDateTime { get; set; }

        public DateTime LastActionDateTime { get; set; }

        public string Status { get; set; }

        public string EndpointKind { get; private set; }

        public List<Model> Models { get; set; }

        public int ScaleUnits { get; set; }

        public bool IsContentLoggingEnabled { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public IReadOnlyDictionary<string, string> EndpointUrls { get; private set; }
    }
}