namespace Microsoft.SpeechServices.CommonLib.CommandParser;

public sealed class ExitCode
{
    public const int NoError = 0;

    public const int InvalidArgument = -1;

    public const int GenericError = 999;

    private ExitCode()
    {
    }
}