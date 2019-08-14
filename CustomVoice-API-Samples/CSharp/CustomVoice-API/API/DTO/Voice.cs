using Newtonsoft.Json;
using System;

namespace CustomVoice_API.API.DTO
{
    class Voice
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

        public string Name { get; private set; }


        public string Locale { get; private set; }


        public Guid Id { get; private set; }


        public string Gender { get; private set; }

        public bool IsPublicVoice { get; private set; }
    }
}
