// <copyright file="ModelIdentity.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;

    public sealed class ModelIdentity
    {
        public ModelIdentity(Guid id)
        {
            this.Id = id;
        }

        public Guid Id { get; private set; }

        public static ModelIdentity Create(Guid Id)
        {
            return new ModelIdentity(Id);
        }
    }
}