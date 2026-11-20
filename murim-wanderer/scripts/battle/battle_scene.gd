extends Control
## 턴제 전투 화면. 규칙은 BattleLogic, 이 스크립트는 화면 연출과 입력만 담당한다.
## 명령: 장착 무공 아이콘(최대 4) + 공격 / 방어 / 아이템 / 도주, 자동 전투·2배속 토글

signal _skip_requested

const PLAYER_POS := Vector2(180, 226)  # 발 위치 (640x360 기준)
const ENEMY_POS := Vector2(460, 214)

var logic := BattleLogic.new()
var enemy_id := ""
var enemy_def: Dictionary = {}
var busy := true

var _player_sprite: TextureRect
var _enemy_sprite: TextureRect
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
var auto_on := false
var auto_allowed := false
var _auto_btn: Button
var _speed_btn: Button
var _skill_buttons: Dictionary = {}


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
	Engine.time_scale = 2.0 if Settings.battle_speed >= 2 else 1.0
	_build()
	_refresh_bars()
	_intro.call_deferred()


# ------------------------------------------------------------------ 화면 구성
func _build() -> void:
	var bg := TextureRect.new()
	bg.texture = load("res://assets/backgrounds/battle_training.png")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	add_child(bg)

	_player_sprite = _fighter(load(DataDB.player_def.get("battle_sprite", "res://assets/characters/doyun_battle.png")), PLAYER_POS)
	_enemy_sprite = _fighter(load(enemy_def.get("sprite", "res://assets/enemies/scarecrow_battle.png")), ENEMY_POS)

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
	mp.offset_top = -124
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
	_cmd_panel.offset_top = -124
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


func _fighter(tex: Texture2D, feet: Vector2) -> TextureRect:
	var r := TextureRect.new()
	r.texture = tex
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var sz := tex.get_size()
	r.size = sz
	r.position = feet - Vector2(sz.x / 2.0, sz.y)
	r.pivot_offset = Vector2(sz.x / 2.0, sz.y)
	add_child(r)
	return r


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


# ------------------------------------------------------------------ 진행
func _intro() -> void:
	_enemy_sprite.modulate.a = 0.0
	var t := create_tween()
	t.tween_property(_enemy_sprite, "modulate:a", 1.0, 0.2)
	_banner(str(enemy_def.get("name", "")))
	await get_tree().create_timer(0.6).timeout
	var fallback := "%s 나타났다!" % KText.josa(str(enemy_def.get("name", "적")), "이/가")
	await _say(str(enemy_def.get("intro", fallback)))
	_show_commands()


func _show_commands() -> void:
	busy = false
	_msg.text = "%s 무엇을 할까?" % KText.josa(logic.p["name"], "은/는")
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
		b.add_theme_constant_override("h_separation", 0)
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
	var desc := "%s%s — %s" % [s.get("name", sid), (" +%d" % lv) if lv > 0 else "", s.get("desc", "")]
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
	var w := 190
	for e in entries:
		var b := UiKit.button(e[0], Vector2(w, 22))
		b.disabled = not e[2]
		b.pressed.connect(e[1])
		_cmd_box.add_child(b)
		buttons.append(b)
	if back:
		var bb := UiKit.button("뒤로", Vector2(w, 22))
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
	await get_tree().create_timer(0.25).timeout
	if not is_inside_tree() or not auto_on or busy or logic.state != BattleLogic.State.ONGOING:
		return
	var choice := logic.auto_choose(GameState.equipped, GameState.item_count("herb"))
	match choice["kind"]:
		"item":
			_use_item(choice["id"])
		_:
			_use_skill(choice["id"])


func _exit_tree() -> void:
	Engine.time_scale = 1.0


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


# ------------------------------------------------------------------ 명령
func _cmd_attack() -> void:
	await _do_player_action(func(): return logic.player_attack())


func _use_skill(sid: String) -> void:
	if busy:
		return
	if sid != "basic_fist" and logic.can_use_skill(sid):
		_cutin(str(DataDB.skills.get(sid, {}).get("name", "")))
	await _do_player_action(func(): return logic.player_skill(sid))


func _cmd_guard() -> void:
	await _do_player_action(func(): return logic.player_guard())


func _cmd_items() -> void:
	var entries: Array = []
	for item_id in GameState.inventory:
		var def: Dictionary = DataDB.items.get(item_id, {})
		if bool(def.get("usable_in_battle", false)):
			entries.append(["%s x%d" % [def.get("name", item_id), GameState.item_count(item_id)], _use_item.bind(item_id), true])
	_fill_commands(entries, 1, true)
	_msg.text = "어떤 아이템을 쓸까?"


func _use_item(item_id: String) -> void:
	var def: Dictionary = DataDB.items.get(item_id, {})
	if not GameState.remove_item(item_id):
		return
	await _do_player_action(func(): return logic.player_item(def))


func _cmd_flee() -> void:
	await _do_player_action(func(): return logic.player_flee())


## 플레이어 행동 → 연출 → (계속 중이면) 적 행동 → 연출 → 명령 대기
func _do_player_action(action: Callable) -> void:
	if busy:
		return
	_hide_commands()
	var events: Array = action.call()
	if events.size() == 1 and events[0]["fx"] == "invalid":
		await _say(events[0]["text"])
		_show_commands()
		return
	await _play_events(events)
	if await _check_end():
		return
	await get_tree().create_timer(0.1).timeout
	await _play_events(logic.enemy_turn())
	if await _check_end():
		return
	_show_commands()


func _play_events(events: Array) -> void:
	for ev in events:
		match ev["fx"]:
			"cast":
				_lunge(_player_sprite, 1)
			"enemy_cast":
				_lunge(_enemy_sprite, -1)
			"hit", "crit":
				var target := _enemy_sprite if ev["target"] == "enemy" else _player_sprite
				_hit_fx(target, int(ev["damage"]), ev["fx"] == "crit")
			"heal":
				_float_text(_player_sprite, "+%d" % int(ev["heal"]) if int(ev["heal"]) > 0 else "회복", Color(0.5, 1, 0.5))
			"buff":
				_flash(_player_sprite, Color(1.6, 1.3, 0.6))
			"guard":
				_flash(_player_sprite, Color(0.7, 0.9, 1.6))
			"down":
				var who := _enemy_sprite if ev["target"] == "enemy" else _player_sprite
				var t := create_tween()
				t.tween_property(who, "modulate", Color(1, 0.3, 0.3, 0.0), 0.6)
		_refresh_bars()
		await _say(ev["text"])


## 전투 종료 여부를 확인하고, 끝났으면 결과 처리 후 true.
func _check_end() -> bool:
	match logic.state:
		BattleLogic.State.WON:
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
			await _confirm()
			GameState.finish_battle("lose")
			return true
		BattleLogic.State.FLED:
			GameState.set_hp_mp(int(logic.p["hp"]), int(logic.p["mp"]))
			var t := create_tween()
			t.tween_property(_player_sprite, "position:x", -160.0, 0.4)
			await t.finished
			GameState.finish_battle("flee")
			return true
	return false


# ------------------------------------------------------------------ 메시지 & 연출
func _say(text: String) -> void:
	_msg.text = text
	var delay := float(DataDB.battle_config.get("message_delay", 0.9))
	var timer := get_tree().create_timer(delay)
	var done := [false]
	var finish := func(): done[0] = true
	timer.timeout.connect(finish)
	_skip_requested.connect(finish, CONNECT_ONE_SHOT)
	while not done[0]:
		await get_tree().process_frame
	if _skip_requested.is_connected(finish):
		_skip_requested.disconnect(finish)


func _confirm() -> void:
	if auto_on:
		await get_tree().create_timer(0.6).timeout
		return
	_msg.text += "  ▼"
	_waiting_confirm = true
	await _skip_requested
	_waiting_confirm = false


func _unhandled_input(event: InputEvent) -> void:
	if not busy:
		if event.is_action_pressed("cancel") and _cmd_box.columns == 1:  # 아이템 목록에서 뒤로
			_show_commands()
			get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		_skip_requested.emit()
		get_viewport().set_input_as_handled()


func _on_message_input(event: InputEvent) -> void:
	if busy and event is InputEventMouseButton and event.pressed:
		_skip_requested.emit()


## 붓글씨 적 이름 띠 (등장 연출)
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


func _slash(sprite: TextureRect, crit: bool) -> void:
	var s := TextureRect.new()
	s.texture = load("res://assets/ui/slash.png")
	s.size = Vector2(128, 128)
	s.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	s.position = sprite.position + sprite.size / 2.0 - s.size / 2.0
	s.pivot_offset = s.size / 2.0
	s.rotation = randf_range(-0.4, 0.4)
	s.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if crit:
		s.modulate = Color8(255, 200, 150)
	add_child(s)
	var t := create_tween()
	t.tween_property(s, "modulate:a", 0.0, 0.18).set_delay(0.06)
	t.tween_callback(s.queue_free)
	if crit:
		_shake(6.0)


func _shake(power: float) -> void:
	var t := create_tween()
	for i in 5:
		t.tween_property(self, "position", Vector2(randf_range(-power, power), randf_range(-power, power)), 0.03)
	t.tween_property(self, "position", Vector2.ZERO, 0.03)


func _lunge(sprite: TextureRect, dir: int) -> void:
	var x := sprite.position.x
	var t := create_tween()
	t.tween_property(sprite, "position:x", x + 18 * dir, 0.08)
	t.tween_property(sprite, "position:x", x, 0.12)


func _hit_fx(sprite: TextureRect, dmg: int, crit: bool) -> void:
	var x := sprite.position.x
	var t := create_tween()
	for i in 3:
		t.tween_property(sprite, "position:x", x + (5 if i % 2 == 0 else -5), 0.04)
	t.tween_property(sprite, "position:x", x, 0.04)
	_flash(sprite, Color(2.5, 2.5, 2.5))
	_slash(sprite, crit)
	_float_text(sprite, str(dmg) + ("!" if crit else ""), Color(1, 0.85, 0.3) if crit else Color(1, 1, 1))


func _flash(sprite: TextureRect, color: Color) -> void:
	var t := create_tween()
	t.tween_property(sprite, "modulate", color, 0.05)
	t.tween_property(sprite, "modulate", Color(1, 1, 1, sprite.modulate.a), 0.2)


func _float_text(sprite: TextureRect, text: String, color: Color) -> void:
	var l := UiKit.label(text, 24, color)
	l.add_theme_color_override("font_outline_color", Color(0.15, 0.05, 0.1))
	l.add_theme_constant_override("outline_size", 6)
	l.position = sprite.position + Vector2(48, 20)
	add_child(l)
	var t := create_tween()
	t.set_parallel(true)
	t.tween_property(l, "position:y", l.position.y - 30, 0.7)
	t.tween_property(l, "modulate:a", 0.0, 0.7).set_delay(0.3)
	t.chain().tween_callback(l.queue_free)
