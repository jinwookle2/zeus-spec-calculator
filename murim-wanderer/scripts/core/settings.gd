extends Node
## 사용자 설정 (user://settings.cfg). 저장 데이터와 분리해 관리한다.

signal changed

const PATH := "user://settings.cfg"
const TEXT_SPEEDS := {"slow": 25.0, "normal": 50.0, "fast": 120.0, "instant": 0.0}
const TEXT_SPEED_NAMES := {"slow": "느림", "normal": "보통", "fast": "빠름", "instant": "즉시"}
const TOUCH_MODES := {"auto": "자동", "on": "켜기", "off": "끄기"}

var master_volume: float = 0.8
var text_speed: String = "normal"
var touch_controls: String = "auto"
var fullscreen: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_load()
	_apply()
	_apply_font()


func chars_per_second() -> float:
	return TEXT_SPEEDS.get(text_speed, 50.0)


func touch_enabled() -> bool:
	match touch_controls:
		"on":
			return true
		"off":
			return false
	return DisplayServer.is_touchscreen_available() or OS.has_feature("mobile")


func set_value(key: String, value: Variant) -> void:
	match key:
		"master_volume":
			master_volume = clampf(float(value), 0.0, 1.0)
		"text_speed":
			if TEXT_SPEEDS.has(value):
				text_speed = value
		"touch_controls":
			if TOUCH_MODES.has(value):
				touch_controls = value
		"fullscreen":
			fullscreen = bool(value)
	_apply()
	save()
	changed.emit()


func save() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "master_volume", master_volume)
	cfg.set_value("game", "text_speed", text_speed)
	cfg.set_value("game", "touch_controls", touch_controls)
	cfg.set_value("video", "fullscreen", fullscreen)
	cfg.save(PATH)


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	master_volume = clampf(float(cfg.get_value("audio", "master_volume", master_volume)), 0.0, 1.0)
	var ts = cfg.get_value("game", "text_speed", text_speed)
	text_speed = ts if TEXT_SPEEDS.has(ts) else "normal"
	var tc = cfg.get_value("game", "touch_controls", touch_controls)
	touch_controls = tc if TOUCH_MODES.has(tc) else "auto"
	fullscreen = bool(cfg.get_value("video", "fullscreen", false))


func _apply() -> void:
	var bus := AudioServer.get_bus_index("Master")
	AudioServer.set_bus_volume_db(bus, linear_to_db(maxf(master_volume, 0.0001)))
	AudioServer.set_bus_mute(bus, master_volume <= 0.001)
	if OS.has_feature("pc") and DisplayServer.get_name() != "headless":
		var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED
		if DisplayServer.window_get_mode() != mode:
			DisplayServer.window_set_mode(mode)


func _apply_font() -> void:
	# 픽셀 폰트를 선명하게: 안티앨리어싱/힌팅 끄기
	var font := load("res://assets/fonts/Galmuri11.ttf") as FontFile
	if font:
		font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
		font.hinting = TextServer.HINTING_NONE
		font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
		ThemeDB.fallback_font = font
		ThemeDB.fallback_font_size = 12
