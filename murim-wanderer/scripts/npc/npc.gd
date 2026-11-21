extends StaticBody2D
## 맵 데이터로 배치되는 NPC. 말을 걸면 플레이어 쪽을 보고 대사를 출력한다.
## def.battle 이 있으면 대사 후 전투를 시작한다.

var def: Dictionary = {}
var facing := "down"
var _look_timer := 0.0
var _home_facing := "down"

@onready var sprite: AnimatedSprite2D = $Sprite


func setup(npc_def: Dictionary) -> void:
	def = npc_def
	name = "NPC_" + str(def.get("id", "npc"))
	var tile: Array = def.get("tile", [0, 0])
	position = MapBuilder.tile_center(Vector2i(int(tile[0]), int(tile[1])))
	facing = str(def.get("facing", "down"))
	_home_facing = facing


func _ready() -> void:
	add_to_group("interactable")
	add_to_group("npc")
	var sprite_id := str(def.get("sprite", "villager"))
	sprite.sprite_frames = SpriteFramesBuilder.from_sheet("res://assets/characters/%s.png" % sprite_id)
	sprite.play("idle_" + facing)
	_look_timer = randf_range(2.0, 5.0)


func npc_id() -> String:
	return str(def.get("id", ""))


func display_name() -> String:
	return str(def.get("name", ""))


func _process(delta: float) -> void:
	# 가끔 두리번거리기 (허수아비 등 정적 스프라이트 제외)
	if bool(def.get("static_sprite", false)) or GameState.is_input_locked():
		return
	_look_timer -= delta
	if _look_timer <= 0.0:
		_look_timer = randf_range(2.5, 6.0)
		var dirs := ["down", "left", "right", _home_facing, _home_facing]
		face(dirs[randi() % dirs.size()])


func face(dir: String) -> void:
	facing = dir
	sprite.play("idle_" + dir)


func face_toward(pos: Vector2) -> void:
	if bool(def.get("static_sprite", false)):
		return
	face(SpriteFramesBuilder.dir_name(pos - global_position))


func emote(text: String = "!") -> void:
	var l := UiKit.label(text, 12, Color8(30, 22, 22))
	var bubble := PanelContainer.new()
	bubble.add_theme_stylebox_override("panel", UiKit.box(Color8(244, 236, 216), Color8(30, 22, 22), 1, 2))
	bubble.add_child(l)
	bubble.position = Vector2(-7, -50)
	bubble.z_index = 20
	add_child(bubble)
	bubble.scale = Vector2(0.2, 0.2)
	var t := create_tween()
	t.tween_property(bubble, "scale", Vector2.ONE, 0.12).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_interval(0.6)
	t.tween_property(bubble, "modulate:a", 0.0, 0.2)
	t.tween_callback(bubble.queue_free)


func interact(player: Node2D) -> void:
	face_toward(player.global_position)
	emote("!" if not def.has("battle") else "!!")
	hop()
	var box := get_tree().get_first_node_in_group("dialogue_box")
	if box:
		var acts: Dictionary = await box.run(str(def.get("dialogue", "")))
		_open_overlay(acts)
	if def.has("battle"):
		hop()
		GameState.start_battle(str(def["battle"]), str(def.get("win_flag", "")), npc_id())
	else:
		face(_home_facing)


func hop() -> void:
	var base := -8.0
	var t := create_tween()
	t.tween_property(sprite, "position:y", base - 6.0, 0.06)
	t.tween_property(sprite, "position:y", base, 0.06)


func _open_overlay(acts: Dictionary) -> void:
	var w := get_tree().current_scene
	if acts.has("open") and w and w.has_method("open_overlay"):
		w.open_overlay(str(acts["open"]))
