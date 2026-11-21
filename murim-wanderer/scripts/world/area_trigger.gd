extends Area2D
## 사각 영역 트리거. kind = "exit" (맵 이동) 또는 "battle" (대사 후 전투).
## 플레이어가 영역 안에서 시작한 경우(전투·맵 이동 후 복귀 등)는 한 번 벗어날 때까지 무시해 즉시 재발동을 막는다.

var kind := "exit"
var def: Dictionary = {}
var _ignore_until_exit := false
var _fired := false


func setup(p_kind: String, p_def: Dictionary) -> void:
	kind = p_kind
	def = p_def
	name = "%s_%s" % [kind, str(def.get("id", def.get("to", "")))]
	var r: Array = def.get("rect", [0, 0, 1, 1])
	var tile_pos := Vector2(int(r[0]), int(r[1])) * MapBuilder.TILE
	var tile_size := Vector2(int(r[2]), int(r[3])) * MapBuilder.TILE
	position = tile_pos + tile_size / 2.0
	var shape := RectangleShape2D.new()
	shape.size = tile_size
	var cs := CollisionShape2D.new()
	cs.shape = shape
	add_child(cs)
	collision_layer = 0
	collision_mask = 2  # 플레이어 레이어


func _ready() -> void:
	monitoring = true
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	# 플레이어가 이 영역 안(또는 바로 옆)에서 시작하면, 한 번 벗어날 때까지 무시
	var r: Array = def.get("rect", [0, 0, 1, 1])
	var area := Rect2(Vector2(int(r[0]), int(r[1])) * MapBuilder.TILE, Vector2(int(r[2]), int(r[3])) * MapBuilder.TILE)
	_ignore_until_exit = area.grow(12).has_point(GameState.player_position)


func _on_body_exited(body: Node) -> void:
	if body.is_in_group("player"):
		_ignore_until_exit = false


func _on_body_entered(body: Node) -> void:
	if _ignore_until_exit or _fired or not body.is_in_group("player"):
		return
	match kind:
		"exit":
			_fired = true
			var spawn: Array = def.get("spawn", [1, 1])
			GameState.travel_to(str(def["to"]), Vector2i(int(spawn[0]), int(spawn[1])), str(def.get("facing", "down")))
		"battle":
			var skip := str(def.get("skip_if_flag", ""))
			if skip != "" and GameState.has_flag(skip):
				return
			if GameState.is_input_locked():
				return
			_fired = true
			await _run_battle_event(body)
			_fired = false


func _run_battle_event(player: Node) -> void:
	GameState.lock_input("event")
	var npc: Node = null
	for n in get_tree().get_nodes_in_group("npc"):
		if n.npc_id() == str(def.get("npc", "")):
			npc = n
	if npc:
		npc.face_toward(player.global_position)
		npc.hop()
		player.set_facing(SpriteFramesBuilder.dir_name(npc.global_position - player.global_position))
	await get_tree().create_timer(0.3).timeout
	GameState.unlock_input("event")
	var box := get_tree().get_first_node_in_group("dialogue_box")
	if box:
		await box.run(str(def.get("dialogue", "")))
	var flag := str(def.get("skip_if_flag", ""))
	GameState.start_battle(str(def.get("battle", "")), flag, str(def.get("npc", "")))
