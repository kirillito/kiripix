// The flows of ticket 0351 (spec §11): the district view's rooms that wait for a Source, with `to-paint` and `inbox`.

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { art, expect, test, type Studio } from "./harness";

const TEMPLATE = "A {{ view }}-view room, {{ width }}x{{ height }} px. {{ mood }}.\n";

// Two rooms with a brief built and no Source, and a third with its Source picked.
function waiting(studio: Studio): void {
  mkdirSync(join(studio.cwd, "style", "prompts"), { recursive: true });
  writeFileSync(join(studio.cwd, "style", "prompts", "room.j2"), TEMPLATE, "utf-8");
  for (const name of ["ch05_a", "ch05_b", "ch05_c"]) {
    const id = `room.${name}`;
    studio.kiripix("new", "room", name, "--view", "top");
    studio.kiripix("set", id, "brief", "width=48", "height=32", `mood=${name}`);
    studio.kiripix("run", id, "brief");
  }
  studio.kiripix("pick", "room.ch05_c", studio.importVariant("room.ch05_c", "c.png", art(24)));
}

const at = (studio: Studio, glob: string) => `${studio.url}?district=${encodeURIComponent(glob)}#${studio.home.split("#")[1]}`;

test("a room without a Source has a tile that copies its prompt and names the file", async ({ page, context, studio }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  waiting(studio);
  await page.goto(at(studio, "room.ch05_*"));
  const tile = page.getByTestId("waiting-room.ch05_a");
  await expect(tile).toBeVisible();
  await expect(page.getByTestId("waiting-room.ch05_c")).toHaveCount(0);
  await expect(page.getByTestId("waiting-name-room.ch05_a")).toHaveText("ch05_a.png");

  await page.getByTestId("waiting-copy-room.ch05_a").click();
  await expect(page.getByTestId("waiting-copy-room.ch05_a")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("48x32 px. ch05_a.");
  await page.screenshot({ path: "shots/district-waiting.png" });
});

test("dropping a PNG on a tile imports one Variant", async ({ page, studio }) => {
  waiting(studio);
  await page.goto(at(studio, "room.ch05_*"));
  const tile = page.getByTestId("waiting-room.ch05_a");
  await expect(tile).toBeVisible();
  const data = await page.evaluateHandle((bytes) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array(bytes)], "painted.png", { type: "image/png" }));
    return transfer;
  }, [...art(24)]);
  await tile.dispatchEvent("drop", { dataTransfer: data });
  // The Variant is stored but not picked, so the room still waits on its Source (`to-paint`'s own rule).
  await expect.poll(() => (studio.json("show", "room.ch05_a").data.variants as unknown[]).length, { timeout: 30000 }).toBe(1);
  await expect(page.getByTestId("waiting-note")).toHaveCount(0);
});

test("Check the inbox files by name and lists what it left", async ({ page, studio }) => {
  waiting(studio);
  studio.write("room.ch05_a.png", art(24));
  studio.write("nothing.png", art(10));
  mkdirSync(join(studio.cwd, "inbox"), { recursive: true });
  for (const name of ["room.ch05_a.png", "nothing.png"]) {
    writeFileSync(join(studio.cwd, "inbox", name), readIncoming(studio, name));
  }
  await page.goto(at(studio, "room.ch05_*"));
  await page.getByTestId("inbox-check").click();
  await expect(page.getByTestId("inbox-summary")).toContainText("1 imported, 1 left");
  await expect(page.getByTestId("inbox-file-inbox/nothing.png")).toHaveAttribute("data-outcome", "unmatched");
  await expect(page.getByTestId("inbox-lone-room.ch05_a")).toBeVisible();
  await page.screenshot({ path: "shots/district-inbox.png" });
});

import { readFileSync } from "node:fs";
function readIncoming(studio: Studio, name: string): Buffer {
  return readFileSync(join(studio.cwd, "incoming", name));
}
