// <copyright file="DatasetIdentity.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using System;

    public sealed class DatasetIdentity
    {
        public DatasetIdentity(Guid id)
        {
            this.Id = id;
        }

        public Guid Id { get; private set; }
    }
}