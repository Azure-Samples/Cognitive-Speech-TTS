using System;

namespace CustomVoice_API.API.DTO
{
    class Identity
    {
        public Identity(Guid id)
        {
            this.Id = id;
        }

        public Guid Id { get; private set; }

        public static Identity Create(Guid Id)
        {
            return new Identity(Id);
        }
    }
}
