extends CanvasLayer
## 대화창. NPC 이름 + 한국어 대사를 타자기 효과로 출력한다.
## 상호작용 키/터치로 넘기며, 열려 있는 동안 플레이어 이동을 잠근다.

signal finished

var _panel: Panel
var _name_panel: PanelContainer
var _name_label: Label
var _text: Label
var _arrow: Label
var _lines: Array = []
var _index := 0
var _typing := false
var _progress := 0.0
var _open := false
var _last_advance_ms := 0
var _blink := 0.0
var _running := false


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("dialogue_box")
	_build()
	visible = false


func _build() -> void:
	var root := Control.new()
	root.theme = UiKit.theme()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	_panel = Panel.new()
	_panel.anchor_left = 0.0
	_panel.anchor_right = 1.0
	_panel.anchor_top = 1.0
	_panel.anchor_bottom = 1.0
	_panel.offset_left = 24
	_panel.offset_right = -24
	_panel.offset_top = -92
	_panel.offset_bottom = -10
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	_panel.gui_input.connect(_on_panel_input)
	root.add_child(_panel)

	_text = UiKit.label("", 12)
	_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text.set_anchors_preset(Control.PRESET_FULL_RECT)
	_text.offset_left = 14
	_text.offset_top = 14
	_text.offset_right = -14
	_text.offset_bottom = -10
	_text.add_theme_constant_override("line_spacing", 4)
	_panel.add_child(_text)

	_arrow = UiKit.label("▼", 12, UiKit.GOLD)
	_arrow.anchor_left = 1.0
	_arrow.anchor_top = 1.0
	_arrow.anchor_right = 1.0
	_arrow.anchor_bottom = 1.0
	_arrow.offset_left = -22
	_arrow.offset_top = -20
	_panel.add_child(_arrow)

	_name_panel = UiKit.panel_container(4)
	_name_panel.add_theme_stylebox_override("panel", UiKit.box(UiKit.VERMILION, UiKit.GOLD, 1, 4))
	_name_panel.position = Vector2(10, -14)
	_panel.add_child(_name_panel)
	_name_label = UiKit.label("", 12, UiKit.TEXT)
	_name_panel.add_child(_name_label)


func is_open() -> bool:
	return _open


## 대사 항목 하나를 실행: 대사 출력 → 효과 적용 → 획득 안내.
func run(entry_id: String) -> Dictionary:
	# 대사 → 획득 안내 사이에도 이동이 풀리지 않도록 전체 구간을 잠근다
	GameState.lock_input("dialogue_run")
	_running = true
	var d := DialogueData.resolve(entry_id)
	if not d["lines"].is_empty():
		await show_lines(d["lines"])
	var notices := DialogueData.apply_actions(d["actions"])
	if not notices.is_empty():
		var sys_lines: Array = []
		for t in notices:
			sys_lines.append({"speaker": "", "text": t})
		await show_lines(sys_lines)
	_running = false
	GameState.unlock_input("dialogue_run")
	return d["actions"]


## 대사 실행 중(획득 안내 포함)이면 true
func is_busy() -> bool:
	return _open or _running


## lines: [{speaker, text}] 또는 문자열 배열
func show_lines(lines: Array) -> void:
	if lines.is_empty():
		return
	_lines = []
	for l in lines:
		_lines.append(l if typeof(l) == TYPE_DICTIONARY else {"speaker": "", "text": str(l)})
	GameState.lock_input("dialogue")
	_open = true
	visible = true
	_index = 0
	_show_current()
	await finished


func _show_current() -> void:
	var line: Dictionary = _lines[_index]
	var speaker := str(line.get("speaker", ""))
	_name_panel.visible = speaker != ""
	_name_label.text = speaker
	_text.text = str(line.get("text", ""))
	var cps := Settings.chars_per_second()
	if cps <= 0.0:
		_text.visible_characters = -1
		_typing = false
	else:
		_text.visible_characters = 0
		_progress = 0.0
		_typing = true
	_arrow.visible = not _typing


func _process(delta: float) -> void:
	if not _open:
		return
	if _typing:
		_progress += delta * Settings.chars_per_second()
		var total := _text.get_total_character_count()
		_text.visible_characters = mini(int(_progress), total)
		if int(_progress) >= total:
			_typing = false
			_text.visible_characters = -1
	_blink += delta
	_arrow.visible = not _typing and fmod(_blink, 0.8) < 0.5


func advance() -> void:
	if not _open:
		return
	var now := Time.get_ticks_msec()
	if now - _last_advance_ms < 80:
		return
	_last_advance_ms = now
	if _typing:
		_typing = false
		_text.visible_characters = -1
		return
	_index += 1
	if _index >= _lines.size():
		_close()
	else:
		_show_current()


func _close() -> void:
	_open = false
	visible = false
	# 대화를 닫은 키 입력이 곧바로 다음 상호작용으로 이어지지 않도록 한 프레임 뒤 해제
	await get_tree().process_frame
	GameState.unlock_input("dialogue")
	finished.emit()


func _input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("cancel"):
		advance()
		get_viewport().set_input_as_handled()


func _on_panel_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		advance()
		_panel.accept_event()
