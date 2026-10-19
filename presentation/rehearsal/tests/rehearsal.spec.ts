import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { judgingPolicy, qualityKeys, rubrics } from "../src/concepts.ts";

async function setup(page: Page) {
  await page.route(/\/api\/transcribe\?preview=1$/, route => route.fulfill({ json: { text: "" } }));
  await page.route("**/api/status", route => route.fulfill({ json: {
    csrf: "test", endpoint: "https://example.services.ai.azure.com/providers/microsoft/v1/systemone",
    deployment: "Decision-1", ready: true,
    checks: [{ name: "Offline test setup", ok: true, detail: "Local fixtures; no cloud calls." }],
  } }));
}

function decisions(id: string, rating = 3, coverage = "explained") {
  return rubrics.find(slide => slide.id === id)!.concepts.map(concept => ({
    conceptId: concept.id, coverage, confidence: 0.99,
    quality: Object.fromEntries(qualityKeys.map(key => [key, {
      rating, range: [Math.floor(rating), Math.ceil(rating)],
      probabilities: Array.from({ length: 4 }, (_, index) => Math.max(0, 1 - Math.abs(index - (rating - 1)))),
    }])),
  }));
}

test("normal navigation stays intact; rehearsal requires explicit consent", async ({ page }) => {
  await setup(page);
  await page.goto("/deck.html");
  await expect(page.locator(".slide.active")).toHaveAttribute("data-rehearsal-id", "opening");
  await expect(page.locator("#rehearsalPanel")).toHaveCount(0);
  await page.locator("#next").click();
  await expect(page.locator(".slide.active")).toHaveAttribute("data-rehearsal-id", "agenda");
  await page.locator("#rehearsalButton").click();
  await expect(page.locator("#rhStart")).toBeDisabled();
  await page.locator("#rhConsent").check();
  await expect(page.locator("#rhStart")).toBeEnabled();
  await page.locator("#rhClose").focus();
  await page.keyboard.press("Escape");
  await expect(page.locator("#rehearsalPanel")).toBeHidden();
  await expect(page.locator("#rehearsalButton")).toBeFocused();
});

test("countdown, quality feedback, late transcript attribution, pause and review", async ({ page }) => {
  await setup(page);
  const spoken: string[] = [];
  const judged: string[] = [];
  let releaseFirst: (() => void) | undefined;
  const firstChunk = new Promise<void>(resolve => { releaseFirst = resolve; });
  await page.route("**/api/transcribe", async route => {
    spoken.push("chunk");
    if (spoken.length === 1) await firstChunk;
    await route.fulfill({ json: { text: "One agent follows a measured path from prompt to evaluation and gated release." } });
  });
  await page.route("**/api/judge", async route => {
    const input = route.request().postDataJSON();
    judged.push(input.slideId);
    await route.fulfill({ json: { decisions: decisions(input.slideId), latencyMs: 35 } });
  });
  await page.clock.install();
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect(page.locator("#rhMode")).toHaveText("Live");
  await expect.poll(() => spoken.length, { timeout: 12_000 }).toBeGreaterThan(0);
  await page.clock.runFor(65_000);
  await expect(page.locator("#rhClock")).toHaveClass(/rh-over/);
  await page.locator("#next").click();
  await expect(page.locator("#rhTitle")).toHaveText("Agenda");
  await expect(page.locator("#rhClock")).not.toHaveClass(/rh-over/);
  await expect(page.locator("#rhClock")).toHaveText(/^0(1:00|0:[3-5]\d)$/);
  await expect(page.locator("#rhOverspill")).toHaveText(/^\+00:\d\d over$/);
  await expect(page.locator("#rhTalkLeft")).toHaveText(/^\d\d:\d\d$/);
  releaseFirst!();
  await expect.poll(() => judged.includes("opening")).toBe(true);
  await expect(page.locator("#rhTranscript")).toHaveText("No speech captured yet.");
  await page.locator("#rhPause").click();
  await expect(page.locator("#rhMode")).toHaveText("Paused");
  const frozen = await page.locator("#rhClock").textContent();
  await page.clock.runFor(20_000);
  await expect(page.locator("#rhClock")).toHaveText(frozen!);
  await page.locator("#rhPause").click();
  await expect(page.locator("#rhMode")).toHaveText("Live");
  await page.clock.runFor(5000);
  await expect(page.locator("#rhClock")).not.toHaveText(frozen!);
  await page.locator("#rhPause").click();
  await page.locator("#rhStop").click();
  await expect(page.locator("#rhReview")).toBeVisible();
  await page.getByRole("button", { name: /^1\. From Prompt to Production/ }).click();
  await expect(page.locator("#rhConcepts")).toContainText("3.0/4");
  await expect(page.locator("#rhTranscript")).toContainText("One agent");
  await page.locator("#rhDetails > summary").click();
  await expect(page.locator("#rhPlayback")).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page.locator("#rhExport").click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("rehearsal-session.json");
  page.once("dialog", dialog => void dialog.accept());
  await page.locator("#rhNew").click();
  await expect(page.locator("#rhSetup")).toBeVisible();
  await expect(page.locator("#rhStart")).toBeDisabled();
  await expect(page.locator("#rhTranscript")).toHaveText("No speech captured yet.");
});

test("judge failure stays explicit, and successful recheck clears the error", async ({ page }) => {
  await setup(page);
  let calls = 0;
  let captured = false;
  await page.route("**/api/transcribe", async route => {
    const first = !captured;
    captured = true;
    await route.fulfill({ json: { text: first ?
      "One purchasing advice agent moves from a first prompt through traces, evaluation, optimisation and a gated production release." : "" } });
  });
  await page.route("**/api/judge", async route => {
    calls++;
    if (calls === 1) return route.fulfill({ status: 502, json: { error: "Decision-1 unavailable. Retry." } });
    const { slideId } = route.request().postDataJSON();
    await route.fulfill({ json: { decisions: decisions(slideId), latencyMs: 35 } });
  });
  await page.clock.install();
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect.poll(() => captured, { timeout: 12_000 }).toBe(true);
  await expect(page.locator("#rhTranscript")).toContainText("One purchasing");
  await page.clock.runFor(10_000);
  await expect(page.locator("#rhError")).toContainText("Decision-1 unavailable");
  await expect(page.locator("#rhConcepts")).not.toContainText("Landed");
  await page.locator("#rhPause").click();
  await page.locator("#rhDetails > summary").click();
  await page.locator("#rhJudge").click();
  await expect(page.locator("#rhConcepts")).toContainText("Landed");
  await expect(page.locator("#rhError")).toBeHidden();
  await page.locator("#rhStop").click();
});

test("microphone denial is explicit and recoverable without leaving a running clock", async ({ page, context }) => {
  await setup(page);
  await context.clearPermissions();
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Denied", "NotAllowedError");
    };
  });
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect(page.locator("#rhError")).toContainText("Microphone permission denied");
  await expect(page.locator("#rhStart")).toBeEnabled();
  await expect(page.locator("#rhLive")).toBeHidden();
});

test("too little speech does not trigger interval, pause or finish judging", async ({ page }) => {
  await setup(page);
  let captured = false;
  let judged = 0;
  await page.route("**/api/transcribe", async route => {
    const first = !captured;
    captured = true;
    await route.fulfill({ json: { text: first ? "Hello everyone." : "" } });
  });
  await page.route("**/api/judge", async route => {
    judged++;
    await route.fulfill({ json: { decisions: decisions("opening"), latencyMs: 35 } });
  });
  await page.clock.install();
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect.poll(() => captured, { timeout: 12_000 }).toBe(true);
  await page.clock.runFor(30_000);
  await page.locator("#rhPause").click();
  await page.locator("#rhStop").click();
  await expect(page.locator("#rhMode")).toHaveText("Finished");
  expect(judged).toBe(0);
  await expect(page.locator("#rhConcepts")).not.toContainText("/4");
  await expect(page.locator("#rhStatus")).toHaveText("More speech needed");
});

test("new speech during an in-flight check is assessed after pause and updates visible scores", async ({ page }) => {
  await setup(page);
  const firstText = "We follow one purchasing agent from its first prompt through traces and evaluation to improvement and a gated production release.";
  const tail = "The important distinction is that a convincing answer is not enough: we need measured evidence before releasing an improvement.";
  let captured = 0;
  const requests: string[] = [];
  let releaseFirst!: () => void;
  let releaseSecond!: () => void;
  const firstGate = new Promise<void>(resolve => { releaseFirst = resolve; });
  const secondGate = new Promise<void>(resolve => { releaseSecond = resolve; });
  await page.route("**/api/transcribe", async route => {
    captured++;
    await route.fulfill({ json: { text: captured === 1 ? firstText : captured === 2 ? tail : "" } });
  });
  await page.route("**/api/judge", async route => {
    const input = route.request().postDataJSON();
    requests.push(input.transcript);
    const first = requests.length === 1;
    await (first ? firstGate : secondGate);
    await route.fulfill({ json: {
      decisions: decisions(input.slideId, first ? 1.5 : 3.5, first ? "mentioned" : "explained"),
      latencyMs: 35,
    } });
  });
  await page.clock.install();
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect(page.locator("#rhTranscript")).toContainText(firstText, { timeout: 12_000 });
  await page.clock.runFor(10_000);
  await expect.poll(() => requests.length).toBe(1);
  await expect(page.locator("#rhTranscript")).toContainText(tail, { timeout: 12_000 });
  await page.locator("#rhPause").click();
  releaseFirst();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[0]).toBe(firstText);
  expect(requests[1]).toBe(`${firstText} ${tail}`);
  await expect(page.locator("#rhConcepts")).toContainText("1.5/4");
  await page.locator("#rhDetails > summary").click();
  await expect(page.locator("#rhJudged")).toContainText("New speech not yet assessed");
  releaseSecond();
  await expect(page.locator("#rhConcepts")).toContainText("3.5/4");
  await expect(page.locator("#rhConcepts")).toContainText("Landed");
  await expect(page.locator("#rhAssessed")).toHaveText(`${firstText} ${tail}`);
  await expect(page.locator("#rhJudged")).toContainText("All captured speech assessed");
  await page.locator("#rhStop").click();
});

test("all three concepts and quality scores fit the live laptop panel without explanatory clutter", async ({ page }) => {
  await setup(page);
  let captured = false;
  await page.route("**/api/transcribe", async route => {
    captured = true;
    await route.fulfill({ json: { text: "Foundry IQ supplies the rules, Fabric IQ supplies budget state and Work IQ identifies today's authorised approver. These sample tools are local stand-ins." } });
  });
  await page.route("**/api/judge", async route => route.fulfill({ json: {
    decisions: decisions("grounding", 3.5), latencyMs: 35,
  } }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.clock.install();
  await page.goto("/deck.html?rehearsal=1#slide-6");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect.poll(() => captured, { timeout: 12_000 }).toBe(true);
  await expect(page.locator("#rhTranscript")).toContainText("Foundry IQ supplies");
  await page.clock.runFor(10_000);
  await expect(page.locator(".rh-quality strong")).toHaveCount(9);
  await expect(page.locator("#rhDetails")).toBeHidden();
  await expect(page.getByText("How quality is scored")).toHaveCount(0);
  await expect(page.locator("#rhConcepts")).not.toContainText("%");
  const lastScore = await page.locator(".rh-quality strong").last().boundingBox();
  expect(lastScore!.y + lastScore!.height).toBeLessThanOrEqual(720);
  await page.locator("#rhStop").click();
});

test("rehearsal fits laptop and narrow screens without clipped controls", async ({ page }) => {
  await setup(page);
  await page.goto("/deck.html?rehearsal=1");
  for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.locator("#rhClose")).toBeVisible();
    const geometry = await page.evaluate(() => {
      const panel = document.getElementById("rehearsalPanel")!;
      const scroll = panel.querySelector(".rh-scroll")!;
      const button = document.getElementById("rehearsalButton")!.getBoundingClientRect();
      return {
        panel: panel.getBoundingClientRect().toJSON(),
        overflow: scroll.scrollWidth - scroll.clientWidth,
        buttonRight: button.right,
        buttonBottom: button.bottom,
        width: window.innerWidth,
        height: window.innerHeight,
      };
    });
    expect(geometry.panel.right).toBeLessThanOrEqual(viewport.width);
    expect(geometry.panel.bottom).toBeLessThanOrEqual(viewport.height);
    expect(geometry.overflow).toBeLessThanOrEqual(1);
    expect(geometry.buttonRight).toBeLessThanOrEqual(viewport.width);
    expect(geometry.buttonBottom).toBeLessThanOrEqual(viewport.height);
    const full = await page.locator("#fullscreenButton").boundingBox();
    expect(full!.x + full!.width).toBeLessThanOrEqual(viewport.width);
  }
});

test("the panel resizes by drag and keyboard, stays bounded and is remembered", async ({ page }) => {
  await setup(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/deck.html?rehearsal=1");
  const panel = page.locator("#rehearsalPanel");
  const handle = page.locator("#rhResize");
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + 4, box.y + 300);
  await page.mouse.down();
  await page.mouse.move(1280 - 600, box.y + 300, { steps: 5 });
  await page.mouse.up();
  expect(Math.round((await panel.boundingBox())!.width)).toBe(600);
  expect(Math.round((await page.locator(".app").boundingBox())!.width)).toBe(680);
  await handle.focus();
  await page.keyboard.press("ArrowRight");
  await expect(handle).toHaveAttribute("aria-valuenow", "584");
  const moved = (await handle.boundingBox())!;
  await page.mouse.move(moved.x + 4, box.y + 300);
  await page.mouse.down();
  await page.mouse.move(10, box.y + 300, { steps: 5 });
  await page.mouse.up();
  await expect(handle).toHaveAttribute("aria-valuenow", "896");
  await page.reload();
  await expect(page.locator("#rhResize")).toHaveAttribute("aria-valuenow", "896");
  await page.locator("#rhResize").dblclick();
  await expect(page.locator("#rhResize")).toHaveAttribute("aria-valuenow", "384");
});

test("Copy for LLM gives the full slide transcript plus the exact model request and response", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await setup(page);
  let count = 0;
  await page.route("**/api/transcribe", route => route.fulfill({ json: { text: `Sentence ${++count} explains one agent moving from prompt to a measured gated release.` } }));
  await page.route("**/api/judge", async route => {
    const input = route.request().postDataJSON();
    await route.fulfill({ json: {
      decisions: decisions(input.slideId), latencyMs: 20,
      request: { state: { presenter_transcript: input.transcript } }, response: { answers: { marker: "raw-output" } },
    } });
  });
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect.poll(() => count, { timeout: 30_000 }).toBeGreaterThan(1);
  await page.locator("#rhPause").click();
  await expect(page.locator("#rhStatus")).toHaveText("Up to date", { timeout: 15_000 });
  await page.locator("#rhCopy").click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const full = await page.locator("#rhTranscript").textContent();
  expect(full).toContain("Sentence 2");
  expect(copied).toContain(full!);
  expect(copied).toContain("The last assessment used this full transcript.");
  expect(copied).toContain(`"presenter_transcript": "${full}"`);
  expect(copied).toContain("raw-output");
});

test("live view shows the latest heard words and when a Decision-1 request is in flight", async ({ page }) => {
  await setup(page);
  let count = 0;
  let release: (() => void) | undefined;
  await page.route("**/api/transcribe", route => route.fulfill({ json: { text: `Phrase ${++count} says visibility is not correctness for this agent trace today.` } }));
  await page.route("**/api/judge", async route => {
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ json: { decisions: decisions(route.request().postDataJSON().slideId), latencyMs: 20 } });
  });
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect(page.locator("#rhJudgeNext")).toHaveText(`next: ${judgingPolicy.newWords} more words`);
  await expect(page.locator("#rhHeardText")).toContainText("today.", { timeout: 30_000 });
  await expect(page.locator("#rhJudgeText")).toContainText("Sending", { timeout: 30_000 });
  await expect(page.locator("#rhJudgeNext")).toBeHidden();
  await expect(page.locator("#rhJudgeText")).toContainText("to Decision-1");
  release!();
  await expect(page.locator("#rhJudgeText")).toContainText("Decision-1 scored", { timeout: 10_000 });
  await expect(page.locator("#rhJudgeNext")).toHaveText(/^next(: \d+ more words?| in \ds)$/);
});

test("provisional words appear in the ticker before the clip is final", async ({ page }) => {
  await setup(page);
  await page.route(/\/api\/transcribe\?preview=1$/, route => route.fulfill({ json: { text: "provisional words arriving" } }));
  await page.route(/\/api\/transcribe$/, route => route.fulfill({ json: { text: "" } }));
  await page.goto("/deck.html?rehearsal=1");
  await page.locator("#rhConsent").check();
  await page.locator("#rhStart").click();
  await expect(page.locator("#rhHeardText .rh-provisional")).toHaveText(/provisional words arriving/, { timeout: 15_000 });
  await page.locator("#rhPause").click();
  await expect(page.locator("#rhHeardText")).not.toContainText("provisional");
});
