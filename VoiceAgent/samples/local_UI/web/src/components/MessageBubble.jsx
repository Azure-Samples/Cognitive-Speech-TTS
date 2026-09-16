// Copyright (c) Microsoft. All rights reserved.
// One chat message bubble. Type drives color + alignment, mirroring the Voice Live
// sample's getMessageClassNames (user=blue/right, assistant=gray/left,
// status=yellow/center, error=red/center, event=faint/center). MCP tool calls and
// approval requests (design §6) render as structured cards; an approval card shows
// Approve/Reject until answered (mirrors chat-interface.tsx).

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ALL_TURN_OUTLIER_PERCENT,
  LATENCY_CHECKPOINTS,
  LATENCY_TONE_LEGEND,
  LATENCY_VISUAL_REFERENCE_MS,
  buildAllTurnLatencyTable,
  buildLatencySumAnalysis,
  formatMetricMs,
  latencyBarPercent,
  latencyRulerTicks,
} from "../lib/turnMetrics.mjs";
// The digit-accuracy demo is the one client function that ships with the portal, and its whole
// value is the side-by-side reading; a raw JSON blob would bury it.
import { digitComparison } from "../lib/digitDemo.mjs";

const LABELS = { user: "You", assistant: "Agent", status: "", error: "error", event: "" };

const STATUS_TEXT = { in_progress: "In progress\u2026", completed: "Completed", failed: "Failed" };

function formatTableValue(column, value) {
  if (value == null) return "\u2014";
  return column.kind === "latency" ? formatMetricMs(value) : String(Math.round(value));
}

function formatDelta(value) {
  if (value == null) return "\u2014";
  if (value === 0) return "0%";
  return `${value > 0 ? "+" : ""}${value}%`;
}

const METRIC_SCOPE_LABELS = {
  envelope: "End-to-end envelope",
  checkpoint: "Cumulative checkpoint",
  atomic: "Mutually exclusive atomic phase",
  subsystem: "Subsystem aggregate",
  count: "Non-latency supporting signal",
};

function MetricExplanation({ column, children, className = "" }) {
  const triggerRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  const show = () => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      const width = Math.min(430, window.innerWidth - 24);
      const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
      const below = rect.bottom + 10;
      const top = below + 430 <= window.innerHeight
        ? below
        : Math.max(12, rect.top - 440);
      setPosition({ top, left });
    }
    setOpen(true);
  };

  const hide = () => {
    if (!pinned) setOpen(false);
  };

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setPinned(false);
        setOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const relationship = {
    envelope: "Total contains the complete wait and equals the sum of the atomic phase columns.",
    checkpoint: "This starts at the turn origin and therefore overlaps Total and multiple atomic phases.",
    atomic: "This column does not overlap another atomic phase; atomic columns add up to Total.",
    subsystem: "This groups mutually exclusive atomic phases by optimization owner. A subsystem can contain multiple non-contiguous intervals, and all subsystem columns add up to Total.",
    count: "This is contextual evidence only and is never added to a latency duration.",
  }[column.scope];

  return (
    <>
      <button
        type="button"
        ref={triggerRef}
        className={`metric-help-trigger ${className}`}
        aria-expanded={open}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={() => {
          const nextPinned = !pinned;
          setPinned(nextPinned);
          if (nextPinned) show();
          else setOpen(false);
        }}
      >
        {children}
        <span className="metric-help-icon" aria-hidden="true">?</span>
      </button>
      {open ? createPortal(
        <aside
          className={`metric-explanation-popover${pinned ? " pinned" : ""}`}
          style={{ top: `${position.top}px`, left: `${position.left}px` }}
          role={pinned ? "dialog" : "tooltip"}
          aria-label={`${column.label} metric definition`}
        >
          <div className="metric-popover-header">
            <div>
              <span className={`metric-scope scope-${column.scope}`}>
                {METRIC_SCOPE_LABELS[column.scope]}
              </span>
              <h3>{column.label}</h3>
            </div>
            {pinned ? (
              <button
                type="button"
                aria-label="Close metric explanation"
                onClick={() => {
                  setPinned(false);
                  setOpen(false);
                }}
              >
                ×
              </button>
            ) : null}
          </div>

          <p className="metric-definition">{column.description}</p>

          {column.includedPhases?.length ? (
            <div className="metric-included-phases">
              <strong>Included phases</strong>
              <ul>
                {column.includedPhases.map((phase) => <li key={phase}>{phase}</li>)}
              </ul>
            </div>
          ) : null}

          <figure className={`metric-boundary-diagram scope-${column.scope}`}>
            <div className="metric-boundary-line">
              <span className="metric-boundary-node start" />
              <span className="metric-boundary-range">
                <i />
              </span>
              <span className="metric-boundary-node end" />
            </div>
            <figcaption>
              <span>{column.startLabel}</span>
              <strong>{column.kind === "latency" ? "elapsed time" : "usage accumulated"}</strong>
              <span>{column.endLabel}</span>
            </figcaption>
          </figure>

          <dl className="metric-popover-details">
            <div>
              <dt>Calculation</dt>
              <dd>
                {column.kind === "latency"
                  ? column.calculation
                    || `${column.endLabel} timestamp \u2212 ${column.startLabel} timestamp`
                  : `Sum reported token usage from ${column.startLabel} through ${column.endLabel}`}
              </dd>
            </div>
            <div>
              <dt>How to interpret a high value</dt>
              <dd>{column.interpretation}</dd>
            </div>
            <div>
              <dt>Relationship to this table</dt>
              <dd>{relationship}</dd>
            </div>
            <div>
              <dt>Average and +/- %</dt>
              <dd>
                Average uses all turns where this metric is available. Each row shows
                <code>(turn value - average) / average × 100%</code>. Missing values are excluded,
                not treated as zero.
              </dd>
            </div>
          </dl>

          <div className="metric-caveats">
            <strong>Measurement caveats</strong>
            <ul>
              {(column.caveats || []).map((caveat) => <li key={caveat}>{caveat}</li>)}
            </ul>
          </div>
          <p className="metric-popover-pin">
            {pinned ? "Pinned. Press Esc or × to close." : "Click the ? to keep this explanation open."}
          </p>
        </aside>,
        document.body,
      ) : null}
    </>
  );
}

function AllTurnsTable({ messages, currentMessageId }) {
  const table = buildAllTurnLatencyTable(messages);
  if (!table.rows.length) {
    return <p className="latency-table-empty">No completed measurable Agent replies yet.</p>;
  }
  return (
    <>
      <p className="latency-table-note">
        Subsystem columns group atomic phases by optimization owner, not timeline order. Each cell shows
        its value and difference from that column's average. Red means at least{" "}
        {ALL_TURN_OUTLIER_PERCENT}% above average and at least 100ms higher (50 for Tokens).
      </p>
      <div className="latency-table-scroll">
        <table className="latency-all-turns-table">
          <thead>
            <tr>
              <th>Turn</th>
              {table.columns.map((column) => (
                <th key={column.key}>
                  <MetricExplanation column={column} className="metric-help-header">
                    {column.label}
                  </MetricExplanation>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="latency-average-row">
              <th>Average</th>
              {table.columns.map((column) => (
                <td key={column.key}>
                  <MetricExplanation column={column} className="metric-help-cell">
                    <span>{formatTableValue(column, column.average)}</span>
                  </MetricExplanation>
                </td>
              ))}
            </tr>
            {table.rows.map((row) => (
              <tr className={row.id === currentMessageId ? "current" : ""} key={row.id}>
                <th title={row.responsePreview}>#{row.turn}</th>
                {table.columns.map((column) => {
                  const cell = row.cells[column.key];
                  return (
                    <td className={cell.outlier ? "outlier" : ""} key={column.key}>
                      <MetricExplanation column={column} className="metric-help-cell">
                        <span>{formatTableValue(column, cell.value)}</span>
                        <small>{formatDelta(cell.deltaPercent)}</small>
                      </MetricExplanation>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function LatencySumPanel({ messages }) {
  const analysis = buildLatencySumAnalysis(messages);
  return (
    <div className="latency-sum-panel">
      <div className="latency-sum-summary">
        <div>
          <span>Included spoken turns</span>
          <strong>{analysis.includedTurns.length}</strong>
        </div>
        <div>
          <span>Cumulative latency</span>
          <strong>{formatMetricMs(analysis.totalDurationMs)}</strong>
        </div>
        <div>
          <span>Excluded responses</span>
          <strong>{analysis.excludedTurns.length}</strong>
        </div>
      </div>
      <p className="latency-table-note">
        Ranked by cumulative elapsed time across completed Agent replies with an audible trigger boundary.
        A large category is the largest measured optimization opportunity, not a claim that all of it
        can be removed.
      </p>

      {analysis.subsystems.length ? (
        <div className="latency-sum-list">
          {analysis.subsystems.map((subsystem, index) => (
            <article className={`latency-sum-row tone-${subsystem.tone}`} key={subsystem.key}>
              <div className="latency-sum-rank">{index + 1}</div>
              <div className="latency-sum-content">
                <div className="latency-sum-title">
                  <strong>{subsystem.label}</strong>
                </div>
                <div className="latency-sum-track">
                  <span
                    className={`latency-sum-fill tone-${subsystem.tone}`}
                    style={{ width: `${subsystem.percent}%` }}
                  />
                </div>
                <div className="latency-sum-metrics">
                  <span><b>Total time</b>{formatMetricMs(subsystem.durationMs)}</span>
                  <span><b>Overall share</b>{subsystem.percent}%</span>
                  <span><b>Avg / turn</b>{formatMetricMs(subsystem.averageMs)}</span>
                  <span><b>Avg share / turn</b>{subsystem.averageTurnPercent}%</span>
                </div>
                <p className="latency-sum-definition">{subsystem.description}</p>
                <dl className="latency-sum-owner">
                  <div><dt>Primary owner</dt><dd>{subsystem.owner}</dd></div>
                  <div><dt>Includes</dt><dd>{subsystem.includedPhases.join(", ")}</dd></div>
                </dl>
                <div className="latency-sum-actions">
                  <strong>If this is high</strong>
                  <ul>
                    {subsystem.actions.map((action) => <li key={action}>{action}</li>)}
                  </ul>
                </div>
                <details className="latency-sum-caveats">
                  <summary>Attribution limits</summary>
                  <ul>
                    {subsystem.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
                  </ul>
                </details>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="latency-table-empty">No completed measurable Agent replies to sum yet.</p>
      )}

      <details className="latency-sum-excluded" open={analysis.excludedTurns.length > 0}>
        <summary>Excluded responses ({analysis.excludedTurns.length})</summary>
        {analysis.excludedTurns.length ? (
          <ol>
            {analysis.excludedTurns.map((turn) => (
              <li key={turn.id}>
                <strong>Response #{turn.turn}</strong>
                <span>{turn.reason}</span>
                {turn.responsePreview ? <small>{turn.responsePreview}</small> : null}
              </li>
            ))}
          </ol>
        ) : (
          <p>None. Every completed response followed recorded user speech.</p>
        )}
      </details>
    </div>
  );
}

function LatencyDialog({ metrics, allMessages, currentMessageId, onClose }) {
  const [tab, setTab] = useState("turn");
  const [activePhaseId, setActivePhaseId] = useState(null);
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const phases = metrics.atomicPhases || [];
  const ticks = latencyRulerTicks(metrics.endToEndMs);
  const origin = {
    user_last_voiced: "last voiced microphone PCM",
    server_vad: "server speech_stopped (proxy)",
    text_input: "text input sent",
    idle_timeout: "idle timeout window start",
    agent_playback_end: "previous Agent speech end",
    response_created: "response.created",
  }[metrics.startSource] || "turn start";
  const headlineLabel = metrics.startSource === "idle_timeout"
    ? "Idle timeout→Agent"
    : metrics.startSource === "agent_playback_end" ? "Agent gap" : "User→Agent";
  const end = {
    playback: "scheduled playback of first speech",
    speech_pcm: "first voiced PCM frame",
    audio_packet: "first audio packet (proxy)",
  }[metrics.endSource] || "Agent response";

  return createPortal(
    <div
      className="latency-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="latency-dialog" role="dialog" aria-modal="true" aria-labelledby="latency-dialog-title">
        <header>
          <div>
            <h2 id="latency-dialog-title">Turn latency analysis</h2>
            <p>{origin} → {end}</p>
          </div>
          <button type="button" className="latency-dialog-close" onClick={onClose} aria-label="Close latency analysis">
            ×
          </button>
        </header>

        <div className="latency-dialog-tabs" role="tablist" aria-label="Latency analysis scope">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "turn"}
            className={tab === "turn" ? "active" : ""}
            onClick={() => setTab("turn")}
          >
            This turn
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "all"}
            className={tab === "all" ? "active" : ""}
            onClick={() => setTab("all")}
          >
            All turns
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "sum"}
            className={tab === "sum" ? "active" : ""}
            onClick={() => setTab("sum")}
          >
            Sum
          </button>
        </div>

        {tab === "turn" ? (
          <>
            <div className="latency-dialog-total">
              <b>{headlineLabel}</b>
              <strong>{formatMetricMs(metrics.endToEndMs)}</strong>
              <span>Overview fits the dialog; phase bars below use a 2-second reference.</span>
            </div>

            <div className="latency-tone-legend" aria-label="Latency subsystem colors">
              {LATENCY_TONE_LEGEND
                .filter(({ tone }) => phases.some((phase) => phase.tone === tone))
                .map(({ tone, label }) => (
                  <span key={tone}>
                    <i className={`latency-tone-swatch tone-${tone}`} aria-hidden="true" />
                    {label}
                  </span>
                ))}
            </div>

            <div className="latency-detail-scroll">
              <div className="latency-detail-canvas">
                <div className="latency-detail-segments">
                  {phases.map((phase) => (
                    <span
                      className={[
                        "atomic-segment",
                        `tone-${phase.tone}`,
                        activePhaseId === phase.id ? "highlighted" : "",
                        activePhaseId && activePhaseId !== phase.id ? "dimmed" : "",
                      ].filter(Boolean).join(" ")}
                      data-phase-id={phase.id}
                      key={phase.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`${phase.label}: ${formatMetricMs(phase.durationMs)}`}
                      onMouseEnter={() => setActivePhaseId(phase.id)}
                      onMouseLeave={() => setActivePhaseId(null)}
                      onFocus={() => setActivePhaseId(phase.id)}
                      onBlur={() => setActivePhaseId(null)}
                      style={{ width: `${latencyBarPercent(phase.durationMs, metrics.endToEndMs)}%` }}
                    />
                  ))}
                </div>
                <div className="latency-ruler">
                  {ticks.map((tick) => (
                    <span key={tick} style={{ left: `${latencyBarPercent(tick, metrics.endToEndMs)}%` }}>
                      {formatMetricMs(tick)}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="latency-phase-list">
              {phases.map((phase, index) => (
                <LatencyPhaseCard
                  key={phase.id}
                  phase={phase}
                  index={index}
                  active={activePhaseId === phase.id}
                  onActiveChange={setActivePhaseId}
                />
              ))}
            </div>
          </>
        ) : tab === "all" ? (
          <AllTurnsTable messages={allMessages} currentMessageId={currentMessageId} />
        ) : (
          <LatencySumPanel messages={allMessages} />
        )}
      </section>
    </div>,
    document.body,
  );
}

function LatencyPhaseCard({ phase, index, active, onActiveChange }) {
  return (
    <article
      className={`latency-phase-card${active ? " active" : ""}`}
      data-phase-id={phase.id}
      tabIndex={0}
      aria-describedby={`phase-tooltip-${phase.id}`}
      onMouseEnter={() => onActiveChange(phase.id)}
      onMouseLeave={() => onActiveChange(null)}
      onFocus={() => onActiveChange(phase.id)}
      onBlur={() => onActiveChange(null)}
    >
      <div className="latency-phase-title">
        <span>{index + 1}</span>
        <b>{phase.label}</b>
        <strong>{formatMetricMs(phase.durationMs)}</strong>
      </div>
      <div className="latency-phase-scroll">
        <div className="latency-phase-canvas">
          <span
            className={`latency-phase-fill tone-${phase.tone}`}
            style={{ width: `${latencyBarPercent(phase.durationMs, LATENCY_VISUAL_REFERENCE_MS)}%` }}
          />
        </div>
      </div>
      <p>{phase.reason}.</p>
      <span className="latency-phase-tooltip" id={`phase-tooltip-${phase.id}`} role="tooltip">
        Calculated as {phase.calculation}
      </span>
    </article>
  );
}

function CompactLatencyBar({ metrics, onOpen }) {
  const phases = metrics.atomicPhases || [];
  const totalWidthPercent = latencyBarPercent(
    metrics.endToEndMs,
    LATENCY_VISUAL_REFERENCE_MS,
  );
  const headlineLabel = metrics.startSource === "idle_timeout"
    ? "Idle timeout→Agent"
    : metrics.startSource === "agent_playback_end" ? "Agent gap" : "User→Agent";
  return (
    <button
      type="button"
      className="compact-latency-trigger"
      onClick={onOpen}
      title="Open the complete turn latency analysis"
    >
      <span className="compact-latency-heading">
        <span className="compact-latency-label">{headlineLabel}</span>
        <strong>{formatMetricMs(metrics.endToEndMs)}</strong>
      </span>
      <span className="compact-latency-scroll">
        <span className="compact-latency-canvas">
          <span
            className="compact-latency-fill"
            style={{ width: `${totalWidthPercent}%` }}
          >
            {phases.map((phase) => (
              <span
                className={`atomic-segment tone-${phase.tone}`}
                key={phase.id}
                style={{ width: `${latencyBarPercent(phase.durationMs, metrics.endToEndMs)}%` }}
              />
            ))}
            {phases.length ? null : <span className="atomic-segment tone-other" style={{ width: "100%" }} />}
          </span>
        </span>
      </span>
    </button>
  );
}

function TurnMetrics({ metrics, allMessages, currentMessageId }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const checkpoints = metrics
    ? LATENCY_CHECKPOINTS.filter((definition) => metrics[definition.key] != null)
    : [];
  const hasTokens = metrics && metrics.totalTokens != null;
  const hasTotal = metrics && metrics.endToEndMs != null;
  if (!hasTotal && checkpoints.length === 0 && !hasTokens) return null;
  const tools = (metrics && metrics.tools) || [];
  return (
    <div className="turn-metrics" aria-label="Agent turn metrics">
      {hasTotal ? (
        <>
          <CompactLatencyBar metrics={metrics} onOpen={() => setDialogOpen(true)} />
          {dialogOpen ? (
            <LatencyDialog
              metrics={metrics}
              allMessages={allMessages}
              currentMessageId={currentMessageId}
              onClose={() => setDialogOpen(false)}
            />
          ) : null}
        </>
      ) : null}
      <div className="turn-metric-notes">
        {checkpoints.map((checkpoint) => (
          <span className="latency-checkpoint" key={checkpoint.key} title={`${checkpoint.description} This checkpoint overlaps the atomic timeline.`}>
            <b>{checkpoint.label}</b> {formatMetricMs(metrics[checkpoint.key])}
          </span>
        ))}
        {hasTokens ? <span className="token-count"><b>Tokens</b> {metrics.totalTokens}</span> : null}
        {tools.map((tool) => (
          <span className="tool-checkpoint" key={tool.id}>
            <b>{tool.kind || "Tool"}</b>{tool.name ? ` ${tool.name}` : ""} {formatMetricMs(tool.durationMs)}
          </span>
        ))}
      </div>
    </div>
  );
}

function UserMetrics({ metrics }) {
  if (!metrics || metrics.sttMs == null) return null;
  return (
    <div className="turn-metrics user-turn-metrics" aria-label="User transcription metrics">
      <span className="turn-metric"><b>STT</b> {formatMetricMs(metrics.sttMs)}</span>
    </div>
  );
}

// What the model believed it heard, beside what the speech recognizer transcribed.
function DigitComparison({ comparison }) {
  if (!comparison) return null;
  if (!comparison.available) {
    return (
      <div className="fn-compare unavailable">
        <div className="fn-compare-title">No transcript for this turn</div>
        <div className="fn-compare-note">
          The recognizer produced nothing to compare, so the agent was told to ask again
          rather than trust either reading.
        </div>
      </div>
    );
  }
  const state = comparison.matches === null
    ? "unknown"
    : comparison.matches ? "match" : "mismatch";
  return (
    <div className={"fn-compare " + state}>
      <div className="fn-compare-title">
        Digit comparison — {comparison.field}
        <span className={"fn-compare-verdict " + state}>
          {state === "match" ? "agreed" : state === "mismatch" ? "corrected" : "not comparable"}
        </span>
      </div>
      <div className="fn-compare-row">
        <span className="fn-compare-label">Agent heard</span>
        <code className="fn-compare-value agent">{comparison.agentHeard || "\u2014"}</code>
      </div>
      <div className="fn-compare-row">
        <span className="fn-compare-label">Azure Speech</span>
        <code className="fn-compare-value truth">{comparison.recognizerValue || "\u2014"}</code>
      </div>
      {comparison.transcript ? (
        <div className="fn-compare-transcript">
          Transcript: “{comparison.transcript}”
        </div>
      ) : null}
    </div>
  );
}

export function MessageBubble({ message, allMessages = [], onApproval }) {
  const { type, content, handoff, mcpApproval, mcpCall, functionCall, metrics } = message;

  if (type === "handoff" && handoff) {
    return (
      <div className="msg handoff">
        <div className="bubble">
          <div className="meta"><span>Agent handoff</span></div>
          <div className="mcp-info">
            <div><strong>Route:</strong> <code>{handoff.fromNodeId}</code> &rarr; <code>{handoff.toNodeId}</code></div>
            <div><strong>Edge:</strong> {handoff.edgeId}</div>
            <div><strong>Status:</strong> <span className={"mcp-status " + handoff.status}>{handoff.status}</span></div>
            {handoff.durationMs != null ? <div><strong>Duration:</strong> {formatMetricMs(handoff.durationMs)}</div> : null}
            {handoff.prepareDurationMs != null ? <div><strong>Prepare:</strong> {formatMetricMs(handoff.prepareDurationMs)}</div> : null}
            {handoff.reason ? <div><strong>Abort reason:</strong> {handoff.reason}</div> : null}
            {handoff.error ? <div><strong>Error:</strong> <code className="wrap err">{JSON.stringify(handoff.error)}</code></div> : null}
          </div>
        </div>
      </div>
    );
  }

  if (type === "mcp_approval" && mcpApproval) {
    return (
      <div className="msg mcp_approval">
        <div className="bubble">
          <div className="meta"><span>MCP tool approval request</span></div>
          <div className="mcp-info">
            <div><strong>Server:</strong> {mcpApproval.serverLabel || "\u2014"}</div>
            <div><strong>Tool:</strong> {mcpApproval.name || "\u2014"}</div>
            <div><strong>Arguments:</strong> <code>{mcpApproval.arguments || "{}"}</code></div>
          </div>
          {!mcpApproval.handled ? (
            <div className="mcp-actions">
              <button className="approve" onClick={() => onApproval(message.id, mcpApproval.approvalRequestId, true)}>Approve</button>
              <button className="reject" onClick={() => onApproval(message.id, mcpApproval.approvalRequestId, false)}>Reject</button>
            </div>
          ) : (
            <div className={"mcp-handled " + (mcpApproval.approved ? "ok" : "denied")}>
              {mcpApproval.approved ? "Approved" : "Denied"}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (type === "mcp_call" && mcpCall) {
    const status = mcpCall.status || "in_progress";
    return (
      <div className="msg mcp_call">
        <div className="bubble">
          <div className="meta"><span>MCP tool call</span></div>
          <div className="mcp-info">
            <div><strong>Server:</strong> {mcpCall.serverLabel || "\u2014"}</div>
            <div><strong>Tool:</strong> {mcpCall.name || "\u2014"}</div>
            {mcpCall.arguments ? <div><strong>Arguments:</strong> <code>{mcpCall.arguments}</code></div> : null}
            <div><strong>Status:</strong> <span className={"mcp-status " + status}>{STATUS_TEXT[status] || status}</span></div>
            {mcpCall.durationMs != null ? (
              <div className="mcp-duration"><strong>Execution time:</strong> {formatMetricMs(mcpCall.durationMs)}</div>
            ) : null}
            {mcpCall.output ? <div><strong>Output:</strong> <code className="wrap">{mcpCall.output}</code></div> : null}
            {mcpCall.error ? <div><strong>Error:</strong> <code className="wrap err">{mcpCall.error}</code></div> : null}
          </div>
        </div>
      </div>
    );
  }

  // A client-executed `function` tool (design §6.1): Voice Live forwarded the call here and this
  // browser produced the output, so the card shows both sides of that exchange.
  if (type === "function_call" && functionCall) {
    const status = functionCall.status || "in_progress";
    const comparison = digitComparison(functionCall.output);
    return (
      <div className="msg function_call">
        <div className="bubble">
          <div className="meta"><span>Client function call</span></div>
          <div className="mcp-info">
            <div><strong>Executed by:</strong> this browser (client-side)</div>
            <div><strong>Function:</strong> {functionCall.name || "\u2014"}</div>
            {functionCall.arguments ? <div><strong>Arguments:</strong> <code className="wrap">{functionCall.arguments}</code></div> : null}
            <div><strong>Status:</strong> <span className={"mcp-status " + status}>{STATUS_TEXT[status] || status}</span></div>
            {functionCall.durationMs != null ? (
              <div className="mcp-duration"><strong>Execution time:</strong> {formatMetricMs(functionCall.durationMs)}</div>
            ) : null}
            <DigitComparison comparison={comparison} />
            {functionCall.output ? (
              <details className="fn-output">
                <summary>Output</summary>
                <code className="wrap">{functionCall.output}</code>
              </details>
            ) : null}
            {functionCall.error ? <div><strong>Error:</strong> <code className="wrap err">{functionCall.error}</code></div> : null}
          </div>
        </div>
      </div>
    );
  }

  if (type === "assistant") {
    return (
      <div className="msg assistant">
        <div className="assistant-message">
          <div className="bubble">
            <div className="meta"><span>{LABELS.assistant}</span></div>
            <div className="text">{content}</div>
          </div>
          {metrics ? (
            <TurnMetrics metrics={metrics} allMessages={allMessages} currentMessageId={message.id} />
          ) : null}
        </div>
      </div>
    );
  }

  if (type === "user") {
    return (
      <div className="msg user">
        <div className="user-message">
          <div className="bubble">
            <div className="meta"><span>{LABELS.user}</span></div>
            <div className="text">{content}</div>
          </div>
          {metrics ? <UserMetrics metrics={metrics} /> : null}
        </div>
      </div>
    );
  }

  const label = LABELS[type] ?? "";
  return (
    <div className={"msg " + type}>
      <div className="bubble">
        {label ? <div className="meta"><span>{label}</span></div> : null}
        <div className="text">{content}</div>
      </div>
    </div>
  );
}
