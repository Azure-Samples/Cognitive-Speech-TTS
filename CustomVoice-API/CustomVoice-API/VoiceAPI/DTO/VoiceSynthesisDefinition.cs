// <copyright file="VoiceSynthesisDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;
    using System.Collections.Generic;

    public sealed class VoiceSynthesisDefinition
    {
        private VoiceSynthesisDefinition(string name, string description, string locale, ModelIdentity model, IReadOnlyDictionary<string, string> properties)
        {
            this.Name = name;
            this.Description = description;
            this.Locale = locale;
            this.Model = model;
            this.Properties = properties;
        }

        /// <inheritdoc />
        public string Name { get; set; }

        /// <inheritdoc />
        public string Description { get; set; }

        public string Locale { get; set; }

        public ModelIdentity Model { get; set; }

        public IReadOnlyDictionary<string, string> Properties { get; set; }

        public static VoiceSynthesisDefinition Create(
            string name,
            string description,
            string locale,
            ModelIdentity model,
            IReadOnlyDictionary<string, string> properties)
        {
            return new VoiceSynthesisDefinition(name, description, locale, model, properties);
        }
    }
}
