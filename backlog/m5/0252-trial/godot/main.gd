extends Node2D
## Trial 0252. Left: the Plate and Layers as CanvasTextures with normal maps, lit by a PointLight2D that follows
## the mouse. Right: the same Plate and Layers plain (no normal map), same light. Same relative light position.
## Run:  Godot --path <this folder>             (move the mouse; wheel = light height; L toggles the left normal maps)
## Auto: Godot --path <this folder> -- --auto [--shots=<dir>]   (scripted light path; saves frames and quits)

const LAYERS := ["layer1", "layer3", "pipe_e", "pipe_w"]
const W := 400
var light_l: PointLight2D
var light_r: PointLight2D
var left_sprites: Array = []
var use_normals := true
var auto := false
var shots := ""
var t := 0.0
var frame := 0

func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	auto = "--auto" in args
	for a in args:
		if a.begins_with("--shots="):
			shots = a.substr(8)
	var cm := CanvasModulate.new()
	cm.color = Color(0.12, 0.12, 0.15)
	add_child(cm)
	for side in 2:
		var root := Node2D.new()
		root.position = Vector2(side * W, 0)
		add_child(root)
		var names: Array = ["plate"] + LAYERS
		for n in names:
			var s := Sprite2D.new()
			s.centered = false
			var tex := CanvasTexture.new()
			var base: String = "plate" if n == "plate" else "layer." + n
			tex.diffuse_texture = load("res://room/%s.png" % base)
			if side == 0:
				tex.normal_texture = load("res://room/%s.n.png" % base)
			tex.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			s.texture = tex
			s.light_mask = 1 << side
			root.add_child(s)
			if side == 0:
				left_sprites.append(s)
	light_l = _make_light(1 << 0)
	light_r = _make_light(1 << 1)
	_place(Vector2(200, 280))

func _make_light(mask: int) -> PointLight2D:
	var l := PointLight2D.new()
	var g := GradientTexture2D.new()
	g.fill = GradientTexture2D.FILL_RADIAL
	g.fill_from = Vector2(0.5, 0.5)
	g.fill_to = Vector2(1.0, 0.5)
	g.width = 512
	g.height = 512
	var gr := Gradient.new()
	gr.set_color(0, Color(1.0, 0.95, 0.8))
	gr.set_color(1, Color(0, 0, 0))
	g.gradient = gr
	l.texture = g
	l.texture_scale = 1.1
	l.energy = 3.5
	l.height = 70.0
	l.range_item_cull_mask = mask
	add_child(l)
	return l

func _place(p: Vector2) -> void:
	var px := fposmod(p.x, W)
	light_l.position = Vector2(px, p.y)
	light_r.position = Vector2(px + W, p.y)

func _process(dt: float) -> void:
	if auto:
		t += 1.0 / 30.0
		# a slow sweep down the left walkway edge, then across the wall block and the pit rim
		var p := Vector2(200 + 150 * sin(t * 0.9), 280 + 220 * sin(t * 0.55 + 1.0))
		_place(p)
		frame += 1
		if shots != "" and frame % 3 == 0 and frame >= 3:
			get_viewport().get_texture().get_image().save_png("%s/f%04d.png" % [shots, frame / 3])
		if frame >= 3 * 90:
			get_tree().quit()
	else:
		_place(get_global_mouse_position())

func _input(e: InputEvent) -> void:
	if e is InputEventMouseButton and e.pressed:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP:
			light_l.height += 8; light_r.height += 8
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			light_l.height = max(4, light_l.height - 8); light_r.height = light_l.height
	if e is InputEventKey and e.pressed and e.keycode == KEY_L:
		use_normals = not use_normals
		for s in left_sprites:
			(s.texture as CanvasTexture).normal_texture = (load(s.texture.diffuse_texture.resource_path.replace(".png", ".n.png")) if use_normals else null)
