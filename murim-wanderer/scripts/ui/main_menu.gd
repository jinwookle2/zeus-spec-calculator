extends Control
## 시작 화면: 새 게임 / 이어하기 / 설정 / 종료(데스크톱 전용).

var _buttons: Array = []
var _continue_btn: Button
var _quit_btn: Button
var _info: Label
var _settings: SettingsPanel
var _menu_box: Control
var _title: Label
var _title_box: Control
var _t := 0.0
var _mists: Array = []


func _ready() -> void:
	theme = UiKit.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	GameState.in_game = false
	_build()
	_refresh_continue()
	if _continue_btn.disabled:
		_buttons[0].grab_focus()
	else:
		_continue_btn.grab_focus()


func _build() -> void:
	var bg := TextureRect.new()
	bg.texture = load("res://assets/backgrounds/title_bg.png")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	add_child(bg)

	# 흐르는 안개
	for i in 2:
		var m := TextureRect.new()
		m.texture = load("res://assets/ui/mist.png")
		m.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		m.size = Vector2(520, 70)
		m.position = Vector2(-200 + i * 420, 170 + i * 50)
		m.modulate = Color(1, 1, 1, 0.55)
		m.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(m)
		_mists.append(m)

	var title_box := VBoxContainer.new()
	title_box.anchor_left = 0.5
	title_box.anchor_right = 0.5
	title_box.offset_top = 18
	title_box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	title_box.add_theme_constant_override("separation", -10)
	add_child(title_box)
	_title_box = title_box
	var title_row := HBoxContainer.new()
	title_row.alignment = BoxContainer.ALIGNMENT_CENTER
	title_row.add_theme_constant_override("separation", 6)
	title_box.add_child(title_row)
	_title = UiKit.brush_label("무림유랑기", 76, Color8(30, 24, 26))
	_title.add_theme_color_override("font_shadow_color", Color8(120, 104, 84, 110))
	_title.add_theme_constant_override("shadow_offset_x", 2)
	_title.add_theme_constant_override("shadow_offset_y", 2)
	title_row.add_child(_title)
	# 낙관(붉은 인장)
	var seal := PanelContainer.new()
	seal.add_theme_stylebox_override("panel", UiKit.box(UiKit.VERMILION, Color8(120, 30, 24), 1, 3))
	seal.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var seal_text := UiKit.brush_label("유랑", 22, Color8(240, 226, 200))
	seal.add_child(seal_text)
	title_row.add_child(seal)
	var sub := UiKit.brush_label("천하제일 허당전", 32, UiKit.VERMILION)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_box.add_child(sub)

	var panel := UiKit.panel_container(10)
	panel.anchor_left = 0.5
	panel.anchor_right = 0.5
	panel.anchor_top = 1.0
	panel.anchor_bottom = 1.0
	panel.offset_top = -170
	panel.offset_bottom = -26
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	add_child(panel)
	_menu_box = panel
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	panel.add_child(v)
	var new_btn := UiKit.button("새 게임", Vector2(150, 26))
	new_btn.pressed.connect(_on_new_game)
	_continue_btn = UiKit.button("이어하기", Vector2(150, 26))
	_continue_btn.pressed.connect(_on_continue)
	var set_btn := UiKit.button("설정", Vector2(150, 26))
	set_btn.pressed.connect(_on_settings)
	_quit_btn = UiKit.button("종료", Vector2(150, 26))
	_quit_btn.pressed.connect(func(): get_tree().quit())
	_quit_btn.visible = not OS.has_feature("mobile") and not OS.has_feature("web")
	_buttons = [new_btn, _continue_btn, set_btn, _quit_btn]
	for b in _buttons:
		v.add_child(b)

	_info = UiKit.label("", 12, Color8(60, 48, 44))
	_info.anchor_left = 0.0
	_info.anchor_right = 1.0
	_info.anchor_top = 1.0
	_info.anchor_bottom = 1.0
	_info.offset_top = -22
	_info.offset_bottom = -6
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_info)

	var ver := UiKit.label("프로토타입 v0.3", 12, Color8(60, 48, 44, 160))
	ver.anchor_left = 1.0
	ver.anchor_right = 1.0
	ver.offset_left = -110
	ver.offset_top = 6
	add_child(ver)

	_settings = SettingsPanel.new()
	_settings.set_anchors_preset(Control.PRESET_CENTER)
	_settings.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_settings.grow_vertical = Control.GROW_DIRECTION_BOTH
	_settings.visible = false
	_settings.closed.connect(_close_settings)
	add_child(_settings)


func _process(delta: float) -> void:
	_t += delta
	_title.modulate.a = 0.85 + 0.15 * sin(_t * 1.5)
	for i in _mists.size():
		var m: TextureRect = _mists[i]
		m.position.x += delta * (10.0 + i * 6.0)
		if m.position.x > 660:
			m.position.x = -540


func _refresh_continue() -> void:
	_continue_btn.disabled = not SaveManager.has_save()
	var summary := SaveManager.save_summary()
	_info.text = ("저장 기록: " + summary) if summary != "" else ""
	UiKit.chain_focus(_buttons)


func _on_new_game() -> void:
	if SceneRouter.is_busy():
		return
	GameState.new_game()
	SceneRouter.change_scene(GameState.WORLD_SCENE)


func _on_continue() -> void:
	if SceneRouter.is_busy():
		return
	var result := SaveManager.load_game()
	match result:
		SaveManager.LoadResult.OK, SaveManager.LoadResult.RESTORED_FROM_BACKUP:
			SceneRouter.change_scene(GameState.WORLD_SCENE)
		_:
			_info.text = SaveManager.last_error
			_continue_btn.disabled = true
			_buttons[0].grab_focus()


func _on_settings() -> void:
	_menu_box.visible = false
	_title_box.visible = false
	_settings.visible = true
	_settings.focus_first()


func _close_settings() -> void:
	_settings.visible = false
	_menu_box.visible = true
	_title_box.visible = true
	_buttons[2].grab_focus()
