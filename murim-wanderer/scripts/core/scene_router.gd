extends CanvasLayer
## 페이드 효과와 함께 장면을 전환한다.

signal scene_changed

var _rect: ColorRect
var _busy := false


func _ready() -> void:
	layer = 100
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rect = ColorRect.new()
	_rect.color = Color(0.06, 0.05, 0.08, 0.0)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_rect)


func is_busy() -> bool:
	return _busy


func change_scene(path: String, flash: bool = false) -> void:
	if _busy:
		return
	_busy = true
	_rect.mouse_filter = Control.MOUSE_FILTER_STOP
	if flash:
		# 전투 진입 연출: 하얗게 번쩍
		_rect.color = Color(1, 1, 1, 0)
		var t0 := create_tween()
		t0.tween_property(_rect, "color:a", 0.9, 0.05)
		t0.tween_property(_rect, "color:a", 0.0, 0.05)
		t0.tween_property(_rect, "color:a", 0.9, 0.05)
		await t0.finished
	_rect.color = Color(0.06, 0.05, 0.08, _rect.color.a)
	var t := create_tween()
	t.tween_property(_rect, "color:a", 1.0, 0.12)
	await t.finished
	get_tree().paused = false
	var err := get_tree().change_scene_to_file(path)
	if err != OK:
		push_error("장면 전환 실패: %s (%d)" % [path, err])
	await get_tree().process_frame
	scene_changed.emit()
	var t2 := create_tween()
	t2.tween_property(_rect, "color:a", 0.0, 0.12)
	await t2.finished
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_busy = false
