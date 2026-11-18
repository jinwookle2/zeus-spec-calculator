extends CanvasLayer
## 모바일 가상 방향키 + 확인(A)/메뉴(B) 버튼.
## TouchScreenButton 이 키보드와 같은 입력 액션(move_*, interact, menu)을 발생시킨다.
## 데스크톱에서는 마우스로도 눌러 볼 수 있다 (emulate_touch_from_mouse).

const MARGIN := 14.0

var _dpad := {}
var _btn_a: TouchScreenButton
var _btn_b: TouchScreenButton
var _root: Node2D


func _ready() -> void:
	layer = 20
	_root = Node2D.new()
	add_child(_root)
	for dir in ["up", "down", "left", "right"]:
		var b := _make_button("res://assets/ui/dpad_%s.png" % dir, "move_" + dir, "")
		b.passby_press = true
		_dpad[dir] = b
	_btn_a = _make_button("res://assets/ui/btn_a.png", "interact", "확인")
	_btn_b = _make_button("res://assets/ui/btn_b.png", "menu", "메뉴")
	get_viewport().size_changed.connect(_layout)
	Settings.changed.connect(_update_visibility)
	_layout()
	_update_visibility()


func _make_button(tex_path: String, action: String, caption: String) -> TouchScreenButton:
	var b := TouchScreenButton.new()
	b.texture_normal = load(tex_path)
	b.action = action
	var size: Vector2 = b.texture_normal.get_size()
	var shape := RectangleShape2D.new()
	shape.size = size + Vector2(8, 8)  # 손가락용 여유
	b.shape = shape
	b.shape_centered = true
	b.visibility_mode = TouchScreenButton.VISIBILITY_ALWAYS
	b.modulate = Color(1, 1, 1, 0.85)
	b.pressed.connect(func(): b.modulate = Color(1.3, 1.3, 1.3, 1.0))
	b.released.connect(func(): b.modulate = Color(1, 1, 1, 0.85))
	if caption != "":
		var l := UiKit.label(caption, 12)
		l.add_theme_color_override("font_outline_color", Color(0.1, 0.06, 0.1))
		l.add_theme_constant_override("outline_size", 4)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.size = size
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(l)
	_root.add_child(b)
	return b


func _layout() -> void:
	var vp := get_viewport().get_visible_rect().size
	var m := SafeArea.margins(get_viewport())
	var cell := 40.0
	var center := Vector2(MARGIN + m.x + cell * 1.5, vp.y - MARGIN - m.w - cell * 1.5)
	_dpad["up"].position = center + Vector2(-cell / 2, -cell * 1.5)
	_dpad["down"].position = center + Vector2(-cell / 2, cell * 0.5)
	_dpad["left"].position = center + Vector2(-cell * 1.5, -cell / 2)
	_dpad["right"].position = center + Vector2(cell * 0.5, -cell / 2)
	var right := vp.x - MARGIN - m.z
	var bottom := vp.y - MARGIN - m.w
	_btn_a.position = Vector2(right - 52, bottom - 52 - 20)
	_btn_b.position = Vector2(right - 52 - 58, bottom - 52 + 4)


func _process(_delta: float) -> void:
	# 대화·메뉴·장면 전환 중에는 버튼을 숨겨 대화창/메뉴를 가리지 않게 한다
	var want_visible := Settings.touch_enabled() and not GameState.is_input_locked()
	if _root.visible != want_visible:
		_root.visible = want_visible
		if not want_visible:
			_release_all()


func _update_visibility() -> void:
	visible = Settings.touch_enabled()
	if not visible:
		_release_all()


func _release_all() -> void:
	for action in ["move_up", "move_down", "move_left", "move_right", "interact", "menu"]:
		Input.action_release(action)


## 테스트/디버그용: 버튼 노드 접근
func get_button(name: String) -> TouchScreenButton:
	match name:
		"a":
			return _btn_a
		"b":
			return _btn_b
	return _dpad.get(name)
