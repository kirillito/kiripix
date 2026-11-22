extends Node2D
## 0347 trial scene: one effect, four quadrants (blend add/mix x lit/unlit) beside Sanjay over the kitchen plate.
## Run: godot --path godot_project --write-movie out.png --fixed-fps 12 --quit-after 40 -- <effect> <route> <frames_root>
const FEET := Vector2(150, 160)
const AT := {
	"hit_spark": {"pos": Vector2(150, 126), "anchor": {"b": Vector2(12, 12), "d": Vector2(12, 12)}, "under": false},
	"sound_wave": {"pos": Vector2(166, 124), "anchor": {"c": Vector2(-6, 32), "d": Vector2(8, 48)}, "under": false},
	"summon_puff": {"pos": Vector2(224, 160), "anchor": {"c": Vector2(24, 34), "d": Vector2(24, 34)}, "under": false},
	"buff_glow": {"pos": Vector2(150, 160), "anchor": {"c": Vector2(24, 54), "d": Vector2(24, 54)}, "under": false},
	"telegraph": {"pos": Vector2(222, 150), "anchor": {"b": Vector2(16, 16), "d": Vector2(16, 16)}, "under": true},
}
const LOOP := {"hit_spark": false, "sound_wave": false, "summon_puff": false, "buff_glow": true, "telegraph": true}


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var effect: String = args[0]
	var route: String = args[1]
	var root: String = args[2]
	var frames := SpriteFrames.new()
	frames.set_animation_loop("default", LOOP[effect])
	frames.set_animation_speed("default", 12)
	var dir := DirAccess.open("%s/%s_%s" % [root, route, effect])
	var names := Array(dir.get_files())
	names.sort()
	for f: String in names:
		if f.ends_with(".png"):
			frames.add_frame("default", ImageTexture.create_from_image(Image.load_from_file("%s/%s_%s/%s" % [root, route, effect, f])))
	var info: Dictionary = AT[effect]
	var quads := [["add", false], ["mix", false], ["add", true], ["mix", true]]
	for i in 4:
		var box := SubViewportContainer.new()
		box.position = Vector2((i % 2) * 336, (i / 2) * 192)
		var view := SubViewport.new()
		view.size = Vector2i(336, 192)
		view.transparent_bg = false
		box.add_child(view)
		add_child(box)
		var plate := Sprite2D.new()
		plate.texture = load("res://ref/room/plate.png")
		plate.centered = false
		view.add_child(plate)
		var mod := CanvasModulate.new()
		mod.color = Color(0.5, 0.5, 0.66)
		view.add_child(mod)
		var light := PointLight2D.new()
		var grad := GradientTexture2D.new()
		grad.fill = GradientTexture2D.FILL_RADIAL
		grad.fill_from = Vector2(0.5, 0.5)
		grad.fill_to = Vector2(1, 0.5)
		grad.width = 256
		grad.height = 256
		var g := Gradient.new()
		g.colors = PackedColorArray([Color(1, 0.9, 0.7), Color(0, 0, 0)])
		grad.gradient = g
		light.texture = grad
		light.position = Vector2(120, 120)
		light.energy = 1.1
		light.texture_scale = 1.0
		view.add_child(light)
		var effect_node := AnimatedSprite2D.new()
		effect_node.sprite_frames = frames
		effect_node.centered = false
		effect_node.position = (info.pos as Vector2) - (info.anchor[route] as Vector2)
		var material := CanvasItemMaterial.new()
		material.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD if quads[i][0] == "add" else CanvasItemMaterial.BLEND_MODE_MIX
		material.light_mode = CanvasItemMaterial.LIGHT_MODE_NORMAL if quads[i][1] else CanvasItemMaterial.LIGHT_MODE_UNSHADED
		effect_node.material = material
		var sanjay: Node2D = (load("res://ref/sanjay/sanjay.tscn") as PackedScene).instantiate()
		sanjay.position = FEET
		(sanjay.get_node("Sprite") as AnimatedSprite2D).play(&"idle_s")
		if info.under:
			view.add_child(effect_node)
			view.add_child(sanjay)
		else:
			view.add_child(sanjay)
			view.add_child(effect_node)
		if effect == "hit_spark" or effect == "sound_wave" or effect == "summon_puff":
			effect_node.set_meta("restart", true)
		effect_node.play("default")
		var label := Label.new()
		label.text = "%s  %s" % [quads[i][0], "lit" if quads[i][1] else "unlit"]
		label.position = Vector2(4, 2)
		view.add_child(label)
	var timer := Timer.new()
	timer.wait_time = 1.0
	timer.autostart = true
	timer.timeout.connect(_restart)
	add_child(timer)


func _restart() -> void:
	for n in find_children("*", "AnimatedSprite2D", true, false):
		if n.has_meta("restart"):
			(n as AnimatedSprite2D).play("default")
