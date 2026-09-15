// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

using System;
using Azure.AI.Projects.Agents.Samples;

if (args.Length == 1 && args[0] is "--help" or "-h")
{
    Console.WriteLine("""
        Foundry voice agent sample

        Usage: dotnet run

        Required:
          FOUNDRY_PROJECT_ENDPOINT          Foundry project HTTPS endpoint.

        To create a temporary agent:
          FOUNDRY_VOICE_MODEL_NAME          Voice model name or deployment name.
                                           Falls back to FOUNDRY_MODEL_NAME.
          FOUNDRY_VOICE_MODEL_TYPE          managed or self-deployed (default).

        To use an existing agent:
          FOUNDRY_VOICE_AGENT_NAME          Use its latest version without changing
                                           or deleting its stored definition.

        Optional:
          FOUNDRY_VOICE_INPUT_AUDIO_PATH    Raw PCM16 mono, 24 kHz input file.
          FOUNDRY_VOICE_OUTPUT_AUDIO_PATH   Output PCM file (default: temporary file).

        Sign in with az login or configure DefaultAzureCredential.
        Conversations and audio are persisted (Store = true).
        A temporary agent is deleted when the sample finishes.
        See README.md and Sample_VoiceAgent.md for prerequisites and details.
        """);
    return 0;
}

if (args.Length != 0)
{
    Console.Error.WriteLine("Unexpected arguments. Use --help for usage.");
    return 1;
}

await Sample_VoiceAgent.RunAsync();
return 0;
