// Ticket 0360 (ADR 0015, spec §6.3, §11): the NPC screen and a crowd's strip on the status board, against a real `kiripix serve` on a
// temporary Project and the fake Blender of tests/fixtures. One character chain is built (slow on the fake Blender): a base and two
// Wearables, a ramp table with named choices, an NPC and a crowd of two.

import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Studio } from "./harness";

const BODY = "character.zed";
const CHARACTERS = join(import.meta.dirname, "..", "..", "tests", "fixtures", "characters");
const SHOTS = join(import.meta.dirname, "..", "shots");
const HAIR = "wearable.hair";
const CAP = "wearable.cap";
const NPC = "npc.guard";

function build(studio: Studio): void {
  appendFileSync(
    join(studio.cwd, "kiripix.toml"),
    '\n[[character.ramps]]\nname = "hair"\nlength = 2\nchoices = { auburn = [[0, 0, 0], [29, 43, 83]], blond = ["#5f574f", "#83769c"] }\n' +
      '\n[[character.ramps]]\nname = "top"\nlength = 2\nchoices = { red = [[95, 87, 79], [131, 118, 156]] }\n',
  );
  studio.kiripix("new", "character", "zed");
  const variant = studio.json("import", BODY, join(CHARACTERS, "rigged.glb")).data.variant as string;
  studio.kiripix("pick", BODY, variant);
  studio.kiripix(
    "decide", BODY, "clips", "--decision",
    JSON.stringify({ decision: "clip", data: { name: "idle", source: "idle", start: 0, end: 2, fps: 12, loop: true } }),
  );
  studio.kiripix("set", BODY, "palette", "colors=4");
  for (const stage of ["model", "rig", "clips", "render", "palette", "finish", "sheet"]) studio.kiripix("run", BODY, stage);
  for (const [id, name, order] of [[HAIR, "hair", 10], [CAP, "cap", 20]] as const) {
    studio.kiripix("new", "wearable", name, "--body", BODY);
    const own = studio.json("import", id, join(CHARACTERS, "rigged.glb")).data.variant as string;
    studio.kiripix("pick", id, own);
    studio.kiripix("set", id, "palette", "colors=4");
    studio.kiripix("set", id, "sheet", `order=${order}`);
    for (const stage of ["model", "rig", "render", "palette", "finish", "sheet"]) studio.kiripix("run", id, stage);
  }
  studio.kiripix("new", "npc", "guard", "--base", BODY);
  studio.kiripix("set", NPC, "choose", `wearables=${HAIR}`, "colours=hair=auburn");
  studio.kiripix("run", NPC, "choose");
  studio.kiripix("new", "npc", "mob", "--base", BODY, "--count", "2", "--seed", "3");
  for (const id of ["npc.mob_01", "npc.mob_02"]) studio.kiripix("run", id, "choose");
}

const param = (studio: Studio, name: string) =>
  ((studio.json("show", NPC).data.stages as { stage: string; params: Record<string, string> }[]).find((one) => one.stage === "choose")!.params[name]);

test("an NPC is dressed by one set at a time, and a crowd re-rolls from the board", async ({ page, segmentingStudio: studio }) => {
  test.setTimeout(360_000); // the character chain and a crowd on the fake Blender, then the screen
  build(studio);
  const sets: string[][] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/set")) sets.push((JSON.parse(request.postData() ?? "{}") as { assignments: string[] }).assignments);
  });
  await page.goto(studio.home);

  // The board: the crowd's strip, with a re-roll on each NPC.
  await expect(page.getByTestId("crowd-strip-mob")).toBeVisible();
  await expect(page.getByTestId("crowd-npc-npc.mob_01")).toBeVisible();
  await expect(page.getByTestId("crowd-npc-npc.mob_02")).toBeVisible();
  const before = studio.json("show", "npc.mob_01").data.stages as { stage: string; params: Record<string, string> }[];
  const mob = JSON.stringify(before.find((one) => one.stage === "choose")!.params);
  await page.getByTestId("reroll-npc.mob_01").click();
  await expect(async () => {
    const after = studio.json("show", "npc.mob_01").data.stages as { stage: string; params: Record<string, string> }[];
    expect(JSON.stringify(after.find((one) => one.stage === "choose")!.params)).not.toBe(mob);
  }).toPass();
  await page.screenshot({ path: join(SHOTS, "0360-npc-crowd.png") });

  // The screen: the figure at a whole-number zoom, the base's Wearables, a swatch per Part.
  await page.getByTestId(`board-${NPC}`).getByRole("button", { name: /choose/ }).click();
  const figure = page.getByTestId("npc-preview");
  await expect(figure).toBeVisible();
  await expect(figure).toHaveAttribute("data-zoom", "2");
  await expect(figure).toHaveAttribute("data-wearing", HAIR);
  await expect(figure).toHaveAttribute("data-colours", "hair=auburn");
  await expect(page.getByTestId(`npc-wear-${HAIR}`)).toBeChecked();
  await expect(page.getByTestId(`npc-wear-${CAP}`)).not.toBeChecked();
  await expect(page.getByTestId("swatch-hair-auburn")).toHaveAttribute("aria-pressed", "true");
  expect(await figure.evaluate((image: HTMLImageElement) => [image.naturalWidth, image.width, getComputedStyle(image).imageRendering])).toEqual([
    Number(await figure.getAttribute("data-width")),
    Number(await figure.getAttribute("data-width")),
    "pixelated",
  ]);
  await page.keyboard.press("z");
  await expect(figure).toHaveAttribute("data-zoom", "3");
  await page.getByTestId("npc-zoom-2").click();
  await expect(figure).toHaveAttribute("data-zoom", "2");
  const first = await figure.getAttribute("src");

  // Putting the cap on is one `set` of `wearables`, and the figure is drawn again.
  sets.length = 0;
  await page.getByTestId(`npc-wear-${CAP}`).click();
  await expect(figure).toHaveAttribute("data-wearing", `${HAIR},${CAP}`);
  expect(sets).toEqual([[`wearables=${HAIR},${CAP}`]]);
  expect(param(studio, "wearables")).toBe(`${HAIR},${CAP}`);
  await expect(figure).not.toHaveAttribute("src", first!);

  // Picking a colour is one `set` of `colours`.
  sets.length = 0;
  await page.getByTestId("swatch-hair-blond").click();
  await expect(figure).toHaveAttribute("data-colours", "hair=blond");
  expect(sets).toEqual([["colours=hair=blond"]]);
  await page.getByTestId("swatch-top-red").click();
  await expect(figure).toHaveAttribute("data-colours", "hair=blond,top=red");
  expect(param(studio, "colours")).toBe("hair=blond,top=red");

  // Reordering is one `set` that writes the moved Wearable's own order: the cap (top) dragged under the hair.
  sets.length = 0;
  await page.getByTestId(`npc-wearable-${CAP}`).dragTo(page.getByTestId(`npc-wearable-${HAIR}`));
  await expect(figure).toHaveAttribute("data-wearing", `${CAP},${HAIR}`);
  expect(sets).toEqual([[`wearables=${CAP}@0,${HAIR}`]]);
  await page.getByTestId(`npc-up-${CAP}`).click();
  await expect(figure).toHaveAttribute("data-wearing", `${HAIR},${CAP}`);
  await page.screenshot({ path: join(SHOTS, "0360-npc-screen.png") });

  // A choice renamed in kiripix.toml: `npc.colour_choice` names the Part, and the finding jumps to it.
  const toml = join(studio.cwd, "kiripix.toml");
  writeFileSync(toml, readFileSync(toml, "utf-8").replace("blond =", "ginger ="));
  await page.getByRole("button", { name: "Reload" }).click(); // a hand edit is not in the change record
  await expect(page.getByTestId("finding-npc.colour_choice")).toBeVisible();
  await page.getByTestId("finding-npc.colour_choice").click();
  await expect(page.getByTestId("npc-part-hair")).toHaveAttribute("data-focused", "true");
  await page.screenshot({ path: join(SHOTS, "0360-npc-finding.png") });
});
