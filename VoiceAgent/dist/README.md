# Bundled Azure AI Projects SDK

`azure_ai_projects-2.7.0b1-py3-none-any.whl` is built from the unmodified
`sdk/ai/azure-ai-projects` package in the Azure SDK for Python repository:

- Branch: [`xitzhang/voice-agent-pupr`](https://github.com/Azure/azure-sdk-for-python/tree/xitzhang/voice-agent-pupr/sdk/ai/azure-ai-projects)
- Commit: [`f84c5330f4246892455f33fccdf9503a774ecf66`](https://github.com/Azure/azure-sdk-for-python/tree/f84c5330f4246892455f33fccdf9503a774ecf66/sdk/ai/azure-ai-projects)
- Package version: `2.7.0b1`
- Built: September 15, 2026, using Python 3.12.10 on Windows (`core.autocrlf=false`, LF checkout)
- Build tools: `build==1.6.0`, `setuptools==84.0.0`, `wheel==0.48.0`
- SHA-256: `f857a1281e2fa3414f25e02aed95dfe2275495027b0a764f38921a8589f15e75`

The wheel includes the upstream MIT license and the synchronous and asynchronous
Voice Agent realtime clients. The samples use Projects SDK APIs for both agent
management and communication, with no `azure-ai-voicelive` dependency.
`samples/requirements.txt` installs this local wheel with its `[realtime]` extra
rather than fetching `azure-ai-projects` from PyPI.

## Rebuild

Use a fresh, separate SDK checkout and build environment. Preserve LF line
endings and use the source commit timestamp for wheel entries:

```powershell
git -c core.autocrlf=false clone --single-branch --branch xitzhang/voice-agent-pupr https://github.com/Azure/azure-sdk-for-python.git
Set-Location azure-sdk-for-python
git config core.autocrlf false
git checkout f84c5330f4246892455f33fccdf9503a774ecf66
python -m venv .build-venv
.\.build-venv\Scripts\Activate.ps1
python -m pip install build==1.6.0 setuptools==84.0.0 wheel==0.48.0
$env:SOURCE_DATE_EPOCH = (git show -s --format=%ct HEAD).Trim()
python -m build --wheel --no-isolation --outdir dist sdk/ai/azure-ai-projects
Get-FileHash -Algorithm SHA256 dist/azure_ai_projects-2.7.0b1-py3-none-any.whl
```

For another build, start from a fresh package checkout again. This branch's
package discovery can include a previous `build/` directory in the wheel.
The bundled wheel was reproduced byte-for-byte from two fresh checkouts.

Copy the resulting wheel into this directory and update the requirements,
source commit, and checksum together when upgrading the SDK.
