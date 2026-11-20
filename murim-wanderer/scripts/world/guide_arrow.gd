extends Node2D
## 「다음 할 일」 목표 방향을 가리키는 작은 화살표. 플레이어 주위를 돌며 목표를 가리킨다.
## 목표가 가깝거나 없으면 숨김.

var player: Node2D
var _t := 0.0


func _process(delta: float) -> void:
	_t += delta
	var target = GameState.guide_target_position()
	if player == null or not is_instance_valid(player) or target == null or GameState.is_input_locked():
		visible = false
		return
	var to: Vector2 = target - player.global_position
	if to.length() < 56.0:
		visible = false
		return
	visible = true
	var dir := to.normalized()
	global_position = player.global_position + Vector2(0, -2) + dir * (30.0 + sin(_t * 5.0) * 3.0)
	rotation = dir.angle()
	queue_redraw()


func _draw() -> void:
	var pts := PackedVector2Array([Vector2(7, 0), Vector2(-4, -5), Vector2(-2, 0), Vector2(-4, 5)])
	draw_colored_polygon(pts, Color8(176, 54, 42, 230))
	draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2], pts[3], pts[0]]), Color8(240, 226, 200, 220), 1.0)
