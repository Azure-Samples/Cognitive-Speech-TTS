namespace Microsoft.SpeechServices.VideoTranslation;

public enum Mode
{
    None = 0,

    QueryMetadata,

    UploadVideoOrAudioFile,

    UploadVideoOrAudioFileIfNotExist,

    UploadVideoOrAudioFileAndCreateTranslation,

    CreateTranslation,

    DeleteVideoOrAudioFile,

    QueryVideoOrAudioFile,

    QueryVideoOrAudioFiles,

    DeleteTranslation,

    QueryTranslation,

    QueryTranslations,

    QueryTargetLocales,

    QueryTargetLocale,

    UpdateTargetLocaleEdittingWebvttFile,

    DeleteTargetLocale,
}