extends CanvasLayer
## 필드 메뉴: 하단 탭 (상태 / 무공 / 가방 / 수련 / 시스템).
## 모바일 엄지 조작을 위해 탭을 화면 아래에 둔다. 새 소식이 있는 탭에는 빨간 점.
## 열려 있는 동안 게임을 일시정지한다.

signal message(text: String)

const TABS := [
	["status", "상태", ""],
	["skills", "무공", "new_skill"],
	["bag", "가방", ""],
	["training", "수련", "offline"],
	["system", "시스템", ""],
]

var _root: Control
var _tab_buttons: Dictionary = {}
var _tab_dots: Dictionary = {}
var _title: Label
var _content_box: VBoxContainer
var _settings: SettingsPanel
var _open := false
var current_tab := "status"


func _ready() -> void:
	layer = 40
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	_root.visible = false
	GameState.notices_changed.connect(_refresh_dots)


func _build() -> void:
	_root = Control.new()
	_root.theme = UiKit.theme()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.04, 0.03, 0.03, 0.88)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)

	_title = UiKit.brush_label("상태", 30, UiKit.TEXT)
	_title.position = Vector2(16, 2)
	_root.add_child(_title)

	var close_btn := UiKit.button("닫기", Vector2(56, 24))
	close_btn.anchor_left = 1.0
	close_btn.anchor_right = 1.0
	close_btn.offset_left = -68
	close_btn.offset_right = -12
	close_btn.offset_top = 8
	close_btn.focus_mode = Control.FOCUS_NONE
	close_btn.pressed.connect(close)
	_root.add_child(close_btn)

	var content := UiKit.panel_container(10)
	content.anchor_right = 1.0
	content.anchor_bottom = 1.0
	content.offset_left = 12
	content.offset_right = -12
	content.offset_top = 38
	content.offset_bottom = -52
	_root.add_child(content)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_child(scroll)
	_content_box = VBoxContainer.new()
	_content_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_content_box.add_theme_constant_override("separation", 4)
	scroll.add_child(_content_box)

	# 하단 탭 바
	var bar := HBoxContainer.new()
	bar.anchor_left = 0.5
	bar.anchor_right = 0.5
	bar.anchor_top = 1.0
	bar.anchor_bottom = 1.0
	bar.offset_top = -44
	bar.offset_bottom = -8
	bar.grow_horizontal = Control.GROW_DIRECTION_BOTH
	bar.add_theme_constant_override("separation", 4)
	_root.add_child(bar)
	for t in TABS:
		var b := UiKit.button(t[1], Vector2(92, 36))
		b.pressed.connect(show_tab.bind(t[0]))
		bar.add_child(b)
		_tab_buttons[t[0]] = b
		var dot := ColorRect.new()
		dot.color = Color8(220, 50, 40)
		dot.size = Vector2(7, 7)
		dot.position = Vector2(80, 4)
		dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		dot.visible = false
		b.add_child(dot)
		_tab_dots[t[0]] = [dot, t[2]]

	_settings = SettingsPanel.new()
	_settings.set_anchors_preset(Control.PRESET_CENTER)
	_settings.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_settings.grow_vertical = Control.GROW_DIRECTION_BOTH
	_settings.visible = false
	_settings.closed.connect(func(): _settings.visible = false; _tab_buttons["system"].grab_focus())
	_root.add_child(_settings)


func is_open() -> bool:
	return _open


func open(tab: String = "") -> void:
	if _open:
		return
	_open = true
	_root.visible = true
	GameState.lock_input("menu")
	get_tree().paused = true
	if tab == "":
		# 새 소식이 있는 탭을 먼저 보여준다
		tab = "training" if GameState.has_notice("offline") else ("skills" if GameState.has_notice("new_skill") else "status")
	show_tab(tab)


func close() -> void:
	if not _open:
		return
	_open = false
	_root.visible = false
	_settings.visible = false
	get_tree().paused = false
	await get_tree().process_frame
	GameState.unlock_input("menu")


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if (event.is_action_pressed("menu") or event.is_action_pressed("cancel")) and not _settings.visible:
		close()
		get_viewport().set_input_as_handled()


func show_tab(tab: String) -> void:
	current_tab = tab
	for t in TABS:
		var b: Button = _tab_buttons[t[0]]
		b.add_theme_stylebox_override("normal", UiKit.box(UiKit.VERMILION if t[0] == tab else Color8(54, 40, 34), UiKit.GOLD if t[0] == tab else Color8(112, 88, 62), 1, 4))
		if t[0] == tab:
			_title.text = t[1]
	match tab:
		"status":
			_show_status()
		"skills":
			_show_skills()
		"bag":
			_show_items()
		"training":
			_show_training()
		"system":
			_show_system()
	_refresh_dots()
	_tab_buttons[tab].grab_focus()


func _refresh_dots() -> void:
	for key in _tab_dots:
		var info: Array = _tab_dots[key]
		info[0].visible = info[1] != "" and GameState.has_notice(info[1])


# ------------------------------------------------------------------ 공용 위젯
func _clear() -> void:
	for c in _content_box.get_children():
		c.queue_free()


func _line(text: String, color: Color = UiKit.TEXT, parent: Node = null) -> Label:
	var l := UiKit.label(text, 12, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(160, 0)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	(parent if parent else _content_box).add_child(l)
	return l


func _icon(icon_name: String) -> TextureRect:
	var t := TextureRect.new()
	t.texture = load("res://assets/ui/icons/%s.png" % icon_name)
	t.custom_minimum_size = Vector2(24, 24)
	t.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	return t


func _row() -> HBoxContainer:
	var r := HBoxContainer.new()
	r.add_theme_constant_override("separation", 6)
	_content_box.add_child(r)
	return r


func _currency_row() -> void:
	var r := _row()
	r.add_child(_icon("gold"))
	_line("%d냥" % int(GameState.player["gold"]), UiKit.NAME, r).size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	r.add_child(_icon("qi"))
	_line("내공 %d" % GameState.qi, Color8(160, 190, 240), r).size_flags_horizontal = Control.SIZE_SHRINK_BEGIN


# ------------------------------------------------------------------ 상태
func _show_status() -> void:
	_clear()
	var p := GameState.player
	var eff := GameState.effective_stats()
	_line("%s  Lv.%d" % [p["name"], int(p["level"])], UiKit.GOLD)
	_line("HP %d / %d     MP %d / %d" % [int(p["hp"]), int(p["max_hp"]), int(p["mp"]), int(p["max_mp"])])
	var atk_bonus := int(eff["attack"]) - int(p["attack"])
	var def_bonus := int(eff["defense"]) - int(p["defense"])
	_line("공격력 %d%s   방어력 %d%s   민첩성 %d" % [int(eff["attack"]), (" (+%d)" % atk_bonus) if atk_bonus > 0 else "",
		int(eff["defense"]), (" (+%d)" % def_bonus) if def_bonus > 0 else "", int(p["agility"])])
	var need := GameState.exp_to_next(int(p["level"]))
	_line("경험치 %d / %d   (다음 레벨까지 %d)" % [int(p["exp"]), need, need - int(p["exp"])])
	var exp_bar := UiKit.bar(UiKit.EXP_COLOR, 6)
	exp_bar.max_value = need
	exp_bar.value = int(p["exp"])
	_content_box.add_child(exp_bar)
	_currency_row()
	_line("")
	_line("임무", UiKit.GOLD)
	if GameState.quests.is_empty():
		_line("  (아직 없음 — 마을 사람들과 이야기해 보자)", UiKit.DIM)
	for qid in GameState.quests:
		var q: Dictionary = DataDB.quests.get(qid, {})
		var st := GameState.get_quest(qid)
		_line(("✔ " if st == "complete" else "● ") + str(q.get("name", qid)), UiKit.TEXT if st != "complete" else UiKit.DIM)
		_line("   " + str(q.get("states", {}).get(st, "")), UiKit.DIM)
	var secs := int(GameState.play_time)
	_line("플레이 시간 %02d:%02d:%02d" % [secs / 3600, (secs / 60) % 60, secs % 60], UiKit.DIM)


# ------------------------------------------------------------------ 무공 (장착 / 강화)
func _show_skills() -> void:
	_clear()
	GameState.clear_notice("new_skill")
	_line("장착 %d / %d   — 장착한 무공이 전투 덱의 초식(카드)이 된다. 내공으로 강화." % [GameState.equipped.size(), GameState.slot_count()], UiKit.DIM)
	_currency_row()
	var deck := GameState.build_deck()
	var counts := {}
	for cid in deck:
		counts[cid] = int(counts.get(cid, 0)) + 1
	var parts: Array = []
	for cid in counts:
		parts.append("%s x%d" % [DataDB.cards[cid]["name"], counts[cid]])
	_line("전투 덱 %d장: %s" % [deck.size(), ", ".join(parts)], Color8(200, 220, 240))
	for sid in GameState.skills:
		var s: Dictionary = DataDB.skills.get(sid, {})
		var r := _row()
		r.add_child(_icon(str(s.get("icon", "skill_fist"))))
		var lv := GameState.skill_level(sid)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_theme_constant_override("separation", 0)
		r.add_child(info)
		_line("%s%s" % [s.get("name", sid), ("  %d성" % lv) if lv > 0 else ""], UiKit.NAME, info)
		_line(str(s.get("desc", "")), UiKit.DIM, info)
		var equipped: bool = GameState.equipped.has(sid)
		var eb := UiKit.button("해제" if equipped else "장착", Vector2(48, 24))
		if equipped:
			eb.add_theme_stylebox_override("normal", UiKit.box(UiKit.VERMILION, UiKit.GOLD, 1, 4))
		eb.disabled = not equipped and GameState.equipped.size() >= GameState.slot_count()
		eb.pressed.connect(_toggle_equip.bind(sid))
		r.add_child(eb)
		var cost := GameState.skill_upgrade_cost(sid)
		var ub := UiKit.button("최대" if cost < 0 else "강화 %d" % cost, Vector2(70, 24))
		ub.disabled = cost < 0 or GameState.qi < cost
		ub.pressed.connect(_upgrade_skill.bind(sid))
		r.add_child(ub)
	var nxt := ""
	for sid in DataDB.skills:
		if not GameState.skills.has(sid):
			nxt += "%s(Lv.%d)  " % [DataDB.skills[sid]["name"], int(DataDB.skills[sid].get("learn_level", 1))]
	if nxt != "":
		_line("앞으로 익힐 무공: " + nxt, UiKit.DIM)


func _toggle_equip(sid: String) -> void:
	if not GameState.toggle_equip(sid):
		message.emit("장착 칸이 가득 찼다" if not GameState.equipped.has(sid) else "무공은 최소 하나는 장착해야 한다")
	_show_skills()


func _upgrade_skill(sid: String) -> void:
	var msg := GameState.upgrade_skill(sid)
	_show_skills()
	if msg != "":
		_line(msg, Color(0.6, 1, 0.6))
		message.emit(msg)


# ------------------------------------------------------------------ 가방 (아이템 + 장비)
func _show_items() -> void:
	_clear()
	_currency_row()
	_line("아이템 (눌러서 사용)", UiKit.GOLD)
	if GameState.inventory.is_empty():
		_line("가방이 비어 있다. 바람만 들어 있다.", UiKit.DIM)
	for item_id in GameState.inventory:
		var def: Dictionary = DataDB.items.get(item_id, {})
		var r := _row()
		r.add_child(_icon(str(def.get("icon", "item_herb"))))
		var b := UiKit.button("%s x%d" % [def.get("name", item_id), GameState.item_count(item_id)], Vector2(120, 24))
		var usable: bool = def.get("type", "") in ["heal_hp", "heal_mp"]
		b.disabled = not usable
		b.pressed.connect(_use_item.bind(item_id))
		r.add_child(b)
		_line(str(def.get("desc", "")), UiKit.DIM, r)
	_line("")
	_line("장비 강화 (냥 소모)", UiKit.GOLD)
	for gid in DataDB.growth.get("gear", {}):
		var g: Dictionary = DataDB.growth["gear"][gid]
		var r := _row()
		r.add_child(_icon(str(g.get("icon", "gear_fist"))))
		var lv := GameState.gear_level(gid)
		var stat_name := "공격력" if g["stat"] == "attack" else "방어력"
		_line("%s +%d  (%s +%d)" % [g["name"], lv, stat_name, lv * int(g["per_level"])], UiKit.NAME, r)
		var cost := GameState.gear_cost(gid)
		var ub := UiKit.button("최대" if cost < 0 else "강화 %d냥" % cost, Vector2(90, 24))
		ub.disabled = cost < 0 or int(GameState.player["gold"]) < cost
		ub.pressed.connect(_upgrade_gear.bind(gid))
		r.add_child(ub)


func _use_item(item_id: String) -> void:
	var msg := GameState.use_item(item_id)
	_show_items()
	if msg != "":
		_line(msg, Color(0.6, 1, 0.6))


func _upgrade_gear(gid: String) -> void:
	var msg := GameState.upgrade_gear(gid)
	_show_items()
	if msg != "":
		_line(msg, Color(0.6, 1, 0.6))
		message.emit(msg)


# ------------------------------------------------------------------ 수련 (폐관수련)
func _show_training() -> void:
	_clear()
	var cfg: Dictionary = DataDB.growth.get("offline", {})
	_line("폐관수련", UiKit.GOLD)
	_line("게임을 꺼 둔 동안에도 도윤은 홀로 수련한다. (%d분 이상, 최대 %d시간)" % [int(cfg.get("min_minutes", 5)), int(cfg.get("max_hours", 8))], UiKit.DIM)
	_currency_row()
	if GameState.has_offline_reward():
		var o := GameState.offline_pending
		_line("수련 시간 %d시간 %d분" % [int(o["minutes"]) / 60, int(o["minutes"]) % 60], UiKit.TEXT)
		_line("받을 보상: 내공 +%d, %d냥" % [int(o["qi"]), int(o["gold"])], UiKit.NAME)
		var b := UiKit.button("보상 받기", Vector2(140, 30))
		b.add_theme_stylebox_override("normal", UiKit.box(UiKit.VERMILION, UiKit.GOLD, 1, 4))
		b.pressed.connect(_claim_offline)
		_content_box.add_child(b)
	else:
		_line("아직 쌓인 수련이 없다. 잠시 쉬었다 오면 내공이 쌓여 있을 것이다.", UiKit.TEXT)
	_line("")
	var lvl := int(GameState.player["level"])
	var per_hour := int(60 * float(cfg.get("qi_per_minute", 0.5)) * (1.0 + float(cfg.get("qi_level_bonus", 0.1)) * (lvl - 1)))
	_line("현재 수련 효율: 시간당 내공 약 %d (레벨이 오를수록 증가)" % per_hour, UiKit.DIM)
	_line("내공은 [무공] 탭에서 무공 강화에 쓴다. 허수아비 수련으로도 얻을 수 있다.", UiKit.DIM)


func _claim_offline() -> void:
	var msg := GameState.claim_offline()
	_show_training()
	if msg != "":
		_line(msg, Color(0.6, 1, 0.6))
		message.emit(msg)


# ------------------------------------------------------------------ 시스템
func _show_system() -> void:
	_clear()
	var save_b := UiKit.button("저장하기", Vector2(160, 30))
	save_b.pressed.connect(_do_save)
	_content_box.add_child(save_b)
	_line("맵을 이동하거나 전투가 끝나면 자동으로 저장된다.", UiKit.DIM)
	var set_b := UiKit.button("설정", Vector2(160, 30))
	set_b.pressed.connect(func(): _settings.visible = true; _settings.focus_first())
	_content_box.add_child(set_b)
	var title_b := UiKit.button("타이틀로", Vector2(160, 30))
	title_b.pressed.connect(_confirm_title)
	_content_box.add_child(title_b)


func _do_save() -> void:
	_clear()
	if SaveManager.save_game():
		_line("저장했다!", Color(0.6, 1, 0.6))
		_line(SaveManager.save_summary(), UiKit.DIM)
		message.emit("저장 완료")
	else:
		_line("저장 실패: " + SaveManager.last_error, UiKit.HP_COLOR)


func _confirm_title() -> void:
	_clear()
	_line("타이틀 화면으로 돌아갈까? (현재 상태를 저장한다)", UiKit.GOLD)
	var yes := UiKit.button("저장하고 타이틀로", Vector2(160, 30))
	yes.pressed.connect(func(): SaveManager.save_game(); close(); GameState.return_to_title())
	_content_box.add_child(yes)
	yes.grab_focus()
