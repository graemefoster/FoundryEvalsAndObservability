import { execFile, spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createServer as createNetServer } from "node:net";
import type { IncomingMessage, ServerResponse } from "node:http";
import { homedir, tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { decisionRequest, judgingPolicy, pairedTheory, readDecisions, rubrics, wordCount } from "./concepts.ts";
import type { ServiceStatus } from "./concepts.ts";

const execute = promisify(execFile);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const endpoint = process.env.DECISION_ENDPOINT ?? "";
const deployment = process.env.DECISION_DEPLOYMENT ?? "Decision-1";
const model = process.env.WHISPER_MODEL ?? join(homedir(), ".cache/whisper/ggml-base.en.bin");
const whisper = process.env.WHISPER_BIN ?? "whisper-cli";
const whisperServerBin = process.env.WHISPER_SERVER_BIN ?? "whisper-server";
let whisperUrl: string | undefined;
let whisperChild: ChildProcess | undefined;
const port = Number(process.env.REHEARSAL_PORT ?? 4173);
const csrf = randomBytes(32).toString("hex");
let token: { value: string; expires: number } | undefined;
let tokenRequest: Promise<string> | undefined;
let transcribing = false;
let judging = false;

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function endpointIsValid() {
  try {
    const url = new URL(endpoint);
    return url.protocol === "https:" && url.hostname.endsWith(".services.ai.azure.com") &&
      url.pathname === "/providers/microsoft/v1/systemone" &&
      !url.search && !url.hash && !url.username && !url.password && !url.port;
  } catch {
    return false;
  }
}

async function getToken(): Promise<string> {
  if (token && token.expires > Date.now() + 60_000) return token.value;
  if (tokenRequest) return tokenRequest;
  tokenRequest = (async () => {
    let stdout: string;
    try {
      ({ stdout } = await execute("az", [
        "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com",
        "--output", "json",
      ], { timeout: 30_000, maxBuffer: 1_048_576 }));
    } catch {
      throw new HttpError(401, "Azure sign-in unavailable. Run az login in a terminal, then Check setup.");
    }
    const result = JSON.parse(stdout);
    if (typeof result.accessToken !== "string" || !result.accessToken ||
        !Number.isFinite(Number(result.expires_on))) {
      throw new HttpError(401, "Azure CLI returned an invalid token. Update/sign in to Azure CLI and retry.");
    }
    token = { value: result.accessToken, expires: Number(result.expires_on) * 1000 };
    return token.value;
  })();
  try {
    return await tokenRequest;
  } finally {
    tokenRequest = undefined;
  }
}

async function status(): Promise<ServiceStatus> {
  const checks: ServiceStatus["checks"] = [];
  checks.push({
    name: "Decision endpoint", ok: endpointIsValid(),
    detail: endpointIsValid() ? `${new URL(endpoint).host} / ${deployment}` :
      "Set DECISION_ENDPOINT to your HTTPS Foundry /providers/microsoft/v1/systemone endpoint.",
  });
  try {
    await getToken();
    checks.push({ name: "Azure sign-in", ok: true, detail: "Azure CLI token ready; kept in this local process." });
  } catch (error) {
    checks.push({ name: "Azure sign-in", ok: false, detail: errorMessage(error) });
  }
  try {
    await access(model);
    checks.push({ name: "Whisper model", ok: true, detail: "Local English model found." });
  } catch {
    checks.push({ name: "Whisper model", ok: false, detail: "Model missing. Set WHISPER_MODEL; see PLAYBOOK.md." });
  }
  for (const [name, command, args] of [
    ...(whisperUrl ? [] : [["Whisper", whisper, ["--help"]] as const]),
    ["Audio conversion", "ffmpeg", ["-version"]],
  ] as const) {
    try {
      await execute(command, [...args], { timeout: 10_000, maxBuffer: 1_048_576 });
      checks.push({ name, ok: true, detail: `${command} available locally.` });
    } catch {
      checks.push({ name, ok: false, detail: `${command} unavailable. Install it; see PLAYBOOK.md.` });
    }
  }
  if (whisperUrl) checks.push({ name: "Whisper", ok: true, detail: "Model loaded in local whisper-server." });
  return { csrf, endpoint, deployment, checks, ready: checks.every(check => check.ok) };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected local service error.";
}

async function body(request: IncomingMessage, limit: number) {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > limit) throw new HttpError(413, "Request too large.");
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export function validateAudio(audio: Buffer) {
  if (audio.length < 46 || audio.toString("ascii", 0, 4) !== "RIFF" ||
      audio.toString("ascii", 8, 12) !== "WAVE" ||
      audio.toString("ascii", 12, 16) !== "fmt " || audio.readUInt32LE(16) !== 16 ||
      audio.readUInt16LE(20) !== 1 || audio.readUInt16LE(22) !== 1 ||
      audio.readUInt16LE(34) !== 16 || audio.toString("ascii", 36, 40) !== "data" ||
      audio.readUInt32LE(4) !== audio.length - 8 ||
      audio.readUInt32LE(40) !== audio.length - 44 || (audio.length - 44) % 2 !== 0) {
    throw new HttpError(400, "Expected mono 16-bit PCM WAV audio.");
  }
  const rate = audio.readUInt32LE(24);
  if (rate < 16_000 || rate > 96_000 || audio.readUInt32LE(28) !== rate * 2 ||
      audio.readUInt16LE(32) !== 2 || (audio.length - 44) / (rate * 2) > 12) {
    throw new HttpError(400, "Audio must be at most 12 seconds at 16-96 kHz.");
  }
  return rate;
}

function cleanTranscript(text: string) {
  return text.replace(/\[BLANK_AUDIO\]|\[SILENCE\]/g, "").replace(/\s+/g, " ").trim();
}

// Keeps the model loaded between clips; falls back to whisper-cli if it cannot start.
async function startWhisperServer() {
  const whisperPort = await new Promise<number>((done, fail) => {
    const probe = createNetServer().once("error", fail).listen(0, "127.0.0.1", () => {
      const address = probe.address();
      probe.close(() => typeof address === "object" && address ? done(address.port) : fail(new Error("No port.")));
    });
  });
  const child = spawn(whisperServerBin, [
    "-m", model, "--host", "127.0.0.1", "--port", String(whisperPort), "-l", "en", "-nt",
  ], { stdio: "ignore" });
  whisperChild = child;
  let exited = false;
  child.on("error", () => { exited = true; });
  child.on("exit", () => { exited = true; whisperUrl = undefined; whisperChild = undefined; });
  for (let attempt = 0; attempt < 240 && !exited; attempt++) {
    try {
      await fetch(`http://127.0.0.1:${whisperPort}/`, { signal: AbortSignal.timeout(1_000) });
      whisperUrl = `http://127.0.0.1:${whisperPort}/inference`;
      return true;
    } catch {
      await new Promise(done => setTimeout(done, 250));
    }
  }
  child.kill();
  return false;
}

async function transcribe(audio: Buffer) {
  const rate = validateAudio(audio);
  const directory = await mkdtemp(join(tmpdir(), "presentation-rehearsal-"));
  try {
    const input = join(directory, "input.wav");
    let wav = input;
    await writeFile(input, audio, { mode: 0o600 });
    if (rate !== 16_000) {
      wav = join(directory, "mono.wav");
      await execute("ffmpeg", [
        "-nostdin", "-loglevel", "error", "-i", input,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav,
      ], { timeout: 15_000, maxBuffer: 1_048_576 });
    }
    if (whisperUrl) {
      const form = new FormData();
      form.append("file", new Blob([await readFile(wav)], { type: "audio/wav" }), "audio.wav");
      form.append("response_format", "json");
      form.append("temperature", "0");
      let result: unknown;
      try {
        const reply = await fetch(whisperUrl, { method: "POST", body: form, signal: AbortSignal.timeout(60_000) });
        if (!reply.ok) throw new Error(`HTTP ${reply.status}`);
        result = await reply.json();
      } catch {
        throw new HttpError(503, "Local whisper-server failed or timed out; no audio was sent to the cloud.");
      }
      if (!result || typeof result !== "object" || !("text" in result) || typeof result.text !== "string") {
        throw new HttpError(502, "Local Whisper returned an invalid transcript.");
      }
      return cleanTranscript(result.text);
    }
    const output = join(directory, "transcript");
    try {
      await execute(whisper, [
        "-m", model, "-f", wav, "-l", "en", "-oj", "-of", output, "-np", "-nt",
      ], { timeout: 60_000, maxBuffer: 4_194_304 });
    } catch {
      throw new HttpError(503, "Local Whisper failed or timed out. Check the model and WHISPER_BIN; no audio was sent to the cloud.");
    }
    const result = JSON.parse(await readFile(`${output}.json`, "utf8"));
    if (!Array.isArray(result.transcription) ||
        !result.transcription.every((segment: unknown) => segment && typeof segment === "object" &&
          "text" in segment && typeof segment.text === "string")) {
      throw new HttpError(502, "Local Whisper returned an invalid transcript.");
    }
    return cleanTranscript(result.transcription.map((segment: { text: string }) => segment.text.trim()).join(" "));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

function json(response: ServerResponse, code: number, value: unknown) {
  response.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(value));
}

export function sameOrigin(host: string | undefined, origin: string | undefined, expectedPort: number) {
  return (host === `127.0.0.1:${expectedPort}` || host === `localhost:${expectedPort}`) &&
    (!origin || origin === `http://${host}`);
}

export const server = createServer(async (request, response) => {
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Referrer-Policy", "no-referrer");
  response.setHeader("Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data:; connect-src 'self'; worker-src 'self'; media-src 'self' blob:; " +
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  try {
    if (!sameOrigin(request.headers.host, request.headers.origin, port)) {
      throw new HttpError(403, "Only same-origin localhost requests are allowed.");
    }
    const path = new URL(request.url ?? "/", `http://${request.headers.host}`).pathname;
    if (request.method === "GET") {
      if (path === "/api/status") return json(response, 200, await status());
      if (path === "/") {
        response.writeHead(302, { Location: "/deck.html?rehearsal=1" });
        return response.end();
      }
      const files: Record<string, [string, string]> = {
        "/deck.html": ["deck.html", "text/html"],
        "/rehearsal/client.js": ["rehearsal/dist/client.js", "text/javascript"],
        "/rehearsal/worklet.js": ["rehearsal/dist/worklet.js", "text/javascript"],
        "/rehearsal/style.css": ["rehearsal/style.css", "text/css"],
      };
      let file = files[path];
      if (/^\/assets\/[a-zA-Z0-9_.-]+\.(png|jpe?g|svg|webp)$/i.test(path)) {
        const mime: Record<string, string> = {
          ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".svg": "image/svg+xml", ".webp": "image/webp",
        };
        file = [path.slice(1), mime[extname(path).toLowerCase()]];
      }
      if (!file) throw new HttpError(404, "Not found.");
      let content: Buffer;
      try {
        content = await readFile(join(root, file[0]));
      } catch {
        throw new HttpError(404, "Presentation file not found. Run npm run build.");
      }
      response.writeHead(200, { "Content-Type": `${file[1]}; charset=utf-8` });
      return response.end(content);
    }
    if (request.method !== "POST") throw new HttpError(405, "Method not allowed.");
    const supplied = request.headers["x-rehearsal-csrf"];
    if (!request.headers.origin || typeof supplied !== "string" || supplied.length !== csrf.length ||
        !timingSafeEqual(Buffer.from(supplied), Buffer.from(csrf))) {
      throw new HttpError(403, "Open rehearsal from this local server before making requests.");
    }
    if (path === "/api/transcribe") {
      if (request.headers["content-type"] !== "audio/wav") throw new HttpError(415, "Expected audio/wav.");
      if (transcribing) throw new HttpError(429, "Whisper is busy. Wait and retry.");
      transcribing = true;
      try {
        const audio = await body(request, 2_400_044);
        return json(response, 200, { text: await transcribe(audio) });
      } finally {
        transcribing = false;
      }
    }
    if (path === "/api/judge") {
      if (request.headers["content-type"] !== "application/json") throw new HttpError(415, "Expected application/json.");
      if (!endpointIsValid()) throw new HttpError(503, "Configure DECISION_ENDPOINT before judging.");
      if (judging) throw new HttpError(429, "Decision-1 is busy. Wait and retry.");
      let input: unknown;
      try {
        input = JSON.parse((await body(request, 524_288)).toString("utf8"));
      } catch (error) {
        if (error instanceof HttpError) throw error;
        throw new HttpError(400, "Invalid JSON request.");
      }
      if (!input || typeof input !== "object" || !("slideId" in input) ||
          !("transcript" in input) || typeof input.transcript !== "string" ||
          !input.transcript.trim() || input.transcript.length > 40_000) {
        throw new HttpError(400, "Supply a slide ID and 1-40,000 characters of transcript.");
      }
      const slide = rubrics.find(item => item.id === input.slideId);
      if (!slide) throw new HttpError(400, "Unknown slide.");
      if (wordCount(input.transcript) < judgingPolicy.finalWords) {
        throw new HttpError(400, `At least ${judgingPolicy.finalWords} spoken words are needed before judging.`);
      }
      judging = true;
      const theory: Record<string, string> = {};
      const supplied = "theory" in input && input.theory && typeof input.theory === "object"
        ? input.theory as Record<string, unknown> : {};
      for (const item of pairedTheory(slide)) {
        const text = supplied[item.id];
        if (typeof text === "string" && text.length <= 40_000) theory[item.id] = text;
      }
      const sent = decisionRequest(slide, input.transcript, deployment, theory);
      try {
        const start = performance.now();
        const result = await fetch(endpoint, {
          method: "POST",
          headers: { Authorization: `Bearer ${await getToken()}`, "Content-Type": "application/json" },
          body: JSON.stringify(sent),
          signal: AbortSignal.timeout(30_000),
        });
        if (!result.ok) {
          if (result.status === 401) token = undefined;
          const hint = ({
            401: "Run az login and retry.",
            403: "Your signed-in identity needs inference access; no roles have been changed.",
            404: "Check DECISION_ENDPOINT and DECISION_DEPLOYMENT.",
            429: "Rate limited; pause and retry shortly.",
          } as Record<number, string>)[result.status] ?? "Check the endpoint and deployment configuration.";
          throw new HttpError(502, `Decision-1 returned HTTP ${result.status}. ${hint}`);
        }
        const received = await result.json();
        const decisions = readDecisions(received, slide);
        return json(response, 200, {
          decisions, latencyMs: Math.round(performance.now() - start), request: sent, response: received,
        });
      } finally {
        judging = false;
      }
    }
    throw new HttpError(404, "Not found.");
  } catch (error) {
    const code = error instanceof HttpError ? error.status : 500;
    const message = error instanceof HttpError ? error.message :
      "Local request failed. Check the server terminal and retry.";
    if (!(error instanceof HttpError)) {
      console.error(error instanceof Error ? `${error.name}: ${error.message}` : "Unexpected local request failure.");
    }
    if (!response.headersSent) json(response, code, { error: message });
    else response.end();
  }
});

server.requestTimeout = 90_000;
server.headersTimeout = 10_000;
if (import.meta.main) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error("REHEARSAL_PORT must be an integer from 1024 to 65535.");
  }
  server.on("error", error => {
    console.error(`Rehearsal server: ${error.message}`);
    process.exitCode = 1;
  });
  for (const signal of ["SIGINT", "SIGTERM"] as const) {
    process.on(signal, () => { whisperChild?.kill(); process.exit(0); });
  }
  process.on("exit", () => whisperChild?.kill());
  void startWhisperServer().then(ok => console.log(ok ?
    "Whisper model loaded in local whisper-server." : "whisper-server unavailable; using whisper-cli per clip."));
  server.listen(port, "127.0.0.1", () => {
    console.log(`Rehearsal: http://127.0.0.1:${port}/deck.html?rehearsal=1`);
    console.log("Audio stays local. Transcripts leave only when you start a consented rehearsal.");
  });
}
