telegraph — Pixelbolt export

telegraph.png: transparent RGBA sprite sheet
telegraph.atlas.json: TexturePacker-style frames, named animation sequences and Aseprite-style frame tags
telegraph.tres: Godot 4 SpriteFrames; it finds telegraph.png in its own folder, so keep the two together
telegraph.css: CSS classes with per-frame timing
frames/: individual PNGs
animations/: animated PNGs (APNG)
telegraph.pixel.json: editable source
player.js: dependency-free Canvas player
preview.html: open directly in a browser, or serve this folder

Canvas: import { SpritePlayer } from './player.js';
const player = await SpritePlayer.load(canvas, './telegraph.atlas.json');
player.play('default');

Godot 4: copy telegraph.png and telegraph.tres into one folder of your project, give an AnimatedSprite2D the Sprite Frames telegraph.tres and play("default"). Set the node's Texture Filter to Nearest for crisp pixels.

CSS: <link rel="stylesheet" href="telegraph.css">
<span class="pf-telegraph pf-telegraph-default"></span>

Timing:
default: 4 frames of 120 ms (8.33 fps)
