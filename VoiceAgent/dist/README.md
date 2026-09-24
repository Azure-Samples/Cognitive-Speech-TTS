# SDK packages

Python samples now install `azure-ai-projects>=2.7.0`
from PyPI, using the `[voice]` extra for SDK voice connections. No Python
wheels are bundled. Use the requirements files under `samples/` to install
the public package.

The .NET sample installs the published
[`Azure.AI.Projects`](https://www.nuget.org/packages/Azure.AI.Projects/3.0.0-beta.3)
and [`Azure.AI.Projects.Agents`](https://www.nuget.org/packages/Azure.AI.Projects.Agents/3.0.0-beta.3)
3.0.0-beta.3 preview SDK packages from NuGet.org. No .NET packages are bundled. See the
[C# setup instructions](../samples/CSharp/README.md) for package and restore details.

## Historical .NET preview build record

The removed bundled package used the same `3.0.0-beta.3` version as the public
release but was a separate preview build. It is no longer a sample dependency.

- Source archive: `Azure.AI.Projects.Agents.3.0.0-beta.3-voice-samples.zip`
- Package: `Azure.AI.Projects.Agents.3.0.0-beta.3.nupkg`
- SDK repository commit recorded in package: `4c94d5d53db51d0fd8089a341ccbe11d4ff9f65d`
- SHA-256: `16f5214c679488943d103a32b7a0fff1321e08815f50400bf14c3f62f3e62329`
- License: MIT

## Historical Python preview build record

The removed preview wheel was built from the unmodified
`sdk/ai/azure-ai-projects` package in the Azure SDK for Python repository.
This record describes the SDK used for the September 16-17 evaluations,
not a current sample dependency.

- Branch: [`xitzhang/voice-agent-pupr`](https://github.com/Azure/azure-sdk-for-python/tree/xitzhang/voice-agent-pupr/sdk/ai/azure-ai-projects)
- Commit: [`f84c5330f4246892455f33fccdf9503a774ecf66`](https://github.com/Azure/azure-sdk-for-python/tree/f84c5330f4246892455f33fccdf9503a774ecf66/sdk/ai/azure-ai-projects)
- Package version: `2.7.0b1`
- Built: September 15, 2026, using Python 3.12.10 on Windows (`core.autocrlf=false`, LF checkout)
- Build tools: `build==1.6.0`, `setuptools==84.0.0`, `wheel==0.48.0`
- SHA-256: `f857a1281e2fa3414f25e02aed95dfe2275495027b0a764f38921a8589f15e75`
