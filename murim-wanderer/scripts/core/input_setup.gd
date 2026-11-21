extends Node
## 키보드 입력 액션을 코드로 등록한다 (project.godot 직렬화보다 읽기/수정이 쉽다).
## 모바일 터치 버튼(TouchScreenButton)도 같은 액션 이름을 사용한다.

const BINDINGS := {
	"move_up": [KEY_UP, KEY_W],
	"move_down": [KEY_DOWN, KEY_S],
	"move_left": [KEY_LEFT, KEY_A],
	"move_right": [KEY_RIGHT, KEY_D],
	"interact": [KEY_Z, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER],
	"cancel": [KEY_X, KEY_BACKSPACE],
	"menu": [KEY_ESCAPE, KEY_C, KEY_TAB],
}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for action in BINDINGS:
		if not InputMap.has_action(action):
			InputMap.add_action(action, 0.3)
		for keycode in BINDINGS[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = keycode
			InputMap.action_add_event(action, ev)
	# 메뉴 버튼 조작: Z=확인, X=취소 (방향키/Enter/Esc 는 Godot 기본값)
	_add_key("ui_accept", KEY_Z)
	_add_key("ui_cancel", KEY_X)
	_add_joy("interact", JOY_BUTTON_A)
	_add_joy("cancel", JOY_BUTTON_B)
	_add_joy("menu", JOY_BUTTON_START)
	_add_joy("move_up", JOY_BUTTON_DPAD_UP)
	_add_joy("move_down", JOY_BUTTON_DPAD_DOWN)
	_add_joy("move_left", JOY_BUTTON_DPAD_LEFT)
	_add_joy("move_right", JOY_BUTTON_DPAD_RIGHT)


func _add_joy(action: String, button: JoyButton) -> void:
	var ev := InputEventJoypadButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


func _add_key(action: String, keycode: Key) -> void:
	var ev := InputEventKey.new()
	ev.physical_keycode = keycode
	InputMap.action_add_event(action, ev)
