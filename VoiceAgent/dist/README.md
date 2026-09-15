# Bundled Azure AI Projects SDK

`azure_ai_projects-2.6.1-py3-none-any.whl` is built from the unmodified
`sdk/ai/azure-ai-projects` package in the Azure SDK for Python repository:

- Branch: [`feature/azure-ai-projects/vnext`](https://github.com/Azure/azure-sdk-for-python/tree/feature/azure-ai-projects/vnext/sdk/ai/azure-ai-projects)
- Commit: [`d5d87df0cd63e131bdbd70cea29b2e5c42999140`](https://github.com/Azure/azure-sdk-for-python/tree/d5d87df0cd63e131bdbd70cea29b2e5c42999140/sdk/ai/azure-ai-projects)
- Package version: `2.6.1`
- Built: September 15, 2026, using Python 3.12.14 on Windows (Git CRLF checkout)
- Build tools: `build==1.6.0`, `setuptools==84.0.0`, `wheel==0.48.0`
- SHA-256: `8a43e302a1cbd26b57e0f2bbd021c43bd6e19867f0b21dac8cc15620c5e53422`

The wheel includes the upstream MIT license. It replaces the separate
`azure-ai-voiceagents` SDK; the samples use the new Projects API only.
`samples/requirements.txt` installs this local wheel rather than fetching
`azure-ai-projects` from PyPI.

## Rebuild

Use a separate SDK checkout and build environment. With the pinned build
tools installed, run from the Azure SDK repository root:

```powershell
git checkout d5d87df0cd63e131bdbd70cea29b2e5c42999140
python -m pip install build==1.6.0 setuptools==84.0.0 wheel==0.48.0
$env:SOURCE_DATE_EPOCH = (git show -s --format=%ct HEAD).Trim()
python -m build --wheel --no-isolation --outdir dist sdk/ai/azure-ai-projects
Get-FileHash -Algorithm SHA256 dist/azure_ai_projects-2.6.1-py3-none-any.whl
```

Copy the resulting wheel into this directory and update the requirements,
source commit, and checksum together when upgrading the SDK.
