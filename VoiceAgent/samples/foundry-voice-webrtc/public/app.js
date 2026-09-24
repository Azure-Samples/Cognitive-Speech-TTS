import { PcmAudio, validateAudioSession } from './pcm-audio.mjs';

const $ = (id) => document.getElementById(id);
let config, call = null;
const messages = new Map();

function showError(message) { $('error').textContent = message; $('error').hidden = false; }
function state(title, hint, badge) {
  $('status').textContent = title; $('hint').textContent = hint; $('connection').textContent = badge;
}
function transcript(id, role, text, append = false) {
  if (!id || !text) return;
  $('empty')?.remove();
  let entry = messages.get(id);
  if (!entry) {
    const box = document.createElement('div'); box.className = `message ${role}`;
    const label = document.createElement('label'); label.textContent = role === 'user' ? 'You' : 'Agent';
    entry = document.createElement('p'); box.append(label, entry); $('transcript').append(box);
    messages.set(id, entry);
  }
  entry.textContent = append ? entry.textContent + text : text;
  $('transcript').scrollTop = $('transcript').scrollHeight;
}
function stop(title = 'Conversation ended', hint = 'Start again whenever you’re ready.') {
  const old = call; call = null;
  if (old) {
    clearTimeout(old.timeout); clearTimeout(old.disconnectTimer); clearInterval(old.clock);
    old.abort.abort(); old.ws?.close(); old.peer?.close(); old.audio?.dispose();
    old.mic?.getTracks().forEach(t => t.stop()); old.remote?.getTracks().forEach(t => t.stop());
  }
  $('remote-audio').pause(); $('remote-audio').srcObject = null;
  $('orb').className = 'orb'; $('play').hidden = true;
  $('start').disabled = !config?.configured; $('stop').disabled = true; $('mute').disabled = true;
  $('transport').disabled = false;
  $('mute').textContent = 'Mute mic'; $('mute').setAttribute('aria-pressed', 'false');
  state(title, hint, 'Offline');
}
function fail(session, error) {
  if (call !== session) return;
  stop('Couldn’t connect', 'Review the message below, then try again.');
  showError(error.message || String(error));
}
async function playAudio() {
  try {
    if (call?.audio) await call.audio.context.resume();
    else await $('remote-audio').play();
    $('play').hidden = true;
  }
  catch { if (call) $('play').hidden = false; }
}
function markReady(session) {
  if (call !== session) return;
  session.ready = true;
  clearTimeout(session.timeout); clearTimeout(session.disconnectTimer);
  $('mute').disabled = false; $('orb').className = 'orb active';
  state('Listening', 'Say hello. Your agent will respond when you pause.', 'Connected');
  if (!session.clock) {
    const began = Date.now();
    session.clock = setInterval(() => {
      const seconds = Math.floor((Date.now() - began) / 1000);
      $('elapsed').textContent = `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
    }, 1000);
  }
}
function openSocket(session, onOpen) {
  const ws = session.ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/voice?transport=${session.transport}`);
  ws.onopen = () => { if (call === session) onOpen?.(ws); };
  let queue = Promise.resolve();
  ws.onmessage = e => { queue = queue.then(() => handleEvent(session, JSON.parse(e.data))).catch(error => fail(session,error)); };
  ws.onerror = () => fail(session,new Error('Local WebSocket connection failed. Check that the sample server is running.'));
  ws.onclose = () => { if (call === session) stop('Session closed', 'The service ended the session. You can start a new one.'); };
}
function waitForIce(peer, signal) {
  if (peer.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve, reject) => {
    const finish = (error) => {
      clearTimeout(timer); peer.removeEventListener('icegatheringstatechange', changed);
      signal.removeEventListener('abort', aborted); error ? reject(error) : resolve();
    };
    const changed = () => { if (peer.iceGatheringState === 'complete') finish(); };
    const aborted = () => finish(new Error('Session cancelled.'));
    const timer = setTimeout(() => finish(new Error('ICE gathering timed out. Check your STUN/TURN configuration.')), 12000);
    peer.addEventListener('icegatheringstatechange', changed); signal.addEventListener('abort', aborted);
    if (signal.aborted) aborted();
  });
}
async function handleEvent(session, event) {
  if (call !== session) return;
  const type = event.type || '';
  if (type === 'session.updated' && session.transport === 'websocket') {
    validateAudioSession(event.session);
    markReady(session);
  } else if (type === 'response.created') {
    session.responseId = event.response?.id;
  } else if (type === 'rtc.call.sdp.created') {
    if (!event.sdp_answer) throw new Error('Azure returned no SDP answer.');
    await session.peer.setRemoteDescription({type:'answer', sdp:event.sdp_answer});
  } else if (['bridge.error','rtc.call.error','error'].includes(type)) {
    throw new Error(event.error?.message || 'Azure could not start this voice session.');
  } else if (type === 'input_audio_buffer.speech_started') {
    session.userSpeaking = true;
    session.interruptedResponse = session.responseId;
    session.audio?.interrupt();
    $('orb').className = 'orb active'; $('status').textContent = 'Listening to you';
  } else if (type === 'input_audio_buffer.speech_stopped') {
    session.userSpeaking = false;
  } else if (['response.audio.delta', 'response.output_audio.delta'].includes(type) && session.audio) {
    const responseId = event.response_id || session.responseId;
    if (event.delta && !session.userSpeaking && (!session.interruptedResponse || responseId !== session.interruptedResponse)) {
      session.audio.play(event.delta);
      if (session.audio.context.state === 'suspended') $('play').hidden = false;
    }
  } else if (type === 'output_audio_buffer.started') {
    $('orb').className = 'orb speaking'; $('status').textContent = 'Your agent is speaking';
  } else if (type === 'output_audio_buffer.stopped' || type === 'output_audio_buffer.cleared') {
    $('orb').className = 'orb active'; $('status').textContent = 'Listening';
  } else if (type === 'conversation.item.input_audio_transcription.completed') {
    transcript(event.item_id, 'user', event.transcript);
  } else if (type === 'conversation.item.input_audio_transcription.failed') {
    showError('Speech transcription failed for this turn. Check the transcription setting in Foundry.');
  } else if (/^response\.(output_audio_transcript|audio_transcript|output_text|text)\.(delta|done)$/.test(type)) {
    transcript(event.item_id || event.response_id, 'assistant', event.delta || event.transcript || event.text, type.endsWith('.delta'));
  }
}
async function start() {
  if (call || !config?.configured) return;
  const session = {abort:new AbortController(), muted:false, transport:$('transport').value, ready:false}; call = session;
  $('error').hidden = true; $('start').disabled = true; $('stop').disabled = false;
  $('transport').disabled = true; $('elapsed').textContent = '00:00';
  state('Let’s connect', 'Allow microphone access when your browser asks.', 'Connecting');
  session.timeout = setTimeout(() => fail(session, new Error('Connection timed out. Check microphone permission, outbound HTTPS access and your selected transport.')), 60000);
  try {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
      throw new Error('Use a microphone-capable browser on localhost or HTTPS.');
    if (session.transport === 'websocket') {
      session.audio = new PcmAudio(playing => {
        if (call !== session) return;
        $('orb').className = playing ? 'orb speaking' : 'orb active';
        $('status').textContent = playing ? 'Your agent is speaking' : 'Listening';
      });
      await session.audio.resumePromise;
      if (call !== session) return;
    } else if (!window.RTCPeerConnection) throw new Error('This browser does not support WebRTC. Choose WebSocket.');
    const mic = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
    if (call !== session) { mic.getTracks().forEach(t => t.stop()); return; }
    session.mic = mic;
    mic.getTracks().forEach(t => { t.onended = () => fail(session, new Error('Microphone disconnected.')); });
    if (session.transport === 'websocket') {
      await session.audio.prepare(mic, audio => {
        if (call !== session || !session.ready || session.ws?.readyState !== WebSocket.OPEN) return;
        if (session.ws.bufferedAmount > 256 * 1024) {
          fail(session, new Error('Audio upload cannot keep up. Check the network and start a new session.'));
          return;
        }
        session.ws.send(JSON.stringify({type:'input_audio_buffer.append', audio}));
      });
      if (call !== session) return;
      state('Connecting to Azure', 'Opening an audio WebSocket. No STUN or TURN needed.', 'Connecting');
      openSocket(session);
      return;
    }
    session.remote = new MediaStream();
    const peer = session.peer = new RTCPeerConnection({iceServers:config.iceServers});
    mic.getTracks().forEach(t => peer.addTrack(t, mic));
    peer.ontrack = e => { if (call === session) { session.remote.addTrack(e.track); $('remote-audio').srcObject = session.remote; playAudio(); } };
    peer.onconnectionstatechange = () => {
      if (call !== session) return;
      if (peer.connectionState === 'connected') {
        markReady(session);
      } else if (peer.connectionState === 'failed') fail(session, new Error('WebRTC media failed. Check firewall rules or configure TURN.'));
      else if (peer.connectionState === 'disconnected') {
        state('Reconnecting', 'The media connection was interrupted.', 'Reconnecting');
        clearTimeout(session.disconnectTimer);
        session.disconnectTimer = setTimeout(() => fail(session, new Error('Media connection lost. Start a new session.')),10000);
      }
    };
    // Required in the offer. Events use the signaling socket to avoid duplicate transcripts.
    session.channel = peer.createDataChannel('voice-live-events');
    await peer.setLocalDescription(await peer.createOffer());
    await waitForIce(peer, session.abort.signal);
    if (call !== session) return;
    openSocket(session, ws => ws.send(JSON.stringify({type:'rtc.call.sdp.create',sdp_offer:peer.localDescription.sdp})));
  } catch (error) {
    if (error.name === 'NotAllowedError') error = new Error('Microphone access was denied. Allow it in your browser’s site permissions and try again.');
    fail(session,error);
  }
}
$('start').onclick = start;
$('stop').onclick = () => stop();
$('play').onclick = playAudio;
$('mute').onclick = () => {
  if (!call?.mic) return;
  call.muted = !call.muted; call.mic.getAudioTracks().forEach(t => { t.enabled = !call.muted; });
  call.audio?.mute(call.muted);
  $('mute').textContent = call.muted ? 'Unmute mic' : 'Mute mic';
  $('mute').setAttribute('aria-pressed', String(call.muted));
  $('hint').textContent = call.muted ? 'Your microphone is muted. You can still hear the agent.' : 'Say hello. Your agent will respond when you pause.';
};
$('clear').onclick = () => { messages.clear(); $('transcript').replaceChildren(); };
window.addEventListener('pagehide', () => stop());
$('transport').onchange = () => {
  $('media').textContent = $('transport').value === 'websocket' ? 'WebSocket · PCM16 / 24 kHz' : 'WebRTC · Opus';
};
try {
  const response = await fetch('/api/config'); if (!response.ok) throw new Error('Could not load server configuration.');
  config = await response.json(); $('agent').textContent = config.agent || 'Not configured';
  $('transport').value = config.defaultTransport || 'websocket'; $('transport').onchange();
  $('start').disabled = !config.configured;
  if (!config.configured) {
    $('setup').open = true;
    state('One small setup first', 'Set your project and agent in .env, then sign in with az login.', 'Setup needed');
    showError((config.setupIssues || ['Complete the server .env settings.']).join(' '));
  } else if (!config.azureCliInstalled) {
    $('setup').open = true;
    showError('Install Azure CLI, then run az login in a normal PowerShell window. No API key or client secret is needed.');
  }
} catch (error) { showError(error.message); }
