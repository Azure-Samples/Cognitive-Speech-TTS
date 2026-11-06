// Copyright (c) Microsoft. All rights reserved.

export const HANDOFF_EVENT_TYPES = new Set([
  "session.handoff.started",
  "session.handoff.completed",
  "session.handoff.aborted",
]);

// Distinct per-node voices make a handoff audibly obvious: each specialist answers in its own
// voice. Voice Live applies `handoff.nodes[*].config.voice` when the node activates; the top-level
// `audio.output.voice` stays the $entrypoint voice (the portal default is the DragonHD Ava voice).
// Shape matches buildVoiceConfig() ({ type: "openai" | "azure-standard", name }) — see
// serviceContract.js. Azure voices are valid for realtime AND cascaded, so this fixed cast works
// whichever model family / entrypoint voice is selected.
//   $entrypoint       -> en-US-Ava:DragonHDLatestNeural  (top-level audio.output.voice)
//   billing           -> en-US-EmmaNeural
//   technical_support -> en-US-AndrewNeural
export const HANDOFF_NODE_VOICES = {
  billing: "en-US-EmmaNeural",
  technical_support: "en-US-AndrewNeural",
};

// The reference scenario: customer service for an online phone store ("Contoso Mobile") that sells
// phones, tablets, accessories, and device protection plans. The $entrypoint is the front-line agent
// that greets, triages, and routes; the nodes are the two specialist desks.
export const STORE_NAME = "Contoso Mobile";

// Entrypoint instructions used INSTEAD of the plain assistant prompt when the handoff graph is on,
// so the front-line agent knows the business, stays in triage (it does not answer specialist
// questions itself), and always speaks a short handover line before the transfer.
export const HANDOFF_ENTRYPOINT_INSTRUCTIONS = [
  `You are the front-line customer service agent for ${STORE_NAME}, an online store that sells`,
  "smartphones, tablets, accessories, and device protection plans.",
  "Greet the customer warmly, ask what they need, and answer only general questions:",
  "store hours, delivery times, order status, and which product is right for them.",
  "You are a triage agent, not a specialist. For anything about invoices, charges, refunds,",
  "or payment methods, call handoff with target billing. For anything about a device that is",
  "broken, will not turn on, will not connect, or needs setup, call handoff with target",
  "technical_support. Before every handoff, tell the customer in one short sentence who you are",
  "transferring them to and why, so the change of voice is never a surprise. Never invent order",
  "numbers, prices, or refund amounts. Keep replies to one or two sentences — this is a phone call.",
].join(" ");

const voiceConfig = (voice) => ({ type: "azure-standard", name: voice });

export function buildCustomerCareHandoff({ supportsTransferMessage = false } = {}) {
  const transferMessage = (message) => (
    supportsTransferMessage ? { transfer_message: message } : {}
  );
  return {
    max_transfers: 6,
    max_attempts: 6,
    nodes: [
      {
        id: "billing",
        description: [
          `The ${STORE_NAME} billing desk. Owns anything about money:`,
          "invoices and receipts, duplicate or unrecognized charges, refunds and their status,",
          "cancellations and returns, promotions and discount codes, installment and trade-in plans,",
          "and updating or removing a saved payment method.",
        ].join(" "),
        config: {
          instructions: [
            `You are the billing specialist at ${STORE_NAME}, an online phone store.`,
            "You have just received a transferred call, so do not greet the customer as if the",
            "conversation is new — briefly confirm what you understand the billing issue to be and continue.",
            "Handle invoices, charges, refunds, returns, discount codes, installment plans, and saved",
            "payment methods. Ask for the order number when you need one, and explain refund timelines",
            "honestly (typically 3-5 business days back to the original payment method).",
            "Never invent amounts, order numbers, or refund decisions.",
            "If the real problem turns out to be a faulty or misbehaving device, say you are bringing in",
            "technical support and call handoff with target technical_support.",
            "Keep replies to one or two sentences.",
          ].join(" "),
          voice: voiceConfig(HANDOFF_NODE_VOICES.billing),
          tools: [],
          tool_choice: "auto",
        },
      },
      {
        id: "technical_support",
        description: [
          `The ${STORE_NAME} technical support desk. Owns anything about a device not working:`,
          "a phone that will not power on, charge, or hold battery, Wi-Fi / cellular / Bluetooth",
          "connectivity failures, software updates and crashes, SIM and eSIM activation,",
          "setup and data transfer to a new phone, and warranty or repair eligibility.",
        ].join(" "),
        config: {
          instructions: [
            `You are the technical support specialist at ${STORE_NAME}, an online phone store.`,
            "You have just received a transferred call, so do not greet the customer as if the",
            "conversation is new — briefly confirm the symptom you are troubleshooting and continue.",
            "Diagnose power, battery, charging, connectivity, software, eSIM activation, and new-device",
            "setup problems. Ask for the device model and what the customer has already tried, then give",
            "one concrete step at a time and wait for the result. Never invent warranty coverage.",
            "If the fix depends on money — a refund, a replacement charge, or an expired warranty the",
            "customer must pay for — say you are bringing in billing and call handoff with target billing.",
            "Keep replies to one or two sentences.",
          ].join(" "),
          voice: voiceConfig(HANDOFF_NODE_VOICES.technical_support),
          tools: [],
          tool_choice: "auto",
        },
      },
    ],
    edges: [
      {
        id: "entrypoint_to_billing",
        source: "$entrypoint",
        target: "billing",
        description: [
          "Use for invoices, receipts, duplicate or unrecognized charges, refunds and refund status,",
          "cancellations, returns, discount codes, installment or trade-in plans, and payment methods.",
        ].join(" "),
        ...transferMessage("Let me bring in our billing team — one moment, please."),
      },
      {
        id: "entrypoint_to_technical_support",
        source: "$entrypoint",
        target: "technical_support",
        description: [
          "Use when a device is faulty or unusable: will not power on, charge, or hold battery,",
          "Wi-Fi / cellular / Bluetooth problems, crashes after an update, SIM or eSIM activation,",
          "new-phone setup and data transfer, or a warranty and repair question.",
        ].join(" "),
        ...transferMessage("I'll hand you over to our technical support team — one moment, please."),
      },
      {
        id: "billing_to_technical_support",
        source: "billing",
        target: "technical_support",
        description: [
          "Use when a billing request is really a device fault — for example the customer wants a refund",
          "because the phone is defective, and the problem should be diagnosed before any refund.",
        ].join(" "),
        ...transferMessage("That sounds like a device issue — let me get technical support on the line."),
      },
      {
        id: "technical_support_to_billing",
        source: "technical_support",
        target: "billing",
        description: [
          "Use when troubleshooting turns into a money question — the device needs a paid replacement,",
          "the warranty has expired, or the customer now wants a refund or return.",
        ].join(" "),
        ...transferMessage("I'll pass you back to billing to sort out the charges — one moment."),
      },
    ],
  };
}

export function handoffMessage(event) {
  if (!event || !HANDOFF_EVENT_TYPES.has(event.type)) return null;
  const status = event.type.split(".").at(-1);
  return {
    id: `handoff-${event.handoff_id}`,
    type: "handoff",
    handoff: {
      status,
      handoffId: event.handoff_id,
      edgeId: event.edge_id,
      fromNodeId: event.from_node_id,
      toNodeId: event.to_node_id,
      reason: event.reason || null,
      durationMs: event.duration_ms,
      prepareDurationMs: event.prepare_duration_ms,
      error: event.error || null,
    },
  };
}

export function activeHandoffNode(session) {
  return session?.handoff?.active_node_id || null;
}

export function shouldStartSessionResources(sessionWasReady) {
  return !sessionWasReady;
}
