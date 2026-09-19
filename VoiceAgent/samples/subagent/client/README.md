---
ai-usage: ai-assisted
---

# Voice agent microphone client

`voice_client.py` connects to an existing Foundry voice agent using the
Projects Python SDK's `project.beta.voice_agents.realtime.connect()`. It streams 24 kHz PCM
microphone audio, plays the agent's audio response, supports interruption,
and displays transcripts and subagent lifecycle events.

This is a client application using the SDK, not an SDK library. It does not
use the separate Voice Live SDK or create/delete agents.
`voice_client_common.py` handles audio devices and terminal output.

## Install

Install PortAudio first:

- Ubuntu/Debian: `sudo apt-get install portaudio19-dev`
- macOS: `brew install portaudio`
- Windows: no additional system package is normally required.

Then create the client environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

The requirements use `azure-ai-projects[voice]>=2.7.0` from PyPI, including
the async connection dependencies. Python 3.10 or later is required.

## Run

Pass the project endpoint and existing voice-agent name directly. Authenticate
first (for example, with `az login`); no scenario `.env` file is required:

```bash
python voice_client.py \
  --project-endpoint <project-endpoint> \
  --agent-name <voice-agent-name>
```

The creation scripts print a launch command with both values filled in.
The client uses the agent's saved voice and turn-detection
configuration without sending `session.update`. Use agents configured for
PCM16 mono audio at 24 kHz, as in these samples.

Start speaking after the client connects. Use headphones to prevent speaker
output from feeding back into the microphone. Press `Ctrl+C` to disconnect.

## WSL

WSLg exposes Windows audio through PulseAudio. If PyAudio finds no devices,
install the ALSA PulseAudio plugin:

```bash
sudo apt-get install libasound2-plugins
```

Create the virtual environment with the Ubuntu system Python rather than a
Conda interpreter. Conda can load an incompatible C++ runtime into PortAudio:

```bash
/usr/bin/python3 -m venv .venv
```
