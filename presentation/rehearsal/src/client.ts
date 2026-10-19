import { judgeReadiness, judgingPolicy, labels, pairedTheory, qualityDimensions, qualityKeys, rubrics, wordCount } from "./concepts.ts";
import type { Decision, JudgeTrigger, ServiceStatus, SlideRubric } from "./concepts.ts";
import { combineWavs, encodeWav } from "./audio.ts";

type Mode = "idle" | "running" | "paused" | "finishing" | "finished";
interface Utterance { text: string; capturedAt: number }
interface SlideState {
  elapsed: number;
  visited: boolean;
  utterances: Utterance[];
  audio: Blob[];
  decisions: Decision[];
  revision: number;
  judgedRevision: number;
  attemptedRevision: number;
  attemptedWords: number;
  assessedTranscript: string;
  checks: number;
  judgedAt?: number;
  latencyMs?: number;
  lastRequest?: unknown;
  lastResponse?: unknown;
  judgeError?: string;
  transcriptionError?: string;
  demoCompleted: boolean;
}
interface AudioChunk { slideId: string; wav: Blob; capturedAt: number; seq: number }

function element<T extends HTMLElement = HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing rehearsal element: ${id}`);
  return node as T;
}

const slideElements = Array.from(document.querySelectorAll<HTMLElement>(".slide"));
const slides = new Map(rubrics.map(rubric => [
  rubric.id, slideElements.find(slide => slide.dataset.rehearsalId === rubric.id),
]));
if (slideElements.filter(slide => slide.dataset.rehearsalId).length !== rubrics.length || [...slides.values()].some(slide =>
  !slide || !Number.isFinite(Number(slide.dataset.minutes)) || Number(slide.dataset.minutes) <= 0)) {
  throw new Error("Deck slides, time budgets and rehearsal rubrics are out of sync.");
}
function emptyState(): SlideState {
  return {
    elapsed: 0, visited: false, utterances: [], audio: [], decisions: [],
    revision: 0, judgedRevision: -1, attemptedRevision: -1, attemptedWords: 0,
    assessedTranscript: "", checks: 0, demoCompleted: false,
  };
}
const states = new Map<string, SlideState>(rubrics.map(slide => [slide.id, emptyState()]));
let activeId = slideElements.find(slide => slide.classList.contains("active"))?.dataset.rehearsalId ?? rubrics[0].id;
let mode: Mode = "idle";
let service: ServiceStatus | undefined;
let since = 0;
let startedAt: string | undefined;
let actionBusy = false;
let audioContext: AudioContext | undefined;
let stream: MediaStream | undefined;
let worklet: AudioWorkletNode | undefined;
let boundaryNumber = 0;
let speechLevel = 0;
let lastSpeechAt = 0;
let preview: { slideId: string; seq: number; text: string } | undefined;
let previewTask: Promise<void> | undefined;
let lastPeekAt = 0;
let transcribedSeq = -1;
let lastJudgeAt = 0;
let judgedCalls = 0;
let errorText = "";
let reviewId: string | undefined;
let recordingUrl: string | undefined;
const boundaries = new Map<number, () => void>();
const audioQueue: AudioChunk[] = [];
const failedAudio: AudioChunk[] = [];
const judgeQueue = new Map<string, JudgeTrigger>();
let transcriptionTask: Promise<void> | undefined;
let judgeTask: Promise<void> | undefined;
let judging: { slideId: string; words: number; since: number } | undefined;

const sheet = document.createElement("link");
sheet.rel = "stylesheet";
sheet.href = "/rehearsal/style.css";
document.head.appendChild(sheet);
const panel = document.createElement("aside");
panel.id = "rehearsalPanel";
panel.hidden = true;
panel.setAttribute("aria-label", "Rehearsal coach");
panel.innerHTML = `
  <header class="rh-header">
    <h2>Rehearsal</h2>
    <button class="control-button" id="rhClose" aria-label="Close rehearsal panel">Close</button>
  </header>
  <div class="rh-scroll">
    <section id="rhSetup">
      <p class="rh-muted">Local Whisper listens. Decision-1 checks spoken concept coverage against the playbook.</p>
      <div id="rhChecks" class="rh-checks" aria-live="polite">Checking local setup...</div>
      <button class="control-button" id="rhCheck">Check setup</button>
      <label class="rh-option"><input type="checkbox" id="rhConsent"> Send this rehearsal's slide transcripts to the configured Foundry endpoint for AI feedback (billable).</label>
      <label class="rh-option"><input type="checkbox" id="rhKeepAudio" checked> Keep audio in this tab for local playback and download.</label>
      <p class="rh-small">Audio never goes to Foundry. Closing or refreshing this tab discards the session unless you download it. Switching tabs for a demo does not pause the clock.</p>
    </section>
    <div class="rh-live" id="rhLive" hidden>
      <div class="rh-clock-row"><div><span class="rh-eyebrow">TIME LEFT</span><div id="rhClock" class="rh-clock">00:00</div></div><span class="rh-badge" id="rhMode">Ready</span></div>
      <div class="rh-time-track" aria-hidden="true"><div id="rhTimeBar"></div></div>
      <div class="rh-time-stats"><span>Talk left <strong id="rhTalkLeft">00:00</strong></span><span>Overspill <strong id="rhOverspill">On time</strong></span></div>
      <div class="rh-line" id="rhHeard"><span class="rh-dot" id="rhHeardDot"></span><span id="rhHeardText">Waiting for speech</span></div>
      <div class="rh-line" id="rhJudgeLine" aria-live="polite"><span class="rh-dot" id="rhJudgeDot"></span><span id="rhJudgeText"></span><span class="rh-next" id="rhJudgeNext" hidden></span></div>
    </div>
    <div class="rh-actions" id="rhSessionControls">
      <button class="control-button rh-primary" id="rhStart" disabled>Start rehearsal</button>
      <button class="control-button" id="rhPause" hidden>Pause</button>
      <button class="control-button" id="rhStop" hidden>Finish</button>
      <span id="rhStatus" role="status" aria-live="polite"></span>
    </div>
    <div id="rhError" class="rh-error" role="alert" hidden></div>
    <section id="rhCurrent">
      <div class="rh-slide-heading"><h3 id="rhTitle"></h3><button class="control-button" id="rhCopy" hidden>Copy for LLM</button></div>
      <div id="rhConcepts" class="rh-concepts"></div>
      <details id="rhDetails" class="rh-transcript" hidden>
        <summary>Review details</summary>
        <p class="rh-small" id="rhPhase"></p>
        <p class="rh-small" id="rhPair"></p>
        <div class="rh-listening"><span id="rhMic">Microphone off</span><meter id="rhLevel" min="0" max="0.08" value="0" aria-label="Microphone level"></meter></div>
        <p class="rh-small" id="rhPipeline"></p>
        <div class="rh-cue" id="rhCue"></div>
        <label class="rh-option" id="rhDemoOption" hidden><input type="checkbox" id="rhDemo"> I completed the on-screen demo (self-reported, not AI-verified).</label>
        <p class="rh-small" id="rhJudged"></p>
        <p class="rh-small" id="rhGate"></p>
        <div id="rhAssessmentDetails" class="rh-small"></div>
        <div class="rh-actions">
          <button class="control-button" id="rhJudge" disabled>Recheck concepts</button>
          <button class="control-button" id="rhRetry" hidden>Retry failed audio</button>
        </div>
        <details class="rh-transcript"><summary>Transcript for this slide <span id="rhWords"></span></summary><div id="rhTranscript" class="rh-transcript-text">No speech captured yet.</div></details>
        <details class="rh-transcript"><summary>Last assessed transcript</summary><div id="rhAssessed" class="rh-transcript-text">No assessment yet.</div></details>
        <div id="rhPlayback" hidden><audio id="rhAudio" controls preload="none" aria-label="Recorded slide audio"></audio><button class="control-button" id="rhDownloadAudio">Download slide audio</button></div>
      </details>
    </section>
    <section id="rhReview" hidden>
      <div class="rh-slide-heading"><span class="rh-eyebrow">REHEARSAL REVIEW</span><h3>What needs another pass?</h3></div>
      <p class="rh-small" id="rhReviewSummary"></p>
      <div id="rhReviewRows"></div>
      <div class="rh-actions"><button class="control-button" id="rhExport">Download session</button><button class="control-button" id="rhBack">Current slide</button><button class="control-button" id="rhNew">New rehearsal</button></div>
    </section>
  </div>
`;
document.body.appendChild(panel);

const resizer = document.createElement("div");
resizer.id = "rhResize";
resizer.tabIndex = 0;
resizer.setAttribute("role", "separator");
resizer.setAttribute("aria-orientation", "vertical");
resizer.setAttribute("aria-label", "Resize rehearsal panel");
resizer.title = "Drag to resize · double-click to reset";
panel.prepend(resizer);
const defaultWidth = 384;
function setPanelWidth(width: number, save = true) {
  const max = Math.max(320, Math.round(window.innerWidth * 0.7));
  const value = Math.round(Math.min(max, Math.max(320, width)));
  document.documentElement.style.setProperty("--rh-width", `${value}px`);
  resizer.setAttribute("aria-valuemin", "320");
  resizer.setAttribute("aria-valuemax", String(max));
  resizer.setAttribute("aria-valuenow", String(value));
  if (save) localStorage.setItem("rehearsalPanelWidth", String(value));
  window.dispatchEvent(new Event("resize"));
}
setPanelWidth(Number(localStorage.getItem("rehearsalPanelWidth")) || defaultWidth, false);
resizer.addEventListener("pointerdown", event => {
  resizer.setPointerCapture(event.pointerId);
  resizer.classList.add("rh-dragging");
  document.documentElement.classList.add("rh-resizing");
});
resizer.addEventListener("pointermove", event => {
  if (resizer.hasPointerCapture(event.pointerId)) setPanelWidth(window.innerWidth - event.clientX);
});
resizer.addEventListener("lostpointercapture", () => {
  resizer.classList.remove("rh-dragging");
  document.documentElement.classList.remove("rh-resizing");
});
resizer.addEventListener("dblclick", () => setPanelWidth(defaultWidth));
resizer.addEventListener("keydown", event => {
  const step = event.shiftKey ? 64 : 16;
  const current = Number(resizer.getAttribute("aria-valuenow"));
  if (event.key === "ArrowLeft") setPanelWidth(current + step);
  else if (event.key === "ArrowRight") setPanelWidth(current - step);
  else if (event.key === "Home") setPanelWidth(defaultWidth);
  else return;
  event.preventDefault();
  event.stopPropagation();
});
window.addEventListener("resize", event => {
  if (event.isTrusted) setPanelWidth(Number(resizer.getAttribute("aria-valuenow")), false);
});

const startButton = element<HTMLButtonElement>("rhStart");
const pauseButton = element<HTMLButtonElement>("rhPause");
const stopButton = element<HTMLButtonElement>("rhStop");
const consent = element<HTMLInputElement>("rhConsent");
const keepAudio = element<HTMLInputElement>("rhKeepAudio");
const demo = element<HTMLInputElement>("rhDemo");

function state(id = activeId) {
  const result = states.get(id);
  if (!result) throw new Error(`Unknown slide ${id}.`);
  return result;
}

function rubric(id = activeId) {
  const result = rubrics.find(slide => slide.id === id);
  if (!result) throw new Error(`Unknown slide rubric ${id}.`);
  return result;
}

function elapsed(id: string, now = performance.now()) {
  return state(id).elapsed + (mode === "running" && id === activeId ? now - since : 0);
}

function budget(id: string) {
  return Number(slides.get(id)!.dataset.minutes) * 60_000;
}

function clock(milliseconds: number) {
  const seconds = Math.floor(Math.abs(milliseconds) / 1000);
  return `${milliseconds < 0 ? "+" : ""}${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function transcript(id: string) {
  return state(id).utterances.map(utterance => utterance.text).join(" ");
}

function explained(decision: Decision) {
  return decision.coverage === "explained" && decision.confidence >= 0.65;
}

function setError(error: unknown) {
  errorText = error instanceof Error ? error.message : String(error);
  render();
}

async function action(operation: () => Promise<void>) {
  if (actionBusy) return;
  actionBusy = true;
  errorText = "";
  render();
  try {
    await operation();
  } catch (error) {
    setError(error);
  } finally {
    actionBusy = false;
    render();
  }
}

async function api<T>(path: string, data?: Blob | object): Promise<T> {
  const response = await fetch(path, data ? {
    method: "POST",
    headers: {
      "Content-Type": data instanceof Blob ? "audio/wav" : "application/json",
      "X-Rehearsal-CSRF": service?.csrf ?? "",
    },
    body: data instanceof Blob ? data : JSON.stringify(data),
    signal: AbortSignal.timeout(path.endsWith("transcribe") ? 75_000 : 40_000),
  } : { signal: AbortSignal.timeout(45_000) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? `Local service returned HTTP ${response.status}.`);
  return result as T;
}

async function checkSetup() {
  startButton.disabled = true;
  element("rhChecks").textContent = "Checking local setup...";
  try {
    service = await api<ServiceStatus>("/api/status");
    const container = element("rhChecks");
    container.replaceChildren(...service.checks.map(check => {
      const row = document.createElement("div");
      row.className = check.ok ? "rh-check rh-ok" : "rh-check rh-problem";
      const title = document.createElement("strong");
      title.textContent = `${check.ok ? "Ready" : "Fix"}: ${check.name}`;
      const detail = document.createElement("span");
      detail.textContent = check.detail;
      row.append(title, detail);
      return row;
    }));
  } catch {
    service = undefined;
    element("rhChecks").textContent = "Local companion unavailable. Run npm start in presentation/rehearsal, then open its localhost URL.";
  }
  render();
}

function captureBoundary(slideId: string, active: boolean) {
  if (!worklet) return Promise.resolve();
  const id = ++boundaryNumber;
  return new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      boundaries.delete(id);
      reject(new Error("Microphone did not flush its final audio. The last segment may be incomplete."));
    }, 3000);
    boundaries.set(id, () => { clearTimeout(timeout); resolve(); });
    worklet!.port.postMessage({ type: "boundary", id, slideId, active });
  });
}

async function openMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    throw new Error("Use a current Chrome or Edge browser on localhost for local microphone capture.");
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    audioContext = new AudioContext({ sampleRate: 16_000 });
    await audioContext.resume();
    if (audioContext.sampleRate !== 16_000 || audioContext.state !== "running") {
      throw new Error("This browser could not start 16 kHz audio. Try Chrome or Edge.");
    }
    await audioContext.audioWorklet.addModule("/rehearsal/worklet.js");
    worklet = new AudioWorkletNode(audioContext, "rehearsal-capture");
    transcribedSeq = -1;
    preview = undefined;
    worklet.port.onmessage = event => {
      const message = event.data;
      if (message.type === "boundary") {
        boundaries.get(message.id)?.();
        boundaries.delete(message.id);
      } else if (message.type === "audio") {
        receiveAudio(message);
      } else if (message.type === "partial") {
        receivePartial(message);
      } else if (message.type === "level") {
        speechLevel = message.rms;
      }
    };
    const mute = audioContext.createGain();
    mute.gain.value = 0;
    audioContext.createMediaStreamSource(stream).connect(worklet).connect(mute).connect(audioContext.destination);
    stream.getAudioTracks()[0].addEventListener("ended", () => {
      if (mode === "running") void action(async () => {
        await pause();
        throw new Error("Microphone disconnected. Reconnect it, then Resume.");
      });
    });
    audioContext.onstatechange = () => {
      if (audioContext?.state === "suspended" && mode === "running") void action(async () => {
        await pause();
        throw new Error("Browser suspended audio capture. Rehearsal paused; Resume to reconnect.");
      });
    };
    await captureBoundary(activeId, true);
  } catch (error) {
    await closeMicrophone();
    if (error instanceof DOMException && error.name === "NotAllowedError") {
      throw new Error("Microphone permission denied. Allow the microphone for this localhost page, then retry.");
    }
    throw error;
  }
}

async function closeMicrophone() {
  stream?.getTracks().forEach(track => track.stop());
  stream = undefined;
  worklet?.disconnect();
  worklet = undefined;
  const context = audioContext;
  audioContext = undefined;
  if (context && context.state !== "closed") await context.close();
  speechLevel = 0;
}

// Provisional words for the ticker only; final clips replace them and are what gets judged.
function receivePartial(message: { slideId: string; seq: number; samples: Float32Array; sampleRate: number; peak: number }) {
  if (previewTask || message.peak < 0.003 || message.samples.length < message.sampleRate / 2) return;
  const wav = encodeWav(message.samples, message.sampleRate);
  previewTask = api<{ text: string }>("/api/transcribe?preview=1", wav).then(result => {
    if (mode === "running" && message.seq > transcribedSeq && typeof result.text === "string") {
      preview = { slideId: message.slideId, seq: message.seq, text: result.text.trim() };
      renderActivity();
    }
  }).catch(() => undefined).finally(() => { previewTask = undefined; });
}

function peekAudio() {
  if (mode !== "running" || !worklet || transcriptionTask || previewTask || audioQueue.length ||
      Date.now() - lastPeekAt < 1000) return;
  lastPeekAt = Date.now();
  worklet.port.postMessage({ type: "peek" });
}

function receiveAudio(message: { slideId: string; seq: number; samples: Float32Array; sampleRate: number; peak: number; capturedAt: number }) {
  if (!states.has(message.slideId)) return setError("Captured audio has an unknown slide ID.");
  const wav = encodeWav(message.samples, message.sampleRate);
  const slideState = state(message.slideId);
  if (keepAudio.checked) slideState.audio.push(wav);
  // Skip only clips where no 100 ms window had speech-like energy.
  if (message.peak < 0.003) {
    if (preview && preview.seq <= message.seq) preview = undefined;
    transcribedSeq = Math.max(transcribedSeq, message.seq);
    return;
  }
  lastSpeechAt = Date.now();
  audioQueue.push({ slideId: message.slideId, wav, capturedAt: message.capturedAt, seq: message.seq });
  pumpTranscription();
  render();
  if (audioQueue.length > 10 && mode === "running") void action(async () => {
    await pause();
    throw new Error("Local transcription cannot keep up. Rehearsal paused so queued audio can finish.");
  });
}

function pumpTranscription() {
  if (transcriptionTask) return;
  transcriptionTask = (async () => {
    while (audioQueue.length) {
      const chunk = audioQueue.shift()!;
      const slideState = state(chunk.slideId);
      await previewTask;
      try {
        const result = await api<{ text: string }>("/api/transcribe", chunk.wav);
        if (typeof result.text !== "string") throw new Error("Local Whisper returned an invalid transcript.");
        if (errorText === slideState.transcriptionError) errorText = "";
        if (!failedAudio.some(failed => failed.slideId === chunk.slideId)) slideState.transcriptionError = undefined;
        transcribedSeq = Math.max(transcribedSeq, chunk.seq);
        if (preview && preview.seq <= chunk.seq) preview = undefined;
        if (result.text.trim()) {
          slideState.utterances.push({ text: result.text.trim(), capturedAt: chunk.capturedAt });
          slideState.utterances.sort((left, right) => left.capturedAt - right.capturedAt);
          slideState.revision++;
          if (mode !== "running" || chunk.slideId !== activeId) queueJudge(chunk.slideId, "boundary");
        }
      } catch (error) {
        failedAudio.push(chunk);
        slideState.transcriptionError = error instanceof Error ? error.message : "Transcription failed.";
        setError(slideState.transcriptionError);
        if (mode === "running") void action(pause);
      }
      render();
    }
  })().finally(() => { transcriptionTask = undefined; render(); });
  render();
}

function queueJudge(id: string, trigger: JudgeTrigger = "interval") {
  const slideState = state(id);
  if (!judgeReadiness(transcript(id), slideState.attemptedWords, trigger).eligible ||
      (trigger !== "manual" && slideState.attemptedRevision >= slideState.revision)) return;
  const priority = { interval: 0, boundary: 1, manual: 2 };
  const queued = judgeQueue.get(id);
  if (!queued || priority[trigger] > priority[queued]) judgeQueue.set(id, trigger);
  if (judgeTask) return;
  judgeTask = (async () => {
    while (judgeQueue.size) {
      const [slideId, reason] = judgeQueue.entries().next().value!;
      judgeQueue.delete(slideId);
      const target = state(slideId);
      const submittedTranscript = transcript(slideId);
      const readiness = judgeReadiness(submittedTranscript, target.attemptedWords, reason);
      if (!readiness.eligible || (reason !== "manual" && target.attemptedRevision >= target.revision)) continue;
      const revision = target.revision;
      target.attemptedRevision = revision;
      target.attemptedWords = readiness.words;
      judging = { slideId, words: readiness.words, since: Date.now() };
      render();
      try {
        const slide = rubrics.find(item => item.id === slideId)!;
        const theory = Object.fromEntries(pairedTheory(slide)
          .map(item => [item.id, transcript(item.id)]).filter(([, text]) => text));
        const result = await api<{ decisions: Decision[]; latencyMs: number; request: unknown; response: unknown }>("/api/judge", {
          slideId, transcript: submittedTranscript, theory,
        });
        target.decisions = result.decisions;
        target.judgedRevision = revision;
        target.assessedTranscript = submittedTranscript;
        target.checks++;
        target.judgedAt = Date.now();
        target.latencyMs = result.latencyMs;
        target.lastRequest = result.request;
        target.lastResponse = result.response;
        if (errorText === target.judgeError) errorText = "";
        target.judgeError = undefined;
        judgedCalls++;
      } catch (error) {
        target.judgeError = error instanceof Error ? error.message : "Decision-1 unavailable.";
        setError(target.judgeError);
      }
      judging = undefined;
      render();
    }
  })().finally(() => { judgeTask = undefined; render(); });
  render();
}

async function start() {
  if (!consent.checked) throw new Error("Consent to transcript judging before starting.");
  if (!service?.ready) throw new Error("Resolve the setup checks before starting.");
  reviewId = undefined;
  await openMicrophone();
  startedAt ??= new Date().toISOString();
  mode = "running";
  state().visited = true;
  since = performance.now();
  lastJudgeAt = Date.now();
  panel.querySelector(".rh-scroll")!.scrollTop = 0;
}

async function pause() {
  if (mode !== "running") return;
  state().elapsed += performance.now() - since;
  mode = "paused";
  try {
    await captureBoundary(activeId, false);
  } finally {
    await closeMicrophone();
    queueJudge(activeId, "boundary");
  }
}

async function finish() {
  if (mode === "running") {
    state().elapsed += performance.now() - since;
  }
  mode = "finishing";
  render();
  try {
    await captureBoundary(activeId, false);
  } finally {
    await closeMicrophone();
    await transcriptionTask;
    for (const [id, slideState] of states) {
      if (slideState.judgedRevision < slideState.revision) queueJudge(id, "boundary");
    }
    await judgeTask;
    mode = "finished";
    renderReview();
    element("rhReview").scrollIntoView({ block: "start" });
  }
}

function renderClock() {
  const now = performance.now();
  const remaining = budget(activeId) - elapsed(activeId, now);
  const clockNode = element("rhClock");
  clockNode.textContent = clock(remaining);
  clockNode.classList.toggle("rh-over", remaining < 0);
  clockNode.classList.toggle("rh-warning", remaining >= 0 && remaining < budget(activeId) * 0.2);
  const bar = element("rhTimeBar");
  bar.style.width = `${Math.min(100, Math.max(0, elapsed(activeId, now) / budget(activeId) * 100))}%`;
  bar.classList.toggle("rh-over", remaining < 0);
  const used = [...states.keys()].reduce((sum, id) => sum + elapsed(id, now), 0);
  const allocated = rubrics.filter(slide => state(slide.id).visited && slide.id !== activeId)
    .reduce((sum, slide) => sum + budget(slide.id), 0);
  const drift = used - Math.min(elapsed(activeId, now), budget(activeId)) - allocated;
  const talkLeft = rubrics.reduce((sum, slide) => sum + budget(slide.id), 0) - used;
  element("rhTalkLeft").textContent = clock(talkLeft);
  element("rhTalkLeft").classList.toggle("rh-over", talkLeft < 0);
  const overspill = element("rhOverspill");
  overspill.textContent = Math.abs(drift) < 1000 ? "On time" : drift > 0 ? `${clock(-drift)} over` : `${clock(-drift)} ahead`;
  overspill.classList.toggle("rh-over", drift >= 1000);
  element("rhMode").textContent = mode === "running" ? (remaining < 0 ? "Over budget" : "Live") :
    ({ idle: "Ready", paused: "Paused", finishing: "Finishing...", finished: "Finished" })[mode];
  element("rhMic").textContent = mode === "running" ?
    (Date.now() - lastSpeechAt < 6000 ? "Listening locally" : "Listening - waiting for speech") : "Microphone off";
  element<HTMLMeterElement>("rhLevel").value = mode === "running" ? speechLevel : 0;
}

function renderConcepts(slide: SlideRubric, slideState: SlideState) {
  const statusLabels = {
    not_covered: "Not yet", mentioned: "Mentioned", explained: "Landed",
    contradicted: "Correct this", uncertain: "Unclear",
  };
  element("rhConcepts").replaceChildren(...slide.concepts.map(concept => {
    const decision = slideState.decisions.find(item => item.conceptId === concept.id);
    const row = document.createElement("div");
    const trusted = decision && decision.confidence >= 0.65;
    row.className = `rh-concept rh-${trusted ? decision.coverage : "pending"}`;
    const heading = document.createElement("div");
    heading.className = "rh-concept-heading";
    const label = document.createElement("strong");
    label.textContent = concept.label;
    label.title = concept.criterion;
    const status = document.createElement("span");
    status.className = "rh-coverage";
    status.textContent = decision ? (trusted ? statusLabels[decision.coverage] : "Not sure yet") :
      (mode === "running" ? "Listening" : slideState.utterances.length ? "More context" : "Not yet");
    heading.append(label, status);
    row.appendChild(heading);
    const hint = document.createElement("p");
    hint.className = "rh-hint";
    hint.textContent = concept.cue;
    row.appendChild(hint);
    if (decision && qualityKeys.some(key => decision.quality[key].rating !== null)) {
      const scores = document.createElement("div");
      scores.className = "rh-quality";
      for (const key of qualityKeys) {
        const quality = decision.quality[key];
        const item = document.createElement("div");
        const name = document.createElement("span");
        name.textContent = qualityDimensions[key].label;
        const score = document.createElement("strong");
        score.textContent = quality.rating === null ? "Unclear" : `${quality.rating.toFixed(1)}/4`;
        item.append(name, score);
        const tentative = quality.range[1] - quality.range[0] >= 2;
        item.title = quality.rating === null ? "No intelligible explanation of this concept to assess." :
          `Probability-weighted score; the scorer's central 80% of grades spans ${quality.range[0]}–${quality.range[1]}/4` +
          (tentative ? " (the scorer is unsure between these grades)." : ".");
        scores.appendChild(item);
      }
      row.appendChild(scores);
    }
    return row;
  }));
  const next = slide.concepts.find(concept =>
    !slideState.decisions.some(decision => decision.conceptId === concept.id && explained(decision)));
  const contradiction = slideState.decisions.find(decision => decision.coverage === "contradicted" && decision.confidence >= 0.65);
  const cue = contradiction ? slide.concepts.find(concept => concept.id === contradiction.conceptId)?.cue : next?.cue;
  const improvement = slideState.decisions.flatMap(decision => qualityKeys.map(key => ({
    concept: slide.concepts.find(concept => concept.id === decision.conceptId)!,
    key, ...decision.quality[key],
  }))).filter(item => item.rating !== null && item.rating < 2.5 && item.range[1] - item.range[0] <= 1)
    .sort((left, right) => left.rating! - right.rating!)[0];
  element("rhCue").textContent = contradiction ? `Clarify this: ${cue}` :
    cue ? `Next idea: ${cue}` : improvement ?
      `${improvement.concept.label}: ${qualityDimensions[improvement.key].cue}` :
      "All spoken objectives clearly covered. Leave space for the transition.";
}

function renderActivity() {
  const id = reviewId ?? activeId;
  const slideState = state(id);
  const finalWords = transcript(id).split(/\s+/).filter(Boolean);
  const previewWords = preview?.slideId === id && mode === "running" ? preview.text.split(/\s+/).filter(Boolean) : [];
  const shown = [...finalWords, ...previewWords].slice(-14);
  const provisional = Math.min(previewWords.length, shown.length);
  const heard = element("rhHeardText");
  if (!shown.length) {
    heard.textContent = mode === "running" ? "Listening for speech…" : "No speech captured on this slide";
  } else {
    const live = document.createElement("span");
    live.className = "rh-provisional";
    live.textContent = (provisional < shown.length ? " " : "") + shown.slice(shown.length - provisional).join(" ");
    heard.replaceChildren((finalWords.length + previewWords.length > 14 ? "… " : "") +
      shown.slice(0, shown.length - provisional).join(" "), live);
  }
  element("rhHeardDot").className = "rh-dot" + (transcriptionTask ? " rh-busy" : mode === "running" ? " rh-on" : "");
  element("rhHeard").title = transcriptionTask ? "Transcribing locally…" : "Latest words heard on this slide";
  const sending = judging?.slideId === id;
  element("rhJudgeDot").className = "rh-dot" + (sending ? " rh-busy rh-send" : slideState.judgeError ? " rh-fail" : "");
  element("rhJudgeText").textContent = sending ?
    `Sending ${judging!.words} words to Decision-1… ${Math.floor((Date.now() - judging!.since) / 1000)}s` :
    slideState.judgeError ? "Decision-1 check failed" :
      slideState.judgedAt ? `Decision-1 scored ${wordCount(slideState.assessedTranscript)} words · ${Math.max(0, Math.round((Date.now() - slideState.judgedAt) / 1000))}s ago` :
        judging ? "Decision-1 busy with another slide" : "Decision-1: no check yet";
  const next = element("rhJudgeNext");
  next.hidden = mode !== "running" || id !== activeId || sending;
  if (!next.hidden) {
    const needed = judgingPolicy.newWords - judgeReadiness(transcript(id), slideState.attemptedWords, "interval").newWords;
    const seconds = Math.max(0, Math.ceil((judgingPolicy.intervalMs - (Date.now() - lastJudgeAt)) / 1000));
    next.textContent = needed > 0 ? `next: ${needed} more word${needed === 1 ? "" : "s"}` : `next in ${seconds}s`;
  }
}

function render() {
  renderActivity();
  const id = reviewId ?? activeId;
  const slide = rubric(id);
  const slideState = state(id);
  const started = mode !== "idle";
  element("rehearsalButton").textContent = mode === "running" ? "Recording" : mode === "paused" ? "Rehearsal paused" : "Rehearse";
  element("rehearsalButton").dataset.recording = String(mode === "running");
  element("rehearsalButton").title = mode === "running" ? "Microphone recording locally. Open rehearsal to pause or finish." : "Open rehearsal coach";
  element("rhSetup").hidden = started;
  element("rhLive").hidden = !started;
  startButton.hidden = mode !== "idle";
  startButton.disabled = actionBusy || !service?.ready || !consent.checked;
  pauseButton.hidden = !["running", "paused"].includes(mode);
  pauseButton.textContent = mode === "paused" ? "Resume" : "Pause";
  pauseButton.disabled = actionBusy;
  stopButton.hidden = !["running", "paused", "finishing"].includes(mode);
  stopButton.disabled = actionBusy || mode === "finishing";
  element("rhError").hidden = !errorText;
  element("rhError").textContent = errorText;
  element("rhPhase").textContent = `${rubrics.indexOf(slide) + 1} / ${rubrics.length} · ${slide.phase}${reviewId ? " · REVIEW" : ""}`;
  element("rhTitle").textContent = slide.title;
  const partners = slide.pair ? rubrics.filter(item => item.pair === slide.pair && item.id !== slide.id) : [];
  element("rhPair").textContent = partners.length ? "Linked: " + partners.map(partner => {
    const partnerState = state(partner.id);
    return `${partner.title} (${partnerState.decisions.filter(explained).length}/${partner.concepts.length} explained)`;
  }).join("; ") : "";
  renderConcepts(slide, slideState);
  element("rhDetails").hidden = !["paused", "finished"].includes(mode);
  element("rhDemoOption").hidden = slide.phase !== "demo" || !started;
  demo.checked = slideState.demoCompleted;
  const currentTranscript = transcript(id);
  const words = wordCount(currentTranscript);
  const submittedWords = wordCount(slideState.assessedTranscript);
  const readiness = judgeReadiness(currentTranscript, slideState.attemptedWords, "interval");
  const upToDate = slideState.revision > 0 && slideState.judgedRevision === slideState.revision;
  element("rhStatus").textContent = !started ? "" : slideState.judgeError || slideState.transcriptionError ?
    "Feedback unavailable" : judgeTask ? "Checking..." : transcriptionTask && mode !== "running" ?
      "Finishing transcript..." : upToDate ? "Up to date" :
        mode === "running" ? "Listening..." : words < judgingPolicy.finalWords ? "More speech needed" : "Feedback pending";
  element("rhJudged").textContent = slideState.judgeError ? `${slideState.judgeError} Previous feedback, if any, is stale.` :
    slideState.judgedAt ?
      `Check ${slideState.checks} assessed ${submittedWords}/${words} words · ${new Date(slideState.judgedAt).toLocaleTimeString()} · ${slideState.latencyMs} ms` +
      (slideState.judgedRevision < slideState.revision ? " · New speech not yet assessed." : " · All captured speech assessed.") :
      "No assessment yet.";
  element("rhGate").textContent = words < judgingPolicy.finalWords ?
    `Too little speech to assess (${words}/${judgingPolicy.finalWords} words for a final check).` :
    `Automatic checks need ${judgingPolicy.newWords} new words; ${readiness.newWords} new words available. Final slide checks use any new speech once there are ${judgingPolicy.finalWords} words in total.`;
  element("rhCopy").hidden = !started || !slideState.utterances.length;
  element("rhTranscript").textContent = currentTranscript || "No speech captured yet.";
  element("rhAssessed").textContent = slideState.assessedTranscript || "No assessment yet.";
  element("rhWords").textContent = `(${words} words)`;
  element("rhAssessmentDetails").replaceChildren(...slideState.decisions.map(decision => {
    const section = document.createElement("p");
    const concept = slide.concepts.find(concept => concept.id === decision.conceptId)!;
    section.textContent = `${concept.label}: ${labels[decision.coverage]}. Coverage-label probability ${Math.round(decision.confidence * 100)}% (not a presentation score). ` +
      qualityKeys.map(key => {
        const quality = decision.quality[key];
        return quality.rating === null ? `${qualityDimensions[key].label}: no explanation to assess.` :
          `${qualityDimensions[key].label}: ${quality.rating.toFixed(1)}/4; grade probabilities 1–4: ${quality.probabilities.map(probability => `${Math.round(probability * 100)}%`).join(", ")}.`;
      }).join(" ");
    return section;
  }));
  element<HTMLButtonElement>("rhJudge").disabled = !started || words < judgingPolicy.finalWords || Boolean(judgeTask);
  element("rhRetry").hidden = failedAudio.length === 0;
  element<HTMLButtonElement>("rhRetry").disabled = Boolean(transcriptionTask);
  element<HTMLButtonElement>("rhNew").disabled = Boolean(transcriptionTask || judgeTask);
  element("rhPipeline").textContent = `${transcriptionTask ? `Transcribing locally (${audioQueue.length + 1} queued)` : "Transcription idle"} · ` +
    `${judgeTask ? "Checking concepts" : `${judgedCalls} checks complete`}` +
    (failedAudio.length ? ` · ${failedAudio.length} audio segments need retry` : "");
  const playable = ["paused", "finished"].includes(mode) && slideState.audio.length > 0;
  element("rhPlayback").hidden = !playable;
  if (playable && element("rhPlayback").dataset.slide !== id) {
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    recordingUrl = URL.createObjectURL(combineWavs(slideState.audio));
    element<HTMLAudioElement>("rhAudio").src = recordingUrl;
    element("rhPlayback").dataset.slide = id;
  } else if (!playable) {
    element("rhPlayback").dataset.slide = "";
    element<HTMLAudioElement>("rhAudio").pause();
  }
  renderClock();
  if (mode === "finished") renderReview();
}

function renderReview() {
  element("rhReview").hidden = false;
  const visited = rubrics.filter(slide => state(slide.id).visited);
  const clearly = visited.reduce((sum, slide) => sum + state(slide.id).decisions.filter(explained).length, 0);
  const objectives = visited.reduce((sum, slide) => sum + slide.concepts.length, 0);
  const stale = visited.filter(slide => (wordCount(transcript(slide.id)) >= judgingPolicy.finalWords && state(slide.id).judgedRevision < state(slide.id).revision) ||
    state(slide.id).judgeError || state(slide.id).transcriptionError);
  element("rhReviewSummary").textContent = `${visited.length}/${rubrics.length} slides visited · ${clearly}/${objectives} objectives clearly explained. ` +
    `${stale.length} slides have incomplete or failed feedback. Download before closing this tab.`;
  element("rhReviewRows").replaceChildren(...rubrics.map(slide => {
    const target = state(slide.id);
    const button = document.createElement("button");
    button.className = "rh-review-row";
    button.setAttribute("aria-pressed", String(reviewId === slide.id));
    const label = document.createElement("strong");
    label.textContent = `${rubrics.indexOf(slide) + 1}. ${slide.title}`;
    const detail = document.createElement("span");
    const over = target.elapsed > budget(slide.id);
    detail.textContent = !target.visited ? "Not visited" :
      `${clock(target.elapsed)} / ${clock(budget(slide.id))}${over ? " · OVER" : ""} · ` +
      `${target.decisions.filter(explained).length}/${slide.concepts.length} explained` +
      (!target.utterances.length ? " · No speech captured" : "") +
      (target.utterances.length && wordCount(transcript(slide.id)) < judgingPolicy.finalWords ? " · Too brief to assess" : "") +
      (target.judgeError || target.transcriptionError ? " · Feedback incomplete" : "") +
      (slide.phase === "demo" ? ` · Demo ${target.demoCompleted ? "self-confirmed" : "not confirmed"}` : "");
    button.append(label, detail);
    button.addEventListener("click", () => {
      reviewId = slide.id;
      render();
      element("rhCurrent").scrollIntoView({ block: "start" });
      element("rhTitle").tabIndex = -1;
      element("rhTitle").focus({ preventScroll: true });
    });
    return button;
  }));
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export function toggle() {
  panel.hidden = !panel.hidden;
  document.documentElement.classList.toggle("rehearsal-open", !panel.hidden);
  element("rehearsalButton").setAttribute("aria-expanded", String(!panel.hidden));
  if (!panel.hidden) {
    for (const id of ["notesPanel", "overview"]) {
      element(id).classList.remove("open");
      element(id).setAttribute("aria-hidden", "true");
    }
    if (!service) void checkSetup();
    element("rhClose").focus();
  } else element("rehearsalButton").focus();
  window.dispatchEvent(new Event("resize"));
}

element("rhClose").addEventListener("click", toggle);
element("rhCheck").addEventListener("click", () => void action(checkSetup));
consent.addEventListener("change", render);
startButton.addEventListener("click", () => void action(start));
pauseButton.addEventListener("click", () => void action(mode === "running" ? pause : start));
stopButton.addEventListener("click", () => void action(finish));
demo.addEventListener("change", () => { state(reviewId ?? activeId).demoCompleted = demo.checked; render(); });
element("rhJudge").addEventListener("click", () => queueJudge(reviewId ?? activeId, "manual"));
element("rhRetry").addEventListener("click", () => {
  audioQueue.push(...failedAudio.splice(0));
  pumpTranscription();
});
element("rhBack").addEventListener("click", () => { reviewId = undefined; render(); });
element("rhNew").addEventListener("click", () => {
  if (mode !== "finished" || transcriptionTask || judgeTask) return;
  if (!window.confirm("Discard this rehearsal and start fresh? Download the session and any audio you want to keep first.")) return;
  for (const slide of rubrics) states.set(slide.id, emptyState());
  if (recordingUrl) URL.revokeObjectURL(recordingUrl);
  recordingUrl = undefined;
  element<HTMLAudioElement>("rhAudio").removeAttribute("src");
  element("rhPlayback").dataset.slide = "";
  failedAudio.length = 0;
  mode = "idle";
  startedAt = undefined;
  reviewId = undefined;
  errorText = "";
  judgedCalls = 0;
  consent.checked = false;
  element("rhReview").hidden = true;
  render();
  panel.querySelector(".rh-scroll")!.scrollTop = 0;
});
function llmBundle(id: string) {
  const slide = rubric(id);
  const target = state(id);
  const full = transcript(id);
  const json = (value: unknown) => "```json\n" + JSON.stringify(value, null, 2) + "\n```";
  return [
    `# Rehearsal feedback: slide ${rubrics.indexOf(slide) + 1} "${slide.title}" (${slide.phase})`,
    "Explain why Decision-1 gave these coverage and quality scores, quoting the transcript, and suggest how to say it better.",
    `## Full transcript captured on this slide (${wordCount(full)} words)`,
    full || "(none)",
    target.assessedTranscript === full ? "The last assessment used this full transcript." :
      `The last assessment used ${wordCount(target.assessedTranscript)} of these words; later speech was not yet assessed.`,
    "## Exact Decision-1 request (last check)",
    target.lastRequest ? json(target.lastRequest) : "(no assessment yet)",
    "## Decision-1 response (last check)",
    target.lastResponse ? json(target.lastResponse) : "(no assessment yet)",
  ].join("\n\n");
}
element("rhCopy").addEventListener("click", async () => {
  const id = reviewId ?? activeId;
  const text = llmBundle(id);
  const button = element<HTMLButtonElement>("rhCopy");
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    download(new Blob([text], { type: "text/markdown" }), `rehearsal-${id}.md`);
    button.textContent = "Downloaded";
  }
  setTimeout(() => { button.textContent = "Copy for LLM"; }, 1500);
});
element("rhDownloadAudio").addEventListener("click", () => {
  const id = reviewId ?? activeId;
  download(combineWavs(state(id).audio), `rehearsal-${id}.wav`);
});
element("rhExport").addEventListener("click", () => {
  const report = {
    schemaVersion: 3, startedAt, exportedAt: new Date().toISOString(), judgingPolicy,
    qualityMethod: "Native ordered score on four anchored levels; zero-based API scores shifted to 1–4.",
    endpoint: service?.endpoint, deployment: service?.deployment,
    scope: "Spoken concept coverage only; not audience understanding or verified screen actions.",
    failedAudioSegments: failedAudio.map(chunk => ({ slideId: chunk.slideId, capturedAt: chunk.capturedAt })),
    slides: rubrics.map(slide => {
      const target = state(slide.id);
      return {
        id: slide.id, title: slide.title, phase: slide.phase, pair: slide.pair,
        budgetMs: budget(slide.id), elapsedMs: elapsed(slide.id), visited: target.visited,
        transcript: target.utterances, concepts: slide.concepts, decisions: target.decisions,
        judgedRevision: target.judgedRevision, transcriptRevision: target.revision, judgedAt: target.judgedAt,
        assessedTranscript: target.assessedTranscript, checks: target.checks,
        lastDecisionRequest: target.lastRequest, lastDecisionResponse: target.lastResponse,
        judgeError: target.judgeError, transcriptionError: target.transcriptionError,
        demoCompletedSelfReported: target.demoCompleted,
      };
    }),
  };
  download(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }), "rehearsal-session.json");
});
document.addEventListener("presentation:slide", event => {
  const index = (event as CustomEvent<{ index: number }>).detail.index;
  const nextId = slideElements[index]?.dataset.rehearsalId;
  if (!nextId || nextId === activeId) return;
  const previousId = activeId;
  if (mode === "running") state(previousId).elapsed += performance.now() - since;
  activeId = nextId;
  reviewId = undefined;
  if (mode === "running") {
    since = performance.now();
    state().visited = true;
    void captureBoundary(activeId, true).catch(setError);
    queueJudge(previousId, "boundary");
  }
  render();
});
panel.addEventListener("keydown", event => {
  if (event.key === "Escape") toggle();
});
window.addEventListener("beforeunload", event => {
  if (startedAt) event.preventDefault();
});
setInterval(() => {
  if (mode !== "idle") renderActivity();
  peekAudio();
  if (mode === "running") {
    renderClock();
    if (Date.now() - lastJudgeAt >= judgingPolicy.intervalMs) {
      lastJudgeAt = Date.now();
      queueJudge(activeId);
    }
  }
}, 250);
render();
