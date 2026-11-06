"""Scrollable GPT Live, delegation, and user transcripts; no protocol handling."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

# Display model/user text literally; never let embedded control codes move the cursor.
# Preserve tabs and newlines. The accumulated transcript itself remains unchanged.
_CONTROL_CODES = dict.fromkeys([*range(9), *range(11, 32), *range(127, 160)])


@dataclass(frozen=True)
class AgentActivity:
    title: str = ""
    status: str = ""
    text: str = ""


def literal(value: str, style: str = "") -> Text:
    """Keep model output literal, including markup-looking text."""
    return Text(value.translate(_CONTROL_CODES), style=style, overflow="fold")


class TranscriptPane(VerticalScroll, can_focus=True):
    """Each pane has its own scroll position and follow-latest state."""

    BINDINGS = [Binding("end", "follow_latest", "Follow latest")]

    def __init__(self, title: str, *, id: str):
        super().__init__(id=id)
        self.border_title = title
        self.content = Static(markup=False)

    def compose(self) -> ComposeResult:
        yield self.content

    def on_mount(self) -> None:
        self.anchor()

    def action_follow_latest(self) -> None:
        self.anchor()


class TranscriptApp(App[None]):
    """Agent on the left (GPT Live above Delegation), User on the right."""

    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("tab", "focus_next", "Next pane"),
        Binding("shift+tab", "focus_previous", "Previous pane", show=False),
        Binding("ctrl+c", "stop_conversation", "End lesson", priority=True),
        Binding("ctrl+q", "stop_conversation", "End lesson", show=False, priority=True),
    ]
    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: auto;
        max-height: 3;
        padding: 0 1;
    }
    #conversation {
        height: 1fr;
        min-height: 8;
    }
    #agent {
        width: 3fr;
        height: 1fr;
        border: round cyan;
    }
    TranscriptPane {
        height: 1fr;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: scroll;
        scrollbar-size: 1 1;
    }
    TranscriptPane > Static {
        width: 1fr;
        height: auto;
        /* Keep short transcripts at the top while anchoring overflowing text. */
        min-height: 100%;
        content-align: left top;
    }
    #gpt-live {
        border: round cyan;
    }
    #delegation-panel {
        height: 1fr;
        border: round yellow;
    }
    #delegation-id {
        height: auto;
        max-height: 3;
        padding: 0 1;
        color: yellow;
    }
    #user {
        width: 2fr;
        height: 1fr;
        border: round green;
    }
    #gpt-live:focus, #user:focus, #delegation-panel:focus-within {
        border: double $accent;
    }
    #scroll-help {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #shortcuts {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, transcript: TranscriptDisplay):
        super().__init__()
        self.transcript = transcript
        self.ready = asyncio.Event()
        self._rendered_versions: dict[str, int] = {}
        self._rendered_status: str | None = None
        self._panes: dict[str, TranscriptPane] = {}
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        yield Static(id="status", markup=False)
        with Horizontal(id="conversation"):
            with Vertical(id="agent"):
                yield TranscriptPane("GPT Live", id="gpt-live")
                with Vertical(id="delegation-panel"):
                    yield Static(id="delegation-id", markup=False)
                    yield TranscriptPane("", id="delegation")
            yield TranscriptPane("User", id="user")
        yield Static(
            "Mouse wheel / arrows / PgUp / PgDn: scroll | Home: start",
            id="scroll-help",
            markup=False,
        )
        yield Static(
            "Tab/Shift+Tab: pane | End: follow | Ctrl+C: end lesson",
            id="shortcuts",
            markup=False,
        )

    def on_mount(self) -> None:
        self._panes = {
            name: self.query_one(f"#{name}", TranscriptPane)
            for name in ("gpt-live", "delegation", "user")
        }
        self._delegation_panel = self.query_one("#delegation-panel")
        self._delegation_id = self.query_one("#delegation-id", Static)
        self._status_line = self.query_one("#status", Static)
        self.query_one("#agent").border_title = "Agent"
        self._delegation_panel.border_title = "Delegation"
        self.refresh_transcripts()
        self._panes["gpt-live"].focus()
        self._refresh_timer = self.set_interval(0.1, self.refresh_transcripts)
        self.ready.set()

    def on_unmount(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._panes.clear()

    def refresh_transcripts(self) -> None:
        if not self._panes:
            return
        if any(
            not widget.is_attached
            for widget in (
                *self._panes.values(),
                self._delegation_panel,
                self._delegation_id,
                self._status_line,
            )
        ):
            return
        model = self.transcript
        for name, pane in self._panes.items():
            if self._rendered_versions.get(name) != model._versions[name]:
                if name == "delegation":
                    content = model.delegation_text()
                    self._delegation_id.update(literal(model.delegation_heading()))
                else:
                    content = literal(
                        model.agent_text if name == "gpt-live" else model.user_text
                    )
                pane.content.update(content)
                self._rendered_versions[name] = model._versions[name]
            # Textual anchoring follows new content only until the user scrolls.
            following = pane.is_anchored and (
                pane.max_scroll_y == 0 or pane.is_vertical_scroll_end
            )
            subtitle = "Following" if following else "Scrollback | End to follow"
            border = self._delegation_panel if name == "delegation" else pane
            if border.border_subtitle != subtitle:
                border.border_subtitle = subtitle
        if self._rendered_status != model.status:
            self._status_line.update(literal(model.status))
            self._rendered_status = model.status

    def action_stop_conversation(self) -> None:
        # Keep the UI alive while the caller closes the session and drains audio.
        self.transcript.request_stop()
        self.refresh_transcripts()


class TranscriptDisplay:
    """Transcript model with an interactive terminal UI or plain-output fallback."""

    def __init__(self, *, console: Console | None = None):
        self.console = console or Console(markup=False, highlight=False)
        self.agent_text = ""
        self.user_text = ""
        self.agent_activities: dict[str, AgentActivity] = {}
        self._latest_activity: str | None = None
        self.status = "Waiting for the Live session..."
        self.stop_requested = asyncio.Event()
        self._versions = {"gpt-live": 0, "delegation": 0, "user": 0}
        self._app: TranscriptApp | None = None
        self._ui_task: asyncio.Task | None = None

    def append_agent(self, delta: str):
        self.agent_text += delta
        self._versions["gpt-live"] += 1

    def append_user(self, delta: str):
        self.user_text += delta
        self._versions["user"] += 1

    def set_status(self, message: str):
        self.status = message
        if self._app is None:
            self.console.print(literal(message))

    def request_stop(self):
        self.stop_requested.set()
        self.set_status("Stopping the lesson; waiting for session finalization...")

    def update_agent_activity(
        self,
        key: str,
        *,
        title: str | None = None,
        status: str | None = None,
        delta: str = "",
    ):
        """Display caller-supplied activity text without interpreting protocol events."""
        previous = self.agent_activities.get(key, AgentActivity())
        self.agent_activities[key] = AgentActivity(
            title=previous.title if title is None else title,
            status=previous.status if status is None else status,
            text=previous.text + delta,
        )
        self._latest_activity = key
        self._versions["delegation"] += 1

    def delegation_heading(self) -> str:
        if self._latest_activity is None:
            return "ID: waiting for a delegation"
        if self._latest_activity == "uncorrelated-backend":
            return "ID: not supplied (uncorrelated backend)"
        return f"Latest ID: {self._latest_activity}"

    def delegation_text(self) -> Text:
        content = Text(overflow="fold")
        for key, activity in self.agent_activities.items():
            if content:
                content.append("\n\n")
            identifier = "not supplied" if key == "uncorrelated-backend" else key
            content.append(literal(f"ID: {identifier}\n", "bold yellow"))
            content.append(literal(activity.title + "\n", "bold yellow"))
            content.append(literal(activity.status, "yellow"))
            if activity.text:
                content.append("\n")
                content.append(literal(activity.text))
        return content

    def _panels(self) -> Table:
        columns = Table.grid(padding=0, expand=True)
        columns.add_column(ratio=3)
        columns.add_column(ratio=2)
        agent = Group(
            Panel(literal(self.agent_text), title="GPT Live", border_style="cyan"),
            Panel(self.delegation_text(), title="Delegation", border_style="yellow"),
        )
        columns.add_row(
            Panel(agent, title="Agent", border_style="cyan", padding=0),
            Panel(literal(self.user_text), title="User", border_style="green"),
        )
        return columns

    async def __aenter__(self):
        if (
            self.console.is_terminal
            and not self.console.is_dumb_terminal
            and sys.stdin.isatty()
        ):
            loop = asyncio.get_running_loop()
            task_factory = loop.get_task_factory()
            self._app = TranscriptApp(self)
            self._ui_task = asyncio.create_task(self._app.run_async())
            self._ui_task.add_done_callback(lambda _: self.stop_requested.set())
            ready = asyncio.create_task(self._app.ready.wait())
            try:
                done, _ = await asyncio.wait(
                    (ready, self._ui_task),
                    timeout=10,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if ready not in done or self._ui_task.done():
                    raise RuntimeError("The terminal transcript UI could not start.")
            except BaseException:
                self._app.exit()
                await self._ui_task
                raise
            finally:
                # Textual enables eager tasks on Python 3.12; keep SDK scheduling unchanged.
                loop.set_task_factory(task_factory)
                ready.cancel()
                await asyncio.gather(ready, return_exceptions=True)
        return self

    async def __aexit__(self, *_):
        if self._app is not None:
            self._app.exit()
            await self._ui_task
            self.console.print(literal(self.status))
        if self.agent_text or self.user_text or self.agent_activities:
            # Preserve every stream and delegation ID after leaving the full-screen UI.
            # Redirected output gets a static view without terminal input or redraws.
            self.console.print(self._panels())
