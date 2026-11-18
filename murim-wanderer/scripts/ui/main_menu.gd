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

	var title_box := VBoxContainer.new()
	title_box.anchor_left = 0.5
	title_box.anchor_right = 0.5
	title_box.offset_top = 34
	title_box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	title_box.add_theme_constant_override("separation", 2)
	add_child(title_box)
	_title_box = title_box
	_title = _outlined("무림유랑기", 48, Color(1.0, 0.92, 0.62), 8)
	title_box.add_child(_title)
	title_box.add_child(_outlined("~ 천하제일 허당전 ~", 24, Color(1, 0.75, 0.6), 6))

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

	_info = UiKit.label("", 12, Color(1, 0.9, 0.75))
	_info.anchor_left = 0.0
	_info.anchor_right = 1.0
	_info.anchor_top = 1.0
	_info.anchor_bottom = 1.0
	_info.offset_top = -22
	_info.offset_bottom = -6
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_info)

	var ver := UiKit.label("프로토타입 v0.1", 12, Color(1, 1, 1, 0.5))
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


func _outlined(text: String, size: int, color: Color, outline: int) -> Label:
	var l := UiKit.label(text, size, color)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_color_override("font_outline_color", Color(0.24, 0.1, 0.16))
	l.add_theme_constant_override("outline_size", outline)
	l.add_theme_color_override("font_shadow_color", Color(0.1, 0.04, 0.08, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 2)
	l.add_theme_constant_override("shadow_offset_y", 3)
	return l


func _process(delta: float) -> void:
	_t += delta
	_title.position.y = roundf(sin(_t * 2.0) * 2.0)


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
