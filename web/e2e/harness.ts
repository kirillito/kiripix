// A real `kiripix serve` on a temporary Project. Tests change the Project through the CLI, as an agent would, and read
// the UI; nothing here imports the UI.

import { execFileSync, spawn, spawnSync, type ChildProcess } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { crc32, deflateSync } from "node:zlib";
import { test as base } from "@playwright/test";

const REPOSITORY = resolve(import.meta.dirname, "..", "..");
const WEB = join(REPOSITORY, "web", "dist");

function kiripixArgs(...args: string[]): string[] {
  return ["run", "--quiet", "--project", REPOSITORY, "kiripix", ...args];
}

type Colour = [number, number, number, number];

// A PNG from a colour for each pixel, so the tests need no image library.
export function png(width: number, height: number, colour: (x: number, y: number) => Colour): Buffer {
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type, "latin1"), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const check = Buffer.alloc(4);
    check.writeUInt32BE(crc32(body));
    return Buffer.concat([length, body, check]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 6, 0, 0, 0], 8);
  const rows = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      rows.set(colour(x, y), y * (width * 4 + 1) + 1 + x * 4);
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// 96 x 64 art, doubled from 48 x 32, in two colours of the default palette split at `edge` (in target pixels).
export function art(edge = 24): Buffer {
  return png(96, 64, (x) => (Math.floor(x / 2) < edge ? [255, 0, 77, 255] : [29, 43, 83, 255]));
}

export class Studio {
  readonly url: string;
  readonly home: string;

  private constructor(
    readonly cwd: string,
    private readonly server: ChildProcess,
    port: number,
    token: string,
  ) {
    this.url = `http://127.0.0.1:${port}/`;
    this.home = `${this.url}#token=${token}`;
  }

  static async start(): Promise<Studio> {
    const cwd = mkdtempSync(join(tmpdir(), "kiripix-e2e-"));
    execFileSync("uv", kiripixArgs("init"), { cwd, stdio: "pipe" });
    const server = spawn("uv", kiripixArgs("serve", "--port", "0", "--print-token", "--web", WEB), {
      cwd,
      stdio: ["ignore", "pipe", "inherit"],
    });
    const ready = await new Promise<{ port: number; token: string }>((done, failed) => {
      let text = "";
      server.stdout!.on("data", (chunk: Buffer) => {
        text += chunk.toString("utf-8");
        const line = text.split("\n")[0];
        if (text.includes("\n")) done(JSON.parse(line) as { port: number; token: string });
      });
      server.once("exit", (code) => failed(new Error(`kiripix serve exited with ${code}`)));
    });
    return new Studio(cwd, server, ready.port, ready.token);
  }

  // A CLI call while the UI is open: an agent at work.
  kiripix(...args: string[]): string {
    return execFileSync("uv", kiripixArgs(...args), { cwd: this.cwd, encoding: "utf-8" });
  }

  json(...args: string[]): { data: Record<string, unknown> } {
    return JSON.parse(this.kiripix(...args, "--json")) as { data: Record<string, unknown> };
  }

  // `run`, which exits 3 where it stops for the Owner: every room stops at a Stage that needs something.
  run(asset: string): void {
    spawnSync("uv", kiripixArgs("run", asset, "--json"), { cwd: this.cwd, encoding: "utf-8" });
  }

  importVariant(asset: string, name: string, content: Buffer): string {
    this.write(name, content);
    return this.json("import", asset, `incoming/${name}`).data.variant as string;
  }

  // A room with its fit waiting for the Owner: an Override on it, then a new Source under it.
  roomInReview(): string {
    const id = this.room();
    this.kiripix("pick", id, this.importVariant(id, "a.png", art(24)));
    this.run(id);
    this.write("paint.png", png(48, 32, (x, y) => (x === 1 && y === 1 ? [0, 0, 0, 255] : [0, 0, 0, 0])));
    this.kiripix("override", id, "fit", "incoming/paint.png");
    this.run(id);
    this.kiripix("pick", id, this.importVariant(id, "b.png", art(10)));
    this.run(id);
    return id;
  }

  write(name: string, content: Buffer): string {
    const path = join(this.cwd, "incoming", name);
    mkdirSync(join(this.cwd, "incoming"), { recursive: true });
    writeFileSync(path, content);
    return path;
  }

  // A 48 x 32 room with a fit that doesn't have to detect its grid.
  room(): string {
    const id = "room.alley";
    this.kiripix("new", "room", "alley", "--view", "top");
    this.kiripix("set", id, "brief", "width=48", "height=32");
    this.kiripix("set", id, "fit", "scale=2");
    return id;
  }

  stop(): void {
    if (process.platform === "win32") {
      try {
        execFileSync("taskkill", ["/pid", String(this.server.pid), "/T", "/F"], { stdio: "pipe" });
      } catch {
        // Already gone.
      }
    } else {
      this.server.kill("SIGKILL");
    }
    rmSync(this.cwd, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

export const test = base.extend<{ studio: Studio }>({
  // eslint-disable-next-line no-empty-pattern
  studio: async ({}, use) => {
    const studio = await Studio.start();
    await use(studio);
    studio.stop();
  },
});

export { expect } from "@playwright/test";
