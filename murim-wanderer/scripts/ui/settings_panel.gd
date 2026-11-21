class_name SettingsPanel
extends PanelContainer
## 설정 화면 (시작 화면과 일시정지 메뉴에서 공용).

signal closed

var _buttons: Array = []
var _volume: HSlider
var _volume_label: Label
var _speed_btn: Button
var _touch_btn: Button
var _full_btn: Button
var _timing_btn: Button


func _ready() -> void:
	theme = UiKit.theme()
	add_theme_stylebox_override("panel", UiKit.box(UiKit.INK, UiKit.GOLD, 2, 12))
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	add_child(v)
	v.add_child(UiKit.label("설정", 12, UiKit.GOLD))

	var vol_row := HBoxContainer.new()
	vol_row.add_theme_constant_override("separation", 8)
	_volume_label = UiKit.label("", 12)
	_volume_label.custom_minimum_size = Vector2(92, 0)
	vol_row.add_child(_volume_label)
	_volume = HSlider.new()
	_volume.min_value = 0
	_volume.max_value = 100
	_volume.step = 10
	_volume.custom_minimum_size = Vector2(120, 20)
	_volume.value = Settings.master_volume * 100
	_volume.value_changed.connect(func(val): Settings.set_value("master_volume", val / 100.0); _refresh())
	vol_row.add_child(_volume)
	v.add_child(vol_row)

	_speed_btn = UiKit.button("", Vector2(220, 26))
	_speed_btn.pressed.connect(_cycle_speed)
	v.add_child(_speed_btn)
	_touch_btn = UiKit.button("", Vector2(220, 26))
	_touch_btn.pressed.connect(_cycle_touch)
	v.add_child(_touch_btn)
	_timing_btn = UiKit.button("", Vector2(220, 26))
	_timing_btn.pressed.connect(func(): Settings.set_value("battle_timing", not Settings.battle_timing); _refresh())
	v.add_child(_timing_btn)
	_full_btn = UiKit.button("", Vector2(220, 26))
	_full_btn.pressed.connect(func(): Settings.set_value("fullscreen", not Settings.fullscreen); _refresh())
	_full_btn.visible = OS.has_feature("pc")
	v.add_child(_full_btn)
	var close := UiKit.button("닫기", Vector2(220, 26))
	close.pressed.connect(func(): closed.emit())
	v.add_child(close)
	_buttons = [_volume, _speed_btn, _touch_btn, _full_btn, close]
	_refresh()


func focus_first() -> void:
	_speed_btn.grab_focus()


func _cycle_speed() -> void:
	var keys := Settings.TEXT_SPEEDS.keys()
	var i := keys.find(Settings.text_speed)
	Settings.set_value("text_speed", keys[(i + 1) % keys.size()])
	_refresh()


func _cycle_touch() -> void:
	var keys := Settings.TOUCH_MODES.keys()
	var i := keys.find(Settings.touch_controls)
	Settings.set_value("touch_controls", keys[(i + 1) % keys.size()])
	_refresh()


func _refresh() -> void:
	_volume_label.text = "음량  %d%%" % int(Settings.master_volume * 100)
	_speed_btn.text = "대사 속도: %s" % Settings.TEXT_SPEED_NAMES[Settings.text_speed]
	_touch_btn.text = "터치 버튼: %s" % Settings.TOUCH_MODES[Settings.touch_controls]
	_full_btn.text = "전체 화면: %s" % ("켜기" if Settings.fullscreen else "끄기")
	_timing_btn.text = "전투 타이밍 입력: %s" % ("켜기" if Settings.battle_timing else "끄기")


func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("cancel"):
		closed.emit()
		get_viewport().set_input_as_handled()
