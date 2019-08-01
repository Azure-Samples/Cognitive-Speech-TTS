// <copyright file="VoiceSynthesisDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;
    using System.Collections.Generic;

    public sealed class VoiceSynthesisDefinition
    {
        private VoiceSynthesisDefinition(string name, string description, string locale, string outputFormat, IEnumerable<Guid> models, IReadOnlyDictionary<string, string> properties)
        {
            this.Name = name;
            this.Description = description;
            this.Locale = locale;
            this.OutputFormat = outputFormat;
            this.Models = models;
            this.Properties = properties;
        }

        /// <inheritdoc />
        public string Name { get; set; }

        /// <inheritdoc />
        public string Description { get; set; }

        public string Locale { get; set; }

        public string OutputFormat { get; set; }

        public IEnumerable<Guid> Models { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public static VoiceSynthesisDefinition Create(
            string name,
            string description,
            string locale,
            string outputFormat,
            IEnumerable<Guid> models,
            IReadOnlyDictionary<string, string> properties)
        {
            return new VoiceSynthesisDefinition(name, description, locale, outputFormat, models, properties);
        }
    }
}
