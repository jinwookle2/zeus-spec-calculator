extends Node
## 자동 테스트 실행기.
##   godot --headless --path . res://tests/test_runner.tscn
## 화면 캡처까지 하려면 (디스플레이 필요):
##   godot --path . res://tests/test_runner.tscn -- --shots=<저장 폴더>
## 종료 코드 0 = 전부 통과.

var passed := 0
var failed := 0
var failures: Array = []
var shots_dir := ""
var _section := ""
var _scenario_done := false


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots_dir = arg.substr(8)
	# 장면 전환에도 살아남도록 루트로 이동
	_relocate.call_deferred()


func _relocate() -> void:
	var tree := get_tree()
	get_parent().remove_child(self)
	tree.root.add_child(self)
	await run_all()


func run_all() -> void:
	SaveManager.save_dir = "user://test_saves"
	DirAccess.make_dir_recursive_absolute(SaveManager.save_dir)
	SaveManager.delete_save()
	Settings.text_speed = "instant"
	Settings.touch_controls = "on"
	Settings.set_value("battle_auto", false)  # 이전 실행에서 저장된 전투 설정 초기화
	Settings.set_value("battle_speed", 1)
	DataDB.battle_config["message_delay"] = 0.03

	test_data_integrity()
	test_ktext()
	test_battle_logic()
	test_game_state()
	test_growth()
	test_save_load()
	test_dialogue_data()
	await test_main_menu()
	await test_playthrough()
	section("시나리오 완주")
	check(_scenario_done, "플레이 시나리오가 중간에 중단되지 않고 끝까지 실행됨")

	SaveManager.delete_save()
	print("")
	print("==================================================")
	print("결과: %d 통과, %d 실패" % [passed, failed])
	for f in failures:
		print("  ✗ " + f)
	print("==================================================")
	get_tree().quit(0 if failed == 0 else 1)


# ------------------------------------------------------------------ 도우미
func section(name: String) -> void:
	_section = name
	print("\n[%s]" % name)


func check(cond: bool, what: String) -> void:
	if cond:
		passed += 1
		print("  ✓ " + what)
	else:
		failed += 1
		failures.append("%s: %s" % [_section, what])
		print("  ✗ " + what)


func frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func seconds(s: float) -> void:
	await get_tree().create_timer(s).timeout


func wait_scene(path: String, timeout: float = 5.0) -> bool:
	var t := 0.0
	while t < timeout:
		var cs := get_tree().current_scene
		if cs and cs.scene_file_path == path and not SceneRouter.is_busy():
			await frames(2)
			return true
		await get_tree().process_frame
		t += get_process_delta_time()
	return false


func hold(action: String, secs: float) -> void:
	Input.action_press(action)
	await seconds(secs)
	Input.action_release(action)
	await seconds(0.05)


func press(action: String) -> void:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = true
	Input.parse_input_event(ev)
	await frames(1)
	var ev2 := InputEventAction.new()
	ev2.action = action
	ev2.pressed = false
	Input.parse_input_event(ev2)
	await frames(2)


func shot(name: String) -> void:
	if shots_dir == "":
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(shots_dir)
	img.save_png(shots_dir.path_join(name + ".png"))
	print("  (캡처) " + name)


func finish_dialogue(box: Node, max_steps: int = 40) -> void:
	var steps := 0
	while box.is_busy() and steps < max_steps:
		await seconds(0.13)
		box.advance()
		steps += 1
	await frames(3)


func world() -> Node:
	return get_tree().current_scene


func place_player(tile: Vector2i, facing: String) -> Node:
	var p: Node = get_tree().get_first_node_in_group("player")
	p.global_position = MapBuilder.tile_center(tile)
	p.set_facing(facing)
	p.get_node("Camera").reset_smoothing()
	return p


# ------------------------------------------------------------------ 데이터
func test_data_integrity() -> void:
	section("데이터 무결성")
	check(not DataDB.player_def.is_empty(), "플레이어 데이터 로드")
	check(DataDB.skills.has("basic_fist") and DataDB.skills.has("combo_fist") and DataDB.skills.has("kihap"), "초기 무술 3종 정의")
	check(DataDB.enemies.has("scarecrow") and DataDB.enemies.has("bandit"), "적 2종 정의")
	var legend: Dictionary = DataDB.tiles["legend"]
	for map_id in DataDB.maps_index["maps"]:
		var m := DataDB.get_map(map_id)
		var size: Array = m["size"]
		var rows: Array = m["tiles"]
		var ok_rows := rows.size() == int(size[1])
		var ok_cols := true
		var ok_chars := true
		for r in rows:
			ok_cols = ok_cols and r.length() == int(size[0])
			for ch in r:
				ok_chars = ok_chars and legend.has(ch)
		check(ok_rows and ok_cols, "%s: 크기 %dx%d 일치" % [map_id, size[0], size[1]])
		check(ok_chars, "%s: 모든 타일 문자가 범례에 있음" % map_id)
		for n in m.get("npcs", []):
			var t := Vector2i(int(n["tile"][0]), int(n["tile"][1]))
			check(not MapBuilder.is_solid(m, t), "%s: NPC %s 위치가 통행 가능 타일" % [map_id, n["id"]])
			check(DataDB.dialogue.has(n["dialogue"]), "%s: NPC %s 대사 존재" % [map_id, n["id"]])
			if n.has("battle"):
				check(DataDB.enemies.has(n["battle"]), "%s: NPC %s 전투 적 존재" % [map_id, n["id"]])
		for e in m.get("events", []):
			check(DataDB.dialogue.has(e["dialogue"]), "%s: 이벤트 %s 대사 존재" % [map_id, e["id"]])
		for x in m.get("exits", []):
			check(DataDB.has_map(x["to"]), "%s: 출구 → %s 맵 존재" % [map_id, x["to"]])
			var dest := DataDB.get_map(x["to"])
			var sp := Vector2i(int(x["spawn"][0]), int(x["spawn"][1]))
			check(not MapBuilder.is_solid(dest, sp), "%s: 출구 도착 지점 통행 가능" % map_id)
	for speaker in DataDB.portraits:
		if str(speaker).begins_with("_"):
			continue
		check(DataDB.portrait(speaker, "normal") != null, "초상화 존재: %s" % speaker)
	for e in ["happy", "angry", "surprised", "sweat"]:
		check(ResourceLoader.exists("res://assets/portraits/doyun_%s.png" % e), "도윤 표정: %s" % e)
	for pose in ["ready", "punch", "kick", "hurt", "guard", "win", "shout", "ko"]:
		check(ResourceLoader.exists("res://assets/battle/doyun_%s.png" % pose), "도윤 전투 자세: %s" % pose)
	for en in DataDB.enemies:
		for pose in ["idle", "windup", "attack", "hurt", "ko"]:
			check(ResourceLoader.exists(DataDB.enemies[en]["battle"] + pose + ".png"), "%s 전투 자세: %s" % [en, pose])
	var village := DataDB.get_map("cheongpung")
	check(village["size"] == [30, 20] or village["size"] == [30.0, 20.0], "청풍마을 30x20 타일")
	check(village["npcs"].size() == 3, "청풍마을 NPC 3명")
	var text := "".join(village["tiles"])
	check(text.count("D") >= 5, "문 타일(집 3 + 도장 + 상점) 존재")


func test_ktext() -> void:
	section("한국어 조사")
	check(KText.josa("도윤", "은/는") == "도윤은", "도윤은")
	check(KText.josa("덕팔", "을/를") == "덕팔을", "덕팔을")
	check(KText.josa("허수아비", "을/를") == "허수아비를", "허수아비를")
	check(KText.josa("약초", "이/가") == "약초가", "약초가")


# ------------------------------------------------------------------ 전투 로직 (카드)
func _new_logic(enemy: String = "bandit", seed_value: int = 7, deck: Array = []) -> BattleLogic:
	var l := BattleLogic.new()
	var stats := {"name": "도윤", "hp": 60, "max_hp": 60, "mp": 20, "max_mp": 20, "attack": 12, "defense": 6, "agility": 8}
	if deck.is_empty():
		deck = ["strike", "strike", "strike", "strike", "defend", "defend", "defend", "defend", "combo_fist", "combo_fist", "kihap"]
	l.setup(stats, enemy, DataDB.enemies[enemy], DataDB.battle_config, DataDB.cards, deck, seed_value, {})
	return l


## 손패를 원하는 카드로 고정하고 기를 채운다
func _hand(l: BattleLogic, cards: Array) -> void:
	l.hand = cards.duplicate()
	l.p["energy"] = 3


func test_battle_logic() -> void:
	section("카드 전투: 기본 규칙")
	var l := _new_logic()
	l.start()
	check(l.hand.size() == 5 and int(l.p["energy"]) == 3, "턴 시작: 카드 5장, 기 3")
	check(l.draw_pile.size() == 6, "나머지 6장은 덱에")
	check(not l.e["intent"].is_empty(), "적의 다음 행동(의도) 예고")
	_hand(l, ["strike"])
	var hp0 := int(l.e["hp"])
	l.play_card(0)
	check(int(l.e["hp"]) == hp0 - 6 and int(l.p["energy"]) == 2, "기본권: 피해 6, 기 1 소모")
	check(l.discard.has("strike") and l.hand.is_empty(), "사용한 카드는 버림 더미로")
	_hand(l, ["defend"])
	l.play_card(0)
	check(int(l.p["block"]) == 5, "막기: 호신 5")
	l.e["intent"] = {"type": "attack", "damage": 8, "text": "공격"}
	var php := int(l.p["hp"])
	l.enemy_turn()
	check(int(l.p["hp"]) == php - 3 and int(l.p["block"]) == 0, "적 공격 8 → 호신 5가 막고 3 피해")
	l.start_player_turn()
	check(int(l.p["block"]) == 0 and int(l.p["energy"]) == 3, "새 턴: 호신 초기화, 기 회복")

	section("카드 전투: 비용 / 버림 / 섞기")
	l = _new_logic()
	_hand(l, ["combo_fist", "combo_fist"])
	l.p["mp"] = 2
	check(not l.can_play(0), "MP 부족 카드 사용 불가")
	l.p["mp"] = 20
	l.p["energy"] = 0
	check(not l.can_play(0), "기 부족 카드 사용 불가")
	var ev := l.play_card(0)
	check(ev.size() == 1 and ev[0]["fx"] == "invalid", "사용 불가 시 아무 일도 없음")
	l = _new_logic("bandit", 3, ["strike", "strike", "strike"])
	l.start()
	check(l.hand.size() == 3 and l.draw_pile.is_empty(), "덱이 적으면 있는 만큼만 뽑음")
	l.end_player_turn()
	check(l.hand.is_empty() and l.discard.size() == 3, "턴 종료: 손패 전부 버림")
	l.start_player_turn()
	check(l.hand.size() == 3 and l.discard.is_empty(), "덱이 비면 버림 더미를 섞어 다시 뽑음")

	section("카드 전투: 초식 효과")
	l = _new_logic()
	_hand(l, ["combo_fist"])
	hp0 = int(l.e["hp"])
	ev = l.play_card(0)
	check(ev.filter(func(x): return x["fx"] in ["hit", "crit"]).size() == 2 and int(l.e["hp"]) == hp0 - 8 and int(l.p["mp"]) == 17, "연속권: 4 x2연타, MP 3")
	_hand(l, ["kihap", "strike", "strike"])
	l.draw_pile = ["defend"]
	l.play_card(0)
	check(l.charge_mult == 2.0 and l.hand.size() == 3, "기합: 다음 공격 2배 + 1장 뽑기")
	hp0 = int(l.e["hp"])
	l.play_card(0)
	check(int(l.e["hp"]) == hp0 - 12 and l.charge_mult == 1.0, "기합 후 기본권 12 피해, 효과 소모")
	l = _new_logic()
	_hand(l, ["weak_point", "strike"])
	l.play_card(0)
	check(int(l.e["vulnerable"]) == 2, "급소 찌르기: 허점 2")
	hp0 = int(l.e["hp"])
	l.play_card(0)
	check(int(l.e["hp"]) == hp0 - 9, "허점 상태: 피해 1.5배 (6 → 9)")
	l = _new_logic()
	_hand(l, ["trip"])
	l.play_card(0)
	l.e["intent"] = {"type": "attack", "damage": 8, "text": "공격"}
	check(l.intent_damage() == 6, "발걸기 위축: 적 공격 8 → 6 예고")
	l = _new_logic()
	_hand(l, ["fighting_spirit", "strike"])
	l.play_card(0)
	check(int(l.p["strength"]) == 2 and l.card_stats("strike")["damage"] == 8, "투지: 기세 +2 → 기본권 8")
	check(not l.discard.has("fighting_spirit"), "투지(지속형)는 버림 더미로 가지 않음")
	l = _new_logic()
	_hand(l, ["counter"])
	l.play_card(0)
	l.e["intent"] = {"type": "attack", "damage": 4, "text": "공격"}
	hp0 = int(l.e["hp"])
	l.enemy_turn()
	check(int(l.e["hp"]) == hp0 - 3, "반격 자세: 맞으면 3 반격")
	l = _new_logic()
	l.e["intent"] = {"type": "block", "block": 8, "text": "방어"}
	l.enemy_turn()
	_hand(l, ["strike"])
	hp0 = int(l.e["hp"])
	l.play_card(0)
	check(int(l.e["hp"]) == hp0 and int(l.e["block"]) == 2, "적 호신 8이 기본권 6을 막음")
	l.e["intent"] = {"type": "buff", "strength": 2, "text": "기세"}
	l.enemy_turn()
	l.e["intent"] = {"type": "attack", "damage": 7, "text": "공격"}
	check(l.intent_damage() == 9 and int(l.e["block"]) == 0, "적 기세 +2 → 공격 9 예고, 적 호신은 자기 턴에 사라짐")

	section("카드 전투: 승패 / 타이밍")
	l = _new_logic()
	l.e["hp"] = 5
	_hand(l, ["strike"])
	ev = l.play_card(0)
	check(l.state == BattleLogic.State.WON and ev[-1]["fx"] == "down", "적 HP 0 → 승리")
	l = _new_logic()
	l.p["hp"] = 3
	l.e["intent"] = {"type": "attack", "damage": 7, "text": "공격"}
	l.enemy_turn()
	check(l.state == BattleLogic.State.LOST, "플레이어 HP 0 → 패배")
	l = _new_logic()
	l.e["hp"] = 999
	_hand(l, ["strike"])
	l.play_card(0, 1.3)
	check(999 - int(l.e["hp"]) == 7, "완벽 타이밍: 6 x1.3 = 7")
	l = _new_logic()
	l.e["intent"] = {"type": "attack", "damage": 10, "text": "공격"}
	l.enemy_turn(true)
	check(int(l.p["hp"]) == 56, "받아치기: 10 x0.4 = 4 피해")
	var c := l.flee_chance()
	check(c >= 0.1 and c <= 0.95, "도주 확률 범위 (%.2f)" % c)
	var rw := l.reward_choices(3)
	check(rw.size() == 3 and rw[0] != rw[1] and rw[1] != rw[2] and DataDB.cards[rw[0]].get("pool", "") == "reward", "보상 후보 3장 (서로 다름)")

	section("카드 전투: 자동 선택")
	l = _new_logic()
	l.e["intent"] = {"type": "idle", "text": "멍"}
	_hand(l, ["defend", "strike"])
	check(l.hand[l.auto_pick()] == "strike", "위협 없으면 공격 카드")
	l.e["intent"] = {"type": "attack", "damage": 12, "text": "공격"}
	l.p["hp"] = 20
	_hand(l, ["strike", "defend"])
	check(l.hand[l.auto_pick()] == "defend", "HP 낮고 큰 공격 예고면 막기")
	l.e["hp"] = 5
	check(l.hand[l.auto_pick()] == "strike", "마무리 가능하면 공격 우선")
	l.p["energy"] = 0
	check(l.auto_pick() == -1, "기가 없으면 턴 종료")


# ------------------------------------------------------------------ 상태
func test_game_state() -> void:
	section("게임 상태 / 성장")
	GameState.new_game()
	var p := GameState.player
	check(int(p["level"]) == 1 and int(p["hp"]) == 60 and int(p["mp"]) == 20, "새 게임 초기 능력치")
	check(GameState.current_map == "cheongpung", "시작 맵은 청풍마을")
	check(GameState.item_count("herb") == 3, "초기 아이템 약초 3개")
	check(GameState.exp_to_next(1) == 20 and GameState.exp_to_next(2) == 30, "필요 경험치 곡선 20 → 30")
	var msgs := GameState.add_exp(8)
	check(msgs.is_empty() and int(p["exp"]) == 8, "경험치 8 획득 (레벨업 없음)")
	msgs = GameState.add_exp(15)
	p = GameState.player
	check(int(p["level"]) == 2 and int(p["exp"]) == 3, "경험치 누적 23 → Lv.2, 남은 경험치 3")
	check(int(p["max_hp"]) == 72 and int(p["attack"]) == 15, "레벨업 능력치 성장 (HP 72, 공격 15)")
	check(msgs.size() >= 1 and "레벨 업" in msgs[0], "레벨업 메시지")
	GameState.player["hp"] = 10
	var m := GameState.use_item("herb")
	check(int(GameState.player["hp"]) == 40 and GameState.item_count("herb") == 2 and m != "", "필드 아이템 사용")
	check(GameState.use_item("manual_fragment") == "", "열쇠 아이템은 사용 불가")
	check(not GameState.remove_item("herb", 99), "부족한 수량 제거 거부")


# ------------------------------------------------------------------ 성장 시스템 (v0.3)
func test_growth() -> void:
	section("성장: 무공 습득 / 장착")
	GameState.new_game()
	check(GameState.skills == ["basic_fist", "combo_fist", "kihap"] and GameState.equipped.size() == 3, "Lv.1 무공 3종 습득·장착")
	check(not GameState.has_notice(), "새 게임 직후 알림 없음")
	for sid in DataDB.skills:
		var icon := "res://assets/ui/icons/%s.png" % DataDB.skills[sid].get("icon", "")
		check(ResourceLoader.exists(icon), "무공 아이콘 존재: %s" % sid)
	var msgs := GameState.add_exp(20)
	check(GameState.skills.has("breathing") and GameState.equipped.has("breathing"), "Lv.2 청풍호흡 습득 → 빈 칸에 자동 장착")
	check(msgs.any(func(m): return "청풍호흡" in m), "새 무공 습득 메시지")
	check(GameState.has_notice("new_skill"), "새 무공 알림(빨간 점)")
	GameState.add_exp(30)
	check(GameState.skills.has("iron_wall") and not GameState.equipped.has("iron_wall"), "Lv.3 철벽세 습득 (칸이 가득 차 미장착)")
	check(not GameState.toggle_equip("iron_wall"), "칸이 가득 차면 장착 실패")
	check(GameState.toggle_equip("kihap") and GameState.toggle_equip("iron_wall"), "기합 해제 후 철벽세 장착")
	GameState.equipped = ["basic_fist"]
	check(not GameState.toggle_equip("basic_fist"), "마지막 무공은 해제 불가")

	section("성장: 강화")
	GameState.new_game()
	check(GameState.upgrade_skill("combo_fist") == "", "내공 부족 시 무공 강화 불가")
	GameState.add_qi(100)
	var msg := GameState.upgrade_skill("combo_fist")
	check(msg != "" and GameState.skill_level("combo_fist") == 1 and GameState.qi == 90, "무공 강화: 내공 10 소모 → 1성")
	var l := BattleLogic.new()
	l.setup(GameState.effective_stats(), "bandit", DataDB.enemies["bandit"], DataDB.battle_config, DataDB.cards, GameState.build_deck(), 1, GameState.skill_levels)
	check(l.card_stats("combo_fist")["damage"] == 5, "무공 1성 → 연속권 카드 타격당 4 → 5")
	check(GameState.build_deck().count("combo_fist") == 2 and GameState.build_deck().count("strike") == 4, "덱: 기본권 4 + 막기 4 + 장착 무공 카드")
	GameState.add_card("iron_palm")
	check(GameState.build_deck().has("iron_palm"), "보상 카드가 덱에 추가")
	GameState.add_qi(500)
	for i in 10:
		GameState.upgrade_skill("combo_fist")
	check(GameState.skill_level("combo_fist") == 5 and GameState.skill_upgrade_cost("combo_fist") == -1, "최대 5성에서 멈춤")
	var atk0 := int(GameState.effective_stats()["attack"])
	check(GameState.upgrade_gear("fist_wrap") != "" and int(GameState.player["gold"]) == 15, "주먹싸개 강화: 15냥 소모")
	check(int(GameState.effective_stats()["attack"]) == atk0 + 2, "장비 강화 → 실제 공격력 +2")
	GameState.player["gold"] = 5
	check(GameState.upgrade_gear("martial_robe") == "", "냥 부족 시 장비 강화 불가")

	section("성장: 폐관수련 (방치 보상)")
	GameState.new_game()
	var now := 2_000_000_000
	GameState.last_active_unix = now - 2 * 60
	GameState.compute_offline(now)
	check(not GameState.has_offline_reward(), "5분 미만은 보상 없음")
	GameState.last_active_unix = now - 2 * 3600
	GameState.compute_offline(now)
	check(GameState.has_offline_reward() and int(GameState.offline_pending["minutes"]) == 120, "2시간 → 120분 적립")
	check(int(GameState.offline_pending["qi"]) == 60 and int(GameState.offline_pending["gold"]) == 24, "보상: 내공 60, 24냥 (Lv.1)")
	check(GameState.has_notice("offline"), "수련 보상 알림(빨간 점)")
	GameState.offline_pending = {}
	GameState.last_active_unix = now - 30 * 3600
	GameState.compute_offline(now)
	check(int(GameState.offline_pending["minutes"]) == 480, "최대 8시간까지만 인정")
	var q0 := GameState.qi
	check(GameState.claim_offline() != "" and GameState.qi > q0 and not GameState.has_offline_reward(), "보상 받기 → 내공 증가")
	check(not GameState.has_notice("offline"), "보상 받으면 알림 해제")

	section("다음 할 일 안내")
	GameState.new_game()
	check("사범" in GameState.guide()["text"], "1: 사범에게 말 걸기")
	GameState.set_flag("talked_master")
	GameState.set_quest("first_training", "active")
	check("산적" in GameState.guide()["text"] and GameState.guide()["map"] == "training_ground", "2: 수련장 산적")
	GameState.current_map = "cheongpung"
	check(GameState.guide_target_position() == MapBuilder.tile_center(Vector2i(14, 19)), "다른 맵 목표면 출구를 가리킴")
	GameState.set_flag("bandit_defeated")
	check("소식" in GameState.guide()["text"], "3: 사범에게 보고")



# ------------------------------------------------------------------ 저장
func test_save_load() -> void:
	section("저장 / 불러오기")
	GameState.new_game()
	GameState.add_exp(25)
	GameState.add_item("qi_pill", 2)
	GameState.set_flag("bandit_defeated")
	GameState.set_quest("first_training", "cleared")
	GameState.set_location("training_ground", Vector2i(5, 7), "left")
	GameState.player["hp"] = 33
	var before := GameState.to_dict()
	check(SaveManager.save_game(), "저장 성공")
	check(FileAccess.file_exists(SaveManager.save_path()), "저장 파일 생성")
	var raw: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SaveManager.save_path()))
	check(int(raw["version"]) == SaveManager.SAVE_VERSION and raw.has("checksum"), "저장 파일에 버전/체크섬 포함")

	GameState.new_game()
	check(SaveManager.load_game() == SaveManager.LoadResult.OK, "불러오기 성공")
	var after := GameState.to_dict()
	check(int(after["player"]["level"]) == int(before["player"]["level"]) and int(after["player"]["exp"]) == int(before["player"]["exp"]), "레벨/경험치 복원")
	check(int(after["player"]["hp"]) == 33, "HP 복원")
	check(GameState.item_count("qi_pill") == 3 and GameState.item_count("herb") == 3, "아이템 복원")
	check(GameState.has_flag("bandit_defeated") and GameState.get_quest("first_training") == "cleared", "플래그/퀘스트 복원")
	check(GameState.current_map == "training_ground" and GameState.player_position == MapBuilder.tile_center(Vector2i(5, 7)) and GameState.facing == "left", "맵/위치/방향 복원")

	# 두 번째 저장 → 첫 번째는 백업으로
	GameState.add_exp(1)
	SaveManager.save_game()
	check(FileAccess.file_exists(SaveManager.backup_path()), "이전 저장본 백업 생성")

	# 본 파일 손상 → 백업으로 복구
	var f := FileAccess.open(SaveManager.save_path(), FileAccess.WRITE)
	f.store_string("{ 이건 망가진 JSON")
	f.close()
	GameState.new_game()
	check(SaveManager.load_game() == SaveManager.LoadResult.RESTORED_FROM_BACKUP, "손상된 저장 → 백업에서 복구")
	check(GameState.current_map == "training_ground", "복구된 데이터 적용")

	# 체크섬 변조 감지
	SaveManager.save_game()
	var env: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SaveManager.save_path()))
	env["data"]["player"]["level"] = 99
	f = FileAccess.open(SaveManager.save_path(), FileAccess.WRITE)
	f.store_string(JSON.stringify(env))
	f.close()
	check(SaveManager.read_envelope(SaveManager.save_path()).is_empty(), "변조된 데이터(체크섬 불일치) 거부")

	# 미래 버전 거부
	env["version"] = 999
	f = FileAccess.open(SaveManager.save_path(), FileAccess.WRITE)
	f.store_string(JSON.stringify(env))
	f.close()
	check(SaveManager.read_envelope(SaveManager.save_path()).is_empty(), "알 수 없는 미래 버전 거부")

	# 둘 다 손상 → 안전하게 실패, 현재 상태 유지
	for path in [SaveManager.save_path(), SaveManager.backup_path()]:
		f = FileAccess.open(path, FileAccess.WRITE)
		f.store_string("garbage")
		f.close()
	GameState.new_game()
	var lvl := int(GameState.player["level"])
	check(SaveManager.load_game() == SaveManager.LoadResult.CORRUPTED, "모두 손상 → CORRUPTED 반환 (크래시 없음)")
	check(int(GameState.player["level"]) == lvl and GameState.current_map == "cheongpung", "실패 시 현재 상태 유지")
	check(not GameState.apply_dict({"player": "x"}), "형식이 틀린 데이터 적용 거부")
	# 이전 버전(v1) 저장 파일 → 새 버전에서 불러오기
	GameState.new_game()
	var v1 := GameState.to_dict()
	for key in ["equipped", "skill_levels", "gear", "qi", "notices", "last_active_unix"]:
		v1.erase(key)
	v1["player"]["level"] = 3
	var env1 := {"version": 1, "saved_at": "2026-11-18T12:00:00", "checksum": SaveManager._checksum(v1), "data": v1}
	f = FileAccess.open(SaveManager.save_path(), FileAccess.WRITE)
	f.store_string(JSON.stringify(env1))
	f.close()
	check(SaveManager.load_game() == SaveManager.LoadResult.OK, "v1 저장 파일 불러오기 (마이그레이션)")
	check(GameState.skills.has("iron_wall") and GameState.equipped.size() >= 1 and GameState.qi == 0, "v1 → 레벨에 맞는 무공·기본값 채움")
	SaveManager.delete_save()
	check(not SaveManager.has_save(), "저장 삭제")


func test_dialogue_data() -> void:
	section("대화 데이터")
	GameState.new_game()
	var d := DialogueData.resolve("master")
	check(d["name"] == "도장 사범 백운", "NPC 이름")
	check("넘어지지 않고 걷는 법" in d["lines"][0]["text"], "사범 첫 대사")
	check(d["lines"].size() >= 3, "여러 줄 대화")
	DialogueData.apply_actions(d["actions"])
	check(GameState.has_flag("talked_master") and GameState.get_quest("first_training") == "active", "대화 효과: 플래그 + 임무 시작")
	check(not ("넘어지지" in DialogueData.resolve("master")["lines"][0]["text"]), "두 번째 대화는 다른 대사")
	GameState.set_flag("bandit_defeated")
	var herbs := GameState.item_count("herb")
	DialogueData.apply_actions(DialogueData.resolve("master")["actions"])
	check(GameState.item_count("herb") == herbs + 2 and GameState.get_quest("first_training") == "complete", "산적 처치 후 보상 + 임무 완료")
	check("너보다는 강할 것 같아" in DialogueData.resolve("villager")["lines"][0]["text"] or GameState.has_flag("bandit_defeated"), "주민 대사")
	check("좋은 물건은 비싸고" in DialogueData.resolve("merchant")["lines"][0]["text"], "상인 대사")


# ------------------------------------------------------------------ 장면 테스트
func test_main_menu() -> void:
	section("시작 화면")
	get_tree().change_scene_to_file("res://scenes/main/main_menu.tscn")
	await frames(5)
	var menu := get_tree().current_scene
	check(menu != null and menu.scene_file_path == "res://scenes/main/main_menu.tscn", "시작 화면 로드")
	var texts: Array = []
	for b in menu.find_children("*", "Button", true, false):
		texts.append(b.text)
	check("새 게임" in texts and "이어하기" in texts and "설정" in texts and "종료" in texts, "메뉴: 새 게임/이어하기/설정/종료")
	check(menu._continue_btn.disabled, "저장 없으면 이어하기 비활성")
	await shot("01_title")
	menu._on_settings()
	await frames(3)
	await shot("02_settings")
	menu._close_settings()


func test_playthrough() -> void:
	section("플레이 시나리오: 새 게임")
	var menu := get_tree().current_scene
	menu._on_new_game()
	check(await wait_scene(GameState.WORLD_SCENE), "새 게임 → 청풍마을 진입")
	var w := world()
	var ground: TileMapLayer = w.get_node("Ground")
	check(ground.get_used_cells().size() == 600, "타일맵 30x20 = 600칸 생성")
	check(get_tree().get_nodes_in_group("npc").size() == 3, "NPC 3명 배치")
	var player: Node = get_tree().get_first_node_in_group("player")
	check(player != null, "플레이어 생성")
	var tex: Texture2D = player.get_node("Sprite").sprite_frames.get_frame_texture("idle_down", 0)
	check(tex != null and tex.get_width() == 32 and tex.get_height() == 48, "플레이어 스프라이트 32x48")
	await seconds(0.5)
	await shot("03_village")

	section("이동 / 애니메이션 / 충돌")
	var start: Vector2 = player.global_position
	Input.action_press("move_right")
	await seconds(0.25)
	check(player.get_node("Sprite").animation == "walk_right", "걷기 애니메이션 재생 (walk_right)")
	Input.action_release("move_right")
	await seconds(0.1)
	check(player.global_position.x > start.x + 10, "오른쪽 이동 (%.0f → %.0f)" % [start.x, player.global_position.x])
	check(player.get_node("Sprite").animation == "idle_right", "멈추면 대기 애니메이션")
	await hold("move_down", 0.3)
	check(player.facing == "down", "아래 방향 전환")
	# 대각선 입력 → 4방향
	Input.action_press("move_left")
	await seconds(0.05)
	Input.action_press("move_up")
	await seconds(0.15)
	var dir: Vector2 = player.velocity.normalized()
	check(dir == Vector2.UP, "대각선 입력 시 나중 입력(위) 우선 → 4방향")
	Input.action_release("move_left")
	Input.action_release("move_up")
	await frames(2)
	# 도장 벽: (11,4)는 창문 벽. (11,5)에서 위로 1초
	place_player(Vector2i(11, 5), "up")
	await frames(2)
	await hold("move_up", 1.0)
	check(player.global_position.y >= 5 * 32 - 5, "건물 벽 충돌 (y=%.0f, 벽 아래 경계 160)" % player.global_position.y)
	# 나무 테두리: (1,1)에서 왼쪽으로
	place_player(Vector2i(1, 1), "left")
	await frames(2)
	await hold("move_left", 0.8)
	check(player.global_position.x >= 32 + 8, "나무(맵 경계) 충돌 (x=%.0f)" % player.global_position.x)
	# 연못: (3,16) 오른쪽 (4,16)은 물
	place_player(Vector2i(3, 17), "right")
	await frames(2)
	await hold("move_right", 0.8)
	check(player.global_position.x <= 4 * 32 - 8, "연못(물) 통과 불가 (x=%.0f)" % player.global_position.x)
	# NPC 충돌: 사범 (17,5) 아래 (17,7)에서 위로
	place_player(Vector2i(17, 7), "up")
	await frames(2)
	await hold("move_up", 0.8)
	check(player.global_position.y > 5 * 32 + 16 + 4, "NPC 통과 불가 (y=%.0f)" % player.global_position.y)

	section("NPC 대화")
	var box: Node = w.get_node("DialogueBox")
	Settings.text_speed = "normal"
	place_player(Vector2i(17, 6), "up")
	await frames(3)
	await press("interact")
	await frames(3)
	check(box.is_open(), "상호작용 → 대화창 열림")
	check(box._name_label.text == "도장 사범 백운", "NPC 이름 표시")
	check(box._portrait_frame.visible and box._portrait.texture != null, "대화창 초상화 표시")
	check(box._portrait.texture.resource_path.ends_with("master_happy.png"), "대사별 표정 (사범 첫 대사: 기쁨)")
	await seconds(0.4)
	await shot("04_dialogue")
	check("천하제일 고수" in box._text.text, "한국어 대사 출력")
	check(GameState.is_input_locked(), "대화 중 입력 잠금")
	var pos_lock: Vector2 = player.global_position
	await hold("move_down", 0.3)
	check(player.global_position == pos_lock, "대화 중 이동 불가")
	var first_text: String = box._text.text
	await seconds(2.0)
	box.advance()
	await frames(2)
	check(box._text.text != first_text, "대사 넘기기 → 다음 줄")
	check(box._name_label.text == "도윤", "화자 전환 (도윤)")
	check(box._portrait.texture.resource_path.find("doyun_") >= 0, "화자에 맞춰 초상화 전환")
	await finish_dialogue(box)
	check(not box.is_busy(), "대화 종료 (획득 안내 포함)")
	check(not GameState.is_input_locked(), "대화 종료 후 잠금 해제")
	check(GameState.get_quest("first_training") == "active", "임무 '첫 수련' 시작")
	await hold("move_down", 0.3)
	check(player.global_position.y > pos_lock.y + 5, "대화 종료 후 이동 재개")
	Settings.text_speed = "instant"
	# 조사 지점: 연못에서 비급 조각
	place_player(Vector2i(6, 14), "down")
	await frames(3)
	await press("interact")
	check(box.is_open(), "숨겨진 이벤트(연못) 조사")
	await finish_dialogue(box)
	check(GameState.item_count("manual_fragment") == 1, "숨겨진 아이템 '낡은 비급 조각' 획득")
	# 상인, 주민
	place_player(Vector2i(23, 8), "up")
	await seconds(0.3)
	await press("interact")
	check(box.is_open() and box._name_label.text == "상인 만복", "상인 대화")
	await finish_dialogue(box)
	await frames(3)
	var shop: Node = w.shop
	check(shop.is_open() and GameState.is_input_locked(), "상인 대화 후 만복상회(상점) 열림")
	await shot("05b_shop")
	var gold0 := int(GameState.player["gold"])
	var herb0 := GameState.item_count("herb")
	check(shop.buy("herb") and int(GameState.player["gold"]) == gold0 - 10 and GameState.item_count("herb") == herb0 + 1, "약초 구입 (10냥)")
	GameState.player["gold"] = 0
	check(not shop.buy("qi_pill"), "돈이 부족하면 구입 불가")
	GameState.player["gold"] = gold0
	await shop.close_shop()
	check(not shop.is_open() and not GameState.is_input_locked(), "상점 닫기 → 이동 재개")
	# 연못 두 번째 조사 → 낚시
	place_player(Vector2i(6, 14), "down")
	await seconds(0.3)
	await press("interact")
	await finish_dialogue(box)
	await frames(3)
	var fishing: Node = w.fishing
	check(fishing.is_open(), "연못 재조사 → 낚시 미니게임 열림")
	await seconds(0.3)
	await shot("05c_fishing")
	fishing.rng.seed = 3
	check(fishing.judge(0.95, 0.2, 0.2) == "", "찌가 구간 밖이면 놓침")
	var caught: String = fishing.judge(0.3, 0.2, 0.2)
	check(caught in ["crucian", "carp", "golden_carp"], "구간 안이면 물고기 획득 (%s)" % caught)
	check(fishing.judge(0.3, 0.2, 0.2) != "crucian", "정중앙 챔질은 잉어 이상 보장")
	fishing._active = true
	fishing._pos = fishing._zone_start + fishing._zone_width / 2.0
	var got: String = fishing.strike()
	check(got != "" and GameState.item_count(got) >= 1, "챔질 → 가방에 물고기 추가 (%s)" % got)
	var g1 := int(GameState.player["gold"])
	check(shop.sell(got) and int(GameState.player["gold"]) > g1, "물고기 판매 → 냥 증가")
	await fishing.stop()
	check(not GameState.is_input_locked(), "낚시 종료 → 이동 재개")
	place_player(Vector2i(8, 9), "up")
	await seconds(0.3)
	await press("interact")
	check(box.is_open() and box._name_label.text == "마을 주민 순이", "주민 대화")
	await finish_dialogue(box)

	section("모바일 터치 조작")
	var touch: Node = w.get_node("TouchControls")
	check(touch.visible, "터치 버튼 표시 (설정: 켜기)")
	place_player(Vector2i(20, 9), "down")
	await frames(3)
	var right_btn: TouchScreenButton = touch.get_button("right")
	var tpos: Vector2 = right_btn.global_position + right_btn.texture_normal.get_size() / 2.0
	var x0: float = player.global_position.x
	_touch(0, tpos, true)
	await seconds(0.3)
	check(Input.is_action_pressed("move_right"), "방향키 터치 → move_right 액션")
	_touch(0, tpos, false)
	await frames(3)
	check(player.global_position.x > x0 + 10, "터치로 캐릭터 이동 (%.0f → %.0f)" % [x0, player.global_position.x])
	check(not Input.is_action_pressed("move_right"), "손을 떼면 정지")
	await shot("05_touch")
	# A 버튼 터치로 대화
	place_player(Vector2i(17, 6), "up")
	await frames(3)
	var a_btn: TouchScreenButton = touch.get_button("a")
	var apos: Vector2 = a_btn.global_position + a_btn.texture_normal.get_size() / 2.0
	_touch(1, apos, true)
	await frames(2)
	_touch(1, apos, false)
	await frames(3)
	check(box.is_open(), "확인(A) 터치 → NPC 대화")
	await finish_dialogue(box)

	section("다음 할 일 안내")
	var hud: Node = w.get_node("HUD")
	check("만복" in hud._guide_label.text or "연못" in hud._guide_label.text or "산적" in hud._guide_label.text, "HUD 안내 바: %s" % hud._guide_label.text)
	check(GameState.guide_target_position() != null, "안내 목표 위치 계산")

	section("일시정지 메뉴")
	var pm: Node = w.get_node("PauseMenu")
	await press("menu")
	await frames(2)
	check(pm.is_open() and get_tree().paused, "메뉴 열기 → 일시정지")
	check(pm._tab_buttons.size() == 5 and pm._tab_buttons.has("skills") and pm._tab_buttons.has("training"), "하단 탭 5개 (상태/무공/가방/수련/시스템)")
	await shot("06_menu_status")
	pm._show_items()
	await frames(2)
	await shot("07_menu_items")
	pm.show_tab("skills")
	await frames(2)
	await shot("07b_menu_skills")
	pm.show_tab("training")
	await frames(2)
	pm.close()
	await frames(3)
	check(not pm.is_open() and not get_tree().paused, "메뉴 닫기")

	section("수련장 이동")
	place_player(Vector2i(14, 17), "down")
	await frames(3)
	Input.action_press("move_down")
	var moved := await wait_scene_map("training_ground", 4.0)
	Input.action_release("move_down")
	check(moved, "남쪽 출구 → 수련장 이동")
	await wait_scene(GameState.WORLD_SCENE)
	w = world()
	player = get_tree().get_first_node_in_group("player")
	check(player.global_position == MapBuilder.tile_center(Vector2i(10, 2)), "수련장 입구(도착 지점)에 등장 (%s)" % player.global_position)
	check(w.get_node("Ground").get_used_cells().size() == 240, "수련장 20x12 타일맵")
	await seconds(0.5)
	await shot("08_training_ground")

	section("첫 전투 (산적 매복)")
	box = w.get_node("DialogueBox")
	Input.action_press("move_down")
	var t0 := Time.get_ticks_msec()
	while not box.is_open() and Time.get_ticks_msec() - t0 < 3000:
		await frames(1)
	Input.action_release("move_down")
	check(box.is_open(), "수련장 진입 → 산적 등장 대사")
	await finish_dialogue(box)
	check(await wait_scene(GameState.BATTLE_SCENE), "턴제 전투 시작")
	var battle: Node = world()
	check(battle.enemy_id == "bandit", "적: 초급 산적")
	await _wait_commands(battle)
	await seconds(0.4)
	await shot("09_battle")
	check(battle._card_nodes.size() == 5 and battle._energy_label.text == "3/3", "카드 5장 + 기 3/3 표시")
	check(battle._intent_box.visible and battle._intent_icon.texture != null, "적 머리 위 의도 표시")
	check(not battle._end_btn.disabled, "턴 종료 버튼")
	check(not battle.auto_allowed and battle._auto_btn.text == "자동 잠김", "스토리 첫 전투는 자동 전투 잠김")
	var exp_before := int(GameState.player["exp"]) + 0
	var lvl_before := int(GameState.player["level"])
	battle.logic.rng.seed = 12345

	section("카드 전투: 타이밍 · 받아치기 · 자세")
	check(battle._player_sprite.texture.resource_path.ends_with("doyun_ready.png"), "대기 자세 (ready)")
	if not battle.logic.hand.has("strike"):
		battle.logic.hand[0] = "strike"
		battle._refresh_hand()
	var ehp_start := int(battle.logic.e["hp"])
	battle.play_card_index(battle.logic.hand.find("strike"))
	var tt := Time.get_ticks_msec()
	while not battle.is_timing_active() and Time.get_ticks_msec() - tt < 2000:
		await frames(1)
	check(battle.is_timing_active(), "공격 카드 → 타이밍 원 표시")
	await seconds(battle._cfg_t("ring_time", 0.55) - 0.02)
	battle.timing_press()
	await frames(2)
	check(battle.last_timing == "perfect", "원이 겹칠 때 누르면 「완벽!」")
	var saw_punch := false
	tt = Time.get_ticks_msec()
	while Time.get_ticks_msec() - tt < 1500 and not saw_punch:
		saw_punch = battle._player_sprite.texture.resource_path.ends_with("doyun_punch.png")
		await frames(1)
	check(saw_punch, "돌진 후 주먹 자세로 타격")
	await _wait_commands(battle)
	check(int(battle.logic.e["hp"]) <= ehp_start - 7, "완벽 기본권 피해 7 이상 (%d → %d)" % [ehp_start, battle.logic.e["hp"]])
	check(battle._card_nodes.size() == 4 and battle._energy_label.text == "2/3", "카드 1장 사용 → 손패 4장, 기 2")
	var parried := false
	for k in 5:
		if parried or battle.logic.state != BattleLogic.State.ONGOING:
			break
		battle.logic.p["hp"] = maxi(int(battle.logic.p["hp"]), 30)
		battle.end_turn()
		tt = Time.get_ticks_msec()
		while battle.busy and Time.get_ticks_msec() - tt < 6000 and battle.logic.state == BattleLogic.State.ONGOING:
			if battle.is_timing_active():
				battle.timing_press()
				await frames(2)
				parried = parried or battle.last_timing == "parry"
			await frames(1)
		await _wait_commands(battle)
	check(parried, "적의 「!」에 맞춰 누르면 받아치기")
	check(battle._card_nodes.size() == 5 and battle.logic.turn >= 2, "다음 턴: 카드 5장 새로 뽑음")
	await shot("10b_battle_dynamic")
	var actions := 0
	var cutin_shot := false
	while battle.logic.state == BattleLogic.State.ONGOING and actions < 60:
		battle.logic.p["hp"] = maxi(int(battle.logic.p["hp"]), 25)
		var idx: int = battle.logic.auto_pick()
		if idx >= 0:
			var cid: String = battle.logic.hand[idx]
			battle.play_card_index(idx)
			if not cutin_shot and cid != "strike" and DataDB.cards[cid].has("damage"):
				await frames(4)
				await shot("10_battle_cutin")
				cutin_shot = true
		else:
			battle.end_turn()
		await _wait_commands(battle)
		actions += 1
	check(battle.logic.state == BattleLogic.State.WON, "카드로 산적을 쓰러뜨림 (%d수)" % actions)
	tt = Time.get_ticks_msec()
	while battle._reward_panel == null and Time.get_ticks_msec() - tt < 8000:
		await frames(2)
	check(battle._reward_panel != null and battle.reward_options.size() == 3, "승리 보상: 초식 카드 3장 중 선택")
	check(battle._p_hp_txt.text == "%d/%d" % [GameState.player["hp"], GameState.player["max_hp"]], "레벨업 후 전투 화면 HP 표시 갱신 (%s)" % battle._p_hp_txt.text)
	await shot("11_battle_win")
	var picked: String = battle.reward_options[0]
	var deck_before := GameState.build_deck().size()
	battle.choose_reward(0)
	check(GameState.build_deck().size() == deck_before + 1 and GameState.bonus_cards.has(picked), "고른 카드가 덱에 추가 (%s)" % picked)
	check(await wait_scene(GameState.WORLD_SCENE), "전투 종료 → 맵 복귀")
	var exp_gained := int(GameState.player["exp"]) != exp_before or int(GameState.player["level"]) > lvl_before
	check(exp_gained, "경험치 획득 (Lv.%d → Lv.%d, EXP %d → %d)" % [lvl_before, GameState.player["level"], exp_before, GameState.player["exp"]])
	check(int(GameState.player["level"]) >= 2, "레벨업 (경험치 25 ≥ 20)")
	check(GameState.has_flag("bandit_defeated") and GameState.get_quest("first_training") == "cleared", "산적 처치 플래그 / 임무 갱신")
	check(GameState.current_map == "training_ground", "원래 맵(수련장)으로 복귀")
	var bandit_present := false
	for n in get_tree().get_nodes_in_group("npc"):
		bandit_present = bandit_present or n.npc_id() == "bandit"
	check(not bandit_present, "쓰러뜨린 산적은 맵에서 사라짐")
	await seconds(0.3)

	section("허수아비 수련 + 도주")
	player = get_tree().get_first_node_in_group("player")
	place_player(Vector2i(5, 6), "up")
	await seconds(0.3)
	await press("interact")
	box = world().get_node("DialogueBox")
	await finish_dialogue(box)
	check(await wait_scene(GameState.BATTLE_SCENE), "허수아비 상호작용 → 전투")
	battle = world()
	await _wait_commands(battle)
	battle.logic.rng.seed = 1
	var tries := 0
	while battle.logic.state == BattleLogic.State.ONGOING and tries < 15:
		battle.logic.p["hp"] = maxi(int(battle.logic.p["hp"]), 30)
		battle._cmd_flee()
		await _wait_commands(battle)
		tries += 1
	check(battle.logic.state == BattleLogic.State.FLED, "도주 성공")
	check(await wait_scene(GameState.WORLD_SCENE), "도주 → 맵 복귀")

	section("자동 전투 + 2배속 (허수아비)")
	place_player(Vector2i(5, 6), "up")
	await seconds(0.3)
	await press("interact")
	box = world().get_node("DialogueBox")
	await finish_dialogue(box)
	check(await wait_scene(GameState.BATTLE_SCENE), "허수아비 전투 시작")
	battle = world()
	await _wait_commands(battle)
	check(battle.auto_allowed, "수련 상대는 자동 전투 허용")
	var qi0 := GameState.qi
	var cards0 := GameState.bonus_cards.size()
	battle.toggle_speed()
	check(Engine.time_scale == 2.0 and battle._speed_btn.text == "2배속", "2배속 켜기 → 게임 속도 2배")
	battle.logic.rng.seed = 5
	battle.toggle_auto()
	check(battle.auto_on, "자동 전투 켜기")
	var t_auto := Time.get_ticks_msec()
	while get_tree().current_scene == battle and Time.get_ticks_msec() - t_auto < 30000:
		await frames(2)
	check(await wait_scene(GameState.WORLD_SCENE), "자동 전투로 허수아비 처치 → 맵 복귀 (입력 없이)")
	check(Engine.time_scale == 1.0, "전투 종료 후 게임 속도 원래대로")
	check(GameState.qi > qi0, "승리 보상 내공 획득 (%d → %d)" % [qi0, GameState.qi])
	check(GameState.bonus_cards.size() == cards0 + 1, "자동 전투 보상 카드 자동 획득")
	check(GameState.has_flag("beaten_scarecrow"), "처치 기록 (다음부터 자동 허용)")
	Settings.set_value("battle_auto", false)
	Settings.set_value("battle_speed", 1)

	section("저장 → 타이틀 → 이어하기")
	player = get_tree().get_first_node_in_group("player")
	place_player(Vector2i(12, 7), "right")
	GameState.player_position = player.global_position
	await frames(2)
	var saved_pos: Vector2 = player.global_position
	var saved_lv := int(GameState.player["level"])
	var saved_exp := int(GameState.player["exp"])
	pm = world().get_node("PauseMenu")
	pm.open()
	pm._do_save()
	await frames(2)
	await shot("12_saved")
	check(SaveManager.has_save(), "메뉴에서 저장")
	pm.close()
	await frames(2)
	GameState.return_to_title()
	check(await wait_scene(GameState.MENU_SCENE), "타이틀로 복귀")
	menu = world()
	check(not menu._continue_btn.disabled, "이어하기 활성화")
	GameState.new_game()  # 상태를 오염시켜 불러오기가 실제로 덮어쓰는지 확인
	menu._on_continue()
	check(await wait_scene(GameState.WORLD_SCENE), "이어하기 → 게임 복귀")
	player = get_tree().get_first_node_in_group("player")
	check(GameState.current_map == "training_ground", "저장한 맵으로 복귀")
	check(player.global_position.distance_to(saved_pos) < 1.0, "저장한 위치로 복귀")
	check(int(GameState.player["level"]) == saved_lv and int(GameState.player["exp"]) == saved_exp, "레벨/경험치 유지")
	check(GameState.has_flag("bandit_defeated"), "진행 플래그 유지")

	section("패배 처리")
	GameState.player["hp"] = 1
	GameState.start_battle("bandit")
	check(await wait_scene(GameState.BATTLE_SCENE), "전투 시작")
	battle = world()
	await _wait_commands(battle)
	for i in 12:
		if battle.logic.state != BattleLogic.State.ONGOING:
			break
		battle.logic.p["hp"] = 1
		battle.end_turn()
		await _wait_commands(battle)
	await _confirm_battle_end(battle)
	check(await wait_scene(GameState.WORLD_SCENE), "패배 → 맵으로 이송")
	check(GameState.current_map == "cheongpung" and int(GameState.player["hp"]) >= 1, "청풍관 앞에서 HP 회복된 상태로 깨어남")
	await seconds(0.6)
	box = world().get_node("DialogueBox")
	await finish_dialogue(box)
	_scenario_done = true


func _confirm_battle_end(battle: Node) -> void:
	for i in 30:
		await seconds(0.1)
		if not is_instance_valid(battle) or get_tree().current_scene != battle:
			return
		battle._skip_requested.emit()


func wait_scene_map(map_id: String, timeout: float) -> bool:
	var t := 0.0
	while t < timeout:
		if GameState.current_map == map_id:
			return true
		await get_tree().process_frame
		t += get_process_delta_time()
	return false


func _wait_commands(battle: Node, timeout: float = 15.0) -> void:
	var t := 0.0
	while t < timeout:
		if not is_instance_valid(battle) or get_tree().current_scene != battle:
			return
		if not battle.busy or battle._waiting_confirm or battle._reward_panel != null:
			await frames(2)
			return
		await get_tree().process_frame
		t += get_process_delta_time()


func _touch(index: int, pos: Vector2, pressed: bool) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = index
	# 뷰포트 좌표 → 창 좌표 (화면 늘이기 배율 반영)
	ev.position = get_tree().root.get_final_transform() * pos
	ev.pressed = pressed
	Input.parse_input_event(ev)
