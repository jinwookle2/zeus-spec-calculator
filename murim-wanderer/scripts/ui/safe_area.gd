class_name SafeArea
extends RefCounted
## 노치/펀치홀 등 모바일 안전 영역을 뷰포트 좌표 여백(left, top, right, bottom)으로 변환.


static func margins(viewport: Viewport) -> Vector4:
	if not OS.has_feature("mobile"):
		return Vector4.ZERO
	var safe := DisplayServer.get_display_safe_area()
	var screen := DisplayServer.screen_get_size()
	if screen.x <= 0 or screen.y <= 0 or safe.size.x <= 0:
		return Vector4.ZERO
	var vp_size := viewport.get_visible_rect().size
	var sx := vp_size.x / float(screen.x)
	var sy := vp_size.y / float(screen.y)
	return Vector4(
		safe.position.x * sx,
		safe.position.y * sy,
		(screen.x - safe.end.x) * sx,
		(screen.y - safe.end.y) * sy
	)
