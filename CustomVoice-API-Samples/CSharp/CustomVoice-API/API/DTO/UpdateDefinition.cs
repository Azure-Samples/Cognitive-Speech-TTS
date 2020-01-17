using System;

namespace CustomVoice_API.API.DTO
{
    public class UpdateDefinition
    {
        private UpdateDefinition(string name, string description, Identity project)
        {
            Name = name;
            Description = description;
            Project = project;
        }

        public string Name { get; private set; }

        public string Description { get; private set; }

        public Identity Project { get; private set; }
    
        public static UpdateDefinition Create(string name, string description, Guid? projectId)
        {

            return new UpdateDefinition(name, description, projectId == null ? null : Identity.Create(projectId.Value));
        }
    }
}
