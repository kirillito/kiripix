buff_glow — Pixelbolt export

buff_glow.png: transparent RGBA sprite sheet
buff_glow.atlas.json: TexturePacker-style frames, named animation sequences and Aseprite-style frame tags
buff_glow.tres: Godot 4 SpriteFrames; it finds buff_glow.png in its own folder, so keep the two together
buff_glow.css: CSS classes with per-frame timing
frames/: individual PNGs
animations/: animated PNGs (APNG)
buff_glow.pixel.json: editable source
player.js: dependency-free Canvas player
preview.html: open directly in a browser, or serve this folder

Canvas: import { SpritePlayer } from './player.js';
const player = await SpritePlayer.load(canvas, './buff_glow.atlas.json');
player.play('buff_glow');

Godot 4: copy buff_glow.png and buff_glow.tres into one folder of your project, give an AnimatedSprite2D the Sprite Frames buff_glow.tres and play("buff_glow"). Set the node's Texture Filter to Nearest for crisp pixels.

CSS: <link rel="stylesheet" href="buff_glow.css">
<span class="pf-buff_glow pf-buff_glow-buff_glow"></span>

Timing:
buff_glow: 12 frames of 80 ms (12.5 fps)
