hit_spark — Pixelbolt export

hit_spark.png: transparent RGBA sprite sheet
hit_spark.atlas.json: TexturePacker-style frames, named animation sequences and Aseprite-style frame tags
hit_spark.tres: Godot 4 SpriteFrames; it finds hit_spark.png in its own folder, so keep the two together
hit_spark.css: CSS classes with per-frame timing
frames/: individual PNGs
animations/: animated PNGs (APNG)
hit_spark.pixel.json: editable source
player.js: dependency-free Canvas player
preview.html: open directly in a browser, or serve this folder

Canvas: import { SpritePlayer } from './player.js';
const player = await SpritePlayer.load(canvas, './hit_spark.atlas.json');
player.play('hit_spark');

Godot 4: copy hit_spark.png and hit_spark.tres into one folder of your project, give an AnimatedSprite2D the Sprite Frames hit_spark.tres and play("hit_spark"). Set the node's Texture Filter to Nearest for crisp pixels.

CSS: <link rel="stylesheet" href="hit_spark.css">
<span class="pf-hit_spark pf-hit_spark-hit_spark"></span>

Timing:
hit_spark: 6 frames of 50 ms (20 fps), plays once
