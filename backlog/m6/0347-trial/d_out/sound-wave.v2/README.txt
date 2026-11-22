sound_wave — Pixelbolt export

sound_wave.png: transparent RGBA sprite sheet
sound_wave.atlas.json: TexturePacker-style frames, named animation sequences and Aseprite-style frame tags
sound_wave.tres: Godot 4 SpriteFrames; it finds sound_wave.png in its own folder, so keep the two together
sound_wave.css: CSS classes with per-frame timing
frames/: individual PNGs
animations/: animated PNGs (APNG)
sound_wave.pixel.json: editable source
player.js: dependency-free Canvas player
preview.html: open directly in a browser, or serve this folder

Canvas: import { SpritePlayer } from './player.js';
const player = await SpritePlayer.load(canvas, './sound_wave.atlas.json');
player.play('sound_wave');

Godot 4: copy sound_wave.png and sound_wave.tres into one folder of your project, give an AnimatedSprite2D the Sprite Frames sound_wave.tres and play("sound_wave"). Set the node's Texture Filter to Nearest for crisp pixels.

CSS: <link rel="stylesheet" href="sound_wave.css">
<span class="pf-sound_wave pf-sound_wave-sound_wave"></span>

Timing:
sound_wave: 10 frames of 60 ms (16.67 fps), plays once
