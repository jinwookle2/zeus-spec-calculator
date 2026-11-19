class_name UiKit
extends RefCounted
## 픽셀아트용 공용 UI 테마와 위젯 생성 도우미.

## 진지한 무협풍 팔레트: 옻칠(검붉은 먹색) 바탕, 놋쇠 테두리, 한지색 글자, 주홍 강조
const GOLD := Color8(190, 156, 96)
const INK := Color8(30, 22, 22, 242)
const TEXT := Color8(234, 224, 202)
const DIM := Color8(150, 138, 120)
const NAME := Color8(222, 196, 140)
const VERMILION := Color8(160, 44, 34)
const HP_COLOR := Color8(176, 54, 42)
const MP_COLOR := Color8(66, 104, 150)
const EXP_COLOR := Color8(196, 160, 80)

static var _brush: Font

static var _theme: Theme


static func theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	t.default_font_size = 12
	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_outline_color", "Label", Color8(20, 14, 14))
	t.set_constant("outline_size", "Label", 0)
	t.set_stylebox("panel", "Panel", box(INK, GOLD, 2))
	t.set_stylebox("panel", "PanelContainer", box(INK, GOLD, 2, 8))
	t.set_stylebox("normal", "Button", box(Color8(54, 40, 34), Color8(112, 88, 62), 1, 4))
	t.set_stylebox("hover", "Button", box(Color8(80, 58, 46), GOLD, 1, 4))
	t.set_stylebox("pressed", "Button", box(VERMILION, GOLD, 1, 4))
	t.set_stylebox("disabled", "Button", box(Color8(36, 28, 26), Color8(70, 60, 54), 1, 4))
	t.set_stylebox("focus", "Button", box(Color(0, 0, 0, 0), Color8(232, 200, 130), 2, 4))
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", Color8(250, 232, 190))
	t.set_color("font_pressed_color", "Button", Color(1, 1, 1))
	t.set_color("font_focus_color", "Button", Color8(250, 232, 190))
	t.set_color("font_disabled_color", "Button", DIM)
	t.set_stylebox("background", "ProgressBar", box(Color8(14, 10, 10), Color8(14, 10, 10), 1, 0))
	t.set_stylebox("fill", "ProgressBar", box(HP_COLOR, HP_COLOR, 0, 0))
	t.set_stylebox("slider", "HSlider", box(Color8(14, 10, 10), GOLD, 1, 2))
	t.set_stylebox("grabber_area", "HSlider", box(VERMILION, VERMILION, 0, 2))
	t.set_stylebox("grabber_area_highlight", "HSlider", box(VERMILION.lightened(0.2), VERMILION.lightened(0.2), 0, 2))
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


## 붓글씨 제목용 글꼴 (나눔손글씨 붓, OFL)
static func brush_font() -> Font:
	if _brush == null:
		_brush = load("res://assets/fonts/NanumBrushScript-Regular.ttf")
	return _brush


static func brush_label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", brush_font())
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


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
