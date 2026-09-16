// Copyright (c) Microsoft. All rights reserved.
// Digit-accuracy demo.
//
// Creates the demo's A/B pair in one click. Both agents get the same intake prompt, model, voice,
// and greeting; the only difference is that the verified one also declares the
// `verify_spoken_digits` function tool and is told to call it before reading any number back.
// Voice Live forwards that call to the browser, which answers it from the Azure Speech transcript
// it has already received for the caller's last turn — so the model reads back the digits the
// recognizer heard rather than the digits it thought it heard.
//
// Creating a pair rather than a single agent is the point: without the control agent there is
// nothing to compare the corrected read-back against.

import { useState } from "react";
import { DIGIT_DEMO_VARIANTS, VERIFY_FUNCTION_NAME, digitDemoAgentSpec } from "../lib/digitDemo.mjs";
import { Icon } from "./ConfigControls.jsx";

// Control first, so the verified agent is the newest one and ends up selected for Connect.
const BUILD_ORDER = [DIGIT_DEMO_VARIANTS.CONTROL, DIGIT_DEMO_VARIANTS.VERIFIED];

export function DigitDemoConfig({
  disabled,
  model,
  voice,
  inferenceMode,
  store,
  clientReferenceEc,
  avatar,
  onCreateAgent,
}) {
  const [state, setState] = useState({ text: "", kind: "" });
  const [pair, setPair] = useState(null);

  const createPair = async () => {
    if (disabled || state.kind === "warn") return;
    setState({ text: "creating control + verified agents...", kind: "warn" });
    const created = {};
    try {
      for (const variant of BUILD_ORDER) {
        const spec = digitDemoAgentSpec(variant);
        const data = await onCreateAgent({
          namePrefix: spec.namePrefix,
          description: spec.description,
          instructions: spec.instructions,
          tools: spec.tools,
          greeting: spec.greeting,
          model,
          voice,
          inferenceMode,
          store,
          clientReferenceEc,
          avatar,
          subagents: [],
          handoff: null,
          handoffInstructions: null,
        });
        created[variant] = (data && data.name) || "";
      }
      setPair(created);
      setState({
        text: "created both — connect to each in turn and read the same number aloud",
        kind: "ok",
      });
    } catch (e) {
      setPair(Object.keys(created).length ? created : null);
      setState({ text: `create failed: ${e.message || e}`, kind: "err" });
    }
  };

  return (
    <div className="demo-scenario">
      <span className="subtle-badge"><Icon name="code" />Client-side function</span>
      <h3>Digit accuracy</h3>
      <p>Compare a model’s digit recognition with a tool that verifies numbers against the Azure Speech transcript.</p>
      <div className="demo-variants">
        <div><span>A</span><strong>Control</strong><p>Reads back the digits the model heard.</p></div>
        <div><span>B</span><strong>Verified</strong><p>Calls <code>{VERIFY_FUNCTION_NAME}</code> before repeating a number.</p></div>
      </div>
      <p className="field-hint">Both agents use the same intake prompt, model, voice, and greeting. Only the verification tool differs.</p>
      <div className="demo-defaults"><span title={model}>{model}</span><span title={voice}>{voice}</span></div>
      <button type="button" className="full" disabled={disabled || state.kind === "warn"} onClick={createPair}>
        {state.kind === "warn" ? "Creating pair…" : "Create A/B pair (verified + control)"}<Icon name="arrow" />
      </button>
      {state.text ? <div className={`form-feedback ${state.kind}`} role="status">{state.text}</div> : null}
      {pair ? (
        <dl className="agent-facts">
          <div><dt>Verified</dt><dd>{pair[DIGIT_DEMO_VARIANTS.VERIFIED] || "\u2014"}</dd></div>
          <div><dt>Control</dt><dd>{pair[DIGIT_DEMO_VARIANTS.CONTROL] || "\u2014"}</dd></div>
        </dl>
      ) : null}
      <details className="advanced-details" open>
        <summary>How to try it</summary>
        <ol className="demo-steps">
          <li>Choose each agent in the playground and connect.</li>
          <li>Use a fictitious name, a sample 10-digit phone number, and a made-up 8-digit customer ID. Do not use real customer data.</li>
          <li>Compare the read-back and the amber <b>Client function call</b> card.</li>
        </ol>
        <p className="field-hint">Uses the model, voice, echo cancellation, avatar, and storage settings in your current configuration.</p>
      </details>
    </div>
  );
}
