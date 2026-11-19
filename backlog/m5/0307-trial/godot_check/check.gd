extends SceneTree
# 0307: each frame as an AtlasTexture (region + margin) of the trimmed atlas, drawn by an AnimatedSprite2D exactly as the export's scene
# does (centered = false, offset = -pivot) in a cell-sized SubViewport with the root at the pivot; the drawn pixels must equal the
# untrimmed cell PNG, and with flip_h must equal the cell flipped. Also: where the pivot pixel (marked in the cell) lands.
func _initialize():
	var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/frames.json"))
	var cell := Vector2i(int(data["cell"][0]), int(data["cell"][1]))
	var pivot := Vector2(data["pivot"][0], data["pivot"][1])
	var atlas := ImageTexture.create_from_image(Image.load_from_file(ProjectSettings.globalize_path("res://data/color.png")))
	var vp := SubViewport.new()
	vp.size = cell
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	root.add_child(vp)
	var holder := Node2D.new()
	holder.position = pivot   # the root of the scene sits at the pivot pixel of the cell
	vp.add_child(holder)
	var spr := AnimatedSprite2D.new()
	spr.centered = false
	spr.offset = -pivot
	holder.add_child(spr)
	var bad := 0
	var bad_flip := 0
	var total := 0
	var first_bad := []
	for f in data["frames"]:
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
		spr.frame = 0
		var want: Image = Image.load_from_file(ProjectSettings.globalize_path("res://data/" + f["cell"]))
		want.convert(Image.FORMAT_RGBA8)
		for flip in [false, true]:
			spr.flip_h = flip
			await process_frame
			await process_frame
			var got: Image = vp.get_texture().get_image()
			got.convert(Image.FORMAT_RGBA8)
			var exp: Image = want.duplicate()
			if flip:
				exp.flip_x()
			var ndiff := 0
			for y in range(cell.y):
				for x in range(cell.x):
					var a: Color = got.get_pixel(x, y)
					var b: Color = exp.get_pixel(x, y)
					if a.a == 0.0 and b.a == 0.0:
						continue
					if not a.is_equal_approx(b):
						ndiff += 1
			if flip:
				if ndiff > 0:
					bad_flip += 1
			else:
				total += 1
				if ndiff > 0:
					bad += 1
					if first_bad.size() < 5:
						first_bad.append("%s/%s/%d (%d px)" % [f["clip"], f["dir"], f["index"], ndiff])
	print("RESULT frames=%d differ_plain=%d differ_flip_h=%d first=%s" % [total, bad, bad_flip, str(first_bad)])
	quit()
