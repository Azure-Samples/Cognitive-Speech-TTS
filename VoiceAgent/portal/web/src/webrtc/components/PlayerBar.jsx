// Copyright (c) Microsoft. All rights reserved.
// Bottom scrubber for the mini portal, styled after the Foundry trace player. Plays the merged
// call recording (audio/content) and overlays one segment per turn (sized by the turn's persisted
// duration) so you can see/jump between turns. Falls back to a "load recording" prompt until the
// merged export is fetched (it's built only after the call ends).

import { useEffect, useMemo, useRef, useState } from "react";

function fmtClock(s) {
  if (!isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const ss = Math.floor(s % 60);
  return `${m}:${String(ss).padStart(2, "0")}`;
}

export function PlayerBar({ segments, wholeAudioUrl, onLoadRecording }) {
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [cur, setCur] = useState(0);
  const [dur, setDur] = useState(0);
  const [rate, setRate] = useState(1);

  // Give segments with no persisted duration an equal nominal weight so the bar still renders.
  const weighted = useMemo(() => {
    const anyReal = segments.some((s) => s.durationMs);
    return segments.map((s) => ({ ...s, w: anyReal ? (s.durationMs || 0) : 1 }));
  }, [segments]);
  const totalW = weighted.reduce((a, s) => a + s.w, 0) || 1;
  const startFrac = (i) => weighted.slice(0, i).reduce((a, s) => a + s.w, 0) / totalW;

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onTime = () => setCur(a.currentTime);
    const onMeta = () => setDur(a.duration || 0);
    const onEnd = () => setPlaying(false);
    a.addEventListener("timeupdate", onTime);
    a.addEventListener("loadedmetadata", onMeta);
    a.addEventListener("ended", onEnd);
    return () => {
      a.removeEventListener("timeupdate", onTime);
      a.removeEventListener("loadedmetadata", onMeta);
      a.removeEventListener("ended", onEnd);
    };
  }, [wholeAudioUrl]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, [rate]);

  const curFrac = dur ? cur / dur : 0;

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) { a.pause(); setPlaying(false); }
    else { a.play().then(() => setPlaying(true)).catch(() => {}); }
  };
  const seekFrac = (f) => {
    const a = audioRef.current;
    if (!a || !dur) return;
    a.currentTime = Math.max(0, Math.min(1, f)) * dur;
    setCur(a.currentTime);
  };
  const jump = (dir) => {
    const bounds = weighted.map((_, i) => startFrac(i));
    if (dir > 0) {
      const next = bounds.find((b) => b > curFrac + 0.001);
      seekFrac(next != null ? next : 1);
    } else {
      const prev = [...bounds].reverse().find((b) => b < curFrac - 0.02);
      seekFrac(prev != null ? prev : 0);
    }
  };
  const activeIdx = weighted.reduce((acc, _, i) => (curFrac >= startFrac(i) ? i : acc), 0);

  if (!wholeAudioUrl) {
    return (
      <div className="mp-player">
        <button className="mp-player-load" onClick={onLoadRecording}>▶ Load recording to scrub</button>
        <span className="mp-player-hint">Plays the merged call audio with per-turn segments</span>
      </div>
    );
  }

  return (
    <div className="mp-player">
      <div className="mp-player-controls">
        <button onClick={() => jump(-1)} title="Previous turn">⏮</button>
        <button className="mp-player-play" onClick={toggle} title={playing ? "Pause" : "Play"}>{playing ? "❚❚" : "▶"}</button>
        <button onClick={() => jump(1)} title="Next turn">⏭</button>
      </div>
      <div className="mp-player-count">{Math.min(activeIdx + 1, weighted.length)} / {weighted.length}</div>
      <div className="mp-player-time">{fmtClock(cur)}</div>
      <div
        className="mp-player-track"
        onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); seekFrac((e.clientX - r.left) / r.width); }}
      >
        {weighted.map((s, i) => (
          <span
            key={i}
            className={"mp-seg" + (i === activeIdx ? " active" : "")}
            style={{ width: `${(s.w / totalW) * 100}%` }}
            title={s.label}
          />
        ))}
        <span className="mp-player-head" style={{ left: `${curFrac * 100}%` }} />
      </div>
      <div className="mp-player-time">{fmtClock(dur)}</div>
      <button className="mp-player-rate" onClick={() => setRate((r) => (r === 1 ? 1.5 : r === 1.5 ? 2 : 1))}>{rate}x</button>
      <audio ref={audioRef} src={wholeAudioUrl} preload="metadata" />
    </div>
  );
}
