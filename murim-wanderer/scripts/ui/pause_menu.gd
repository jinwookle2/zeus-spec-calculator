extends CanvasLayer
## 필드 메뉴: 상태 / 아이템 / 저장 / 설정 / 타이틀로.
## 열려 있는 동안 게임을 일시정지한다.

signal message(text: String)

var _root: Control
var _menu_buttons: Array = []
var _content: PanelContainer
var _content_box: VBoxContainer
var _settings: SettingsPanel
var _open := false


func _ready() -> void:
	layer = 40
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	_root.visible = false


func _build() -> void:
	_root = Control.new()
	_root.theme = UiKit.theme()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.05, 0.03, 0.08, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)

	var menu := UiKit.panel_container(8)
	menu.anchor_left = 1.0
	menu.anchor_right = 1.0
	menu.offset_left = -132
	menu.offset_right = -12
	menu.offset_top = 40
	_root.add_child(menu)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 5)
	menu.add_child(v)
	var entries := [["상태", _show_status], ["아이템", _show_items], ["저장하기", _do_save],
		["설정", _show_settings], ["타이틀로", _confirm_title], ["닫기", close]]
	for e in entries:
		var b := UiKit.button(e[0], Vector2(104, 26))
		b.pressed.connect(e[1])
		v.add_child(b)
		_menu_buttons.append(b)
	UiKit.chain_focus(_menu_buttons)

	_content = UiKit.panel_container(10)
	_content.anchor_left = 0.0
	_content.anchor_right = 1.0
	_content.offset_left = 12
	_content.offset_right = -146
	_content.offset_top = 40
	_content.anchor_bottom = 1.0
	_content.offset_bottom = -12
	_root.add_child(_content)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content.add_child(scroll)
	_content_box = VBoxContainer.new()
	_content_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content_box.add_theme_constant_override("separation", 4)
	scroll.add_child(_content_box)

	_settings = SettingsPanel.new()
	_settings.set_anchors_preset(Control.PRESET_CENTER)
	_settings.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_settings.grow_vertical = Control.GROW_DIRECTION_BOTH
	_settings.visible = false
	_settings.closed.connect(func(): _settings.visible = false; _menu_buttons[3].grab_focus())
	_root.add_child(_settings)


func is_open() -> bool:
	return _open


func open() -> void:
	if _open:
		return
	_open = true
	_root.visible = true
	GameState.lock_input("menu")
	get_tree().paused = true
	_show_status()
	_menu_buttons[0].grab_focus()


func close() -> void:
	if not _open:
		return
	_open = false
	_root.visible = false
	_settings.visible = false
	get_tree().paused = false
	await get_tree().process_frame
	GameState.unlock_input("menu")


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if (event.is_action_pressed("menu") or event.is_action_pressed("cancel")) and not _settings.visible:
		close()
		get_viewport().set_input_as_handled()


func _clear() -> void:
	for c in _content_box.get_children():
		c.queue_free()


func _line(text: String, color: Color = UiKit.TEXT) -> Label:
	var l := UiKit.label(text, 12, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(200, 0)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content_box.add_child(l)
	return l


func _show_status() -> void:
	_clear()
	var p := GameState.player
	_line("%s  Lv.%d" % [p["name"], int(p["level"])], UiKit.GOLD)
	_line("HP %d / %d     MP %d / %d" % [int(p["hp"]), int(p["max_hp"]), int(p["mp"]), int(p["max_mp"])])
	_line("공격력 %d   방어력 %d   민첩성 %d" % [int(p["attack"]), int(p["defense"]), int(p["agility"])])
	var need := GameState.exp_to_next(int(p["level"]))
	_line("경험치 %d / %d   (다음 레벨까지 %d)" % [int(p["exp"]), need, need - int(p["exp"])])
	var exp_bar := UiKit.bar(UiKit.EXP_COLOR, 6)
	exp_bar.max_value = need
	exp_bar.value = int(p["exp"])
	_content_box.add_child(exp_bar)
	_line("소지금 %d냥" % int(p["gold"]))
	var skill_names: Array = []
	for s in GameState.skills:
		skill_names.append(DataDB.skills.get(s, {}).get("name", s))
	_line("무술: " + ", ".join(skill_names))
	_line("")
	_line("임무", UiKit.GOLD)
	if GameState.quests.is_empty():
		_line("  (아직 없음 — 마을 사람들과 이야기해 보자)", UiKit.DIM)
	for qid in GameState.quests:
		var q: Dictionary = DataDB.quests.get(qid, {})
		var st := GameState.get_quest(qid)
		var mark := "✔ " if st == "complete" else "● "
		_line(mark + str(q.get("name", qid)), UiKit.TEXT if st != "complete" else UiKit.DIM)
		_line("   " + str(q.get("states", {}).get(st, "")), UiKit.DIM)
	_line("")
	var secs := int(GameState.play_time)
	_line("플레이 시간 %02d:%02d:%02d" % [secs / 3600, (secs / 60) % 60, secs % 60], UiKit.DIM)


func _show_items() -> void:
	_clear()
	_line("아이템 (눌러서 사용)", UiKit.GOLD)
	if GameState.inventory.is_empty():
		_line("가방이 비어 있다. 바람만 들어 있다.", UiKit.DIM)
	for item_id in GameState.inventory:
		var def: Dictionary = DataDB.items.get(item_id, {})
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		var b := UiKit.button("%s x%d" % [def.get("name", item_id), GameState.item_count(item_id)], Vector2(130, 24))
		var usable: bool = def.get("type", "") in ["heal_hp", "heal_mp"]
		b.disabled = not usable
		b.pressed.connect(_use_item.bind(item_id))
		row.add_child(b)
		var d := UiKit.label(str(def.get("desc", "")), 12, UiKit.DIM)
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		d.custom_minimum_size = Vector2(140, 0)
		row.add_child(d)
		_content_box.add_child(row)


func _use_item(item_id: String) -> void:
	var msg := GameState.use_item(item_id)
	_show_items()
	if msg != "":
		_line(msg, Color(0.6, 1, 0.6))
	_menu_buttons[1].grab_focus()


func _do_save() -> void:
	_clear()
	if SaveManager.save_game():
		_line("저장했다!", Color(0.6, 1, 0.6))
		_line(SaveManager.save_summary(), UiKit.DIM)
		message.emit("저장 완료")
	else:
		_line("저장 실패: " + SaveManager.last_error, UiKit.HP_COLOR)


func _show_settings() -> void:
	_settings.visible = true
	_settings.focus_first()


func _confirm_title() -> void:
	_clear()
	_line("타이틀 화면으로 돌아갈까?", UiKit.GOLD)
	_line("저장하지 않은 진행 상황은 사라진다.", UiKit.DIM)
	var yes := UiKit.button("타이틀로", Vector2(120, 26))
	yes.pressed.connect(func(): close(); GameState.return_to_title())
	_content_box.add_child(yes)
	yes.grab_focus()
