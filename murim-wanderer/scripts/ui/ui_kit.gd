class_name UiKit
extends RefCounted
## 픽셀아트용 공용 UI 테마와 위젯 생성 도우미.

const GOLD := Color(0.86, 0.68, 0.32)
const INK := Color(0.11, 0.09, 0.16, 0.94)
const TEXT := Color(0.98, 0.95, 0.86)
const DIM := Color(0.6, 0.56, 0.5)
const HP_COLOR := Color(0.85, 0.27, 0.25)
const MP_COLOR := Color(0.3, 0.5, 0.9)
const EXP_COLOR := Color(0.95, 0.78, 0.3)

static var _theme: Theme


static func theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	t.default_font_size = 12
	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_outline_color", "Label", Color(0.08, 0.06, 0.1))
	t.set_constant("outline_size", "Label", 0)
	t.set_stylebox("panel", "Panel", box(INK, GOLD, 2))
	t.set_stylebox("panel", "PanelContainer", box(INK, GOLD, 2, 8))
	t.set_stylebox("normal", "Button", box(Color(0.22, 0.17, 0.28), Color(0.55, 0.45, 0.32), 1, 4))
	t.set_stylebox("hover", "Button", box(Color(0.33, 0.25, 0.38), GOLD, 1, 4))
	t.set_stylebox("pressed", "Button", box(Color(0.62, 0.26, 0.2), GOLD, 1, 4))
	t.set_stylebox("disabled", "Button", box(Color(0.15, 0.13, 0.18), Color(0.3, 0.28, 0.3), 1, 4))
	t.set_stylebox("focus", "Button", box(Color(0, 0, 0, 0), Color(1, 0.9, 0.5), 2, 4))
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", Color(1, 0.95, 0.7))
	t.set_color("font_pressed_color", "Button", Color(1, 1, 1))
	t.set_color("font_focus_color", "Button", Color(1, 0.95, 0.7))
	t.set_color("font_disabled_color", "Button", DIM)
	t.set_stylebox("background", "ProgressBar", box(Color(0.06, 0.05, 0.08), Color(0.06, 0.05, 0.08), 1, 0))
	t.set_stylebox("fill", "ProgressBar", box(HP_COLOR, HP_COLOR, 0, 0))
	t.set_stylebox("slider", "HSlider", box(Color(0.06, 0.05, 0.08), GOLD, 1, 2))
	t.set_stylebox("grabber_area", "HSlider", box(Color(0.62, 0.26, 0.2), Color(0.62, 0.26, 0.2), 0, 2))
	t.set_stylebox("grabber_area_highlight", "HSlider", box(Color(0.8, 0.35, 0.25), Color(0.8, 0.35, 0.25), 0, 2))
	_theme = t
	return t


static func box(bg: Color, border: Color, width: int = 2, margin: int = 6) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(width)
	s.set_content_margin_all(margin)
	s.anti_aliasing = false
	return s


static func label(text: String, size: int = 12, color: Color = TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


static func button(text: String, min_size: Vector2 = Vector2(96, 26)) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = min_size
	b.focus_mode = Control.FOCUS_ALL
	return b


static func bar(color: Color, height: int = 8) -> ProgressBar:
	var p := ProgressBar.new()
	p.show_percentage = false
	p.custom_minimum_size = Vector2(0, height)
	p.add_theme_stylebox_override("fill", box(color, color.lightened(0.25), 0, 0))
	return p


static func panel_container(margin: int = 8) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", box(INK, GOLD, 2, margin))
	return p


## 버튼 목록에 위/아래 포커스 이웃을 연결한다 (키보드/패드 조작용).
static func chain_focus(buttons: Array) -> void:
	var enabled := buttons.filter(func(b): return is_instance_valid(b) and not b.disabled and b.visible)
	for i in enabled.size():
		var b: Control = enabled[i]
		b.focus_neighbor_top = b.get_path_to(enabled[(i - 1 + enabled.size()) % enabled.size()])
		b.focus_neighbor_bottom = b.get_path_to(enabled[(i + 1) % enabled.size()])


static func first_enabled(buttons: Array) -> Control:
	for b in buttons:
		if is_instance_valid(b) and not b.disabled and b.visible:
			return b
	return null
