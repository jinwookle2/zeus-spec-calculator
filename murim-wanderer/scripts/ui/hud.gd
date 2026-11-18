extends CanvasLayer
## 필드 HUD: 이름/레벨, HP·MP 바, 지역명, 메뉴 버튼, 알림 메시지.

signal menu_pressed

var _lv: Label
var _hp_bar: ProgressBar
var _mp_bar: ProgressBar
var _hp_text: Label
var _mp_text: Label
var _map_label: Label
var _toast: PanelContainer
var _toast_label: Label
var _root: Control


func _ready() -> void:
	layer = 10
	_build()
	GameState.stats_changed.connect(refresh)
	get_viewport().size_changed.connect(_apply_safe_area)
	_apply_safe_area()
	refresh()


func _build() -> void:
	_root = Control.new()
	_root.theme = UiKit.theme()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)

	var box := UiKit.panel_container(6)
	box.position = Vector2(8, 8)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(box)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	box.add_child(v)
	_lv = UiKit.label("", 12, Color(1, 0.93, 0.7))
	v.add_child(_lv)
	for kind in ["HP", "MP"]:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		var tag := UiKit.label(kind, 12, UiKit.HP_COLOR.lightened(0.3) if kind == "HP" else UiKit.MP_COLOR.lightened(0.3))
		tag.custom_minimum_size = Vector2(20, 0)
		row.add_child(tag)
		var b := UiKit.bar(UiKit.HP_COLOR if kind == "HP" else UiKit.MP_COLOR, 8)
		b.custom_minimum_size = Vector2(70, 8)
		b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(b)
		var t := UiKit.label("", 12)
		t.custom_minimum_size = Vector2(48, 0)
		row.add_child(t)
		v.add_child(row)
		if kind == "HP":
			_hp_bar = b
			_hp_text = t
		else:
			_mp_bar = b
			_mp_text = t

	var right := HBoxContainer.new()
	right.anchor_left = 1.0
	right.anchor_right = 1.0
	right.offset_left = -170
	right.offset_right = -8
	right.offset_top = 8
	right.alignment = BoxContainer.ALIGNMENT_END
	right.add_theme_constant_override("separation", 6)
	right.name = "Right"
	_root.add_child(right)
	var map_box := UiKit.panel_container(5)
	map_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_map_label = UiKit.label("", 12, Color(1, 0.93, 0.7))
	map_box.add_child(_map_label)
	right.add_child(map_box)
	var menu_btn := UiKit.button("메뉴", Vector2(48, 26))
	menu_btn.focus_mode = Control.FOCUS_NONE
	menu_btn.pressed.connect(func(): menu_pressed.emit())
	right.add_child(menu_btn)

	_toast = UiKit.panel_container(6)
	_toast.anchor_left = 0.5
	_toast.anchor_right = 0.5
	_toast.offset_top = 56
	_toast.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.modulate.a = 0.0
	_toast_label = UiKit.label("", 12)
	_toast.add_child(_toast_label)
	_root.add_child(_toast)


func set_map_name(text: String) -> void:
	_map_label.text = text


func refresh() -> void:
	var p := GameState.player
	if p.is_empty():
		return
	_lv.text = "%s  Lv.%d" % [p["name"], int(p["level"])]
	_hp_bar.max_value = int(p["max_hp"])
	_hp_bar.value = int(p["hp"])
	_mp_bar.max_value = maxi(1, int(p["max_mp"]))
	_mp_bar.value = int(p["mp"])
	_hp_text.text = "%d/%d" % [int(p["hp"]), int(p["max_hp"])]
	_mp_text.text = "%d/%d" % [int(p["mp"]), int(p["max_mp"])]


func toast(text: String, duration: float = 1.8) -> void:
	_toast_label.text = text
	var t := create_tween()
	t.tween_property(_toast, "modulate:a", 1.0, 0.15)
	t.tween_interval(duration)
	t.tween_property(_toast, "modulate:a", 0.0, 0.3)


func _apply_safe_area() -> void:
	var m := SafeArea.margins(get_viewport())
	_root.offset_left = m.x
	_root.offset_top = m.y
	_root.offset_right = -m.z
	_root.offset_bottom = -m.w
