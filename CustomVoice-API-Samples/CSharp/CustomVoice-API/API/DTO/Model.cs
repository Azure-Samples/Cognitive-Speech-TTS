using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CustomVoice_API.API.DTO
{
    class Model
    {
        [JsonConstructor]
        private Model(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status,
=======
            OneApiState state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            string modelKind,
            Model baseModel,
            List<Dataset> datasets,
            IReadOnlyDictionary<string, string> properties)
        {
            this.Id = id;
            this.Name = name;
            this.Created = created;
            this.LastAction = lastAction;
<<<<<<< HEAD
            this.Status = status;
=======
            this.State = state;
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            this.Description = description;
            this.Locale = locale.Name;
            this.ModelKind = modelKind;
            this.BaseModel = baseModel;
            this.Datasets = datasets;
            this.Properties = properties;
        }

        public Guid Id { get; private set; }

        public string Name { get; private set; }

        public DateTime Created { get; private set; }

        public DateTime LastAction { get; private set; }

<<<<<<< HEAD
        public OneApiState Status { get; private set; }
=======
        public OneApiState State { get; private set; }
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287

        public string Description { get; private set; }

        public string Locale { get; private set; }

        public string ModelKind { get; private set; }

        public Model BaseModel { get; private set; }

        public List<Dataset> Datasets { get; private set; }

        public IReadOnlyDictionary<string, string> Properties { get; private set; }

        public static Model Create(
            Guid id,
            string name,
            string description,
            CultureInfo locale,
            DateTime created,
            DateTime lastAction,
<<<<<<< HEAD
            OneApiState status,
=======
            OneApiState state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
            string modelKind,
            Model baseModel,
            List<Dataset> datasets,
            IReadOnlyDictionary<string, string> properties)
        {
            return new Model(
                id,
                name,
                description,
                locale,
                created,
                lastAction,
<<<<<<< HEAD
                status,
=======
                state,
>>>>>>> 5963da04cb22a1ddd5eab239d6ff5d5fd19ab287
                modelKind,
                baseModel,
                datasets,
                properties);
        }
    }
}
