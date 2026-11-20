extends Control
## 턴제 전투 화면 (v0.4: 역동적 연출). 규칙은 BattleLogic, 이 스크립트는 연출과 입력.
##
## - 자세(포즈) 그림 전환: 대기/돌진/주먹/발차기/맞음/방어/승리/쓰러짐
## - 돌진 → 타격 순간 정지(히트스톱) → 넉백 → 복귀, 화면 흔들림·줌, 무공별 이펙트
## - 타이밍 입력: 공격 시 좁아지는 원이 겹칠 때 [확인] = 완벽(추가 피해)
##               적이 무기를 치켜들고 "!" 가 뜰 때 [확인] = 받아치기(피해 감소)
## - 명령: 장착 무공 아이콘(최대 4) + 공격/방어/아이템/도주, 자동 전투·배속 토글

signal _skip_requested
signal _timing_pressed

const PLAYER_HOME := Vector2(170, 232)  # 발 위치 (640x360 기준)
const ENEMY_HOME := Vector2(470, 226)

var logic := BattleLogic.new()
var enemy_id := ""
var enemy_def: Dictionary = {}
var busy := true
var auto_on := false
var auto_allowed := false
var timing_enabled := true
var last_timing := ""  # "perfect" | "good" | "parry" | ""

var _stage: Control
var _player_sprite: TextureRect
var _enemy_sprite: TextureRect
var _player_tex: Dictionary = {}
var _enemy_tex: Dictionary = {}
var _msg: Label
var _cmd_panel: PanelContainer
var _cmd_box: GridContainer
var _p_name: Label
var _p_hp: ProgressBar
var _p_mp: ProgressBar
var _p_hp_txt: Label
var _p_mp_txt: Label
var _e_name: Label
var _e_hp: ProgressBar
var _charge_label: Label
var _waiting_confirm := false
var _auto_btn: Button
var _speed_btn: Button
var _skill_buttons: Dictionary = {}
var _tap_catcher: Control
var _timing_active := false
var _shield: TextureRect
var _breath_tween: Tween


func _ready() -> void:
	theme = UiKit.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	enemy_id = str(GameState.pending_battle.get("enemy", "scarecrow"))
	if GameState.player.is_empty():
		GameState.new_game()  # 에디터에서 장면만 단독 실행한 경우
	enemy_def = DataDB.enemies.get(enemy_id, {})
	logic.setup(GameState.effective_stats(), enemy_id, enemy_def, DataDB.battle_config, DataDB.skills, -1, GameState.skill_levels, DataDB.growth)
	# 자동 전투: 반복 수련 상대이거나 이미 한 번 이긴 상대만 (A안: 스토리 첫 전투는 직접)
	auto_allowed = bool(enemy_def.get("auto_ok", false)) or GameState.has_flag("beaten_" + enemy_id)
	auto_on = auto_allowed and Settings.battle_auto
	timing_enabled = Settings.battle_timing
	Engine.time_scale = 2.0 if Settings.battle_speed >= 2 else 1.0
	_load_textures()
	_build()
	_refresh_bars()
	_intro.call_deferred()


func _exit_tree() -> void:
	Engine.time_scale = 1.0


func _cfg_t(key: String, fallback: float) -> float:
	return float(DataDB.battle_config.get("timing", {}).get(key, fallback))


# ------------------------------------------------------------------ 화면 구성
func _load_textures() -> void:
	var pp: String = DataDB.player_def.get("battle", "res://assets/battle/doyun_")
	for pose in ["ready", "punch", "kick", "hurt", "guard", "win", "shout", "ko"]:
		_player_tex[pose] = load(pp + pose + ".png")
	var ep: String = enemy_def.get("battle", "res://assets/battle/scarecrow_")
	for pose in ["idle", "windup", "attack", "hurt", "ko"]:
		var path: String = ep + pose + ".png"
		_enemy_tex[pose] = load(path) if ResourceLoader.exists(path) else load(ep + "idle.png")


func _build() -> void:
	# 무대 (배경 + 인물 + 이펙트) — 줌·흔들림은 무대에만 적용
	_stage = Control.new()
	_stage.set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_stage)
	var bg := TextureRect.new()
	bg.texture = load("res://assets/backgrounds/battle_training.png")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.offset_left = -24
	bg.offset_right = 24
	bg.offset_top = -14
	bg.offset_bottom = 14
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_stage.add_child(bg)
	_player_sprite = _fighter(_player_tex["ready"], PLAYER_HOME)
	_enemy_sprite = _fighter(_enemy_tex["idle"], ENEMY_HOME)
	_idle_breath()

	# 플레이어 상태 (좌상단)
	var pp := UiKit.panel_container(6)
	pp.position = Vector2(8, 8)
	add_child(pp)
	var pv := VBoxContainer.new()
	pv.add_theme_constant_override("separation", 2)
	pp.add_child(pv)
	_p_name = UiKit.label("", 12, UiKit.NAME)
	pv.add_child(_p_name)
	var hp_row := _stat_row("HP", UiKit.HP_COLOR)
	_p_hp = hp_row[0]
	_p_hp_txt = hp_row[1]
	pv.add_child(hp_row[2])
	var mp_row := _stat_row("MP", UiKit.MP_COLOR)
	_p_mp = mp_row[0]
	_p_mp_txt = mp_row[1]
	pv.add_child(mp_row[2])
	_charge_label = UiKit.label("기합 충전!", 12, UiKit.EXP_COLOR)
	_charge_label.visible = false
	pv.add_child(_charge_label)

	# 적 상태 (우상단)
	var ep := UiKit.panel_container(6)
	ep.anchor_left = 1.0
	ep.anchor_right = 1.0
	ep.offset_left = -188
	ep.offset_right = -8
	ep.offset_top = 8
	add_child(ep)
	var ev := VBoxContainer.new()
	ev.add_theme_constant_override("separation", 3)
	ep.add_child(ev)
	_e_name = UiKit.label(str(enemy_def.get("name", "?")), 12, UiKit.NAME)
	ev.add_child(_e_name)
	_e_hp = UiKit.bar(UiKit.HP_COLOR, 8)
	ev.add_child(_e_hp)

	# 메시지 창 (하단 좌측)
	var mp := UiKit.panel_container(10)
	mp.anchor_top = 1.0
	mp.anchor_bottom = 1.0
	mp.anchor_right = 1.0
	mp.offset_left = 8
	mp.offset_right = -222
	mp.offset_top = -100
	mp.offset_bottom = -8
	mp.mouse_filter = Control.MOUSE_FILTER_STOP
	mp.gui_input.connect(_on_message_input)
	add_child(mp)
	_msg = UiKit.label("", 12)
	_msg.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_msg.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	_msg.add_theme_constant_override("line_spacing", 4)
	mp.add_child(_msg)

	# 명령 창 (하단 우측)
	_cmd_panel = UiKit.panel_container(8)
	_cmd_panel.anchor_left = 1.0
	_cmd_panel.anchor_right = 1.0
	_cmd_panel.anchor_top = 1.0
	_cmd_panel.anchor_bottom = 1.0
	_cmd_panel.offset_left = -214
	_cmd_panel.offset_right = -8
	_cmd_panel.offset_top = -100
	_cmd_panel.offset_bottom = -8
	add_child(_cmd_panel)
	_cmd_box = GridContainer.new()
	_cmd_box.add_theme_constant_override("h_separation", 4)
	_cmd_box.add_theme_constant_override("v_separation", 4)
	_cmd_panel.add_child(_cmd_box)
	_cmd_panel.visible = false

	# 자동 / 배속 토글 (상단 중앙)
	var toggles := HBoxContainer.new()
	toggles.anchor_left = 0.5
	toggles.anchor_right = 0.5
	toggles.offset_top = 8
	toggles.grow_horizontal = Control.GROW_DIRECTION_BOTH
	toggles.add_theme_constant_override("separation", 4)
	add_child(toggles)
	_auto_btn = UiKit.button("", Vector2(64, 24))
	_auto_btn.focus_mode = Control.FOCUS_NONE
	_auto_btn.pressed.connect(toggle_auto)
	toggles.add_child(_auto_btn)
	_speed_btn = UiKit.button("", Vector2(56, 24))
	_speed_btn.focus_mode = Control.FOCUS_NONE
	_speed_btn.pressed.connect(toggle_speed)
	toggles.add_child(_speed_btn)
	_refresh_toggles()

	# 타이밍 입력용 화면 전체 터치 영역 (타이밍 중에만 활성)
	_tap_catcher = Control.new()
	_tap_catcher.set_anchors_preset(Control.PRESET_FULL_RECT)
	_tap_catcher.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tap_catcher.gui_input.connect(func(e):
		if _timing_active and e is InputEventMouseButton and e.pressed:
			_timing_pressed.emit())
	add_child(_tap_catcher)


func _fighter(tex: Texture2D, feet: Vector2) -> TextureRect:
	var r := TextureRect.new()
	r.texture = tex
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	r.size = Vector2(144, 144)
	r.position = feet - Vector2(72, 144)
	r.pivot_offset = Vector2(72, 144)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(r)
	return r


func _home(sprite: TextureRect) -> Vector2:
	return (PLAYER_HOME if sprite == _player_sprite else ENEMY_HOME) - Vector2(72, 144)


func _stat_row(tag: String, color: Color) -> Array:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	var l := UiKit.label(tag, 12, color.lightened(0.3))
	l.custom_minimum_size = Vector2(20, 0)
	row.add_child(l)
	var b := UiKit.bar(color, 8)
	b.custom_minimum_size = Vector2(80, 8)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(b)
	var t := UiKit.label("", 12)
	t.custom_minimum_size = Vector2(52, 0)
	row.add_child(t)
	return [b, t, row]


func _refresh_bars() -> void:
	var p := logic.p
	_p_name.text = "%s  Lv.%d" % [p["name"], int(GameState.player["level"])]
	_p_hp.max_value = int(p["max_hp"])
	_p_hp.value = int(p["hp"])
	_p_hp_txt.text = "%d/%d" % [int(p["hp"]), int(p["max_hp"])]
	_p_mp.max_value = maxi(1, int(p["max_mp"]))
	_p_mp.value = int(p["mp"])
	_p_mp_txt.text = "%d/%d" % [int(p["mp"]), int(p["max_mp"])]
	_e_hp.max_value = int(logic.e["max_hp"])
	_e_hp.value = int(logic.e["hp"])
	_charge_label.visible = logic.charge_mult > 1.0


# ------------------------------------------------------------------ 자세 / 대기 동작
func _pose(sprite: TextureRect, pose: String) -> void:
	var tex_map := _player_tex if sprite == _player_sprite else _enemy_tex
	if tex_map.has(pose) and tex_map[pose]:
		sprite.texture = tex_map[pose]


func _idle_breath() -> void:
	if _breath_tween:
		_breath_tween.kill()
	_breath_tween = create_tween().set_loops()
	_breath_tween.tween_property(_player_sprite, "scale", Vector2(1.0, 1.025), 0.5).set_trans(Tween.TRANS_SINE)
	_breath_tween.parallel().tween_property(_enemy_sprite, "scale", Vector2(1.02, 0.985), 0.5).set_trans(Tween.TRANS_SINE)
	_breath_tween.tween_property(_player_sprite, "scale", Vector2.ONE, 0.5).set_trans(Tween.TRANS_SINE)
	_breath_tween.parallel().tween_property(_enemy_sprite, "scale", Vector2.ONE, 0.5).set_trans(Tween.TRANS_SINE)


# ------------------------------------------------------------------ 진행
func _intro() -> void:
	_enemy_sprite.modulate.a = 0.0
	_enemy_sprite.position.x += 60
	var t := create_tween().set_parallel(true)
	t.tween_property(_enemy_sprite, "modulate:a", 1.0, 0.2)
	t.tween_property(_enemy_sprite, "position:x", _home(_enemy_sprite).x, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_banner(str(enemy_def.get("name", "")))
	await get_tree().create_timer(0.6).timeout
	var fallback := "%s 나타났다!" % KText.josa(str(enemy_def.get("name", "적")), "이/가")
	await _say(str(enemy_def.get("intro", fallback)))
	_show_commands()


func _show_commands() -> void:
	busy = false
	_pose(_player_sprite, "ready")
	_msg.text = "%s 무엇을 할까?" % KText.josa(logic.p["name"], "은/는")
	if timing_enabled and not auto_on:
		_msg.text += "\n(공격 때 원이 겹치면, 적의 「!」에 맞춰 [확인])"
	for c in _cmd_box.get_children():
		c.queue_free()
	_skill_buttons.clear()
	_cmd_box.columns = 4
	var buttons: Array = []
	for i in GameState.slot_count():
		if i < GameState.equipped.size():
			var sid: String = GameState.equipped[i]
			var b := _skill_button(sid)
			_cmd_box.add_child(b)
			buttons.append(b)
			_skill_buttons[sid] = b
		else:
			var empty := UiKit.button("", Vector2(45, 44))
			empty.disabled = true
			_cmd_box.add_child(empty)
	for e in [["공격", _cmd_attack, true], ["방어", _cmd_guard, true],
			["아이템", _cmd_items, _has_battle_items()], ["도주", _cmd_flee, true]]:
		var b := UiKit.button(e[0], Vector2(45, 24))
		b.add_theme_stylebox_override("normal", UiKit.box(Color8(54, 40, 34), Color8(112, 88, 62), 1, 2))
		b.disabled = not e[2]
		b.pressed.connect(e[1])
		_cmd_box.add_child(b)
		buttons.append(b)
	_cmd_panel.visible = true
	UiKit.chain_focus(buttons)
	var first := UiKit.first_enabled(buttons)
	if first and not auto_on:
		first.grab_focus.call_deferred()
	if auto_on:
		_auto_step.call_deferred()


func _skill_button(sid: String) -> Button:
	var s: Dictionary = DataDB.skills.get(sid, {})
	var b := Button.new()
	b.custom_minimum_size = Vector2(45, 44)
	b.icon = load("res://assets/ui/icons/%s.png" % s.get("icon", "skill_fist"))
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
	var cost := int(s.get("mp_cost", 0))
	b.text = ("MP%d" % cost) if cost > 0 else "—"
	b.add_theme_font_size_override("font_size", 12)
	b.add_theme_stylebox_override("normal", UiKit.box(Color8(54, 40, 34), Color8(112, 88, 62), 1, 2))
	b.add_theme_stylebox_override("hover", UiKit.box(Color8(80, 58, 46), UiKit.GOLD, 1, 2))
	b.add_theme_stylebox_override("pressed", UiKit.box(UiKit.VERMILION, UiKit.GOLD, 1, 2))
	b.add_theme_stylebox_override("disabled", UiKit.box(Color8(36, 28, 26), Color8(70, 60, 54), 1, 2))
	b.disabled = not logic.can_use_skill(sid)
	if b.disabled:
		b.modulate = Color(0.6, 0.6, 0.6)
	b.tooltip_text = str(s.get("name", sid))
	var lv := GameState.skill_level(sid)
	var desc := "%s%s — %s" % [s.get("name", sid), (" %d성" % lv) if lv > 0 else "", s.get("desc", "")]
	b.focus_entered.connect(func(): if not busy: _msg.text = desc)
	b.mouse_entered.connect(func(): if not busy: _msg.text = desc)
	b.pressed.connect(_use_skill.bind(sid))
	return b


## 아이템 등 목록형 하위 메뉴
func _fill_commands(entries: Array, columns: int, back: bool = false) -> void:
	for c in _cmd_box.get_children():
		c.queue_free()
	_cmd_box.columns = columns
	var buttons: Array = []
	for e in entries:
		var b := UiKit.button(e[0], Vector2(190, 22))
		b.disabled = not e[2]
		b.pressed.connect(e[1])
		_cmd_box.add_child(b)
		buttons.append(b)
	if back:
		var bb := UiKit.button("뒤로", Vector2(190, 22))
		bb.pressed.connect(_show_commands)
		_cmd_box.add_child(bb)
		buttons.append(bb)
	_cmd_panel.visible = true
	UiKit.chain_focus(buttons)
	var first := UiKit.first_enabled(buttons)
	if first:
		first.grab_focus.call_deferred()


func _hide_commands() -> void:
	busy = true
	_cmd_panel.visible = false


func _has_battle_items() -> bool:
	for item_id in GameState.inventory:
		if bool(DataDB.items.get(item_id, {}).get("usable_in_battle", false)):
			return true
	return false


# ------------------------------------------------------------------ 자동 전투 / 배속
func toggle_auto() -> void:
	if not auto_allowed:
		_msg.text = "첫 대결은 직접 싸워야 한다. (한 번 이긴 상대·수련 상대만 자동 전투)"
		return
	auto_on = not auto_on
	Settings.set_value("battle_auto", auto_on)
	_refresh_toggles()
	if auto_on and not busy:
		_auto_step()


func toggle_speed() -> void:
	Settings.set_value("battle_speed", 1 if Settings.battle_speed >= 2 else 2)
	Engine.time_scale = 2.0 if Settings.battle_speed >= 2 else 1.0
	_refresh_toggles()


func _refresh_toggles() -> void:
	if not _auto_btn:
		return
	_auto_btn.text = ("자동 ON" if auto_on else "자동") if auto_allowed else "자동 잠김"
	_auto_btn.modulate = Color(1.25, 1.1, 0.8) if auto_on else (Color(1, 1, 1) if auto_allowed else Color(0.6, 0.6, 0.6))
	_speed_btn.text = "2배속" if Settings.battle_speed >= 2 else "1배속"
	_speed_btn.modulate = Color(1.25, 1.1, 0.8) if Settings.battle_speed >= 2 else Color(1, 1, 1)


func _auto_step() -> void:
	await get_tree().create_timer(0.2).timeout
	if not is_inside_tree() or not auto_on or busy or logic.state != BattleLogic.State.ONGOING:
		return
	var choice := logic.auto_choose(GameState.equipped, GameState.item_count("herb"))
	match choice["kind"]:
		"item":
			_use_item(choice["id"])
		_:
			_use_skill(choice["id"])


# ------------------------------------------------------------------ 명령
func _cmd_attack() -> void:
	await _use_skill("basic_fist")


func _use_skill(sid: String) -> void:
	if busy:
		return
	var s: Dictionary = DataDB.skills.get(sid, {})
	if not logic.can_use_skill(sid):
		_msg.text = "MP가 부족하다!"
		return
	_hide_commands()
	var timing := 1.0
	last_timing = ""
	if s.get("type", "") == "attack":
		if sid != "basic_fist":
			_cutin(str(s.get("name", "")))
		timing = await _timing_ring()
	var events := logic.player_skill(sid, timing)
	match s.get("type", ""):
		"attack":
			await _attack_sequence(sid, events)
		"buff":
			await _buff_sequence(events)
		"heal_mp":
			await _breath_sequence(events)
		"guard":
			await _guard_sequence(events)
		_:
			await _play_texts(events)
	await _after_player_action()


func _cmd_guard() -> void:
	if busy:
		return
	_hide_commands()
	await _guard_sequence(logic.player_guard())
	await _after_player_action()


func _cmd_items() -> void:
	var entries: Array = []
	for item_id in GameState.inventory:
		var def: Dictionary = DataDB.items.get(item_id, {})
		if bool(def.get("usable_in_battle", false)):
			entries.append(["%s x%d" % [def.get("name", item_id), GameState.item_count(item_id)], _use_item.bind(item_id), true])
	_fill_commands(entries, 1, true)
	_msg.text = "어떤 아이템을 쓸까?"


func _use_item(item_id: String) -> void:
	if busy:
		return
	var def: Dictionary = DataDB.items.get(item_id, {})
	if not GameState.remove_item(item_id):
		return
	_hide_commands()
	var events := logic.player_item(def)
	_pose(_player_sprite, "win")
	for ev in events:
		if ev["fx"] == "heal":
			_float_text(_player_sprite, "+%d" % int(ev["heal"]) if int(ev["heal"]) > 0 else "회복", Color(0.5, 1, 0.5))
			_wisps(_player_sprite, Color8(150, 240, 150))
	_refresh_bars()
	await _play_texts(events)
	await _after_player_action()


func _cmd_flee() -> void:
	if busy:
		return
	_hide_commands()
	var events := logic.player_flee()
	if logic.state == BattleLogic.State.FLED:
		await _play_texts(events)
	else:
		_pose(_player_sprite, "hurt")
		var x := _player_sprite.position.x
		var t := create_tween()
		t.tween_property(_player_sprite, "position:x", x - 30, 0.15)
		t.tween_property(_player_sprite, "rotation", 0.25, 0.08)
		t.tween_property(_player_sprite, "rotation", 0.0, 0.1)
		t.tween_property(_player_sprite, "position:x", x, 0.15)
		await _play_texts(events)
	await _after_player_action()


## 플레이어 행동 후: 종료 확인 → 적 턴 → 종료 확인 → 명령 대기
func _after_player_action() -> void:
	if await _check_end():
		return
	await get_tree().create_timer(0.08).timeout
	await _enemy_sequence()
	if await _check_end():
		return
	_show_commands()


# ------------------------------------------------------------------ 연출: 플레이어
func _attack_sequence(sid: String, events: Array) -> void:
	var cast_text := ""
	var hits: Array = []
	var tail: Array = []
	for ev in events:
		match ev["fx"]:
			"cast":
				cast_text = ev["text"]
			"hit", "crit":
				hits.append(ev)
			_:
				tail.append(ev)
	_msg.text = cast_text + ("  완벽!" if last_timing == "perfect" else "")
	var home := _home(_player_sprite)
	var strike_x := _enemy_sprite.position.x - 78
	# 돌진 (잔상)
	_pose(_player_sprite, "ready")
	_afterimage(_player_sprite)
	var t := create_tween()
	t.tween_property(_player_sprite, "position:x", strike_x, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	await t.finished
	var is_kick := sid == "wind_kick"
	for i in hits.size():
		var ev: Dictionary = hits[i]
		var crit: bool = ev["fx"] == "crit"
		_pose(_player_sprite, "kick" if is_kick or (sid == "combo_fist" and i == 1) else "punch")
		_player_sprite.position.x = strike_x + 6
		if is_kick:
			_fx("res://assets/fx/wind.png", _enemy_sprite, Vector2(160, 160), 0.3, Color8(200, 240, 230))
			_zoom(1.08, 0.25)
		await _impact(_enemy_sprite, int(ev["damage"]), crit or last_timing == "perfect")
		_refresh_bars()
		if i < hits.size() - 1:
			_afterimage(_player_sprite)
			_pose(_player_sprite, "ready")
			_player_sprite.position.x = strike_x
			await get_tree().create_timer(0.07).timeout
	if hits.size() > 0:
		_msg.text = "\n".join(hits.map(func(e): return e["text"]))
	# 복귀
	await get_tree().create_timer(0.12).timeout
	_pose(_player_sprite, "ready")
	var back := create_tween()
	back.tween_property(_player_sprite, "position:x", home.x, 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	await back.finished
	if not tail.is_empty():
		for ev in tail:
			if ev["fx"] == "down":
				_knock_out(_enemy_sprite)
		await _play_texts(tail)
	else:
		await _say(_msg.text)


func _buff_sequence(events: Array) -> void:
	_pose(_player_sprite, "shout")
	_msg.text = events[0]["text"]
	_fx("res://assets/fx/ring.png", _player_sprite, Vector2(220, 220), 0.4, Color8(255, 210, 120), Vector2(0.3, 0.3))
	_flash(_player_sprite, Color(1.8, 1.5, 0.7))
	_zoom(1.05, 0.3)
	_shake(3.0)
	await get_tree().create_timer(0.3).timeout
	_refresh_bars()
	await _play_texts(events.slice(1))


func _breath_sequence(events: Array) -> void:
	_pose(_player_sprite, "guard")
	_wisps(_player_sprite, Color8(150, 200, 255))
	_refresh_bars()
	await _play_texts(events)


func _guard_sequence(events: Array) -> void:
	_pose(_player_sprite, "guard")
	if _shield:
		_shield.queue_free()
	_shield = _fx("res://assets/fx/shield.png", _player_sprite, Vector2(150, 160), -1.0, Color(1, 1, 1, 0.85))
	await _play_texts(events)


# ------------------------------------------------------------------ 연출: 적
func _enemy_sequence() -> void:
	if logic.state != BattleLogic.State.ONGOING:
		return
	var action := logic.choose_enemy_action()
	var parried := false
	if action.get("type", "attack") == "attack":
		_msg.text = str(action.get("text", ""))
		_pose(_enemy_sprite, "windup")
		parried = await _parry_window()
		# 돌진 공격
		var home := _home(_enemy_sprite)
		var t := create_tween()
		t.tween_property(_enemy_sprite, "position:x", _player_sprite.position.x + 82, 0.11).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		await t.finished
		_pose(_enemy_sprite, "attack")
		var events := logic.enemy_turn(action, parried)
		for ev in events:
			if ev["fx"] in ["hit", "crit", "parry"]:
				if parried or logic.player_guarding:
					_pose(_player_sprite, "guard")
				await _impact(_player_sprite, int(ev["damage"]), ev["fx"] == "crit", parried)
		_refresh_bars()
		await get_tree().create_timer(0.1).timeout
		_pose(_enemy_sprite, "idle")
		var back := create_tween()
		back.tween_property(_enemy_sprite, "position:x", home.x, 0.15)
		await back.finished
		if logic.state == BattleLogic.State.LOST:
			_knock_out(_player_sprite)
		else:
			_pose(_player_sprite, "ready")
		await _play_texts(events.slice(1))
	else:
		var events := logic.enemy_turn(action)
		var bob := create_tween()
		bob.tween_property(_enemy_sprite, "position:y", _enemy_sprite.position.y - 8, 0.1)
		bob.tween_property(_enemy_sprite, "position:y", _home(_enemy_sprite).y, 0.1)
		await _play_texts(events)
	if _shield:
		_shield.queue_free()
		_shield = null


# ------------------------------------------------------------------ 타이밍 입력
## 공격 타이밍 원: 바깥 원이 줄어들어 과녁 원과 겹칠 때 누르면 완벽. 반환: 피해 배율
func _timing_ring() -> float:
	if not timing_enabled or auto_on:
		return 1.0
	var target := _fx("res://assets/fx/target_ring.png", _enemy_sprite, Vector2(64, 64), -1.0, Color(1, 1, 1, 0.9))
	var ring := _fx("res://assets/fx/target_ring.png", _enemy_sprite, Vector2(64, 64), -1.0, Color8(255, 200, 120))
	var dur := _cfg_t("ring_time", 0.55)
	var win := _cfg_t("perfect_window", 0.16)
	var start := Time.get_ticks_msec()
	_timing_active = true
	_tap_catcher.mouse_filter = Control.MOUSE_FILTER_STOP
	var pressed_at := -1.0
	var done := [false]
	var on_press := func(): done[0] = true
	_timing_pressed.connect(on_press)
	while not done[0]:
		var el := (Time.get_ticks_msec() - start) / 1000.0 * Engine.time_scale
		if el > dur + win:
			break
		var s := lerpf(2.4, 1.0, clampf(el / dur, 0.0, 1.0))
		ring.scale = Vector2(s, s)
		await get_tree().process_frame
	if done[0]:
		pressed_at = (Time.get_ticks_msec() - start) / 1000.0 * Engine.time_scale
	_timing_pressed.disconnect(on_press)
	_timing_active = false
	_tap_catcher.mouse_filter = Control.MOUSE_FILTER_IGNORE
	target.queue_free()
	ring.queue_free()
	if pressed_at >= 0.0 and absf(pressed_at - dur) <= win:
		last_timing = "perfect"
		_popup_word("완벽!", _enemy_sprite, Color8(255, 220, 120))
		return _cfg_t("perfect_mult", 1.3)
	last_timing = "good"
	return 1.0


## 적의 공격 직전 "!" 가 떠 있는 동안 누르면 받아치기 성공
func _parry_window() -> bool:
	var windup := _cfg_t("windup_time", 0.45)
	if not timing_enabled or auto_on:
		await get_tree().create_timer(windup * 0.6).timeout
		return false
	await get_tree().create_timer(windup * 0.5).timeout
	var mark := UiKit.brush_label("!", 56, Color8(240, 70, 50))
	mark.add_theme_color_override("font_outline_color", Color8(20, 14, 14))
	mark.add_theme_constant_override("outline_size", 8)
	mark.position = _enemy_sprite.position + Vector2(58, -10)
	_stage.add_child(mark)
	var win := _cfg_t("parry_window", 0.28)
	var start := Time.get_ticks_msec()
	_timing_active = true
	_tap_catcher.mouse_filter = Control.MOUSE_FILTER_STOP
	var done := [false]
	var on_press := func(): done[0] = true
	_timing_pressed.connect(on_press)
	while not done[0] and (Time.get_ticks_msec() - start) / 1000.0 * Engine.time_scale < win:
		await get_tree().process_frame
	_timing_pressed.disconnect(on_press)
	_timing_active = false
	_tap_catcher.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mark.queue_free()
	if done[0]:
		last_timing = "parry"
		_popup_word("받아치기!", _player_sprite, Color8(160, 210, 255))
		return true
	return false


## 테스트/디버그: 타이밍 입력을 누른 것으로 처리
func timing_press() -> void:
	if _timing_active:
		_timing_pressed.emit()


func is_timing_active() -> bool:
	return _timing_active


# ------------------------------------------------------------------ 종료 처리
## 전투 종료 여부를 확인하고, 끝났으면 결과 처리 후 true.
func _check_end() -> bool:
	match logic.state:
		BattleLogic.State.WON:
			_knock_out(_enemy_sprite)
			_pose(_player_sprite, "win")
			_banner("승 리")
			GameState.set_hp_mp(int(logic.p["hp"]), int(logic.p["mp"]))
			GameState.set_flag("beaten_" + enemy_id)
			var qi_gain := int(logic.e["qi"])
			if qi_gain > 0:
				GameState.add_qi(qi_gain)
			var exp_gain := int(logic.e["exp"])
			var gold := int(logic.e["gold"])
			await _say("경험치 %d, 내공 %d을(를) 얻었다!" % [exp_gain, qi_gain])
			if gold > 0:
				GameState.player["gold"] = int(GameState.player["gold"]) + gold
				await _say("%d냥을 주웠다! (덕팔의 비상금인 것 같다)" % gold if enemy_id == "bandit" else "%d냥을 얻었다!" % gold)
			for line in GameState.add_exp(exp_gain):
				# 레벨업 시 회복/성장한 능력치를 전투 화면에도 반영
				var eff := GameState.effective_stats()
				for key in ["hp", "max_hp", "mp", "max_mp", "attack", "defense", "agility"]:
					logic.p[key] = int(eff[key])
				_refresh_bars()
				_flash(_player_sprite, Color(1.8, 1.6, 0.8))
				await _say(line)
			await _confirm()
			GameState.finish_battle("win")
			return true
		BattleLogic.State.LOST:
			_knock_out(_player_sprite)
			await _confirm()
			GameState.finish_battle("lose")
			return true
		BattleLogic.State.FLED:
			GameState.set_hp_mp(int(logic.p["hp"]), int(logic.p["mp"]))
			_pose(_player_sprite, "ready")
			_player_sprite.flip_h = true
			var t := create_tween()
			t.tween_property(_player_sprite, "position:x", -170.0, 0.35)
			await t.finished
			GameState.finish_battle("flee")
			return true
	return false


# ------------------------------------------------------------------ 메시지
func _say(text: String) -> void:
	_msg.text = text
	var delay := float(DataDB.battle_config.get("message_delay", 0.4))
	var timer := get_tree().create_timer(delay)
	var done := [false]
	var finish := func(): done[0] = true
	timer.timeout.connect(finish)
	_skip_requested.connect(finish, CONNECT_ONE_SHOT)
	while not done[0]:
		await get_tree().process_frame
	if _skip_requested.is_connected(finish):
		_skip_requested.disconnect(finish)


func _play_texts(events: Array) -> void:
	for ev in events:
		_refresh_bars()
		await _say(ev["text"])


func _confirm() -> void:
	if auto_on:
		await get_tree().create_timer(0.6).timeout
		return
	_msg.text += "  ▼"
	_waiting_confirm = true
	await _skip_requested
	_waiting_confirm = false


func _unhandled_input(event: InputEvent) -> void:
	if _timing_active and (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		_timing_pressed.emit()
		get_viewport().set_input_as_handled()
		return
	if not busy:
		if event.is_action_pressed("cancel") and _cmd_box.columns == 1:  # 아이템 목록에서 뒤로
			_show_commands()
			get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		_skip_requested.emit()
		get_viewport().set_input_as_handled()


func _on_message_input(event: InputEvent) -> void:
	if busy and not _timing_active and event is InputEventMouseButton and event.pressed:
		_skip_requested.emit()


# ------------------------------------------------------------------ 이펙트
## 타격: 히트스톱 + 이펙트 + 넉백 + 숫자
func _impact(target: TextureRect, dmg: int, strong: bool, parried: bool = false) -> void:
	var is_enemy := target == _enemy_sprite
	if not (parried or (not is_enemy and logic.player_guarding)):
		_pose(target, "hurt")
	_fx("res://assets/fx/impact.png", target, Vector2(96, 96) * (1.4 if strong else 1.0), 0.18,
		Color8(160, 210, 255) if parried else (Color8(255, 220, 140) if strong else Color(1, 1, 1)), Vector2(0.4, 0.4))
	_flash(target, Color(2.6, 2.6, 2.6))
	_float_text(target, str(dmg) + ("!" if strong else ""), Color(1, 0.85, 0.3) if strong else Color(1, 1, 1), 1.4 if strong else 1.0)
	_shake(7.0 if strong else 3.5)
	if strong:
		_zoom(1.07, 0.2)
	# 히트스톱
	await get_tree().create_timer(0.07 if strong else 0.05).timeout
	var dir := 1.0 if is_enemy else -1.0
	var x := target.position.x
	var t := create_tween()
	t.tween_property(target, "position:x", x + 14.0 * dir, 0.06).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.tween_property(target, "position:x", x, 0.12)
	await get_tree().create_timer(0.08).timeout
	if is_enemy and logic.state == BattleLogic.State.ONGOING:
		_pose(target, "idle")


func _knock_out(sprite: TextureRect) -> void:
	_pose(sprite, "ko")
	var t := create_tween()
	var dir := 1.0 if sprite == _enemy_sprite else -1.0
	t.tween_property(sprite, "position:x", sprite.position.x + 30.0 * dir, 0.25).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.parallel().tween_property(sprite, "position:y", sprite.position.y + 6, 0.25)
	if sprite == _enemy_sprite:
		t.tween_property(sprite, "modulate", Color(1, 0.4, 0.4, 0.0), 0.6).set_delay(0.3)


func _fx(path: String, target: TextureRect, size: Vector2, life: float, color: Color = Color.WHITE, from_scale: Vector2 = Vector2.ONE) -> TextureRect:
	var r := TextureRect.new()
	r.texture = load(path)
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.size = size
	r.pivot_offset = size / 2.0
	r.position = target.position + Vector2(72, 80) - size / 2.0
	r.modulate = color
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(r)
	if life > 0.0:
		r.scale = from_scale
		var t := create_tween().set_parallel(true)
		t.tween_property(r, "scale", Vector2.ONE * 1.15, life).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		t.tween_property(r, "modulate:a", 0.0, life).set_delay(life * 0.4)
		t.chain().tween_callback(r.queue_free)
	return r


func _wisps(target: TextureRect, color: Color) -> void:
	for i in 6:
		var w := TextureRect.new()
		w.texture = load("res://assets/fx/wisp.png")
		w.modulate = color
		w.mouse_filter = Control.MOUSE_FILTER_IGNORE
		w.position = target.position + Vector2(randf_range(36, 100), randf_range(80, 130))
		_stage.add_child(w)
		var t := create_tween().set_parallel(true)
		t.tween_property(w, "position:y", w.position.y - randf_range(50, 90), 0.7).set_delay(i * 0.05)
		t.tween_property(w, "modulate:a", 0.0, 0.7).set_delay(i * 0.05 + 0.2)
		t.chain().tween_callback(w.queue_free)


func _afterimage(sprite: TextureRect) -> void:
	var g := TextureRect.new()
	g.texture = sprite.texture
	g.expand_mode = sprite.expand_mode
	g.stretch_mode = sprite.stretch_mode
	g.size = sprite.size
	g.position = sprite.position
	g.flip_h = sprite.flip_h
	g.modulate = Color(0.6, 0.8, 1.0, 0.5)
	g.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(g)
	_stage.move_child(g, sprite.get_index())
	var t := create_tween()
	t.tween_property(g, "modulate:a", 0.0, 0.22)
	t.tween_callback(g.queue_free)


func _zoom(amount: float, dur: float) -> void:
	_stage.pivot_offset = get_viewport_rect().size / 2.0
	var t := create_tween()
	t.tween_property(_stage, "scale", Vector2.ONE * amount, dur * 0.35).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.tween_property(_stage, "scale", Vector2.ONE, dur * 0.65).set_trans(Tween.TRANS_QUAD)


func _shake(power: float) -> void:
	var t := create_tween()
	for i in 5:
		t.tween_property(_stage, "position", Vector2(randf_range(-power, power), randf_range(-power, power)), 0.03)
	t.tween_property(_stage, "position", Vector2.ZERO, 0.03)


func _flash(sprite: TextureRect, color: Color) -> void:
	var t := create_tween()
	t.tween_property(sprite, "self_modulate", color, 0.04)
	t.tween_property(sprite, "self_modulate", Color(1, 1, 1), 0.18)


func _float_text(sprite: TextureRect, text: String, color: Color, size_mult: float = 1.0) -> void:
	var l := UiKit.label(text, 24, color)
	l.add_theme_color_override("font_outline_color", Color(0.15, 0.05, 0.1))
	l.add_theme_constant_override("outline_size", 6)
	l.position = sprite.position + Vector2(56, 24)
	l.pivot_offset = Vector2(16, 12)
	l.scale = Vector2.ONE * 0.4
	add_child(l)
	var t := create_tween()
	t.tween_property(l, "scale", Vector2.ONE * 1.3 * size_mult, 0.08).set_trans(Tween.TRANS_BACK)
	t.tween_property(l, "scale", Vector2.ONE * size_mult, 0.08)
	t.parallel().tween_property(l, "position:y", l.position.y - 28, 0.6)
	t.tween_property(l, "modulate:a", 0.0, 0.25)
	t.tween_callback(l.queue_free)


func _popup_word(text: String, sprite: TextureRect, color: Color) -> void:
	var l := UiKit.brush_label(text, 34, color)
	l.add_theme_color_override("font_outline_color", Color8(20, 14, 14))
	l.add_theme_constant_override("outline_size", 6)
	l.position = sprite.position + Vector2(20, -10)
	add_child(l)
	var t := create_tween()
	t.tween_property(l, "position:y", l.position.y - 16, 0.35).set_trans(Tween.TRANS_BACK)
	t.tween_property(l, "modulate:a", 0.0, 0.25)
	t.tween_callback(l.queue_free)


## 붓글씨 띠 (등장·승리)
func _banner(text: String) -> void:
	var band := ColorRect.new()
	band.color = Color8(20, 14, 14, 200)
	band.anchor_right = 1.0
	band.offset_top = 112
	band.offset_bottom = 172
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(band)
	var l := UiKit.brush_label(text, 48, UiKit.TEXT)
	l.set_anchors_preset(Control.PRESET_FULL_RECT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	band.add_child(l)
	band.modulate.a = 0.0
	var t := create_tween()
	t.tween_property(band, "modulate:a", 1.0, 0.12)
	t.tween_interval(0.5)
	t.tween_property(band, "modulate:a", 0.0, 0.2)
	t.tween_callback(band.queue_free)


## 무공 이름 붓글씨 컷인
func _cutin(text: String) -> void:
	var band := ColorRect.new()
	band.color = Color8(20, 14, 14, 215)
	band.anchor_right = 1.0
	band.offset_top = 128
	band.offset_bottom = 176
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(band)
	var red := ColorRect.new()
	red.color = UiKit.VERMILION
	red.anchor_right = 1.0
	red.offset_bottom = 3
	band.add_child(red)
	var l := UiKit.brush_label(text, 44, UiKit.TEXT)
	l.set_anchors_preset(Control.PRESET_FULL_RECT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	band.add_child(l)
	l.position.x = 120
	var t := create_tween().set_parallel(true)
	t.tween_property(l, "position:x", 0.0, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.tween_property(band, "modulate:a", 0.0, 0.15).set_delay(0.38)
	t.chain().tween_callback(band.queue_free)
