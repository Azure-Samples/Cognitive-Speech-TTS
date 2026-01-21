namespace Microsoft.SpeechServices.VideoTranslation.DataContracts.DTOs;

// No need expose optional features list to end user.
public class VideoTranslationProfileMetadata
{
    public string Name { get; set; }

    public bool? IsPrivate { get; set; }

    public bool? IsDefault { get; set; }

    public string Description { get; set; }
}
