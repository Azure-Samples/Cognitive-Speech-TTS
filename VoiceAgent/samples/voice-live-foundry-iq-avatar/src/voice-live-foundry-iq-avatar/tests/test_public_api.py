from __future__ import annotations

from pathlib import Path


RUNTIME = Path(__file__).parents[1]
ROOT = Path(__file__).parents[3]
SOURCE_SUFFIXES = {".py", ".yaml", ".yml", ".html", ".md", ".sh", ".ps1"}


def test_sample_does_not_use_private_voice_agent_contracts() -> None:
    forbidden = [
        "VoiceAgents=" + "V1Preview",
        "/endpoint/protocols/" + "voice",
        "session." + "_prepare_url",
        "kind: " + "voice",
    ]
    files = [path for path in ROOT.rglob("*") if path.suffix in SOURCE_SUFFIXES]

    for path in files:
        if path == Path(__file__):
            continue
        content = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in content, f"{marker!r} found in {path.relative_to(ROOT)}"


def test_browser_defaults_static_host_to_agent_and_proxy_to_same_origin() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")

    assert 'loc.port === "8765"' in html
    assert 'return "ws://localhost:8088/invocations_ws"' in html
    assert "if (/^wss:" not in html
    assert "isDirectFoundryUrl(url)" in html
    assert "socket.onmessage = (ev) => {\n      if (ws !== socket) return;" in html


def test_avatar_browser_is_optional_and_uses_its_own_audio() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")

    assert '<fieldset id="avatarPanel" hidden>' in html
    assert "let avatarEnabled = false" in html
    assert "if (!avatarMedia) setupAvatarMedia();" in html
    assert "video.muted = false;" in html
    assert 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"' in html
    assert "if (avatarEnabled) return;" in html
    assert "personal" not in html.lower()
    assert 'case "mcp_status":' in html
    assert "Knowledge MCP ${msg.operation}: ${msg.status}" in html


def test_avatar_browser_has_bounded_buffer_and_cleans_up() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")

    assert "MAX_AVATAR_QUEUE_BYTES = 32 * 1024 * 1024" in html
    assert "MAX_AVATAR_BUFFER_SECONDS = 60" in html
    assert "avatarBuffer.remove(0, removeBefore);" in html
    assert "avatarEvents?.abort();" in html
    assert "URL.revokeObjectURL(avatarUrl)" in html
    assert 'video.removeAttribute("src");' in html
    assert "avatarFailed = true;" in html
    assert "if (avatarFailed) return;" in html


def test_avatar_completion_waits_for_media_boundary_and_interruption_keeps_stream() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")

    assert "avatarQueue.push(null);" in html
    assert 'video.addEventListener("timeupdate", updateAvatarPlayback, options);' in html
    assert "video.currentTime >= avatarDoneTime - 0.05" in html
    speech_started = html.split('case "user_speech_started":', 1)[1].split(
        'case "user_speech_stopped":', 1
    )[0]
    assert "interruptAvatar();" in speech_started
    interruption = html.split("function interruptAvatar()", 1)[1].split(
        "// ---- Mic capture", 1
    )[0]
    assert "avatarSeekToLive = true;" in interruption
    assert "releaseAvatarMedia" not in interruption
    assert html.count('if (avatarMedia !== media || error.name === "AbortError") return;') == 2


def test_cancelled_greeting_does_not_schedule_playback_completion() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")
    completion = html.split('case "response_done":', 1)[1].split('case "error":', 1)[0]
    guard = 'if (msg.kind === "greeting" && msg.status !== "completed") break;'
    assert completion.index(guard) < completion.index("avatarQueue.push(null)")
    assert completion.index(guard) < completion.index("doneTimer = setTimeout")


def test_knowledge_browser_preserves_pcm_microphone_and_interruption() -> None:
    html = (RUNTIME / "chat_client" / "index.html").read_text(encoding="utf-8")

    assert "const SR = 24_000;" in html
    assert "const CHUNK_SAMPLES = 2400;" in html
    assert "navigator.mediaDevices.getUserMedia({" in html
    assert "micNode = micCtx.createScriptProcessor(2048, 1, 1);" in html
    assert "onChunk(i16.buffer);" in html
    assert "if (micMuted) return;" in html
    assert "socket.readyState === WebSocket.OPEN) socket.send(buf);" in html
    assert "const sr = view.getUint32(0, true);" in html
    assert "const ch = view.getUint32(4, true);" in html
    assert "playPcm(new Uint8Array(ev.data, 8), sr, ch);" in html
    assert "for (const s of playSources) { try { s.stop(); } catch {} }" in html
    speech_started = html.split('case "user_speech_started":', 1)[1].split(
        'case "user_speech_stopped":', 1
    )[0]
    assert "clearTimeout(doneTimer); doneTimer = null;" in speech_started
    assert "cancelPlayback();" in speech_started


def test_azd_up_provisions_before_deploying() -> None:
    manifest = (ROOT / "azure.yaml").read_text(encoding="utf-8")

    provision = manifest.index("- azd: provision")
    deploy = manifest.index("- azd: deploy --all")
    assert provision < deploy
