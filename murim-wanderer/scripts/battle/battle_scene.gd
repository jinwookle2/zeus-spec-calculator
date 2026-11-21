extends Control
## 카드 전투 화면 (v0.5). 규칙은 BattleLogic, 이 스크립트는 연출과 입력.
##
## 화면: 위 — 상태창·적 의도 / 가운데 — 무대(자세·돌진·타격 연출) / 아래 — 손패·기(에너지)·턴 종료
## - 카드를 눌러 사용 (기·MP 소모). 공격 카드는 타이밍 원이 겹칠 때 [확인] = 완벽(x1.3)
## - 턴 종료 → 적이 예고한 행동 실행. 「!」에 맞춰 [확인] = 받아치기(피해 x0.4)
## - 승리하면 보상 카드 3장 중 1장 선택

signal _skip_requested
signal _timing_pressed
signal _reward_done

const PLAYER_HOME := Vector2(150, 226)  # 발 위치 (640x360 기준)
const ENEMY_HOME := Vector2(480, 220)
const CARD_SIZE := Vector2(72, 98)

var logic := BattleLogic.new()
var enemy_id := ""
var enemy_def: Dictionary = {}
var busy := true
var auto_on := false
var auto_allowed := false
var timing_enabled := true
var last_timing := ""  # "perfect" | "good" | "parry" | ""
var reward_options: Array = []

var _stage: Control
var _player_sprite: TextureRect
var _enemy_sprite: TextureRect
var _player_tex: Dictionary = {}
var _enemy_tex: Dictionary = {}
var _msg: Label
var _hand_box: Control
var _card_nodes: Array = []
var _energy_label: Label
var _pile_label: Label
var _end_btn: Button
var _item_btn: Button
var _flee_btn: Button
var _list_panel: PanelContainer
var _list_box: VBoxContainer
var _p_name: Label
var _p_hp: ProgressBar
var _p_mp: ProgressBar
var _p_hp_txt: Label
var _p_mp_txt: Label
var _p_status: Label
var _e_name: Label
var _e_hp: ProgressBar
var _e_hp_txt: Label
var _e_status: Label
var _intent_box: HBoxContainer
var _intent_icon: TextureRect
var _intent_label: Label
var _waiting_confirm := false
var _auto_btn: Button
var _speed_btn: Button
var _tap_catcher: Control
var _timing_active := false
var _shield: TextureRect
var _breath_tween: Tween
var _reward_panel: PanelContainer


func _ready() -> void:
	theme = UiKit.theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	enemy_id = str(GameState.pending_battle.get("enemy", "scarecrow"))
	if GameState.player.is_empty():
		GameState.new_game()  # 에디터에서 장면만 단독 실행한 경우
	enemy_def = DataDB.enemies.get(enemy_id, {})
	logic.setup(GameState.effective_stats(), enemy_id, enemy_def, DataDB.battle_config, DataDB.cards,
		GameState.build_deck(), -1, GameState.skill_levels)
	# 자동 전투: 반복 수련 상대이거나 이미 한 번 이긴 상대만 (A안: 스토리 첫 전투는 직접)
	auto_allowed = bool(enemy_def.get("auto_ok", false)) or GameState.has_flag("beaten_" + enemy_id)
	auto_on = auto_allowed and Settings.battle_auto
	timing_enabled = Settings.battle_timing
	Engine.time_scale = 2.0 if Settings.battle_speed >= 2 else 1.0
	_load_textures()
	_build()
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
	# 무대 (배경 + 인물 + 이펙트) — 줌·흔들림은 무대에만
	_stage = Control.new()
	_stage.set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_stage)
	var bg := TextureRect.new()
	bg.texture = load("res://assets/backgrounds/battle_training.png")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.offset_left = -24
	bg.offset_right = 24
	bg.offset_top = -20
	bg.offset_bottom = 8
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_stage.add_child(bg)
	_player_sprite = _fighter(_player_tex["ready"], PLAYER_HOME)
	_enemy_sprite = _fighter(_enemy_tex["idle"], ENEMY_HOME)
	_idle_breath()

	# 적 의도 (머리 위)
	_intent_box = HBoxContainer.new()
	_intent_box.add_theme_constant_override("separation", 2)
	_intent_box.position = ENEMY_HOME + Vector2(-112, -138)
	_stage.add_child(_intent_box)
	_intent_icon = TextureRect.new()
	_intent_box.add_child(_intent_icon)
	_intent_label = UiKit.label("", 24, Color8(250, 240, 220))
	_intent_label.add_theme_color_override("font_outline_color", Color8(20, 14, 14))
	_intent_label.add_theme_constant_override("outline_size", 6)
	_intent_box.add_child(_intent_label)

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
	_p_status = UiKit.label("", 12, Color8(170, 200, 250))
	pv.add_child(_p_status)

	# 적 상태 (우상단)
	var ep := UiKit.panel_container(6)
	ep.anchor_left = 1.0
	ep.anchor_right = 1.0
	ep.offset_left = -188
	ep.offset_right = -8
	ep.offset_top = 8
	add_child(ep)
	var ev := VBoxContainer.new()
	ev.add_theme_constant_override("separation", 2)
	ep.add_child(ev)
	_e_name = UiKit.label(str(enemy_def.get("name", "?")), 12, UiKit.NAME)
	ev.add_child(_e_name)
	var erow := HBoxContainer.new()
	erow.add_theme_constant_override("separation", 4)
	_e_hp = UiKit.bar(UiKit.HP_COLOR, 8)
	_e_hp.custom_minimum_size = Vector2(110, 8)
	_e_hp.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	erow.add_child(_e_hp)
	_e_hp_txt = UiKit.label("", 12)
	erow.add_child(_e_hp_txt)
	ev.add_child(erow)
	_e_status = UiKit.label("", 12, Color8(250, 170, 150))
	ev.add_child(_e_status)

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

	# 메시지 띠 (무대와 손패 사이)
	var band := ColorRect.new()
	band.color = Color8(20, 14, 14, 170)
	band.anchor_right = 1.0
	band.anchor_top = 1.0
	band.anchor_bottom = 1.0
	band.offset_top = -126
	band.offset_bottom = -106
	band.mouse_filter = Control.MOUSE_FILTER_STOP
	band.gui_input.connect(_on_message_input)
	add_child(band)
	_msg = UiKit.label("", 12)
	_msg.set_anchors_preset(Control.PRESET_FULL_RECT)
	_msg.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_msg.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_msg.clip_text = true
	band.add_child(_msg)

	# 아래: 기(에너지) 구슬 + 덱 수
	var orb := PanelContainer.new()
	var orb_style := UiKit.box(UiKit.VERMILION, UiKit.GOLD, 2, 4)
	orb_style.set_corner_radius_all(24)
	orb.add_theme_stylebox_override("panel", orb_style)
	orb.anchor_top = 1.0
	orb.anchor_bottom = 1.0
	orb.offset_left = 8
	orb.offset_right = 64
	orb.offset_top = -100
	orb.offset_bottom = -44
	orb.custom_minimum_size = Vector2(56, 48)
	add_child(orb)
	var ov := VBoxContainer.new()
	ov.add_theme_constant_override("separation", -2)
	orb.add_child(ov)
	var qi_tag := UiKit.label("기", 12, Color8(250, 230, 190))
	qi_tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ov.add_child(qi_tag)
	_energy_label = UiKit.label("", 24, Color8(255, 246, 220))
	_energy_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ov.add_child(_energy_label)
	_pile_label = UiKit.label("", 12, UiKit.DIM)
	_pile_label.anchor_top = 1.0
	_pile_label.anchor_bottom = 1.0
	_pile_label.offset_left = 6
	_pile_label.offset_right = 68
	_pile_label.offset_top = -40
	_pile_label.offset_bottom = -4
	_pile_label.add_theme_color_override("font_color", Color8(236, 226, 204))
	_pile_label.add_theme_color_override("font_outline_color", Color8(20, 14, 14))
	_pile_label.add_theme_constant_override("outline_size", 4)
	add_child(_pile_label)

	# 손패
	_hand_box = Control.new()
	_hand_box.anchor_left = 0.0
	_hand_box.anchor_right = 1.0
	_hand_box.anchor_top = 1.0
	_hand_box.anchor_bottom = 1.0
	_hand_box.offset_left = 70
	_hand_box.offset_right = -88
	_hand_box.offset_top = -104
	_hand_box.offset_bottom = -4
	_hand_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hand_box)

	# 오른쪽: 아이템 / 턴 종료 / 도주
	var rv := VBoxContainer.new()
	rv.anchor_left = 1.0
	rv.anchor_right = 1.0
	rv.anchor_top = 1.0
	rv.anchor_bottom = 1.0
	rv.offset_left = -84
	rv.offset_right = -8
	rv.offset_top = -98
	rv.add_theme_constant_override("separation", 4)
	add_child(rv)
	_item_btn = UiKit.button("아이템", Vector2(76, 22))
	_item_btn.pressed.connect(_cmd_items)
	rv.add_child(_item_btn)
	_end_btn = UiKit.button("턴 종료", Vector2(76, 38))
	_end_btn.add_theme_stylebox_override("normal", UiKit.box(UiKit.VERMILION, UiKit.GOLD, 1, 4))
	_end_btn.pressed.connect(end_turn)
	rv.add_child(_end_btn)
	_flee_btn = UiKit.button("도주", Vector2(76, 22))
	_flee_btn.pressed.connect(_cmd_flee)
	rv.add_child(_flee_btn)

	# 아이템 목록 팝업
	_list_panel = UiKit.panel_container(8)
	_list_panel.anchor_left = 1.0
	_list_panel.anchor_right = 1.0
	_list_panel.anchor_top = 1.0
	_list_panel.anchor_bottom = 1.0
	_list_panel.offset_left = -290
	_list_panel.offset_right = -92
	_list_panel.offset_top = -150
	_list_panel.offset_bottom = -104
	_list_panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_list_panel.visible = false
	add_child(_list_panel)
	_list_box = VBoxContainer.new()
	_list_box.add_theme_constant_override("separation", 4)
	_list_panel.add_child(_list_box)

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


# ------------------------------------------------------------------ 표시 갱신
func _refresh_all() -> void:
	_refresh_bars()
	_refresh_intent()
	_refresh_hand()


func _refresh_bars() -> void:
	var p := logic.p
	var e := logic.e
	_p_name.text = "%s  Lv.%d" % [p["name"], int(GameState.player["level"])]
	_p_hp.max_value = int(p["max_hp"])
	_p_hp.value = int(p["hp"])
	_p_hp_txt.text = "%d/%d" % [int(p["hp"]), int(p["max_hp"])]
	_p_mp.max_value = maxi(1, int(p["max_mp"]))
	_p_mp.value = int(p["mp"])
	_p_mp_txt.text = "%d/%d" % [int(p["mp"]), int(p["max_mp"])]
	_p_status.text = _status_text(p, logic.charge_mult)
	_e_hp.max_value = int(e["max_hp"])
	_e_hp.value = int(e["hp"])
	_e_hp_txt.text = "%d/%d" % [int(e["hp"]), int(e["max_hp"])]
	_e_status.text = _status_text(e, 1.0)
	_energy_label.text = "%d/%d" % [int(p["energy"]), int(p["max_energy"])]
	_pile_label.text = "덱 %d\n버림 %d" % [logic.draw_pile.size(), logic.discard.size()]


func _status_text(who: Dictionary, charge: float) -> String:
	var parts: Array = []
	if int(who.get("block", 0)) > 0:
		parts.append("호신 %d" % int(who["block"]))
	if int(who.get("strength", 0)) > 0:
		parts.append("기세+%d" % int(who["strength"]))
	if int(who.get("vulnerable", 0)) > 0:
		parts.append("허점%d" % int(who["vulnerable"]))
	if int(who.get("weak", 0)) > 0:
		parts.append("위축%d" % int(who["weak"]))
	if int(who.get("thorns", 0)) > 0:
		parts.append("반격%d" % int(who["thorns"]))
	if charge > 1.0:
		parts.append("기합x%d" % int(charge))
	return " ".join(parts)


func _refresh_intent() -> void:
	var a: Dictionary = logic.e.get("intent", {})
	var t := str(a.get("type", ""))
	_intent_box.visible = logic.state == BattleLogic.State.ONGOING and t != ""
	match t:
		"attack":
			_intent_icon.texture = load("res://assets/ui/icons/intent_attack.png")
			_intent_label.text = str(logic.intent_damage())
			_intent_label.add_theme_color_override("font_color", Color8(255, 140, 120))
		"block":
			_intent_icon.texture = load("res://assets/ui/icons/intent_block.png")
			_intent_label.text = str(int(a.get("block", 0)))
			_intent_label.add_theme_color_override("font_color", Color8(170, 200, 250))
		"buff":
			_intent_icon.texture = load("res://assets/ui/icons/intent_buff.png")
			_intent_label.text = ""
		_:
			_intent_icon.texture = load("res://assets/ui/icons/intent_idle.png")
			_intent_label.text = ""


func _refresh_hand() -> void:
	for n in _card_nodes:
		n.queue_free()
	_card_nodes.clear()
	var n := logic.hand.size()
	if n == 0:
		_update_buttons()
		return
	var width := _hand_box.size.x if _hand_box.size.x > 0 else 456.0
	var step := minf(CARD_SIZE.x + 4, (width - CARD_SIZE.x) / maxf(1, n - 1)) if n > 1 else 0.0
	var total := step * (n - 1) + CARD_SIZE.x
	var x0 := (width - total) / 2.0
	for i in n:
		var c := _make_card(logic.hand[i], i)
		c.position = Vector2(x0 + step * i, 6)
		_hand_box.add_child(c)
		_card_nodes.append(c)
	_update_buttons()


func _has_battle_items() -> bool:
	for item_id in GameState.inventory:
		if bool(DataDB.items.get(item_id, {}).get("usable_in_battle", false)):
			return true
	return false


func _update_buttons() -> void:
	var can_act := not busy and logic.state == BattleLogic.State.ONGOING
	_end_btn.disabled = not can_act
	_item_btn.disabled = not can_act or not _has_battle_items()
	_flee_btn.disabled = not can_act


## 카드 한 장 (버튼): 기 비용 · MP · 아이콘 · 이름 · 설명
func _make_card(card_id: String, index: int) -> Button:
	var s := logic.card_stats(card_id)
	var b := Button.new()
	b.custom_minimum_size = CARD_SIZE
	b.size = CARD_SIZE
	b.clip_contents = true
	b.focus_mode = Control.FOCUS_ALL
	var border := UiKit.VERMILION if s["type"] == "attack" else (UiKit.GOLD if s["type"] == "power" else Color8(70, 130, 140))
	b.add_theme_stylebox_override("normal", UiKit.box(Color8(236, 226, 204), border, 2, 0))
	b.add_theme_stylebox_override("hover", UiKit.box(Color8(250, 242, 222), UiKit.GOLD, 2, 0))
	b.add_theme_stylebox_override("focus", UiKit.box(Color(0, 0, 0, 0), Color8(255, 230, 150), 2, 0))
	b.add_theme_stylebox_override("pressed", UiKit.box(Color8(255, 236, 200), UiKit.GOLD, 2, 0))
	b.add_theme_stylebox_override("disabled", UiKit.box(Color8(150, 140, 126), Color8(90, 80, 70), 2, 0))
	var playable := logic.can_play(index) and not busy
	b.disabled = not playable
	var cost := UiKit.label(str(s["cost"]), 12, Color8(255, 246, 220))
	var cost_bg := PanelContainer.new()
	var cs := UiKit.box(UiKit.VERMILION, Color8(40, 20, 20), 1, 0)
	cs.set_corner_radius_all(8)
	cost_bg.add_theme_stylebox_override("panel", cs)
	cost_bg.position = Vector2(2, 2)
	cost_bg.custom_minimum_size = Vector2(16, 16)
	cost.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cost_bg.add_child(cost)
	cost_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(cost_bg)
	if int(s["mp"]) > 0:
		var mp := UiKit.label("MP%d" % s["mp"], 12, Color8(40, 80, 150))
		mp.position = Vector2(40, 2)
		mp.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(mp)
	var icon := TextureRect.new()
	icon.texture = load("res://assets/ui/icons/%s.png" % s["icon"])
	icon.position = Vector2(24, 17)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(icon)
	var nm := UiKit.label(s["name"], 12, Color8(40, 26, 24))
	nm.position = Vector2(0, 42)
	nm.custom_minimum_size = Vector2(CARD_SIZE.x, 14)
	nm.size = Vector2(CARD_SIZE.x, 14)
	nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nm.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(nm)
	var ds := UiKit.label(s["desc"], 12, Color8(90, 64, 54))
	ds.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ds.custom_minimum_size = Vector2(CARD_SIZE.x - 4, 0)
	ds.position = Vector2(2, 57)
	ds.size = Vector2(CARD_SIZE.x - 4, 40)
	ds.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ds.add_theme_constant_override("line_spacing", -2)
	ds.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(ds)
	b.tooltip_text = "%s — %s" % [s["name"], s["desc"]]
	b.pressed.connect(func(): play_card_index(index))
	b.mouse_entered.connect(func(): if not b.disabled: b.position.y = -4)
	b.mouse_exited.connect(func(): b.position.y = 6)
	b.focus_entered.connect(func(): b.position.y = -4; if not busy: _msg.text = "%s — %s" % [s["name"], s["desc"]])
	b.focus_exited.connect(func(): b.position.y = 6)
	return b


# ------------------------------------------------------------------ 자세 / 대기
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
	_refresh_bars()
	await get_tree().create_timer(0.6).timeout
	var fallback := "%s 나타났다!" % KText.josa(str(enemy_def.get("name", "적")), "이/가")
	await _say(str(enemy_def.get("intro", fallback)))
	logic.start()
	_begin_player_turn()


func _begin_player_turn() -> void:
	busy = false
	_pose(_player_sprite, "ready")
	_msg.text = "카드를 골라 쓰자. 적의 머리 위는 다음 행동 예고." if logic.turn <= 1 else "%d턴 — 기 %d" % [logic.turn, logic.p["energy"]]
	_refresh_all()
	_deal_animation()
	if auto_on:
		_auto_step.call_deferred()
	elif not _card_nodes.is_empty():
		_card_nodes[0].grab_focus.call_deferred()


func _deal_animation() -> void:
	for i in _card_nodes.size():
		var c: Control = _card_nodes[i]
		var target := c.position
		c.position = Vector2(-80, target.y + 40)
		c.modulate.a = 0.0
		var t := create_tween().set_parallel(true)
		t.tween_property(c, "position", target, 0.16).set_delay(i * 0.04).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		t.tween_property(c, "modulate:a", 1.0, 0.1).set_delay(i * 0.04)


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
	while is_inside_tree() and auto_on and not busy and logic.state == BattleLogic.State.ONGOING:
		var hp_ratio := float(logic.p["hp"]) / maxf(1.0, float(logic.p["max_hp"]))
		if hp_ratio < 0.3 and GameState.item_count("herb") > 0:
			await _use_item("herb")
			continue
		var idx := logic.auto_pick()
		if idx >= 0:
			await play_card_index(idx)
		else:
			await end_turn()
			return


# ------------------------------------------------------------------ 명령
## 손패의 index 번째 카드 사용
func play_card_index(index: int) -> void:
	if busy or not logic.can_play(index):
		if not busy and index < _card_nodes.size():
			var c: Control = _card_nodes[index]
			var t := create_tween()
			t.tween_property(c, "position:x", c.position.x + 4, 0.04)
			t.tween_property(c, "position:x", c.position.x, 0.04)
			_msg.text = "기나 MP가 부족하다!"
		return
	busy = true
	_list_panel.visible = false
	var card_id: String = logic.hand[index]
	var c: Dictionary = DataDB.cards.get(card_id, {})
	var s := logic.card_stats(card_id)
	# 낸 카드가 위로 솟구치며 사라짐
	if index < _card_nodes.size():
		var node: Control = _card_nodes[index]
		var t := create_tween().set_parallel(true)
		t.tween_property(node, "position:y", node.position.y - 60, 0.15)
		t.tween_property(node, "modulate:a", 0.0, 0.15)
	_update_buttons()
	var timing := 1.0
	last_timing = ""
	if s["damage"] > 0:
		if card_id != "strike":
			_cutin(s["name"])
		timing = await _timing_ring()
	var events := logic.play_card(index, timing)
	if s["damage"] > 0:
		await _attack_sequence(card_id, events)
	else:
		await _skill_sequence(c, events)
	_refresh_all()
	if await _check_end():
		return
	busy = false
	_refresh_hand()
	if not auto_on and not _card_nodes.is_empty():
		_card_nodes[mini(index, _card_nodes.size() - 1)].grab_focus.call_deferred()


## 턴 종료 → 적 행동 → 다음 턴
func end_turn() -> void:
	if busy:
		return
	busy = true
	_list_panel.visible = false
	for n in _card_nodes:
		var t := create_tween().set_parallel(true)
		t.tween_property(n, "position:x", 520.0, 0.18)
		t.tween_property(n, "modulate:a", 0.0, 0.18)
	logic.end_player_turn()
	_update_buttons()
	await get_tree().create_timer(0.15).timeout
	await _enemy_sequence()
	if await _check_end():
		return
	logic.start_player_turn()
	_begin_player_turn()


func _cmd_items() -> void:
	if busy:
		return
	if _list_panel.visible:
		_list_panel.visible = false
		return
	for c in _list_box.get_children():
		c.queue_free()
	for item_id in GameState.inventory:
		var def: Dictionary = DataDB.items.get(item_id, {})
		if bool(def.get("usable_in_battle", false)):
			var b := UiKit.button("%s x%d" % [def.get("name", item_id), GameState.item_count(item_id)], Vector2(180, 22))
			b.pressed.connect(func(): _use_item(item_id))
			_list_box.add_child(b)
	var close := UiKit.button("닫기", Vector2(180, 22))
	close.pressed.connect(func(): _list_panel.visible = false)
	_list_box.add_child(close)
	_list_panel.visible = true
	_list_box.get_child(0).grab_focus.call_deferred()


## 아이템 사용 (턴을 소모하지 않음)
func _use_item(item_id: String) -> void:
	if busy:
		return
	var def: Dictionary = DataDB.items.get(item_id, {})
	if not GameState.remove_item(item_id):
		return
	busy = true
	_list_panel.visible = false
	var events := logic.use_item(def)
	_pose(_player_sprite, "win")
	for ev in events:
		if ev["fx"] == "heal":
			_float_text(_player_sprite, "+%d" % int(ev["heal"]) if int(ev["heal"]) > 0 else "회복", Color(0.5, 1, 0.5))
			_wisps(_player_sprite, Color8(150, 240, 150))
	_refresh_bars()
	await _play_texts(events)
	_pose(_player_sprite, "ready")
	busy = false
	_refresh_hand()


func _cmd_flee() -> void:
	if busy:
		return
	busy = true
	var events := logic.try_flee()
	if logic.state == BattleLogic.State.FLED:
		await _play_texts(events)
		await _check_end()
		return
	_pose(_player_sprite, "hurt")
	var x := _player_sprite.position.x
	var t := create_tween()
	t.tween_property(_player_sprite, "position:x", x - 30, 0.15)
	t.tween_property(_player_sprite, "rotation", 0.25, 0.08)
	t.tween_property(_player_sprite, "rotation", 0.0, 0.1)
	t.tween_property(_player_sprite, "position:x", x, 0.15)
	await _play_texts(events)
	busy = false
	await end_turn()


# ------------------------------------------------------------------ 연출: 플레이어
func _attack_sequence(card_id: String, events: Array) -> void:
	var hits: Array = []
	var tail: Array = []
	for ev in events:
		match ev["fx"]:
			"cast":
				_msg.text = ev["text"] + ("  완벽!" if last_timing == "perfect" else "")
			"hit", "crit":
				hits.append(ev)
			_:
				tail.append(ev)
	var home := _home(_player_sprite)
	var strike_x := _enemy_sprite.position.x - 78
	_pose(_player_sprite, "ready")
	_afterimage(_player_sprite)
	var t := create_tween()
	t.tween_property(_player_sprite, "position:x", strike_x, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	await t.finished
	var kick: bool = card_id in ["wind_kick", "trip"]
	for i in hits.size():
		var ev: Dictionary = hits[i]
		_pose(_player_sprite, "kick" if kick or (card_id == "combo_fist" and i == 1) else "punch")
		_player_sprite.position.x = strike_x + 6
		if card_id == "wind_kick":
			_fx("res://assets/fx/wind.png", _enemy_sprite, Vector2(160, 160), 0.3, Color8(200, 240, 230))
			_zoom(1.08, 0.25)
		if int(ev["block"]) > 0:
			_float_text(_enemy_sprite, "막음 %d" % int(ev["block"]), Color8(170, 200, 250), 0.8)
		await _impact(_enemy_sprite, int(ev["damage"]), ev["fx"] == "crit")
		_refresh_bars()
		if i < hits.size() - 1:
			_afterimage(_player_sprite)
			_pose(_player_sprite, "ready")
			_player_sprite.position.x = strike_x
			await get_tree().create_timer(0.06).timeout
	if hits.size() > 0:
		_msg.text = "  ".join(hits.map(func(e): return e["text"]))
	await get_tree().create_timer(0.1).timeout
	_pose(_player_sprite, "ready")
	var back := create_tween()
	back.tween_property(_player_sprite, "position:x", home.x, 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	await back.finished
	for ev in tail:
		match ev["fx"]:
			"down":
				_knock_out(_enemy_sprite)
			"debuff":
				_float_text(_enemy_sprite, "허점!" if "허점" in ev["text"] else "위축!", Color8(220, 150, 255), 0.9)
		_msg.text = ev["text"]
		await get_tree().create_timer(0.25).timeout
	_refresh_bars()


func _skill_sequence(c: Dictionary, events: Array) -> void:
	for ev in events:
		match ev["fx"]:
			"cast":
				_msg.text = ev["text"]
				_pose(_player_sprite, "guard" if c.has("block") else "shout")
			"block":
				if _shield:
					_shield.queue_free()
				_shield = _fx("res://assets/fx/shield.png", _player_sprite, Vector2(150, 160), -1.0, Color(1, 1, 1, 0.85))
				_float_text(_player_sprite, "호신 +%d" % logic.card_stats(_card_id_of(c))["block"], Color8(170, 200, 250), 0.8)
			"buff":
				_fx("res://assets/fx/ring.png", _player_sprite, Vector2(220, 220), 0.4, Color8(255, 210, 120), Vector2(0.3, 0.3))
				_flash(_player_sprite, Color(1.8, 1.5, 0.7))
				_zoom(1.05, 0.3)
				_shake(3.0)
			"heal":
				_wisps(_player_sprite, Color8(150, 200, 255))
			"draw":
				pass
		if ev["fx"] != "cast":
			_msg.text = ev["text"]
		_refresh_bars()
		await get_tree().create_timer(0.22).timeout


func _card_id_of(c: Dictionary) -> String:
	for id in DataDB.cards:
		if DataDB.cards[id] == c:
			return id
	return ""


# ------------------------------------------------------------------ 연출: 적
func _enemy_sequence() -> void:
	if logic.state != BattleLogic.State.ONGOING:
		return
	var a: Dictionary = logic.e["intent"]
	_intent_box.visible = false
	if a.get("type", "attack") == "attack":
		_msg.text = str(a.get("text", ""))
		_pose(_enemy_sprite, "windup")
		var parried := await _parry_window()
		var home := _home(_enemy_sprite)
		var t := create_tween()
		t.tween_property(_enemy_sprite, "position:x", _player_sprite.position.x + 82, 0.11).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		await t.finished
		_pose(_enemy_sprite, "attack")
		var events := logic.enemy_turn(parried)
		for ev in events:
			if ev["target"] == "player" and ev["fx"] in ["hit", "parry"]:
				var guarded := parried or int(ev["block"]) > 0
				if guarded:
					_pose(_player_sprite, "guard")
				if int(ev["block"]) > 0:
					_float_text(_player_sprite, "막음 %d" % int(ev["block"]), Color8(170, 200, 250), 0.8)
				await _impact(_player_sprite, int(ev["damage"]), false, guarded)
			elif ev["target"] == "enemy" and ev["fx"] == "hit":
				await _impact(_enemy_sprite, int(ev["damage"]), false)
		_refresh_bars()
		await get_tree().create_timer(0.1).timeout
		_pose(_enemy_sprite, "idle")
		var back := create_tween()
		back.tween_property(_enemy_sprite, "position:x", home.x, 0.15)
		await back.finished
		if logic.state == BattleLogic.State.LOST:
			_knock_out(_player_sprite)
		elif logic.state == BattleLogic.State.WON:
			_knock_out(_enemy_sprite)
		else:
			_pose(_player_sprite, "ready")
		await _play_texts(events.slice(1))
	else:
		var events := logic.enemy_turn()
		var bob := create_tween()
		bob.tween_property(_enemy_sprite, "position:y", _enemy_sprite.position.y - 8, 0.1)
		bob.tween_property(_enemy_sprite, "position:y", _home(_enemy_sprite).y, 0.1)
		if a.get("type", "") == "block":
			_fx("res://assets/fx/shield.png", _enemy_sprite, Vector2(150, 160), 0.6, Color(1, 1, 1, 0.8))
		elif a.get("type", "") == "buff":
			_fx("res://assets/fx/ring.png", _enemy_sprite, Vector2(200, 200), 0.4, Color8(255, 120, 90), Vector2(0.3, 0.3))
		_refresh_bars()
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
		var sc := lerpf(2.4, 1.0, clampf(el / dur, 0.0, 1.0))
		ring.scale = Vector2(sc, sc)
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
			busy = true
			_update_buttons()
			for n in _card_nodes:
				n.queue_free()
			_card_nodes.clear()
			_intent_box.visible = false
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
				var eff := GameState.effective_stats()
				for key in ["hp", "max_hp", "mp", "max_mp", "attack", "defense", "agility"]:
					logic.p[key] = int(eff[key])
				_refresh_bars()
				_flash(_player_sprite, Color(1.8, 1.6, 0.8))
				await _say(line)
			await _card_reward()
			GameState.finish_battle("win")
			return true
		BattleLogic.State.LOST:
			busy = true
			_update_buttons()
			_knock_out(_player_sprite)
			await _confirm()
			GameState.finish_battle("lose")
			return true
		BattleLogic.State.FLED:
			busy = true
			GameState.set_hp_mp(int(logic.p["hp"]), int(logic.p["mp"]))
			_pose(_player_sprite, "ready")
			_player_sprite.flip_h = true
			var t := create_tween()
			t.tween_property(_player_sprite, "position:x", -170.0, 0.35)
			await t.finished
			GameState.finish_battle("flee")
			return true
	return false


## 승리 보상: 카드 3장 중 1장 (또는 넘기기)
func _card_reward() -> void:
	reward_options = logic.reward_choices(int(DataDB.battle_config.get("cards", {}).get("reward_choices", 3)))
	if reward_options.is_empty():
		await _confirm()
		return
	if auto_on:
		GameState.add_card(reward_options[0])
		await _say("보상 초식 『%s』을(를) 덱에 넣었다." % logic.card_stats(reward_options[0])["name"])
		return
	_reward_panel = UiKit.panel_container(10)
	_reward_panel.set_anchors_preset(Control.PRESET_CENTER)
	_reward_panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_reward_panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(_reward_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	_reward_panel.add_child(v)
	var title := UiKit.brush_label("새 초식을 하나 익히자", 28, UiKit.TEXT)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)
	var first: Control = null
	for cid in reward_options:
		var holder := Control.new()
		holder.custom_minimum_size = CARD_SIZE + Vector2(0, 8)
		var card := _make_reward_card(cid)
		holder.add_child(card)
		row.add_child(holder)
		if first == null:
			first = card
	var skip := UiKit.button("넘기기", Vector2(100, 24))
	skip.pressed.connect(func(): choose_reward(-1))
	var srow := HBoxContainer.new()
	srow.alignment = BoxContainer.ALIGNMENT_CENTER
	srow.add_child(skip)
	v.add_child(srow)
	first.grab_focus.call_deferred()
	await _reward_done


func _make_reward_card(cid: String) -> Button:
	var saved_busy := busy
	busy = false  # 카드 모양을 '사용 가능' 상태로 그리기 위해
	var saved_hand := logic.hand
	logic.hand = [cid]
	var saved_energy := int(logic.p["energy"])
	var saved_mp := int(logic.p["mp"])
	logic.p["energy"] = 9
	logic.p["mp"] = 99
	var state_saved := logic.state
	logic.state = BattleLogic.State.ONGOING
	var b := _make_card(cid, 0)
	logic.state = state_saved
	logic.p["energy"] = saved_energy
	logic.p["mp"] = saved_mp
	logic.hand = saved_hand
	busy = saved_busy
	for con in b.pressed.get_connections():
		b.pressed.disconnect(con["callable"])
	b.mouse_entered.connect(func(): b.position.y = -4)
	b.pressed.connect(func(): choose_reward(reward_options.find(cid)))
	b.position = Vector2(0, 6)
	return b


## 보상 선택 (index -1 = 넘기기)
func choose_reward(index: int) -> void:
	if index >= 0 and index < reward_options.size():
		GameState.add_card(reward_options[index])
		_msg.text = "『%s』을(를) 덱에 넣었다!" % logic.card_stats(reward_options[index])["name"]
	if _reward_panel:
		_reward_panel.queue_free()
		_reward_panel = null
	_reward_done.emit()


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
	if _reward_panel:
		return
	if not busy:
		if event.is_action_pressed("cancel"):
			if _list_panel.visible:
				_list_panel.visible = false
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
func _impact(target: TextureRect, dmg: int, strong: bool, guarded: bool = false) -> void:
	var is_enemy := target == _enemy_sprite
	if not guarded:
		_pose(target, "hurt")
	_fx("res://assets/fx/impact.png", target, Vector2(96, 96) * (1.4 if strong else 1.0), 0.18,
		Color8(160, 210, 255) if guarded else (Color8(255, 220, 140) if strong else Color(1, 1, 1)), Vector2(0.4, 0.4))
	_flash(target, Color(2.6, 2.6, 2.6))
	_float_text(target, str(dmg) + ("!" if strong else ""), Color(1, 0.85, 0.3) if strong else Color(1, 1, 1), 1.4 if strong else 1.0)
	_shake(7.0 if strong else 3.5)
	if strong:
		_zoom(1.07, 0.2)
	await get_tree().create_timer(0.07 if strong else 0.05).timeout  # 히트스톱
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
	band.offset_top = 96
	band.offset_bottom = 152
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


## 초식 이름 붓글씨 컷인
func _cutin(text: String) -> void:
	var band := ColorRect.new()
	band.color = Color8(20, 14, 14, 215)
	band.anchor_right = 1.0
	band.offset_top = 112
	band.offset_bottom = 160
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
