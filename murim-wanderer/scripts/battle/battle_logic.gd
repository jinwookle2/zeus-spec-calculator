class_name BattleLogic
extends RefCounted
## 턴제 전투 규칙 (UI 와 분리된 순수 로직 → 자동 테스트 가능).
## 각 행동 함수는 화면에 순서대로 보여줄 이벤트 목록을 돌려준다.
## 이벤트: {"text": String, "target": "player"|"enemy"|"", "damage": int, "heal": int, "fx": String}

enum State { ONGOING, WON, LOST, FLED }

var state: State = State.ONGOING
var p: Dictionary = {}  # 플레이어 전투 능력치 사본
var e: Dictionary = {}  # 적 능력치
var enemy_id: String = ""
var cfg: Dictionary = {}
var skills_db: Dictionary = {}
var rng := RandomNumberGenerator.new()
var player_guarding := false
var guard_override := -1.0  # 철벽세 등 특수 방어 배율 (이번 적 턴 한정)
var enemy_guarding := false
var charge_mult := 1.0
var turn := 1
var skill_levels: Dictionary = {}
var growth_cfg: Dictionary = {}


func setup(player_stats: Dictionary, p_enemy_id: String, enemy_def: Dictionary, config: Dictionary, skills: Dictionary, seed_value: int = -1, p_skill_levels: Dictionary = {}, p_growth: Dictionary = {}) -> void:
	enemy_id = p_enemy_id
	skill_levels = p_skill_levels
	growth_cfg = p_growth
	cfg = config
	skills_db = skills
	if seed_value >= 0:
		rng.seed = seed_value
	else:
		rng.randomize()
	p = {
		"name": str(player_stats.get("name", "도윤")),
		"hp": int(player_stats["hp"]), "max_hp": int(player_stats["max_hp"]),
		"mp": int(player_stats["mp"]), "max_mp": int(player_stats["max_mp"]),
		"attack": int(player_stats["attack"]), "defense": int(player_stats["defense"]),
		"agility": int(player_stats["agility"]),
	}
	e = {
		"name": str(enemy_def.get("name", "적")),
		"hp": int(enemy_def.get("max_hp", 10)), "max_hp": int(enemy_def.get("max_hp", 10)),
		"mp": int(enemy_def.get("max_mp", 0)), "max_mp": int(enemy_def.get("max_mp", 0)),
		"attack": int(enemy_def.get("attack", 5)), "defense": int(enemy_def.get("defense", 0)),
		"agility": int(enemy_def.get("agility", 1)),
		"exp": int(enemy_def.get("exp", 0)), "gold": int(enemy_def.get("gold", 0)), "qi": int(enemy_def.get("qi", 0)),
		"actions": enemy_def.get("actions", []),
	}
	state = State.ONGOING


# ------------------------------------------------------------------ 피해 계산
## 피해 = max(최소, (공격*위력 - 방어*계수) * 난수) * 치명타 * 배율 * (방어 시 감소)
func calc_damage(atk: int, def: int, power: float, defender_guarding: bool, mult: float = 1.0, guard_mult: float = -1.0) -> Dictionary:
	var d: Dictionary = cfg.get("damage", {})
	var min_damage := int(d.get("min_damage", 1))
	var raw := float(atk) * power - float(def) * float(d.get("defense_factor", 0.5))
	raw *= rng.randf_range(float(d.get("variance_min", 0.85)), float(d.get("variance_max", 1.15)))
	var crit := rng.randf() < float(d.get("crit_chance", 0.08))
	var dmg := maxf(raw, float(min_damage))
	if crit:
		dmg *= float(d.get("crit_multiplier", 1.5))
	dmg *= mult
	if defender_guarding:
		dmg *= guard_mult if guard_mult >= 0.0 else float(d.get("guard_multiplier", 0.5))
	return {"amount": maxi(min_damage, int(round(dmg))), "crit": crit}


# ------------------------------------------------------------------ 무공 강화 반영
func _lv(skill_id: String) -> int:
	return int(skill_levels.get(skill_id, 0))


func _up(key: String, fallback: float) -> float:
	return float(growth_cfg.get("skill_upgrade", {}).get(key, fallback))


## 강화 단계를 반영한 위력
func skill_power(skill_id: String) -> float:
	var s: Dictionary = skills_db.get(skill_id, {})
	return float(s.get("power", 1.0)) * (1.0 + _up("power_per_level", 0.12) * _lv(skill_id))


func skill_buff(skill_id: String) -> float:
	var s: Dictionary = skills_db.get(skill_id, {})
	return float(s.get("buff_multiplier", 1.8)) + _up("buff_per_level", 0.1) * _lv(skill_id)


func skill_heal(skill_id: String) -> int:
	var s: Dictionary = skills_db.get(skill_id, {})
	return int(s.get("amount", 0)) + int(_up("heal_per_level", 2)) * _lv(skill_id)


# ------------------------------------------------------------------ 플레이어 행동
func player_attack() -> Array:
	return player_skill("basic_fist")


func can_use_skill(skill_id: String) -> bool:
	var s: Dictionary = skills_db.get(skill_id, {})
	return not s.is_empty() and int(p["mp"]) >= int(s.get("mp_cost", 0))


## timing: 타이밍 입력 배율 (완벽 = timing.perfect_mult, 보통 1.0)
func player_skill(skill_id: String, timing: float = 1.0) -> Array:
	var s: Dictionary = skills_db.get(skill_id, {})
	if s.is_empty():
		return [_ev("알 수 없는 무술이다.", "", 0, 0, "invalid")]
	if not can_use_skill(skill_id):
		return [_ev("MP가 부족하다!", "", 0, 0, "invalid")]
	player_guarding = false
	p["mp"] = int(p["mp"]) - int(s.get("mp_cost", 0))
	var events: Array = []
	events.append(_ev(str(s.get("use_text", "{user}의 %s!" % s.get("name", ""))).format({"user": p["name"]}), "", 0, 0, "cast"))
	match s.get("type", "attack"):
		"attack":
			var hits := int(s.get("hits", 1))
			var mult := charge_mult * timing
			charge_mult = 1.0
			for i in hits:
				if int(e["hp"]) <= 0:
					break
				var r := calc_damage(int(p["attack"]), int(e["defense"]), skill_power(skill_id), enemy_guarding, mult)
				e["hp"] = maxi(0, int(e["hp"]) - int(r["amount"]))
				var prefix := "회심의 일격! " if r["crit"] else ""
				var text := "%s%s에게 %d의 피해!" % [prefix, e["name"], r["amount"]]
				events.append(_ev(text, "enemy", int(r["amount"]), 0, "crit" if r["crit"] else "hit"))
			_check_enemy_down(events)
		"buff":
			charge_mult = skill_buff(skill_id)
			events.append(_ev("기가 모인다! 다음 공격이 강해진다.", "player", 0, 0, "buff"))
		"heal_mp":
			var before := int(p["mp"])
			p["mp"] = mini(int(p["max_mp"]), before + skill_heal(skill_id))
			player_guarding = true
			events.append(_ev("내공이 차오른다. MP %d 회복." % (int(p["mp"]) - before), "player", 0, int(p["mp"]) - before, "heal"))
		"guard":
			player_guarding = true
			guard_override = float(s.get("guard_multiplier", 0.25))
			events.append(_ev("바위처럼 버틴다! 받는 피해가 크게 줄어든다.", "player", 0, 0, "guard"))
	return events


func player_guard() -> Array:
	player_guarding = true
	return [_ev("%s 방어 자세를 취했다." % KText.josa(p["name"], "은/는"), "player", 0, 0, "guard")]


## 아이템 효과만 적용 (소지 수량 차감은 호출 측에서).
func player_item(item_def: Dictionary) -> Array:
	player_guarding = false
	var amount := int(item_def.get("amount", 0))
	var name := str(item_def.get("name", "아이템"))
	match item_def.get("type", ""):
		"heal_hp":
			var before := int(p["hp"])
			p["hp"] = mini(int(p["max_hp"]), before + amount)
			return [_ev("%s 사용했다! HP %d 회복." % [KText.josa(name, "을/를"), int(p["hp"]) - before], "player", 0, int(p["hp"]) - before, "heal")]
		"heal_mp":
			var before_mp := int(p["mp"])
			p["mp"] = mini(int(p["max_mp"]), before_mp + amount)
			return [_ev("%s 사용했다! MP %d 회복." % [KText.josa(name, "을/를"), int(p["mp"]) - before_mp], "player", 0, 0, "heal")]
	return [_ev("지금은 쓸 수 없다.", "", 0, 0, "invalid")]


func flee_chance() -> float:
	var f: Dictionary = cfg.get("flee", {})
	var c := float(f.get("base_chance", 0.5)) + float(int(p["agility"]) - int(e["agility"])) * float(f.get("agility_factor", 0.05))
	return clampf(c, float(f.get("min_chance", 0.1)), float(f.get("max_chance", 0.95)))


func player_flee() -> Array:
	player_guarding = false
	if rng.randf() < flee_chance():
		state = State.FLED
		return [_ev("%s 걸음아 날 살려라 도망쳤다!" % KText.josa(p["name"], "은/는"), "", 0, 0, "flee")]
	return [_ev("도망치려 했지만 발이 꼬였다!", "", 0, 0, "fail")]


# ------------------------------------------------------------------ 적 행동
func choose_enemy_action() -> Dictionary:
	var actions: Array = e["actions"]
	if actions.is_empty():
		return {"type": "attack", "power": 1.0, "text": "%s의 공격!" % e["name"]}
	var total := 0
	for a in actions:
		total += int(a.get("weight", 1))
	var roll := rng.randi_range(1, maxi(total, 1))
	for a in actions:
		roll -= int(a.get("weight", 1))
		if roll <= 0:
			return a
	return actions[-1]


## parried: 플레이어가 적의 공격 타이밍에 맞춰 받아쳤는지 (받는 피해 감소)
func enemy_turn(forced_action: Dictionary = {}, parried: bool = false) -> Array:
	if state != State.ONGOING:
		return []
	enemy_guarding = false
	var a: Dictionary = forced_action if not forced_action.is_empty() else choose_enemy_action()
	var events: Array = []
	events.append(_ev(str(a.get("text", "%s의 공격!" % e["name"])), "", 0, 0, "enemy_cast"))
	match a.get("type", "attack"):
		"attack":
			var pm := float(cfg.get("timing", {}).get("parry_mult", 0.4)) if parried else 1.0
			var r := calc_damage(int(e["attack"]), int(p["defense"]), float(a.get("power", 1.0)), player_guarding, pm, guard_override if player_guarding else -1.0)
			p["hp"] = maxi(0, int(p["hp"]) - int(r["amount"]))
			var prefix := "아픈 곳을 맞았다! " if r["crit"] else ""
			var guard_txt := " (받아쳤다!)" if parried else (" (방어!)" if player_guarding else "")
			events.append(_ev("%s%s %d의 피해를 입었다!%s" % [prefix, KText.josa(p["name"], "은/는"), r["amount"], guard_txt], "player", int(r["amount"]), 0, "parry" if parried else ("crit" if r["crit"] else "hit")))
			if int(p["hp"]) <= 0:
				state = State.LOST
				events.append(_ev("%s 쓰러졌다..." % KText.josa(p["name"], "은/는"), "player", 0, 0, "down"))
		"guard":
			enemy_guarding = true
		"idle":
			pass
	guard_override = -1.0
	turn += 1
	return events


func _check_enemy_down(events: Array) -> void:
	if int(e["hp"]) <= 0:
		state = State.WON
		events.append(_ev("%s 쓰러뜨렸다!" % KText.josa(e["name"], "을/를"), "enemy", 0, 0, "down"))


func _ev(text: String, target: String, damage: int, heal: int, fx: String) -> Dictionary:
	return {"text": text, "target": target, "damage": damage, "heal": heal, "fx": fx}


# ------------------------------------------------------------------ 자동 전투 판단
## 자동 전투가 고를 행동: {"kind": "skill"|"item"|"guard", "id": String}
## 우선순위: 위급하면 약초 → MP 부족하면 호흡 → (여유 있으면) 기합 → 가장 센 공격 무공
func auto_choose(equipped: Array, herb_count: int) -> Dictionary:
	var hp_ratio := float(p["hp"]) / maxf(1.0, float(p["max_hp"]))
	if hp_ratio < 0.35 and herb_count > 0:
		return {"kind": "item", "id": "herb"}
	var best := "basic_fist"
	var best_score := 0.0
	for sid in equipped:
		var s: Dictionary = skills_db.get(sid, {})
		if s.get("type", "") == "attack" and can_use_skill(sid):
			var score := skill_power(sid) * int(s.get("hits", 1))
			if score > best_score:
				best_score = score
				best = sid
	if charge_mult <= 1.0 and equipped.has("kihap") and int(e["hp"]) > int(e["max_hp"]) / 3:
		var kihap_cost := int(skills_db.get("kihap", {}).get("mp_cost", 3))
		var best_cost := int(skills_db.get(best, {}).get("mp_cost", 0))
		if int(p["mp"]) >= kihap_cost + best_cost and best != "basic_fist":
			return {"kind": "skill", "id": "kihap"}
	if best == "basic_fist" and equipped.has("breathing") and int(p["mp"]) < int(p["max_mp"]) / 3:
		return {"kind": "skill", "id": "breathing"}
	return {"kind": "skill", "id": best}
