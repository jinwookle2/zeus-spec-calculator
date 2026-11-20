extends Node
## 진행 중인 게임의 모든 상태(능력치, 아이템, 플래그, 퀘스트, 위치)를 보관하는 싱글턴.
## 저장/불러오기는 to_dict()/apply_dict() 를 통해 SaveManager 가 담당한다.

signal stats_changed
signal inventory_changed
signal quest_changed
signal notices_changed

const WORLD_SCENE := "res://scenes/world/world.tscn"
const BATTLE_SCENE := "res://scenes/battle/battle.tscn"
const MENU_SCENE := "res://scenes/main/main_menu.tscn"
const TILE := 32

var player: Dictionary = {}
var skills: Array = []
var inventory: Dictionary = {}
var flags: Dictionary = {}
var quests: Dictionary = {}
var current_map: String = ""
var player_position: Vector2 = Vector2.ZERO
var facing: String = "down"
var play_time: float = 0.0
var pending_battle: Dictionary = {}
var last_battle_result: Dictionary = {}
var in_game: bool = false
# --- 성장 (v0.3)
var equipped: Array = []          # 장착 무공 (최대 growth.skill_slots)
var skill_levels: Dictionary = {}  # 무공 강화 단계
var gear: Dictionary = {}          # 장비 강화 단계
var qi: int = 0                    # 내공 (무공 강화 재화)
var notices: Dictionary = {}       # 빨간 점 알림 ("new_skill" 등)
var last_active_unix: int = 0
var offline_pending: Dictionary = {}  # {"minutes", "qi", "gold"}
var _active_timer := 0.0

var _input_locks: Dictionary = {}


func _process(delta: float) -> void:
	if in_game:
		play_time += delta
		_active_timer += delta
		if _active_timer >= 10.0:
			_active_timer = 0.0
			last_active_unix = int(Time.get_unix_time_from_system())


## 모바일에서 앱이 내려가거나 창을 닫을 때 자동 저장 (필드에 있을 때만)
func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_APPLICATION_PAUSED:
		autosave()


func autosave() -> void:
	if in_game and pending_battle.is_empty() and get_tree() and get_tree().current_scene \
			and get_tree().current_scene.scene_file_path == WORLD_SCENE:
		SaveManager.save_game()


# ------------------------------------------------------------------ 새 게임
func new_game() -> void:
	var def: Dictionary = DataDB.player_def
	var base: Dictionary = def.get("base", {})
	player = {
		"name": def.get("name", "도윤"),
		"level": int(base.get("level", 1)),
		"exp": 0,
		"max_hp": int(base.get("max_hp", 60)),
		"max_mp": int(base.get("max_mp", 20)),
		"attack": int(base.get("attack", 12)),
		"defense": int(base.get("defense", 6)),
		"agility": int(base.get("agility", 8)),
		"gold": int(base.get("gold", 0)),
	}
	player["hp"] = player["max_hp"]
	player["mp"] = player["max_mp"]
	skills = []
	equipped = []
	skill_levels = {}
	gear = {}
	for gid in growth().get("gear", {}):
		gear[gid] = 0
	qi = 0
	notices = {}
	offline_pending = {}
	last_active_unix = int(Time.get_unix_time_from_system())
	learn_skills_for_level(int(player["level"]))
	notices.clear()  # 시작 무공은 알림 없음
	inventory = {}
	for item_id in def.get("starting_items", {}):
		inventory[item_id] = int(def["starting_items"][item_id])
	flags = {}
	quests = {}
	play_time = 0.0
	pending_battle = {}
	last_battle_result = {}
	var start_map: String = DataDB.maps_index.get("start_map", "cheongpung")
	var map_data := DataDB.get_map(start_map)
	var spawn: Array = map_data.get("spawn", [1, 1])
	set_location(start_map, Vector2i(int(spawn[0]), int(spawn[1])), "down")
	in_game = true
	clear_input_locks()
	stats_changed.emit()
	inventory_changed.emit()


# ------------------------------------------------------------------ 입력 잠금 (대화/메뉴 중 이동 제한)
func lock_input(reason: String) -> void:
	_input_locks[reason] = true


func unlock_input(reason: String) -> void:
	_input_locks.erase(reason)


func is_input_locked() -> bool:
	return not _input_locks.is_empty()


func clear_input_locks() -> void:
	_input_locks.clear()


# ------------------------------------------------------------------ 성장
func exp_to_next(level: int) -> int:
	var curve: Dictionary = DataDB.player_def.get("exp_curve", {})
	var base := float(curve.get("base", 20))
	var factor := float(curve.get("factor", 1.5))
	return int(round(base * pow(factor, level - 1)))


func max_level() -> int:
	return int(DataDB.player_def.get("exp_curve", {}).get("max_level", 30))


## 경험치를 더하고 레벨업 메시지 목록을 돌려준다.
func add_exp(amount: int) -> Array:
	var msgs: Array = []
	player["exp"] = int(player["exp"]) + maxi(amount, 0)
	while int(player["level"]) < max_level() and int(player["exp"]) >= exp_to_next(int(player["level"])):
		player["exp"] = int(player["exp"]) - exp_to_next(int(player["level"]))
		msgs.append_array(_level_up())
	stats_changed.emit()
	return msgs


func _level_up() -> Array:
	var growth: Dictionary = DataDB.player_def.get("growth_per_level", {})
	player["level"] = int(player["level"]) + 1
	var parts: Array = []
	var labels := {"max_hp": "HP", "max_mp": "MP", "attack": "공격력", "defense": "방어력", "agility": "민첩성"}
	for key in labels:
		var g := int(growth.get(key, 0))
		if g > 0:
			player[key] = int(player[key]) + g
			parts.append("%s+%d" % [labels[key], g])
	player["hp"] = player["max_hp"]
	player["mp"] = player["max_mp"]
	var msgs: Array = ["레벨 업! %s의 레벨이 %d이(가) 되었다!" % [player["name"], player["level"]], " ".join(parts)]
	for nm in learn_skills_for_level(int(player["level"])):
		msgs.append("새 무공 『%s』을(를) 깨우쳤다!" % nm)
	return msgs


func heal_full() -> void:
	player["hp"] = player["max_hp"]
	player["mp"] = player["max_mp"]
	stats_changed.emit()


func set_hp_mp(hp: int, mp: int) -> void:
	player["hp"] = clampi(hp, 0, int(player["max_hp"]))
	player["mp"] = clampi(mp, 0, int(player["max_mp"]))
	stats_changed.emit()


# ------------------------------------------------------------------ 아이템
func add_item(item_id: String, count: int = 1) -> void:
	inventory[item_id] = item_count(item_id) + count
	inventory_changed.emit()


func remove_item(item_id: String, count: int = 1) -> bool:
	if item_count(item_id) < count:
		return false
	inventory[item_id] = item_count(item_id) - count
	if inventory[item_id] <= 0:
		inventory.erase(item_id)
	inventory_changed.emit()
	return true


func item_count(item_id: String) -> int:
	return int(inventory.get(item_id, 0))


## 필드/전투 공용 아이템 사용. 결과 메시지를 돌려준다 (실패 시 빈 문자열).
func use_item(item_id: String) -> String:
	var def: Dictionary = DataDB.items.get(item_id, {})
	if def.is_empty() or item_count(item_id) <= 0:
		return ""
	var amount := int(def.get("amount", 0))
	match def.get("type", ""):
		"heal_hp":
			var before := int(player["hp"])
			player["hp"] = mini(int(player["max_hp"]), before + amount)
			remove_item(item_id)
			stats_changed.emit()
			return "%s을(를) 사용했다. HP가 %d 회복되었다." % [def["name"], int(player["hp"]) - before]
		"heal_mp":
			var before_mp := int(player["mp"])
			player["mp"] = mini(int(player["max_mp"]), before_mp + amount)
			remove_item(item_id)
			stats_changed.emit()
			return "%s을(를) 사용했다. MP가 %d 회복되었다." % [def["name"], int(player["mp"]) - before_mp]
	return ""


# ------------------------------------------------------------------ 플래그 / 퀘스트
func set_flag(flag: String, value: bool = true) -> void:
	if value:
		flags[flag] = true
	else:
		flags.erase(flag)


func has_flag(flag: String) -> bool:
	return bool(flags.get(flag, false))


func set_quest(quest_id: String, state: String) -> void:
	quests[quest_id] = state
	quest_changed.emit()


func get_quest(quest_id: String) -> String:
	return str(quests.get(quest_id, ""))


# ------------------------------------------------------------------ 위치 / 장면 전환
func set_location(map_id: String, tile: Vector2i, new_facing: String = "down") -> void:
	current_map = map_id
	player_position = Vector2(tile.x * TILE + TILE / 2.0, tile.y * TILE + TILE / 2.0)
	facing = new_facing


func travel_to(map_id: String, tile: Vector2i, new_facing: String = "down") -> void:
	set_location(map_id, tile, new_facing)
	clear_input_locks()
	# 페이드 아웃 동안 이전 맵의 플레이어가 위치를 덮어쓰지 않도록 잠금 (새 맵 world.gd 가 해제)
	lock_input("transition")
	last_active_unix = int(Time.get_unix_time_from_system())
	SceneRouter.change_scene(WORLD_SCENE)


func start_battle(enemy_id: String, win_flag: String = "", npc_id: String = "") -> void:
	pending_battle = {
		"enemy": enemy_id,
		"win_flag": win_flag,
		"npc": npc_id,
		"return_map": current_map,
		"return_position": player_position,
		"return_facing": facing,
	}
	lock_input("battle")
	SceneRouter.change_scene(BATTLE_SCENE, true)


## 전투 종료 후 호출. result: "win" | "lose" | "flee"
func finish_battle(result: String) -> void:
	last_battle_result = {"result": result, "enemy": pending_battle.get("enemy", "")}
	if result == "win":
		var flag: String = pending_battle.get("win_flag", "")
		if flag != "":
			set_flag(flag)
		if pending_battle.get("enemy", "") == "bandit" and get_quest("first_training") == "active":
			set_quest("first_training", "cleared")
	if result == "lose":
		var cfg: Dictionary = DataDB.battle_config.get("defeat", {})
		var ratio := float(cfg.get("revive_hp_ratio", 0.5))
		player["hp"] = maxi(1, int(int(player["max_hp"]) * ratio))
		var tile: Array = cfg.get("return_tile", [15, 7])
		set_location(cfg.get("return_map", "cheongpung"), Vector2i(int(tile[0]), int(tile[1])), "down")
	else:
		current_map = pending_battle.get("return_map", current_map)
		player_position = pending_battle.get("return_position", player_position)
		facing = pending_battle.get("return_facing", facing)
	pending_battle = {}
	clear_input_locks()
	stats_changed.emit()
	SceneRouter.change_scene(WORLD_SCENE)


func return_to_title() -> void:
	in_game = false
	clear_input_locks()
	SceneRouter.change_scene(MENU_SCENE)


# ------------------------------------------------------------------ 직렬화
func to_dict() -> Dictionary:
	return {
		"player": player.duplicate(true),
		"skills": skills.duplicate(),
		"inventory": inventory.duplicate(true),
		"flags": flags.duplicate(true),
		"quests": quests.duplicate(true),
		"map": current_map,
		"position": [player_position.x, player_position.y],
		"facing": facing,
		"play_time": play_time,
		"equipped": equipped.duplicate(),
		"skill_levels": skill_levels.duplicate(true),
		"gear": gear.duplicate(true),
		"qi": qi,
		"notices": notices.duplicate(true),
		"last_active_unix": last_active_unix,
	}


## 저장 데이터를 검증한 뒤 적용한다. 잘못된 데이터면 상태를 바꾸지 않고 false.
func apply_dict(d: Dictionary) -> bool:
	if not validate_dict(d):
		return false
	var p: Dictionary = d["player"]
	var new_player := {}
	for key in ["level", "exp", "hp", "mp", "max_hp", "max_mp", "attack", "defense", "agility", "gold"]:
		new_player[key] = int(p[key])
	new_player["name"] = str(p.get("name", DataDB.player_def.get("name", "도윤")))
	new_player["max_hp"] = maxi(1, new_player["max_hp"])
	new_player["max_mp"] = maxi(0, new_player["max_mp"])
	new_player["hp"] = clampi(new_player["hp"], 1, new_player["max_hp"])
	new_player["mp"] = clampi(new_player["mp"], 0, new_player["max_mp"])
	player = new_player
	skills = []
	for s in d["skills"]:
		if DataDB.skills.has(str(s)):
			skills.append(str(s))
	if skills.is_empty():
		skills = DataDB.player_def.get("starting_skills", []).duplicate()
	inventory = {}
	for item_id in d["inventory"]:
		if DataDB.items.has(item_id) and int(d["inventory"][item_id]) > 0:
			inventory[item_id] = int(d["inventory"][item_id])
	flags = {}
	for f in d["flags"]:
		if bool(d["flags"][f]):
			flags[str(f)] = true
	quests = {}
	for q in d["quests"]:
		quests[str(q)] = str(d["quests"][q])
	current_map = d["map"]
	player_position = Vector2(float(d["position"][0]), float(d["position"][1]))
	facing = str(d.get("facing", "down"))
	if not facing in ["down", "up", "left", "right"]:
		facing = "down"
	play_time = float(d.get("play_time", 0.0))
	# v0.3 성장 데이터 (없으면 기본값 — 이전 저장 호환)
	learn_skills_for_level(int(player["level"]))
	skill_levels = {}
	var sl = d.get("skill_levels", {})
	if typeof(sl) == TYPE_DICTIONARY:
		for sid in sl:
			if DataDB.skills.has(str(sid)):
				skill_levels[str(sid)] = clampi(int(sl[sid]), 0, int(growth()["skill_upgrade"]["max_level"]))
	gear = {}
	var gd = d.get("gear", {})
	for gid in growth().get("gear", {}):
		var lv := 0
		if typeof(gd) == TYPE_DICTIONARY and gd.has(gid):
			lv = int(gd[gid])
		gear[gid] = clampi(lv, 0, int(growth()["gear"][gid]["max_level"]))
	qi = maxi(0, int(d.get("qi", 0)))
	equipped = []
	var eq = d.get("equipped", [])
	if typeof(eq) == TYPE_ARRAY:
		for sid in eq:
			if skills.has(str(sid)) and not equipped.has(str(sid)) and equipped.size() < slot_count():
				equipped.append(str(sid))
	if equipped.is_empty():
		_auto_equip()
	notices = {}
	var nt = d.get("notices", {})
	if typeof(nt) == TYPE_DICTIONARY:
		for k in nt:
			if bool(nt[k]):
				notices[str(k)] = true
	last_active_unix = int(d.get("last_active_unix", 0))
	compute_offline()
	last_active_unix = int(Time.get_unix_time_from_system())
	pending_battle = {}
	in_game = true
	clear_input_locks()
	stats_changed.emit()
	inventory_changed.emit()
	return true


func validate_dict(d: Variant) -> bool:
	if typeof(d) != TYPE_DICTIONARY:
		return false
	for key in ["player", "skills", "inventory", "flags", "quests", "map", "position"]:
		if not d.has(key):
			return false
	if typeof(d["player"]) != TYPE_DICTIONARY or typeof(d["skills"]) != TYPE_ARRAY:
		return false
	if typeof(d["inventory"]) != TYPE_DICTIONARY or typeof(d["flags"]) != TYPE_DICTIONARY:
		return false
	if typeof(d["quests"]) != TYPE_DICTIONARY:
		return false
	for key in ["level", "exp", "hp", "mp", "max_hp", "max_mp", "attack", "defense", "agility", "gold"]:
		var v = d["player"].get(key)
		if typeof(v) != TYPE_INT and typeof(v) != TYPE_FLOAT:
			return false
	if int(d["player"]["level"]) < 1:
		return false
	if typeof(d["map"]) != TYPE_STRING or not DataDB.has_map(d["map"]):
		return false
	var pos = d["position"]
	if typeof(pos) != TYPE_ARRAY or pos.size() != 2:
		return false
	for v in pos:
		if typeof(v) != TYPE_INT and typeof(v) != TYPE_FLOAT:
			return false
	return true


# ------------------------------------------------------------------ 성장: 무공 습득 / 장착
func growth() -> Dictionary:
	return DataDB.growth


func slot_count() -> int:
	return int(growth().get("skill_slots", 4))


## 현재 레벨까지 익힐 수 있는 무공을 습득하고 새로 익힌 무공 이름 목록을 돌려준다.
func learn_skills_for_level(level: int) -> Array:
	var learned: Array = []
	var ids := DataDB.skills.keys().filter(func(k): return not str(k).begins_with("_"))
	ids.sort_custom(func(a, b): return int(DataDB.skills[a].get("learn_level", 1)) < int(DataDB.skills[b].get("learn_level", 1)))
	for sid in ids:
		if str(sid).begins_with("_"):
			continue
		if int(DataDB.skills[sid].get("learn_level", 1)) <= level and not skills.has(sid):
			skills.append(sid)
			learned.append(DataDB.skills[sid].get("name", sid))
			if equipped.size() < slot_count():
				equipped.append(sid)
			set_notice("new_skill")
	return learned


func _auto_equip() -> void:
	equipped = []
	for sid in skills:
		if equipped.size() < slot_count():
			equipped.append(sid)


## 장착/해제 전환. 슬롯이 가득 차면 false. 마지막 1개는 해제 불가.
func toggle_equip(sid: String) -> bool:
	if equipped.has(sid):
		if equipped.size() <= 1:
			return false
		equipped.erase(sid)
		return true
	if not skills.has(sid) or equipped.size() >= slot_count():
		return false
	equipped.append(sid)
	return true


# ------------------------------------------------------------------ 성장: 강화
func skill_level(sid: String) -> int:
	return int(skill_levels.get(sid, 0))


## 다음 강화 비용(내공). 최대 단계면 -1
func skill_upgrade_cost(sid: String) -> int:
	var up: Dictionary = growth()["skill_upgrade"]
	var lv := skill_level(sid)
	if lv >= int(up["max_level"]):
		return -1
	return int(up["cost_qi"][lv])


func upgrade_skill(sid: String) -> String:
	var cost := skill_upgrade_cost(sid)
	if cost < 0 or qi < cost or not skills.has(sid):
		return ""
	qi -= cost
	skill_levels[sid] = skill_level(sid) + 1
	stats_changed.emit()
	return "『%s』 %d성 달성!" % [DataDB.skills[sid]["name"], skill_level(sid)]


func gear_level(gid: String) -> int:
	return int(gear.get(gid, 0))


func gear_cost(gid: String) -> int:
	var lv := gear_level(gid)
	var def: Dictionary = growth()["gear"].get(gid, {})
	var costs: Array = growth()["gear_cost_gold"]
	if def.is_empty() or lv >= int(def["max_level"]) or lv >= costs.size():
		return -1
	return int(costs[lv])


func upgrade_gear(gid: String) -> String:
	var cost := gear_cost(gid)
	if cost < 0 or int(player["gold"]) < cost:
		return ""
	player["gold"] = int(player["gold"]) - cost
	gear[gid] = gear_level(gid) + 1
	stats_changed.emit()
	var def: Dictionary = growth()["gear"][gid]
	return "%s +%d 강화 성공!" % [def["name"], gear_level(gid)]


## 장비 보너스를 더한 실제 능력치
func effective_stats() -> Dictionary:
	var s := player.duplicate()
	for gid in growth().get("gear", {}):
		var def: Dictionary = growth()["gear"][gid]
		s[def["stat"]] = int(s[def["stat"]]) + gear_level(gid) * int(def["per_level"])
	return s


func add_qi(amount: int) -> void:
	qi += maxi(0, amount)
	stats_changed.emit()


func add_gold(amount: int) -> void:
	player["gold"] = maxi(0, int(player["gold"]) + amount)
	stats_changed.emit()


# ------------------------------------------------------------------ 폐관수련 (방치 보상)
## last_active_unix 이후 지난 시간으로 보상을 계산해 offline_pending 에 쌓는다.
func compute_offline(now_unix: int = -1) -> void:
	var cfg: Dictionary = growth().get("offline", {})
	if now_unix < 0:
		now_unix = int(Time.get_unix_time_from_system())
	if last_active_unix <= 0 or now_unix <= last_active_unix:
		return
	var minutes := mini((now_unix - last_active_unix) / 60, int(cfg.get("max_hours", 8)) * 60)
	minutes += int(offline_pending.get("minutes", 0))
	minutes = mini(minutes, int(cfg.get("max_hours", 8)) * 60)
	if minutes < int(cfg.get("min_minutes", 5)):
		return
	var lvl := int(player.get("level", 1))
	var q := int(minutes * float(cfg.get("qi_per_minute", 0.5)) * (1.0 + float(cfg.get("qi_level_bonus", 0.1)) * (lvl - 1)))
	var g := int(minutes * float(cfg.get("gold_per_minute", 0.2)))
	offline_pending = {"minutes": minutes, "qi": q, "gold": g}
	set_notice("offline")


func has_offline_reward() -> bool:
	return int(offline_pending.get("minutes", 0)) > 0


func claim_offline() -> String:
	if not has_offline_reward():
		return ""
	var m := int(offline_pending["minutes"])
	var q := int(offline_pending["qi"])
	var g := int(offline_pending["gold"])
	add_qi(q)
	add_gold(g)
	offline_pending = {}
	clear_notice("offline")
	return "폐관수련 %d시간 %d분 — 내공 +%d, %d냥 획득!" % [m / 60, m % 60, q, g]


# ------------------------------------------------------------------ 알림 (빨간 점)
func set_notice(key: String) -> void:
	notices[key] = true
	notices_changed.emit()


func clear_notice(key: String) -> void:
	if notices.erase(key):
		notices_changed.emit()


func has_notice(key: String = "") -> bool:
	if key == "":
		return not notices.is_empty()
	return bool(notices.get(key, false))


# ------------------------------------------------------------------ 다음 할 일 안내
## {"text": 안내문, "map": 목표 맵, "tile": Vector2i 또는 null}
func guide() -> Dictionary:
	if not has_flag("talked_master"):
		return _goal("청풍관 앞 사범 백운에게 말을 걸자", "cheongpung", Vector2i(17, 5))
	if get_quest("first_training") == "active" and not has_flag("bandit_defeated"):
		return _goal("남쪽 수련장의 산적을 혼내주자", "training_ground", Vector2i(10, 6))
	if has_flag("bandit_defeated") and not has_flag("master_reward"):
		return _goal("사범 백운에게 산적 소식을 알리자", "cheongpung", Vector2i(17, 5))
	if not has_flag("merchant_gift"):
		return _goal("만복상회 상인 만복에게 들러 보자", "cheongpung", Vector2i(23, 7))
	if not has_flag("fragment_found"):
		return _goal("마을 연못 근처를 살펴보자", "cheongpung", Vector2i(6, 15))
	if int(player["level"]) < 4:
		return _goal("허수아비 수련으로 Lv.4 청풍각을 익히자", "training_ground", Vector2i(5, 5))
	return _goal("메뉴 › 무공에서 무공을 강화하자", "", null)


func _goal(text: String, map_id: String, tile) -> Dictionary:
	return {"text": text, "map": map_id, "tile": tile}


## 현재 맵 기준 안내 화살표가 가리킬 픽셀 좌표 (없으면 null)
func guide_target_position() -> Variant:
	var g := guide()
	if g["tile"] == null or g["map"] == "":
		return null
	if g["map"] == current_map:
		return MapBuilder.tile_center(g["tile"])
	for ex in DataDB.get_map(current_map).get("exits", []):
		if ex["to"] == g["map"]:
			var r: Array = ex["rect"]
			return MapBuilder.tile_center(Vector2i(int(r[0]), int(r[1])))
	return null
