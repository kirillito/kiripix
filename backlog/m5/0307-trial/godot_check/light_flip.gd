extends SceneTree
# Does Godot 4.7 flip the normal map's x when a sprite is flipped (flip_h)? A flat white texture with a normal map that leans +x
# (R 255, G 128, B 128), a DirectionalLight2D at 8 rotations, flip_h off and on; the mean lit brightness of each.
func _lit(angle: float, flip: bool) -> float:
	var vp := SubViewport.new()
	vp.size = Vector2i(8, 8)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var diffuse := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	diffuse.fill(Color(1, 1, 1, 1))
	var normal := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	normal.fill(Color8(255, 128, 255, 255))   # x = +1, y = 0 (z left at 1, the shader normalises)
	var tex := CanvasTexture.new()
	tex.diffuse_texture = ImageTexture.create_from_image(diffuse)
	tex.normal_texture = ImageTexture.create_from_image(normal)
	tex.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	s.flip_h = flip
	vp.add_child(s)
	var light := DirectionalLight2D.new()
	light.rotation = angle
	light.height = 0.1
	light.energy = 1.0
	light.blend_mode = Light2D.BLEND_MODE_ADD
	vp.add_child(light)
	var mod := CanvasModulate.new()
	mod.color = Color(0, 0, 0, 1)
	vp.add_child(mod)
	await process_frame
	await process_frame
	await process_frame
	var img := vp.get_texture().get_image()
	var c := img.get_pixel(4, 4)
	vp.queue_free()
	return c.r
func _initialize():
	var lines := []
	for k in range(8):
		var a := k * PI / 4.0
		var off = await _lit(a, false)
		var on = await _lit(a, true)
		lines.append("angle=%d deg  no_flip=%.3f  flip_h=%.3f" % [k * 45, off, on])
	print("LIGHT_FLIP\n" + "\n".join(lines))
	quit()
