extends Node
## 진행 중인 게임의 모든 상태(능력치, 아이템, 플래그, 퀘스트, 위치)를 보관하는 싱글턴.
## 저장/불러오기는 to_dict()/apply_dict() 를 통해 SaveManager 가 담당한다.

signal stats_changed
signal inventory_changed
signal quest_changed

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

var _input_locks: Dictionary = {}


func _process(delta: float) -> void:
	if in_game:
		play_time += delta


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
	skills = def.get("starting_skills", []).duplicate()
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
	return ["레벨 업! %s의 레벨이 %d이(가) 되었다!" % [player["name"], player["level"]], " ".join(parts)]


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
