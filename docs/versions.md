# Pinned external versions

Pinned at M0 (2026-11-02). Exports and renders are reproducible only against these versions; changing one is a
deliberate decision, recorded here with its date.

| Tool | Pinned | Exact release used | Why this one |
|---|---|---|---|
| Godot | **4.7** | 4.7.2-stable (2026-08-18) | Newest stable. 4.8 is in beta (4.8-beta2, 2026-10-29). |
| Blender | **5.2 LTS** | 5.2.3 (2026-10-22) | Newest LTS, supported until July 2028. 5.3 is in beta and isn't LTS. |
| ffmpeg | the `imageio-ffmpeg` wheel **0.8.1** (`uv.lock`) | 9.0.2 (Windows x86-64 wheel, checked 2026-11-27) | A sound's decoding, resampling, loudness, denoise and Vorbis encoding (ADR 0016). Pinned through the lock, not the system. |

- Godot 4.7 confirmed by the owner on 2026-11-02. Plan: move to 4.8 once it leaves beta.
- Godot: the `version` in `[export.godot]` of `kiripix.toml` defaults to `"4.7"`. Patch releases (4.7.x) don't change
  the scene and resource formats Kiripix writes.
- Blender: headless renders run on 5.2 LTS. Patch releases (5.2.x) are fine; a new LTS is a deliberate upgrade.
- ffmpeg: it comes from the `imageio-ffmpeg==0.8.1` wheel and runs only through `kiripix/recipes/ffmpeg.py`; another wheel
  version, or a system ffmpeg, is refused (`ffmpeg.wrong_version`, fix `uv sync`). The first line of `ffmpeg -version` is a
  computed input (`ffmpeg.version`) of every Stage that runs it, so a lock update makes those Stages stale. The bundled
  binary is a **GPL** build (it has libx264 and the like): a dev-time tool that ships nothing to the game (the game gets only
  the OGG files it makes), so the GPL doesn't reach the game or Kiripix's own MIT code, which runs it as a separate
  process. Checked on Windows on 2026-11-27: it decodes WAV, FLAC, MP3 and OGG, and has `libvorbis`, `loudnorm`, `afftdn`,
  `rubberband` and `atempo`. The Linux wheel wasn't checked (no Linux machine); it may bundle another ffmpeg version.

Sources: [Godot download archive](https://godotengine.org/download/archive/),
[Godot release policy](https://docs.godotengine.org/en/stable/about/release_policy.html),
[Blender LTS](https://www.blender.org/download/lts/),
[Blender 5.2 LTS release notes](https://developer.blender.org/docs/release_notes/5.2/).
