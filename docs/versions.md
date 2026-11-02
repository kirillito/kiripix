# Pinned external versions

Pinned at M0 (2026-11-02). Exports and renders are reproducible only against these versions; changing one is a
deliberate decision, recorded here with its date.

| Tool | Pinned | Exact release used | Why this one |
|---|---|---|---|
| Godot | **4.7** | 4.7.2-stable (2026-08-18) | Newest stable. 4.8 is in beta (4.8-beta2, 2026-10-29). |
| Blender | **5.2 LTS** | 5.2.3 (2026-10-22) | Newest LTS, supported until July 2028. 5.3 is in beta and isn't LTS. |

- Godot 4.7 confirmed by the owner on 2026-11-02. Plan: move to 4.8 once it leaves beta.
- Godot: the `version` in `[export.godot]` of `kiripix.toml` defaults to `"4.7"`. Patch releases (4.7.x) don't change
  the scene and resource formats Kiripix writes.
- Blender: headless renders run on 5.2 LTS. Patch releases (5.2.x) are fine; a new LTS is a deliberate upgrade.

Sources: [Godot download archive](https://godotengine.org/download/archive/),
[Godot release policy](https://docs.godotengine.org/en/stable/about/release_policy.html),
[Blender LTS](https://www.blender.org/download/lts/),
[Blender 5.2 LTS release notes](https://developer.blender.org/docs/release_notes/5.2/).
