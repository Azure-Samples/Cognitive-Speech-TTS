// <copyright file="BatchSynthesisDefinition.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;

    public sealed class BatchSynthesisDefinition
    {
        private BatchSynthesisDefinition(string name, string description, string locale, Uri inputTextUrl)
        {
            this.Name = name;
            this.Description = description;
            this.InputTextUrl = inputTextUrl;
            this.Locale = locale;
        }

        private BatchSynthesisDefinition(string name, string description, string locale, Uri inputTextUrl, ModelIdentity model)
        {
            this.Name = name;
            this.Description = description;
            this.InputTextUrl = inputTextUrl;
            this.Locale = locale;
            this.Model = model;
        }

        /// <inheritdoc />
        public string Name { get; set; }

        /// <inheritdoc />
        public string Description { get; set; }

        /// <inheritdoc />
        public Uri InputTextUrl { get; set; }

        public string Locale { get; set; }

        public ModelIdentity Model { get; set; }

        public static BatchSynthesisDefinition Create(
            string name,
            string description,
            string locale,
            Uri inputTextUrl)
        {
            return new BatchSynthesisDefinition(name, description, locale, inputTextUrl, null);
        }

        public static BatchSynthesisDefinition Create(
            string name,
            string description,
            string locale,
            Uri inputTextUrl,
            ModelIdentity model)
        {
            return new BatchSynthesisDefinition(name, description, locale, inputTextUrl, model);
        }
    }
}
