extends Node2D
## 맵 분위기 연출: 석등 불빛(가산 혼합, 깜빡임), 흩날리는 낙엽, 흐르는 안개.

var player: Node2D
var _glows: Array = []
var _mists: Array = []
var _leaves: CPUParticles2D
var _t := 0.0
var _map_size := Vector2.ZERO


func setup(map_data: Dictionary, p: Node2D) -> void:
	player = p
	z_index = 10
	_map_size = Vector2(MapBuilder.map_pixel_size(map_data))
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	var glow_tex: Texture2D = load("res://assets/ui/glow.png")
	var rows: Array = map_data.get("tiles", [])
	for y in rows.size():
		for x in rows[y].length():
			if rows[y][x] == "L":
				var g := Sprite2D.new()
				g.texture = glow_tex
				g.material = add
				g.scale = Vector2(1.6, 1.6)
				g.position = MapBuilder.tile_center(Vector2i(x, y)) + Vector2(0, -4)
				add_child(g)
				_glows.append(g)
	# 낙엽 (월드 좌표에 남도록 local_coords=false, 화면 위쪽에서 생성)
	_leaves = CPUParticles2D.new()
	_leaves.texture = load("res://assets/ui/leaf.png")
	_leaves.amount = 14
	_leaves.lifetime = 9.0
	_leaves.preprocess = 6.0
	_leaves.local_coords = false
	_leaves.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	_leaves.emission_rect_extents = Vector2(380, 8)
	_leaves.direction = Vector2(1, 1)
	_leaves.spread = 25.0
	_leaves.gravity = Vector2(6, 14)
	_leaves.initial_velocity_min = 10.0
	_leaves.initial_velocity_max = 24.0
	_leaves.angular_velocity_min = -90.0
	_leaves.angular_velocity_max = 90.0
	_leaves.angle_min = 0.0
	_leaves.angle_max = 360.0
	_leaves.scale_amount_min = 1.0
	_leaves.scale_amount_max = 1.6
	_leaves.color = Color(1, 1, 1, 0.85)
	add_child(_leaves)
	# 안개 띠
	var mist_tex: Texture2D = load("res://assets/ui/mist.png")
	for i in 2:
		var m := Sprite2D.new()
		m.texture = mist_tex
		m.scale = Vector2(4.0, 2.5)
		m.modulate = Color(1, 1, 1, 0.22)
		m.position = Vector2(randf() * _map_size.x, _map_size.y * (0.35 + 0.4 * i))
		add_child(m)
		_mists.append(m)


func _process(delta: float) -> void:
	_t += delta
	for i in _glows.size():
		var g: Sprite2D = _glows[i]
		g.modulate.a = 0.75 + 0.2 * sin(_t * 3.1 + i * 1.7) + 0.05 * sin(_t * 11.0 + i)
	if player and is_instance_valid(player):
		_leaves.global_position = player.global_position + Vector2(-60, -230)
	for i in _mists.size():
		var m: Sprite2D = _mists[i]
		m.position.x += delta * (8.0 + i * 5.0)
		if m.position.x - 256 > _map_size.x:
			m.position.x = -256
