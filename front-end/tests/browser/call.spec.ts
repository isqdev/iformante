import { expect, test, type Page } from "@playwright/test";
import type { MessageSource } from "../../app/models/message";

test.use({ launchOptions: { args: ["--autoplay-policy=user-gesture-required"] } });

declare global {
  interface Window { callTestMicRequests: number; callTestAudioContexts: AudioContext[] }
}

function audioEvents(seconds = 2, sources: MessageSource[] = []) {
  const pcm = Buffer.alloc(22050 * seconds * 2);
  for (let i = 0; i < pcm.length / 2; i++) pcm.writeInt16LE(Math.round(Math.sin(i * 2 * Math.PI * 180 / 22050) * 8000), i * 2);
  const event = (name: string, data: object) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
  return event("state", { value: "transcribing" }) + event("transcript", { text: "Olá, InFormante." }) + event("answer", { text: "Olá! Como posso ajudar?", message_id: "msgai0001", sources }) + event("state", { value: "speaking" }) + event("audio_format", { sample_rate: 22050, channels: 1, sample_width: 2 }) + event("alignment", { items: [{ phoneme: "a", start: 0, duration: seconds }] }) + event("audio", { sequence: 0, data: pcm.toString("base64") }) + event("audio_done", { samples: pcm.length / 2 }) + event("done", { message_id: "msgai0001", sources });
}

async function fixture(page: Page, seconds = 2, micFailures = 0, options: { sources?: MessageSource[]; signedIn?: boolean; responseGate?: Promise<void> } = {}) {
  let uploads = 0;
  let cancels = 0;
  let playback = "";
  const forms: string[] = [];
  let conversationWrites = 0;
  await page.addInitScript(({ micFailures }) => {
    const testWindow = window;
    testWindow.callTestMicRequests = 0;
    testWindow.callTestAudioContexts = [];
    const BrowserAudioContext = window.AudioContext;
    window.AudioContext = class extends BrowserAudioContext {
      constructor(options?: AudioContextOptions) {
        super(options);
        testWindow.callTestAudioContexts.push(this);
      }
    };
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      testWindow.callTestMicRequests++;
      if (testWindow.callTestMicRequests <= micFailures) throw new DOMException("Microphone denied", "NotAllowedError");
      const context = new AudioContext();
      const oscillator = context.createOscillator();
      oscillator.frequency.value = 250;
      const destination = context.createMediaStreamDestination();
      oscillator.connect(destination);
      oscillator.start();
      // Synthetic input follows the same autoplay policy: it starts only on
      // the first real gesture, never blocking page initialization.
      const resume = () => { void context.resume(); };
      window.addEventListener("keydown", resume, { capture: true });
      window.addEventListener("pointerdown", resume, { capture: true });
      return destination.stream;
    }});
  }, { micFailures });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/content")) return route.fulfill({ path: "tests/fixtures/viewer.pdf", contentType: "application/pdf" });
    if (path === "/api/auth/me") return route.fulfill({ json: options.signedIn ? { id: "testuser1", first_name: "Teste", role: "COMMON" } : null });
    if (path.startsWith("/api/conversations")) {
      if (route.request().method() !== "GET") conversationWrites++;
      return route.fulfill({ json: [] });
    }
    if (path === "/api/call/status") return route.fulfill({ json: { ready: true, voice_ready: true, answer_ready: true, transcription_ready: true } });
    if (path === "/api/call/stream") {
      uploads++;
      forms.push(route.request().postDataBuffer()?.toString() ?? "");
      if (options.responseGate) await options.responseGate;
      return route.fulfill({ contentType: "text/event-stream", body: audioEvents(seconds, options.sources) });
    }
    if (path === "/api/call/cancel") { cancels++; return route.fulfill({ json: { cancelled: true } }); }
    if (path === "/api/call/playback") { playback = route.request().postDataJSON().status; return route.fulfill({ json: { saved: false } }); }
    return route.fulfill({ json: {} });
  });
  await page.goto("/call");
  if (micFailures) await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  else await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
  return { uploads: () => uploads, cancels: () => cancels, playback: () => playback, forms, conversationWrites: () => conversationWrites };
}

async function record(page: Page, requireSpeaking = true) {
  await page.keyboard.down("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "recording");
  await expect(page.getByTestId("call-talk")).toHaveClass(/bg-primary\/90/);
  await expect(page.getByTestId("call-talk")).not.toHaveClass(/text-destructive/);
  await page.waitForTimeout(800);
  await page.keyboard.up("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", requireSpeaking ? "speaking" : /speaking|ready/);
}

test("sidebar opens /call and detailed avatar is scoped to the page", async ({ page }) => {
  await fixture(page);
  await expect(page.getByTestId("call-avatar")).toBeVisible();
  await page.getByRole("button", { name: "Nova conversa", exact: true }).click();
  await expect(page).toHaveURL(/\/$/, { timeout: 15000 });
  await expect(page.getByTestId("call-avatar")).toHaveCount(0);
  await page.getByRole("button", { name: "Chamada", exact: true }).click();
  await expect(page).toHaveURL(/\/call$/);
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
});

test("opening /call prepares the microphone without recording or an enable button", async ({ page }) => {
  const count = await fixture(page);
  expect(await page.evaluate(() => window.callTestMicRequests)).toBe(1);
  await expect(page.getByTestId("call-talk")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Habilitar chamada" })).toHaveCount(0);
  expect(count.uploads()).toBe(0);
  await page.getByRole("button", { name: "Encerrar chamada" }).click();
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "off");
  await page.waitForTimeout(200);
  expect(await page.evaluate(() => window.callTestMicRequests)).toBe(1);
  await expect(page.getByRole("button", { name: "Retomar chamada" })).toBeVisible();
});

test("denied microphone permission offers a manual retry without repeated requests", async ({ page }) => {
  const count = await fixture(page, 2, 1);
  await expect(page.getByText("Permita o microfone para conversar. Verifique também a saída de áudio.")).toBeVisible();
  expect(count.uploads()).toBe(0);
  await page.getByRole("button", { name: "Tentar novamente" }).click();
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
  expect(await page.evaluate(() => window.callTestMicRequests)).toBe(2);
});

test("space records only while held and repeated keydown does not duplicate uploads", async ({ page }) => {
  const count = await fixture(page, 1);
  await page.keyboard.down("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "recording");
  await page.keyboard.down("Space");
  await page.waitForTimeout(800);
  expect(count.uploads()).toBe(0);
  await page.keyboard.up("Space");
  await expect.poll(count.uploads).toBe(1);
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
  expect(count.playback()).toBe("");
});

test("held pointer has the same recording behavior", async ({ page }) => {
  const count = await fixture(page, 1);
  await page.getByTestId("call-talk").hover();
  await page.mouse.down();
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "recording");
  await page.waitForTimeout(800);
  expect(count.uploads()).toBe(0);
  await page.mouse.up();
  await expect.poll(count.uploads).toBe(1);
});

test("space presses during playback do not interrupt or start a recording", async ({ page }) => {
  const count = await fixture(page, 5);
  await record(page);
  await page.keyboard.press("Space");
  await page.keyboard.down("Space");
  await page.waitForTimeout(800);
  await page.keyboard.up("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "speaking");
  await expect(page.getByText(/2 vezes para interromper/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Ver conversa completa" })).toHaveCount(0);
  expect(count.cancels()).toBe(0);
  expect(count.uploads()).toBe(1);
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready", { timeout: 10000 });
  expect(count.playback()).toBe("");
  await page.keyboard.down("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "recording");
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.keyboard.up("Space");
});

test("talk button is unavailable during playback without cancelling it", async ({ page }) => {
  const count = await fixture(page, 5);
  await record(page);
  await expect(page.getByTestId("call-talk")).toBeDisabled();
  const bounds = await page.getByTestId("call-talk").boundingBox();
  if (!bounds) throw new Error("Talk button unavailable");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.down(); await page.mouse.up(); await page.mouse.down(); await page.mouse.up();
  expect(count.cancels()).toBe(0);
  expect(count.uploads()).toBe(1);
  await expect(page.getByTestId("call-talk")).toBeEnabled({ timeout: 10000 });
  expect(count.playback()).toBe("");
});

test("loss of focus discards a held recording", async ({ page }) => {
  const count = await fixture(page);
  await page.keyboard.down("Space");
  await page.waitForTimeout(800);
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.keyboard.up("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
  expect(count.uploads()).toBe(0);
});

test("mouth only articulates during playback and danger button ends the call", async ({ page }) => {
  const count = await fixture(page, 5);
  const mouth = page.getByTestId("call-mouth");
  const closed = await mouth.getAttribute("d");
  await page.keyboard.down("Space");
  await page.waitForTimeout(800);
  expect(await mouth.getAttribute("d")).toBe(closed);
  await page.keyboard.up("Space");
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "speaking");
  await expect.poll(() => mouth.getAttribute("d")).not.toBe(closed);
  const endCall = page.getByRole("button", { name: "Encerrar chamada" });
  await expect(endCall).toHaveClass(/text-destructive/);
  await endCall.click();
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "off");
  await page.waitForTimeout(500);
  await expect.poll(() => mouth.getAttribute("d")).toBe(closed);
  await expect.poll(count.cancels).toBe(1);
  await page.getByRole("button", { name: "Retomar chamada" }).click();
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
});

test("mobile layout has a held touch target and no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixture(page);
  await expect(page.getByText("Uma resposta breve, feita para ouvir.")).toHaveCount(0);
  await expect(page.getByTestId("call-talk")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const stage = await page.locator(".call-stage").boundingBox();
  const main = await page.locator("main.call-page").boundingBox();
  expect(Math.abs(stage!.y + stage!.height / 2 - main!.y - main!.height / 2)).toBeLessThan(2);
  await page.screenshot({ path: "test-results/call-mobile.png", fullPage: true });
});

test("desktop call layout renders without browser errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await fixture(page);
  await expect(page.getByRole("heading", { name: "Fale com o InFormante" })).toBeVisible();
  await expect(page.getByText("Sua pergunta", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Resposta do InFormante", { exact: true })).toHaveCount(0);
  const avatar = await page.getByTestId("call-avatar").boundingBox();
  const main = await page.locator("main.call-page").boundingBox();
  expect(Math.abs(avatar!.x + avatar!.width / 2 - main!.x - main!.width / 2)).toBeLessThan(2);
  await page.screenshot({ path: "test-results/call-desktop.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("PDF sources use the same fullscreen viewer as /docs", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const count = await fixture(page, 1, 0, { sources: [{ document_id: "doc123456", filename: "Documento.pdf", source_type: "PDF", url: null }] });
  await record(page, false);
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready");
  await page.getByRole("button", { name: "Documento.pdf" }).click();
  await expect(page.getByLabel("Página atual")).toBeVisible();
  const dialog = await page.getByRole("dialog").boundingBox();
  expect(dialog?.width).toBe(390);
  expect(dialog?.height).toBe(844);
  await page.getByRole("dialog").focus();
  await page.keyboard.press("Space");
  expect(count.uploads()).toBe(1);
  await page.getByLabel("Fechar visualizador").click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("web sources open the source URL instead of a blank PDF modal", async ({ page, context }) => {
  await context.route("https://call-source.example/**", (route) => route.fulfill({ contentType: "text/html", body: "<title>Fonte</title>" }));
  await fixture(page, 1, 0, { sources: [{ document_id: "web123456", filename: "Fonte web", source_type: "WEB_PAGE", url: "https://call-source.example/edital" }] });
  await record(page, false);
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Fonte web" }).click();
  const popup = await popupPromise;
  await expect(popup).toHaveURL("https://call-source.example/edital");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("signed-in calls retain temporary context and show the requested loading indicator", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => { releaseResponse = resolve; });
  const count = await fixture(page, 1, 0, { signedIn: true, responseGate });
  await page.keyboard.down("Space");
  await expect.poll(() => page.evaluate(() => window.callTestAudioContexts.every((context) => context.state === "running"))).toBe(true);
  await page.waitForTimeout(800);
  await page.keyboard.up("Space");
  try {
    await expect(page.getByRole("img", { name: "Gerando resposta" })).toBeVisible();
    await expect(page.getByText("Entendendo sua pergunta…", { exact: true })).toBeVisible();
  } finally {
    releaseResponse();
  }
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready", { timeout: 10000 });
  await record(page, false);
  await expect(page.locator("main.call-page")).toHaveAttribute("data-state", "ready", { timeout: 10000 });
  expect(count.forms).toHaveLength(2);
  expect(count.forms[1]).toContain("Olá, InFormante.");
  expect(count.forms[1]).not.toContain('name="conversation_id"');
  expect(count.conversationWrites()).toBe(0);
  expect(count.playback()).toBe("");
  await expect(page).toHaveURL(/\/call$/);
  expect(errors).toEqual([]);
});
