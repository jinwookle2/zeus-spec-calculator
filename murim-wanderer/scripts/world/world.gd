extends Node2D
## 필드 장면. GameState.current_map 의 맵 데이터를 읽어
## 타일맵 / NPC / 조사 지점 / 출구·전투 트리거 / 플레이어를 배치한다.

const PlayerScene := preload("res://scenes/player/player.tscn")
const NpcScene := preload("res://scenes/npc/npc.tscn")
const MapEventScript := preload("res://scripts/world/map_event.gd")
const AreaTriggerScript := preload("res://scripts/world/area_trigger.gd")
const GuideArrowScript := preload("res://scripts/world/guide_arrow.gd")
const FishingScript := preload("res://scripts/ui/fishing.gd")
const ShopScript := preload("res://scripts/ui/shop.gd")
const AmbienceScript := preload("res://scripts/world/ambience.gd")

var fishing: CanvasLayer
var shop: CanvasLayer

var map_data: Dictionary = {}
var player: CharacterBody2D

@onready var entities: Node2D = $Entities
@onready var triggers: Node2D = $Triggers
@onready var hud = $HUD
@onready var dialogue_box = $DialogueBox
@onready var pause_menu = $PauseMenu
@onready var touch_controls = $TouchControls


func _ready() -> void:
	if not GameState.in_game:
		# 에디터에서 이 장면을 직접 실행한 경우 새 게임으로 시작
		GameState.new_game()
	map_data = DataDB.get_map(GameState.current_map)
	if map_data.is_empty():
		push_error("맵을 불러오지 못했습니다: %s" % GameState.current_map)
		return
	_build_map()
	_spawn_npcs()
	_spawn_events()
	_spawn_player()
	GameState.unlock_input("transition")
	GameState.autosave.call_deferred()  # 맵 진입(이동·전투 복귀·이어하기) 시 자동 저장
	var arrow := Node2D.new()
	arrow.set_script(GuideArrowScript)
	arrow.player = player
	arrow.z_index = 5
	add_child(arrow)
	fishing = CanvasLayer.new()
	fishing.set_script(FishingScript)
	add_child(fishing)
	shop = CanvasLayer.new()
	shop.set_script(ShopScript)
	add_child(shop)
	var amb := Node2D.new()
	amb.set_script(AmbienceScript)
	add_child(amb)
	amb.setup(map_data, player)
	hud.set_map_name(str(map_data.get("name", "")))
	hud.menu_pressed.connect(_open_menu)
	pause_menu.message.connect(hud.toast)
	if GameState.last_battle_result.get("result", "") == "lose":
		GameState.last_battle_result = {}
		_after_defeat.call_deferred()
	else:
		GameState.last_battle_result = {}


func _build_map() -> void:
	var layer := MapBuilder.build_layer(map_data)
	add_child(layer)
	move_child(layer, 0)


func _spawn_npcs() -> void:
	for d in map_data.get("npcs", []):
		var hide_flag := str(d.get("hide_if_flag", ""))
		if hide_flag != "" and GameState.has_flag(hide_flag):
			continue
		var npc := NpcScene.instantiate()
		npc.setup(d)
		entities.add_child(npc)


func _spawn_events() -> void:
	for d in map_data.get("events", []):
		match d.get("type", "talk"):
			"talk":
				var ev := Node2D.new()
				ev.set_script(MapEventScript)
				ev.setup(d)
				triggers.add_child(ev)
			"battle_trigger":
				var area := Area2D.new()
				area.set_script(AreaTriggerScript)
				area.setup("battle", d)
				triggers.add_child(area)
	for d in map_data.get("exits", []):
		var area := Area2D.new()
		area.set_script(AreaTriggerScript)
		area.setup("exit", d)
		triggers.add_child(area)


func _spawn_player() -> void:
	player = PlayerScene.instantiate()
	player.position = GameState.player_position
	entities.add_child(player)
	var cam: Camera2D = player.get_node("Camera")
	var size := MapBuilder.map_pixel_size(map_data)
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = size.x
	cam.limit_bottom = size.y
	cam.reset_smoothing()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("menu") and not GameState.is_input_locked() and not pause_menu.is_open():
		_open_menu()
		get_viewport().set_input_as_handled()


## 대화 효과로 여는 창: "shop" | "fishing"
func open_overlay(kind: String) -> void:
	match kind:
		"shop":
			shop.open_shop()
		"fishing":
			fishing.start()


func _open_menu() -> void:
	if dialogue_box.is_busy() or SceneRouter.is_busy() or shop.is_open() or fishing.is_open():
		return
	pause_menu.open()


func _after_defeat() -> void:
	await get_tree().create_timer(0.4).timeout
	await dialogue_box.show_lines([
		{"speaker": "", "text": "...정신을 차려 보니 청풍관 앞이었다."},
		{"speaker": "도장 사범 백운", "text": "허허, 기절해서 실려 왔구나. 나한테 말을 걸면 기운을 불어넣어 주마."},
	])
