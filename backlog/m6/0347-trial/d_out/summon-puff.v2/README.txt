summon_puff — Pixelbolt export

summon_puff.png: transparent RGBA sprite sheet
summon_puff.atlas.json: TexturePacker-style frames, named animation sequences and Aseprite-style frame tags
summon_puff.tres: Godot 4 SpriteFrames; it finds summon_puff.png in its own folder, so keep the two together
summon_puff.css: CSS classes with per-frame timing
frames/: individual PNGs
animations/: animated PNGs (APNG)
summon_puff.pixel.json: editable source
player.js: dependency-free Canvas player
preview.html: open directly in a browser, or serve this folder

Canvas: import { SpritePlayer } from './player.js';
const player = await SpritePlayer.load(canvas, './summon_puff.atlas.json');
player.play('summon_puff');

Godot 4: copy summon_puff.png and summon_puff.tres into one folder of your project, give an AnimatedSprite2D the Sprite Frames summon_puff.tres and play("summon_puff"). Set the node's Texture Filter to Nearest for crisp pixels.

CSS: <link rel="stylesheet" href="summon_puff.css">
<span class="pf-summon_puff pf-summon_puff-summon_puff"></span>

Timing:
summon_puff: 10 frames of 70 ms (14.29 fps), plays once
