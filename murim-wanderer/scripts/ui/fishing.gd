extends CanvasLayer
## 연못 낚시 미니게임. 좌우로 움직이는 찌가 붉은 구간에 있을 때 [확인]을 누르면 낚는다.
## 결과 확률은 data/items/economy.json 의 fishing.table.

signal finished(result: String)

var _root: Control
var _bar: Panel
var _zone: ColorRect
var _marker: ColorRect
var _info: Label
var _pos := 0.0       # 0..1
var _dir := 1.0
var _zone_start := 0.4
var _zone_width := 0.2
var _active := false
var _cfg: Dictionary = {}
var rng := RandomNumberGenerator.new()

const BAR_W := 300.0


func _ready() -> void:
	layer = 45
	process_mode = Node.PROCESS_MODE_ALWAYS
	rng.randomize()
	_cfg = DataDB.economy.get("fishing", {})
	_build()
	_root.visible = false


func _build() -> void:
	_root = Control.new()
	_root.theme = UiKit.theme()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var box := UiKit.panel_container(12)
	box.set_anchors_preset(Control.PRESET_CENTER)
	box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	box.grow_vertical = Control.GROW_DIRECTION_BOTH
	_root.add_child(box)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	box.add_child(v)
	var title := UiKit.brush_label("연못 낚시", 30, UiKit.TEXT)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	_bar = Panel.new()
	_bar.custom_minimum_size = Vector2(BAR_W, 22)
	_bar.add_theme_stylebox_override("panel", UiKit.box(Color8(40, 64, 72), UiKit.GOLD, 1, 0))
	v.add_child(_bar)
	_zone = ColorRect.new()
	_zone.color = Color8(176, 54, 42, 200)
	_bar.add_child(_zone)
	_marker = ColorRect.new()
	_marker.color = Color8(240, 226, 200)
	_marker.size = Vector2(4, 22)
	_bar.add_child(_marker)
	_info = UiKit.label("", 12)
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_info.custom_minimum_size = Vector2(BAR_W, 30)
	v.add_child(_info)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 8)
	v.add_child(row)
	var cast_b := UiKit.button("챔질!", Vector2(100, 30))
	cast_b.pressed.connect(strike)
	row.add_child(cast_b)
	var quit_b := UiKit.button("그만하기", Vector2(100, 30))
	quit_b.pressed.connect(stop)
	row.add_child(quit_b)


func is_open() -> bool:
	return _root.visible


func start() -> void:
	_root.visible = true
	GameState.lock_input("fishing")
	_new_round()


func _new_round() -> void:
	var zmin := float(_cfg.get("zone_min", 0.14))
	var zmax := float(_cfg.get("zone_max", 0.24))
	_zone_width = rng.randf_range(zmin, zmax)
	_zone_start = rng.randf_range(0.05, 0.95 - _zone_width)
	_zone.position = Vector2(_zone_start * BAR_W, 0)
	_zone.size = Vector2(_zone_width * BAR_W, 22)
	_pos = 0.0
	_dir = 1.0
	_active = true
	_info.text = "찌가 붉은 곳에 올 때 [확인] 또는 「챔질!」"


func _process(delta: float) -> void:
	if not _active:
		return
	_pos += _dir * delta * float(_cfg.get("marker_speed", 1.3))
	if _pos >= 1.0:
		_pos = 1.0
		_dir = -1.0
	elif _pos <= 0.0:
		_pos = 0.0
		_dir = 1.0
	_marker.position.x = _pos * BAR_W - 2


## 현재 위치로 판정. 반환: 잡은 아이템 id 또는 "" (놓침)
func strike() -> String:
	if not _active:
		_new_round()
		return ""
	_active = false
	var result := judge(_pos, _zone_start, _zone_width)
	if result == "":
		_info.text = "놓쳤다! 물고기가 비웃으며 사라졌다. (다시 「챔질!」로 던지기)"
	else:
		GameState.add_item(result)
		_info.text = "『%s』을(를) 낚았다! (다시 「챔질!」로 던지기)" % DataDB.item_name(result)
	return result


## 판정 로직 (테스트 가능): 구간 안이면 확률표대로, 정중앙 근처면 잉어 이상 보장
func judge(pos: float, zone_start: float, zone_width: float) -> String:
	if pos < zone_start or pos > zone_start + zone_width:
		return ""
	var center := zone_start + zone_width / 2.0
	var table: Array = _cfg.get("table", [{"item": "crucian", "weight": 1}])
	var total := 0
	for t in table:
		total += int(t["weight"])
	var roll := rng.randi_range(1, maxi(1, total))
	var picked: String = table[0]["item"]
	for t in table:
		roll -= int(t["weight"])
		if roll <= 0:
			picked = t["item"]
			break
	if absf(pos - center) < zone_width * 0.12 and picked == "crucian":
		picked = str(_cfg.get("perfect_bonus", "carp"))
	return picked


func stop() -> void:
	_active = false
	_root.visible = false
	await get_tree().process_frame
	GameState.unlock_input("fishing")
	finished.emit("")


func _input(event: InputEvent) -> void:
	if not _root.visible:
		return
	if event.is_action_pressed("interact"):
		strike()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("cancel") or event.is_action_pressed("menu"):
		stop()
		get_viewport().set_input_as_handled()
