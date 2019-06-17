// <copyright file="Voice.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace Microsoft.SpeechServices.Cris.Http
{
    using Newtonsoft.Json;
    using System;

    public sealed class Voice
    {
        [JsonConstructor]
        private Voice(Guid id, string name, string locale, string gender, bool isPublicVoice)
        {
            this.Id = id;
            this.Name = name;
            this.Gender = gender;
            this.Locale = locale;
            this.IsPublicVoice = isPublicVoice;
        }

        public string Name { get; set; }


        public string Locale { get; set; }


        public Guid Id { get; set; }


        public string Gender { get; set; }

        public bool IsPublicVoice { get; set; }
    }
}