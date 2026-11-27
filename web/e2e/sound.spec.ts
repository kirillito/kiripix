// Ticket 0398 (ADR 0016, spec §6.8, §11): the Sound screen, against a real `kiripix serve` on a temporary Project. The recording is made
// here from noise bursts at known times; ffmpeg is the Project's own. The Owner imports it with its Provenance, keeps four Takes,
// reorders them, listens, tunes one Variation and approves the export, all in the page.

import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Studio } from "./harness";

const SHOTS = join(import.meta.dirname, "..", "shots");
const ASSET = "sound.steps";
const RATE = 44100;
const CLICKS = [0.5, 1.2, 2.0, 2.7, 3.4];

// A 16-bit mono WAV: faint noise with a decaying burst at each time.
function recording(): Buffer {
  const frames = 4 * RATE;
  const samples = new Int16Array(frames);
  let seed = 7;
  const noise = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 2 ** 31 - 1;
  };
  for (let i = 0; i < frames; i++) samples[i] = Math.round(noise() * 3);
  for (const time of CLICKS) {
    const start = Math.floor(time * RATE);
    for (let i = 0; i < 0.4 * RATE && start + i < frames; i++) {
      samples[start + i] += Math.round(noise() * Math.exp(-i / RATE / 0.025) * 16000);
    }
  }
  const data = Buffer.from(samples.buffer);
  const head = Buffer.alloc(44);
  head.write("RIFF", 0);
  head.writeUInt32LE(36 + data.length, 4);
  head.write("WAVEfmt ", 8);
  head.writeUInt32LE(16, 16);
  head.writeUInt16LE(1, 20);
  head.writeUInt16LE(1, 22);
  head.writeUInt32LE(RATE, 24);
  head.writeUInt32LE(RATE * 2, 28);
  head.writeUInt16LE(2, 32);
  head.writeUInt16LE(16, 34);
  head.write("data", 36);
  head.writeUInt32LE(data.length, 40);
  return Buffer.concat([head, data]);
}

const keepSpans = (studio: Studio) => {
  const stage = (studio.json("show", ASSET).data.stages as { stage: string; decisions: { name: string; data: { takes: { start_ms: number }[] } }[] }[]).find((one) => one.stage === "keep")!;
  return stage.decisions.filter((one) => one.name === "keep").at(-1)?.data.takes ?? [];
};

test("the Owner keeps four steps, hears them at a walking pace, tunes one and approves the export without the CLI", async ({ page, studio }) => {
  test.setTimeout(240_000);
  mkdirSync(SHOTS, { recursive: true });
  const game = join(studio.cwd, "game");
  mkdirSync(game);
  writeFileSync(join(game, "project.godot"), "config_version=5\n");
  const toml = join(studio.cwd, "kiripix.toml");
  const text = readFileSync(toml, "utf-8");
  writeFileSync(toml, text.replace('# project = "C:/Workspace/my-game"   # the Godot project to export into', 'project = "game"'));
  studio.kiripix("new", "sound", "steps", "--use", "sfx");
  studio.write("steps.wav", recording());

  const decides: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/decide")) decides.push((JSON.parse((JSON.parse(request.postData() ?? "{}") as { decision: string }).decision) as { decision: string }).decision);
  });
  await page.goto(studio.home);
  await page.getByTestId(`board-${ASSET}`).getByRole("button", { name: /source/ }).click();

  // The recording is imported with its Provenance and picked, in the page.
  await expect(page.getByTestId("sound-no-recording")).toBeVisible();
  await page.getByTestId("provenance-author").fill("A. Foley");
  await page.getByTestId("provenance-licence").fill("CC0 1.0");
  await page.getByTestId("provenance-url").fill("https://example.com/steps");
  await page.getByTestId("sound-import-input").setInputFiles(join(studio.cwd, "incoming", "steps.wav"));
  await expect(page.locator("[data-testid^='variant-'][data-picked='true']")).toHaveCount(1);
  await page.locator("[data-testid^='recording-play-']").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-plays", "1");

  // A Run builds source and slice, then stops at `keep`, which waits for the Owner (an agent may record it, so it is not a queue stop).
  await page.getByTestId("run").click();
  await expect(page.getByTestId("stage-slice")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("stage-keep")).toHaveAttribute("data-status", "needs-input");

  // The waveform with its five Takes; a click on a Take plays it as recorded.
  await page.getByTestId("stage-slice").click();
  await expect(page.getByTestId("sound-summary")).toContainText("5 Takes");
  await expect(page.getByTestId("sheet-box-5")).toBeVisible();
  await expect(page.getByTestId("sound-sheet-image")).toBeVisible();
  await page.getByTestId("sheet-box-2").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", "source:2");
  await expect(page.getByTestId("sound-take-2")).toHaveAttribute("data-selected", "true");

  // Keep: four ticks are four Decisions, each the whole list by spans.
  await page.getByTestId("stage-keep").click();
  decides.length = 0;
  for (const take of [1, 2, 3, 4]) {
    await page.getByTestId(`take-keep-${take}`).click();
    await expect(page.getByTestId(`kept-${take}`)).toBeVisible();
  }
  expect(decides).toEqual(["keep", "keep", "keep", "keep"]);
  expect(keepSpans(studio)).toHaveLength(4);
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "1");

  // Reordering is one Decision: Variation 2 moves up (Take 2 becomes the first).
  decides.length = 0;
  await page.getByTestId("kept-up-2").click();
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "2");
  expect(decides).toEqual(["keep"]);
  // ... and by dragging: Take 4 (last) onto the first place.
  await page.getByTestId("kept-4").dragTo(page.getByTestId("kept-1"));
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "4");
  expect(decides).toEqual(["keep", "keep"]);
  await page.getByTestId("kept-up-1").isDisabled();
  await page.getByTestId("kept-down-1").click();
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "2");
  await expect(page.getByTestId("kept-2")).toHaveAttribute("data-take", "4");
  // Ctrl+Z undoes the last Decision.
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "4");
  await page.keyboard.press("Control+Shift+z");
  await expect(page.getByTestId("kept-1")).toHaveAttribute("data-take", "2");

  // The kept set in sequence at the interval, as the game plays it.
  await page.getByTestId("seq-interval").fill("200");
  await page.getByTestId("seq-play").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", /(seq:source:\d,){3}seq:source:\d$/, { timeout: 5000 });
  await page.screenshot({ path: join(SHOTS, "0398-sound-keep.png") });

  // Run builds process and export; the Variations can be played processed, and A/B'd.
  await page.getByTestId("run").click();
  await expect(page.getByTestId("stage-process")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("stage-export")).toHaveAttribute("data-status", "done");
  await page.getByTestId("stage-process").click();
  await expect(page.getByTestId("variation-4")).toBeVisible();
  await expect(page.getByTestId("variation-1")).toContainText("2"); // Variation 1 is Take 2
  await page.getByTestId("variation-play-1").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", /processed:1$/);
  await page.getByTestId("heard-processed").click();
  await page.keyboard.press("3");
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", /processed:\d$/);
  await page.getByTestId("variation-ab-2").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", /source:4,processed:2$/);

  // The processing parameters are the Stage's own, from `describe`; one Variation is tuned by one Decision.
  await expect(page.getByTestId("sound-tune")).toBeVisible();
  decides.length = 0;
  await page.getByTestId("tune-speed").fill("1.5");
  await page.getByTestId("tune-apply").click();
  await expect(page.getByTestId("stage-process")).toHaveAttribute("data-status", "stale");
  expect(decides).toEqual(["tune"]); // the A/B'd Variation 2
  await page.getByTestId("run").click();
  await expect(page.getByTestId("variation-2")).toHaveAttribute("data-overridden", "true");
  await expect(page.getByTestId("variation-1")).toHaveAttribute("data-overridden", "false");
  await page.screenshot({ path: join(SHOTS, "0398-sound-process.png") });

  // Export: asks first, then the Owner approves; the files are in the game.
  await expect(page.getByTestId("stage-export")).toHaveAttribute("data-status", "done");
  await page.getByTestId("stage-export").click();
  await expect(page.getByTestId("export-file-4")).toBeVisible();
  await page.getByTestId("export-play-1").click();
  await expect(page.getByTestId("sound-log")).toHaveAttribute("data-log", /export:1$/);
  await page.getByTestId("sound-export-check").click();
  await expect(page.getByTestId("sound-export-plan")).toContainText("would write");
  expect(readdirSync(game)).toEqual(["project.godot"]); // nothing is written until it is approved
  await page.screenshot({ path: join(SHOTS, "0398-sound-export.png") });
  await page.getByTestId("sound-export-approve").click();
  await expect(page.getByTestId("sound-exported")).toBeVisible();
  const folder = join(game, "audio", "sfx");
  expect(readdirSync(folder).filter((file) => file.endsWith(".ogg")).sort()).toEqual(["steps_1.ogg", "steps_2.ogg", "steps_3.ogg", "steps_4.ogg"]);

  // A slice that cuts the Takes differently moves their bounds: `keep` is waiting for the Owner's review, and the queue lists it.
  studio.kiripix("set", ASSET, "slice", "tail=60");
  studio.run(ASSET);
  await page.getByRole("button", { name: "Reload" }).click();
  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 1");
  await page.getByTestId("queue-open").click();
  await expect(page.getByTestId("queue-type")).toHaveText("Review");
  await expect(page.getByTestId("stage-title")).toHaveText("keep");
  await expect(page.getByTestId("sound-screen")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "0398-sound-queue.png") });
  await page.keyboard.press("a");
  await expect(page.getByTestId("queue-open")).toHaveText("Queue · 0");
});
