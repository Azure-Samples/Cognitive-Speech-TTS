// Copyright (c) Microsoft. All rights reserved.

// Insert a timeline item immediately before a known response bubble. If the response
// has not rendered yet (the common tool-first path), append the item; the response will
// be appended later when its first text/audio content arrives.
export function insertBeforeMessage(messages, message, beforeId) {
  if (messages.some((item) => item.id === message.id)) return messages;
  const next = [...messages];
  const beforeIndex = beforeId ? next.findIndex((item) => item.id === beforeId) : -1;
  if (beforeIndex >= 0) next.splice(beforeIndex, 0, message);
  else next.push(message);
  return next;
}

export function describeSessionClose(code, reason = "") {
  if (code === 1001 && reason === "Conversation ended by agent") {
    return { text: "conversation ended by agent", kind: "ok" };
  }
  if (code === 1001) {
    return { text: "session ended (idle/timeout)", kind: "" };
  }
  return { text: "disconnected", kind: "" };
}

export function shouldDrainSessionAudio(
  code,
  reason,
  clientCloseRequested = false,
) {
  return (
    !clientCloseRequested
    && code === 1001
    && reason === "Conversation ended by agent"
  );
}
