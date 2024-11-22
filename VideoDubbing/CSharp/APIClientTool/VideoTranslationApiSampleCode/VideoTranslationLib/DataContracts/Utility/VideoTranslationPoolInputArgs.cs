using Microsoft.SpeechServices.Common.Client;
using Microsoft.SpeechServices.CommonLib.Enums;
using Microsoft.SpeechServices.VideoTranslation.Enums;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;

namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.Utility
{
    public class VideoTranslationPoolInputArgs
    {
        public VideoTranslationPoolInputArgs()
        {
            this.AdditionalHeaders = new Dictionary<string, string>();
            this.AdditionalProperties = new Dictionary<string, string>();
        }

        public string VideoFilePath { get; set; }

        public CultureInfo SourceLocale { get; set; }

        public VideoTranslationVoiceKind? VoiceKind { get; set; }

        public string EnableFeatures { get; set; }

        public string ProfileName { get; set; }

        public bool? WithoutSubtitleInTranslatedVideoFile { get; set; }

        public int? SubtitleMaxCharCountPerSegment { get; set; }

        public bool? ExportPersonalVoicePromptAudioMetadata { get; set; }

        public string PersonalVoiceModelName { get; set; }

        public bool? IsAssociatedWithTargetLocale { get; set; }

        public VideoTranslationWebvttSourceKind? WebvttSourceKind { get; set; }

        public List<CultureInfo> TargetLocales { get; set; }

        public Dictionary<string, string> AdditionalProperties { get; private set; }

        public Dictionary<string, string> AdditionalHeaders { get; private set; }
    }
}
