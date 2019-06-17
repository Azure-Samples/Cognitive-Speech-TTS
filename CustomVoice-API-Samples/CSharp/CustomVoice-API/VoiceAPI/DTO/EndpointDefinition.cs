// <copyright file="EndpointDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System.Collections.Generic;

    public sealed class EndpointDefinition
    {
        public EndpointDefinition(
            string name,
            string description,
            string locale,
            List<ModelIdentity> models,
            IReadOnlyDictionary<string, string> properties,
            int concurrentRecognitions,
            bool isContentLoggingEnabled)
        {
            this.Name = name;
            this.Description = description;
            this.Locale = locale;
            this.Models = models;
            this.Properties = properties;
            this.concurrentRecognitions = concurrentRecognitions;
            this.IsContentLoggingEnabled = isContentLoggingEnabled;
        }

        public string Name { get; set; }

        public string Description { get; set; }

        public string Locale { get; set; }

        public List<ModelIdentity> Models { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public int concurrentRecognitions { get; set; }

        public bool IsContentLoggingEnabled { get; set; }
        
    }
}
