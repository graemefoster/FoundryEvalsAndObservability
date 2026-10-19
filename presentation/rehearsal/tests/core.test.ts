import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { encodeWav } from "../src/audio.ts";
import { decisionRequest, judgeReadiness, qualityKeys, readDecisions, rubrics, wordCount } from "../src/concepts.ts";
import { sameOrigin, validateAudio } from "../src/server.ts";

const slide = rubrics.find(item => item.id === "observe")!;
function answer(choice = "explained", probability = 0.9) {
  return { type: "choice", choice, probabilities: { [choice]: probability } };
}
function response(coverage = "explained") {
  return { answers: Object.fromEntries(slide.concepts.flatMap(concept => [
    [concept.id, answer(coverage)],
    ...qualityKeys.map(key => [`${concept.id}__${key}`, {
      type: "score", score: 2, probabilities: { "0": 0, "1": 0, "2": 1, "3": 0 },
    }]),
  ])) };
}

test("rubrics map exactly to deck slide IDs and have linked theory/demo phases", async () => {
  const html = await readFile(new URL("../../deck.html", import.meta.url), "utf8");
  const ids = [...html.matchAll(/data-rehearsal-id="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(ids, rubrics.map(item => item.id));
  for (const item of rubrics.filter(item => item.phase === "demo")) {
    assert.ok(rubrics.some(other => other.phase === "theory" && other.pair === item.pair));
  }
});

test("one batch includes coverage plus three anchored quality decisions per concept", () => {
  const request = decisionRequest(slide, "Traces show calls, not correctness.", "my-deployment");
  assert.equal(request.model, "my-deployment");
  assert.equal(request.state.slide, slide.title);
  assert.equal(request.state.phase, "theory");
  assert.equal(request.state.presenter_transcript, "Traces show calls, not correctness.");
  assert.match(request.state.talk.thesis, /measured, not asserted/);
  assert.equal(request.state.position.total_slides, rubrics.length);
  assert.ok(!("paired_theory" in request.state));
  assert.equal(Object.keys(request.questions).length, slide.concepts.length * 4);
  assert.equal(request.questions[`${slide.concepts[0].id}__clarity`].type, "score");
  assert.match(JSON.stringify(request.questions), /not just keywords/);
});

test("demo slides carry every paired theory slide's objectives and spoken transcript as background", () => {
  const demo = rubrics.find(item => item.id === "demo-gates")!;
  const request = decisionRequest(demo, "Here is the blocked pull request.", "d",
    { "test-sets": "Three sets.", gates: "x".repeat(20_000), observe: "ignored" });
  const theory = request.state.paired_theory!;
  assert.deepEqual(theory.map(item => item.slide), ["Three test sets", "What the gate checks"]);
  assert.equal(theory[0].presenter_transcript, "Three sets.");
  assert.equal(theory[1].presenter_transcript.length, 20_000);
  assert.ok(theory[0].objectives.length > 0);
  assert.match(JSON.stringify(request.questions), /never speech from paired_theory/);
});

test("reads coverage and quality without confusing probability with the rating", () => {
  const result = readDecisions(response(), slide);
  assert.equal(result[0].coverage, "explained");
  assert.equal(result[0].confidence, 0.9);
  assert.deepEqual(result[0].quality.clarity, { rating: 3, range: [3, 3], probabilities: [0, 0, 1, 0] });
});

test("adjacent quality grades produce a usable ordered score, not a confidence-cutoff blank", () => {
  const payload = response();
  payload.answers[`${slide.concepts[0].id}__clarity`] = {
    type: "score", score: 2.5, probabilities: { "0": 0, "1": 0, "2": 0.5, "3": 0.5 },
  };
  const quality = readDecisions(payload, slide)[0].quality.clarity;
  assert.equal(quality.rating, 3.5);
  assert.deepEqual(quality.range, [3, 4]);
});

test("meaningful-content gate batches new words but permits a final tail and deliberate recheck", () => {
  const text = (length: number) => Array.from({ length }, () => "word").join(" ");
  assert.equal(wordCount("... !!!"), 0);
  assert.equal(wordCount("We're testing next-action feedback."), 4);
  assert.equal(judgeReadiness(text(7), 0, "interval").eligible, false);
  assert.equal(judgeReadiness(text(8), 0, "interval").eligible, true);
  assert.equal(judgeReadiness(text(22), 15, "interval").eligible, false);
  assert.equal(judgeReadiness(text(23), 15, "interval").eligible, true);
  assert.equal(judgeReadiness(text(7), 0, "boundary").eligible, false);
  assert.equal(judgeReadiness(text(8), 0, "boundary").eligible, true);
  assert.equal(judgeReadiness(text(16), 15, "boundary").eligible, true);
  assert.equal(judgeReadiness(text(15), 15, "boundary").eligible, false);
  assert.equal(judgeReadiness(text(15), 15, "manual").eligible, true);
});

test("absent or ambiguous concepts cannot acquire impressive quality ratings", () => {
  for (const coverage of ["not_covered", "uncertain"]) {
    for (const decision of readDecisions(response(coverage), slide)) {
      for (const key of qualityKeys) assert.equal(decision.quality[key].rating, null);
    }
  }
});

test("missing answers, unsupported choices and nonfinite probabilities fail explicitly", () => {
  assert.throws(() => readDecisions({}, slide), /no answers/);
  const missing = response();
  delete missing.answers[`${slide.concepts[0].id}__economy`];
  assert.throws(() => readDecisions(missing, slide), /omitted/);
  const invalid = response();
  invalid.answers[slide.concepts[0].id] = answer("invented", 1);
  assert.throws(() => readDecisions(invalid, slide), /invalid choice/);
  for (const probability of [NaN, Infinity, -0.1, 1.1]) {
    const malformed = response();
    malformed.answers[slide.concepts[0].id] = answer("explained", probability);
    assert.throws(() => readDecisions(malformed, slide), /invalid probability/);
  }
  const malformed = response();
  malformed.answers[`${slide.concepts[0].id}__clarity`] = {
    type: "score", score: 2, probabilities: { "0": 0.5, "1": 0.5, "2": 0, "3": 0 },
  };
  assert.throws(() => readDecisions(malformed, slide), /inconsistent score/);
});

test("PCM encoder clips safely and the server rejects malformed or excessive audio", async () => {
  const wav = Buffer.from(await encodeWav(new Float32Array([-2, 0, 2])).arrayBuffer());
  assert.equal(validateAudio(wav), 16_000);
  assert.equal(wav.readInt16LE(44), -32768);
  assert.equal(wav.readInt16LE(46), 0);
  assert.equal(wav.readInt16LE(48), 32767);
  const bad = Buffer.from(wav);
  bad.writeUInt32LE(500, 40);
  assert.throws(() => validateAudio(bad), /Expected mono/);
  const long = Buffer.from(await encodeWav(new Float32Array(16_000 * 13)).arrayBuffer());
  assert.throws(() => validateAudio(long), /at most 12 seconds/);
});

test("local service denies cross-origin and DNS-rebound hosts", () => {
  assert.ok(sameOrigin("127.0.0.1:4173", "http://127.0.0.1:4173", 4173));
  assert.ok(sameOrigin("localhost:4173", undefined, 4173));
  assert.equal(sameOrigin("127.0.0.1:4173", "https://attacker.example", 4173), false);
  assert.equal(sameOrigin("attacker.example:4173", undefined, 4173), false);
  assert.equal(sameOrigin("127.0.0.1:4173", "null", 4173), false);
});
