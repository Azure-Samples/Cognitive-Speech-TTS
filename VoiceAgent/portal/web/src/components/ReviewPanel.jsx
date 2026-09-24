import { useEffect, useState } from "react";

import { renderDefinition, summaryChips } from "../lib/agentReview.mjs";

/* The review stage: what the service wrote, before you talk to it.
 *
 * Only the generate path has one. Configuring an agent by hand decides every
 * field yourself, so there is nothing to read back; generating hands those
 * decisions to the service, which returns two thousand words of instructions, a
 * voice it picked, and a turn-detection strategy it chose. Connecting straight
 * to that would be talking to something you have not seen.
 *
 * Tabs rather than a single scroll because the chat has to live here too once
 * you connect, and mid-conversation the useful question is often "does that
 * answer match the Tone section it was given" -- which wants one click, not a
 * scroll back through the transcript.
 */

const TAB_DEFINITION = "definition";
const TAB_CHAT = "chat";
const TAB_WORKFLOW = "workflow";

/* The definition as YAML-ish text. Not a JSON dump: instructions are prose with
 * newlines in them, and JSON.stringify turns those into \n escapes that nobody
 * can read.
 *
 * `identity` comes from outside the definition -- name, version and draft live
 * on the agent resource, not on the definition it holds -- but they belong at
 * the top of what a reader sees. The Connection dropdown below lists agents by
 * name, and without the name here there is nothing tying what you just read to
 * what you are about to select. */
export function ReviewPanel({ definition, identity, elapsedMs, workflow, children }) {
  const [tab, setTab] = useState(TAB_CHAT);

  /* The panel mounts before anything has been generated, so the initial tab
   * cannot depend on a definition that does not exist yet. Switch when one
   * arrives: a fresh definition is the thing the caller just asked for, and
   * leaving them on the session they have not started would hide it. */
  useEffect(() => {
    if (definition) setTab(TAB_DEFINITION);
  }, [definition]);

  useEffect(() => {
    if ((!definition && tab === TAB_DEFINITION) || (!workflow && tab === TAB_WORKFLOW)) {
      setTab(TAB_CHAT);
    }
  }, [definition, workflow, tab]);

  const chips = definition ? summaryChips(definition) : [];
  const body = definition ? renderDefinition(definition, identity) : "";
  const reviewing = Boolean(definition) && tab === TAB_DEFINITION;
  const showingWorkflow = Boolean(workflow) && tab === TAB_WORKFLOW;
  const hasTabs = Boolean(definition || workflow);

  /* `children` stays mounted whatever tab is showing, and is hidden with CSS
   * rather than unrendered.
   *
   * It is the chat, and the chat owns the elements that actually play the
   * agent: the <audio> sink fed by the WebRTC stream, and the avatar <video>.
   * On the WebRTC transport nothing else plays audio, so unmounting the chat to
   * show the definition would connect a session you cannot hear. Reviewing then
   * connecting is the normal path through this page, which would have made that
   * the default experience rather than an edge case.
   *
   * Keeping one root element also means React reconciles the chat subtree
   * instead of tearing it down when the first definition arrives, so a
   * half-typed message survives. */
  return (
    <div className="review-panel">
      {hasTabs ? (
        <>
          <div className="review-tabs" role="tablist" aria-label="Agent playground views">
            {definition ? <button
              type="button"
              role="tab"
              id="review-tab-definition"
              aria-controls="review-panel-definition"
              aria-selected={tab === TAB_DEFINITION}
              className={"review-tab" + (tab === TAB_DEFINITION ? " active" : "")}
              onClick={() => setTab(TAB_DEFINITION)}
            >
              Definition
            </button> : null}
            <button
              type="button"
              role="tab"
              id="review-tab-session"
              aria-controls="review-panel-session"
              aria-selected={tab === TAB_CHAT}
              className={"review-tab" + (tab === TAB_CHAT ? " active" : "")}
              onClick={() => setTab(TAB_CHAT)}
            >
              Session
            </button>
            {workflow ? (
              <button
                type="button"
                role="tab"
                id="review-tab-workflow"
                aria-controls="review-panel-workflow"
                aria-selected={tab === TAB_WORKFLOW}
                className={"review-tab" + (tab === TAB_WORKFLOW ? " active" : "")}
                onClick={() => setTab(TAB_WORKFLOW)}
              >
                Workflow
              </button>
            ) : null}
          </div>
          {definition && elapsedMs ? (
            <div className="review-meta">generated in {(elapsedMs / 1000).toFixed(1)}s</div>
          ) : null}
        </>
      ) : null}

      {reviewing ? (
        <div
          className="review-body"
          id="review-panel-definition"
          role="tabpanel"
          aria-labelledby="review-tab-definition"
        >
          {chips.length ? (
            <div className="review-chips">
              {chips.map(([label, value]) => (
                <span className="review-chip" key={label}>
                  <span className="review-chip-label">{label}</span>
                  <span className="review-chip-value">{value}</span>
                </span>
              ))}
            </div>
          ) : null}
          <pre className="review-definition">{body}</pre>
        </div>
      ) : null}

      {workflow ? (
        <div className={"review-workflow" + (showingWorkflow ? "" : " hidden")}
          id="review-panel-workflow" role="tabpanel" aria-labelledby="review-tab-workflow">
          {workflow}
        </div>
      ) : null}

      <div
        className={"review-session" + (reviewing || showingWorkflow ? " hidden" : "")}
        id="review-panel-session"
        role={hasTabs ? "tabpanel" : undefined}
        aria-labelledby={hasTabs ? "review-tab-session" : undefined}
      >
        {children}
      </div>
    </div>
  );
}
