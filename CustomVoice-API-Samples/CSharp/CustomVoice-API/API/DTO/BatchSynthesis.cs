using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class BatchSynthesis
    {
        [JsonConstructor]
        private BatchSynthesis(
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            Guid id,
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status,
=======
            OneApiState state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            Uri resultsUrl,
            Model model,
            string statusMessage)
        {
            this.Name = name;
            this.Description = description;
            this.Properties = properties;
            this.Locale = locale.Name;
            this.Id = id;
            this.Created = created;
            this.LastAction = lastAction;
<<<<<<< HEAD
            this.Status = status;
=======
            this.State = state;
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            this.ResultsUrl = resultsUrl;
            this.Model = model;
            this.StatusMessage = statusMessage;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public string Locale { get; private set; }

        public Guid Id { get; private set; }

        public DateTime Created { get; private set; }

        public DateTime LastAction { get; private set; }

<<<<<<< HEAD
        public OneApiState Status { get; private set; }
=======
        public OneApiState State { get; private set; }
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287

        public Uri ResultsUrl { get; private set; }

        public Model Model { get; private set; }

        public string StatusMessage { get; private set; }

        public static BatchSynthesis Create(
            Guid id,
            string name,
            string description,
            IReadOnlyDictionary<string, string> properties,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status,
=======
            OneApiState state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            Uri resultsUrl,
            Model model,
            string statusMessage)
        {
            return new BatchSynthesis(
                name,
                description,
                properties,
                locale,
                id,
                created,
                lastAction,
<<<<<<< HEAD
                status,
=======
                state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
                resultsUrl,
                model,
                statusMessage);
        }
    }
}
