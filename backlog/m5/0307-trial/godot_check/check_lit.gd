extends SceneTree
# 0307: the export's way: AtlasTexture over a CanvasTexture (diffuse + normal atlases). Trimmed atlas with margin, lit by a
# DirectionalLight2D (so the normal map is used), against the same frame as a whole cell in its own CanvasTexture. Every 7th frame,
# flip_h off and on, two light angles.
func _img(p: String) -> ImageTexture:
	return ImageTexture.create_from_image(Image.load_from_file(ProjectSettings.globalize_path(p)))
func _initialize():
	var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/frames.json"))
	var cell := Vector2i(int(data["cell"][0]), int(data["cell"][1]))
	var pivot := Vector2(data["pivot"][0], data["pivot"][1])
	var atlas := CanvasTexture.new()
	atlas.diffuse_texture = _img("res://data/color.png")
	atlas.normal_texture = _img("res://data/normal.png")
	atlas.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var vp := SubViewport.new()
	vp.size = cell
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var holder := Node2D.new()
	holder.position = pivot
	vp.add_child(holder)
	var spr := AnimatedSprite2D.new()
	spr.centered = false
	spr.offset = -pivot
	holder.add_child(spr)
	var light := DirectionalLight2D.new()
	light.height = 0.5
	light.energy = 1.0
	vp.add_child(light)
	var mod := CanvasModulate.new()
	mod.color = Color(0.25, 0.25, 0.25, 1)
	vp.add_child(mod)
	var ref := Sprite2D.new()
	ref.centered = false
	ref.position = Vector2.ZERO
	var rvp := SubViewport.new()
	rvp.size = cell
	rvp.transparent_bg = true
	rvp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(rvp)
	rvp.add_child(ref)
	var rlight := DirectionalLight2D.new()
	rlight.height = 0.5
	rvp.add_child(rlight)
	var rmod := CanvasModulate.new()
	rmod.color = Color(0.25, 0.25, 0.25, 1)
	rvp.add_child(rmod)
	var total := 0
	var bad := 0
	var firsts := []
	var n := 0
	for f in data["frames"]:
		n += 1
		if n % 7 != 0:
			continue
		var at := AtlasTexture.new()
		at.atlas = atlas
		var r = f["region"]
		var m = f["margin"]
		at.region = Rect2(r[0], r[1], r[2], r[3])
		at.margin = Rect2(m[0], m[1], m[2], m[3])
		var sf := SpriteFrames.new()
		sf.add_frame("default", at)
		spr.sprite_frames = sf
		spr.animation = "default"
		var whole := CanvasTexture.new()
		whole.diffuse_texture = _img("res://data/" + f["cell"])
		whole.normal_texture = _img("res://data/" + str(f["cell"]).replace(".png", "_n.png"))
		whole.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		ref.texture = whole
		for flip in [false, true]:
			for ang in [0.8, 2.4]:
				spr.flip_h = flip
				ref.flip_h = flip
				light.rotation = ang
				rlight.rotation = ang
				await process_frame
				await process_frame
				var a: Image = vp.get_texture().get_image()
				var b: Image = rvp.get_texture().get_image()
				a.convert(Image.FORMAT_RGBA8)
				b.convert(Image.FORMAT_RGBA8)
				var nd := 0
				for y in range(cell.y):
					for x in range(cell.x):
						var pa: Color = a.get_pixel(x, y)
						var pb: Color = b.get_pixel(x, y)
						if pa.a == 0.0 and pb.a == 0.0:
							continue
						if absf(pa.r - pb.r) > 0.01 or absf(pa.g - pb.g) > 0.01 or absf(pa.b - pb.b) > 0.01 or absf(pa.a - pb.a) > 0.01:
							nd += 1
				total += 1
				if nd > 0:
					bad += 1
					if firsts.size() < 5:
						firsts.append("%s/%s/%d flip=%s (%d px)" % [f["clip"], f["dir"], f["index"], str(flip), nd])
	print("RESULT_LIT renders=%d differ=%d first=%s" % [total, bad, str(firsts)])
	quit()
