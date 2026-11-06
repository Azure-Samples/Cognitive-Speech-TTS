"""Check Azure WebSocket upgrade and session readiness without sending microphone audio."""

import asyncio
import json

import aiohttp

from auth import AzureCliTokenProvider
from server import connect_voice, describe_connection_error, load_settings


async def check():
    cfg = load_settings()
    if not cfg.configured:
        print(json.dumps({"ok": False, "stage": "configuration", "issues": cfg.setup_issues,
                          "message": "Set project endpoint and agent name in .env, then sign in with az login."}))
        return 1
    events = []
    stage = "azure_cli_authentication"
    try:
        async with asyncio.timeout(50):
            async with aiohttp.ClientSession() as client:
                provider = AzureCliTokenProvider()
                token = await provider.get_token(client)
                stage = "websocket_upgrade"
                async with connect_voice(client, cfg, {"Authorization": f"Bearer {token}",
                        "Foundry-Features": cfg.features}, "websocket") as ws:
                    print(json.dumps({"stage": "websocket_upgrade", "ok": True}), flush=True)
                    stage = "session_startup"
                    async for message in ws:
                        if message.type != aiohttp.WSMsgType.TEXT:
                            continue
                        event = json.loads(message.data)
                        events.append(event.get("type"))
                        if event.get("type") == "session.updated":
                            print(json.dumps({"ok": True, "stage": "session_ready", "events": events,
                                              "note": "No microphone audio or user turn was sent."}))
                            return 0
                        if event.get("type") == "error":
                            print(json.dumps({"ok": False, "stage": "service_error", "events": events}))
                            return 1
        print(json.dumps({"ok": False, "stage": "closed_before_ready", "events": events}))
    except Exception as error:
        os_error = getattr(error, "os_error", error)
        print(json.dumps({"ok": False, "stage": stage, "error_type": type(error).__name__,
                          "message": describe_connection_error(error),
                          "http_status": getattr(error, "status", None),
                          "errno": getattr(os_error, "errno", None),
                          "winerror": getattr(os_error, "winerror", None), "events": events}))
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
