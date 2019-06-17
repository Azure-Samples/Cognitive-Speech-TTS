using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Microsoft.SpeechServices.Cris.Http
{
    public sealed class VoiceSynthesisUpdate
    {
        [Obsolete("This may only be used by serializers. Please use the other constructor.")]
        public VoiceSynthesisUpdate()
        {
        }

        private VoiceSynthesisUpdate(string name, string description)
        {
            this.Name = name?.Trim();
            this.Description = description?.Trim();
        }

        public string Name { get; set; }

        /// <inheritdoc />
        public string Description { get; set; }

        public static VoiceSynthesisUpdate Create(
            string name,
            string description)
        {
            return new VoiceSynthesisUpdate(name, description);
        }
    }
}
