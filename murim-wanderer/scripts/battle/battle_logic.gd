class_name BattleLogic
extends RefCounted
## 카드(초식) 턴제 전투 규칙 — UI 와 분리된 순수 로직 (자동 테스트 대상).
##
## 흐름: start() → [플레이어 턴: 기 3, 카드 5장, 카드 사용…, end_player_turn()]
##        → enemy_turn() → start_player_turn() → …
## - 적은 다음 행동(의도)을 미리 보여준다: e["intent"]
## - 호신(block)은 피해를 먼저 막고, 자기 턴 시작 시 사라진다
## - 상태: 기세(피해 +), 허점(받는 피해 x1.5), 위축(주는 피해 x0.75), 반격(맞으면 되돌려줌)
## 이벤트: {"text", "target": "player"|"enemy"|"", "damage", "heal", "block", "fx"}

enum State { ONGOING, WON, LOST, FLED }

var state: State = State.ONGOING
var p: Dictionary = {}
var e: Dictionary = {}
var enemy_id := ""
var cfg: Dictionary = {}
var cards_db: Dictionary = {}
var skill_levels: Dictionary = {}
var rng := RandomNumberGenerator.new()
var draw_pile: Array = []
var hand: Array = []
var discard: Array = []
var charge_mult := 1.0
var turn := 0


func setup(player_stats: Dictionary, p_enemy_id: String, enemy_def: Dictionary, config: Dictionary,
		p_cards: Dictionary, deck: Array, seed_value: int = -1, p_skill_levels: Dictionary = {}) -> void:
	enemy_id = p_enemy_id
	cfg = config
	cards_db = p_cards
	skill_levels = p_skill_levels
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
		"block": 0, "strength": 0, "weak": 0, "vulnerable": 0, "thorns": 0,
		"energy": 0, "max_energy": int(_c("energy", 3)),
	}
	e = {
		"name": str(enemy_def.get("name", "적")),
		"hp": int(enemy_def.get("max_hp", 10)), "max_hp": int(enemy_def.get("max_hp", 10)),
		"agility": int(enemy_def.get("agility", 1)),
		"exp": int(enemy_def.get("exp", 0)), "gold": int(enemy_def.get("gold", 0)), "qi": int(enemy_def.get("qi", 0)),
		"actions": enemy_def.get("actions", []),
		"block": 0, "strength": 0, "weak": 0, "vulnerable": 0, "intent": {},
	}
	draw_pile = deck.duplicate()
	_shuffle(draw_pile)
	hand = []
	discard = []
	state = State.ONGOING


func _c(key: String, fallback: Variant) -> Variant:
	return cfg.get("cards", {}).get(key, fallback)


func _shuffle(arr: Array) -> void:
	for i in range(arr.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp = arr[i]
		arr[i] = arr[j]
		arr[j] = tmp


# ------------------------------------------------------------------ 카드 수치
## 카드의 실제 수치(강화·능력치·기세 반영). 화면 표시와 계산에 같이 쓴다.
func card_stats(card_id: String) -> Dictionary:
	var c: Dictionary = cards_db.get(card_id, {})
	var lv := int(skill_levels.get(str(c.get("skill", "")), 0))
	var up := int(c.get("upgrade", 0)) * lv
	var atk_bonus := (int(p.get("attack", 12)) - int(_c("base_attack", 12))) / int(_c("atk_per_bonus", 3))
	var def_bonus := (int(p.get("defense", 6)) - int(_c("base_defense", 6))) / int(_c("def_per_bonus", 3))
	var out := {
		"name": str(c.get("name", card_id)), "type": str(c.get("type", "skill")),
		"cost": int(c.get("cost", 1)), "mp": int(c.get("mp", 0)), "hits": int(c.get("hits", 1)),
		"damage": 0, "block": 0, "icon": str(c.get("icon", "skill_fist")),
	}
	if c.has("damage"):
		out["damage"] = maxi(0, int(c["damage"]) + up + maxi(0, atk_bonus) + int(p.get("strength", 0)))
	if c.has("block"):
		out["block"] = maxi(0, int(c["block"]) + up + maxi(0, def_bonus))
	out["restore_mp"] = int(c.get("restore_mp", 0)) + (up if c.has("restore_mp") else 0)
	var desc := str(c.get("desc", ""))
	out["desc"] = desc.format({"dmg": out["damage"], "blk": out["block"], "mp": out["restore_mp"]})
	return out


func can_play(index: int) -> bool:
	if state != State.ONGOING or index < 0 or index >= hand.size():
		return false
	var s := card_stats(hand[index])
	return int(p["energy"]) >= s["cost"] and int(p["mp"]) >= s["mp"]


# ------------------------------------------------------------------ 턴 진행
func start() -> Array:
	turn = 0
	return start_player_turn()


func start_player_turn() -> Array:
	turn += 1
	p["block"] = 0
	p["thorns"] = 0
	p["energy"] = int(p["max_energy"])
	var events: Array = []
	draw(int(_c("hand_size", 5)))
	choose_intent()
	events.append(_ev("%d턴 — 기 %d, 카드 %d장" % [turn, p["energy"], hand.size()], "", 0, 0, "turn"))
	return events


func draw(n: int) -> int:
	var drawn := 0
	for i in n:
		if hand.size() >= int(_c("max_hand", 10)):
			break
		if draw_pile.is_empty():
			if discard.is_empty():
				break
			draw_pile = discard.duplicate()
			discard.clear()
			_shuffle(draw_pile)
		hand.append(draw_pile.pop_back())
		drawn += 1
	return drawn


func end_player_turn() -> void:
	discard.append_array(hand)
	hand.clear()
	_tick(p)


## 상태 지속 턴 감소
func _tick(who: Dictionary) -> void:
	for k in ["weak", "vulnerable"]:
		who[k] = maxi(0, int(who[k]) - 1)


# ------------------------------------------------------------------ 카드 사용
## timing: 타이밍 입력 배율 (완벽 = 1.3)
func play_card(index: int, timing: float = 1.0) -> Array:
	if not can_play(index):
		return [_ev("기나 MP가 부족하다!", "", 0, 0, "invalid")]
	var card_id: String = hand[index]
	var c: Dictionary = cards_db.get(card_id, {})
	var s := card_stats(card_id)
	p["energy"] = int(p["energy"]) - s["cost"]
	p["mp"] = int(p["mp"]) - s["mp"]
	hand.remove_at(index)
	if str(c.get("type", "")) != "power":
		discard.append(card_id)
	var events: Array = [_ev("%s의 %s!" % [p["name"], s["name"]], "", 0, 0, "cast")]
	if s["damage"] > 0:
		var mult := charge_mult * timing
		charge_mult = 1.0
		for i in s["hits"]:
			if int(e["hp"]) <= 0:
				break
			events.append(_hit_enemy(s["damage"], mult))
	if s["block"] > 0:
		p["block"] = int(p["block"]) + s["block"]
		events.append(_ev("호신 +%d (총 %d)" % [s["block"], p["block"]], "player", 0, 0, "block"))
	if int(s["restore_mp"]) > 0:
		var before := int(p["mp"])
		p["mp"] = mini(int(p["max_mp"]), before + int(s["restore_mp"]))
		events.append(_ev("내공이 차오른다. MP +%d" % (int(p["mp"]) - before), "player", 0, int(p["mp"]) - before, "heal"))
	if c.has("charge"):
		charge_mult = float(c["charge"])
		events.append(_ev("기가 모인다! 다음 공격 피해 %d배." % int(charge_mult), "player", 0, 0, "buff"))
	if c.has("vulnerable") and int(e["hp"]) > 0:
		e["vulnerable"] = int(e["vulnerable"]) + int(c["vulnerable"])
		events.append(_ev("%s에게 허점이 생겼다! (%d턴)" % [e["name"], e["vulnerable"]], "enemy", 0, 0, "debuff"))
	if c.has("weak") and int(e["hp"]) > 0:
		e["weak"] = int(e["weak"]) + int(c["weak"])
		events.append(_ev("%s 위축되었다! (%d턴)" % [KText.josa(e["name"], "이/가"), e["weak"]], "enemy", 0, 0, "debuff"))
	if c.has("thorns"):
		p["thorns"] = int(p["thorns"]) + int(c["thorns"])
	if c.has("strength"):
		p["strength"] = int(p["strength"]) + int(c["strength"])
		events.append(_ev("투지가 끓어오른다! 기세 +%d" % int(c["strength"]), "player", 0, 0, "buff"))
	if c.has("draw"):
		var n := draw(int(c["draw"]))
		events.append(_ev("카드 %d장을 뽑았다." % n, "", 0, 0, "draw"))
	_check_enemy_down(events)
	return events


## 적에게 피해 (기세는 card_stats 에서 이미 반영). 호신 먼저 깎음.
func _hit_enemy(base: int, mult: float) -> Dictionary:
	var dmg := float(base) * mult
	if int(p["weak"]) > 0:
		dmg *= float(_c("weak_mult", 0.75))
	if int(e["vulnerable"]) > 0:
		dmg *= float(_c("vulnerable_mult", 1.5))
	var total := int(floor(dmg))
	var absorbed := mini(int(e["block"]), total)
	e["block"] = int(e["block"]) - absorbed
	var through := total - absorbed
	e["hp"] = maxi(0, int(e["hp"]) - through)
	var txt := "%s에게 %d의 피해!" % [e["name"], through] + (" (호신 %d 막음)" % absorbed if absorbed > 0 else "")
	var ev := _ev(txt, "enemy", through, 0, "crit" if mult > 1.0 else "hit")
	ev["block"] = absorbed
	return ev


func _check_enemy_down(events: Array) -> void:
	if int(e["hp"]) <= 0 and state == State.ONGOING:
		state = State.WON
		events.append(_ev("%s 쓰러뜨렸다!" % KText.josa(e["name"], "을/를"), "enemy", 0, 0, "down"))


func use_item(item_def: Dictionary) -> Array:
	var amount := int(item_def.get("amount", 0))
	var item_name := str(item_def.get("name", "아이템"))
	match item_def.get("type", ""):
		"heal_hp":
			var before := int(p["hp"])
			p["hp"] = mini(int(p["max_hp"]), before + amount)
			return [_ev("%s 사용했다! HP %d 회복." % [KText.josa(item_name, "을/를"), int(p["hp"]) - before], "player", 0, int(p["hp"]) - before, "heal")]
		"heal_mp":
			var before_mp := int(p["mp"])
			p["mp"] = mini(int(p["max_mp"]), before_mp + amount)
			return [_ev("%s 사용했다! MP %d 회복." % [KText.josa(item_name, "을/를"), int(p["mp"]) - before_mp], "player", 0, 0, "heal")]
	return [_ev("지금은 쓸 수 없다.", "", 0, 0, "invalid")]


func flee_chance() -> float:
	var f: Dictionary = cfg.get("flee", {})
	var ch := float(f.get("base_chance", 0.5)) + float(int(p["agility"]) - int(e["agility"])) * float(f.get("agility_factor", 0.05))
	return clampf(ch, float(f.get("min_chance", 0.1)), float(f.get("max_chance", 0.95)))


func try_flee() -> Array:
	if rng.randf() < flee_chance():
		state = State.FLED
		return [_ev("%s 걸음아 날 살려라 도망쳤다!" % KText.josa(p["name"], "은/는"), "", 0, 0, "flee")]
	return [_ev("도망치려 했지만 발이 꼬였다! (턴 종료)", "", 0, 0, "fail")]


# ------------------------------------------------------------------ 적
func choose_intent() -> Dictionary:
	var actions: Array = e["actions"]
	if actions.is_empty():
		e["intent"] = {"type": "attack", "damage": 5, "text": "%s의 공격!" % e["name"]}
		return e["intent"]
	var total := 0
	for a in actions:
		total += int(a.get("weight", 1))
	var roll := rng.randi_range(1, maxi(total, 1))
	for a in actions:
		roll -= int(a.get("weight", 1))
		if roll <= 0:
			e["intent"] = a
			return a
	e["intent"] = actions[-1]
	return e["intent"]


## 의도 표시용 예상 피해 (기세·위축·허점 반영, 호신은 미반영)
func intent_damage() -> int:
	var a: Dictionary = e["intent"]
	if a.get("type", "") != "attack":
		return 0
	var dmg := float(int(a.get("damage", 0)) + int(e["strength"]))
	if int(e["weak"]) > 0:
		dmg *= float(_c("weak_mult", 0.75))
	if int(p["vulnerable"]) > 0:
		dmg *= float(_c("vulnerable_mult", 1.5))
	return int(floor(dmg))


## 적이 의도대로 행동. parried: 타이밍 받아치기 성공 (피해 x parry_mult)
func enemy_turn(parried: bool = false) -> Array:
	if state != State.ONGOING:
		return []
	e["block"] = 0
	var a: Dictionary = e["intent"]
	var events: Array = [_ev(str(a.get("text", "%s의 공격!" % e["name"])), "", 0, 0, "enemy_cast")]
	match a.get("type", "attack"):
		"attack":
			var dmg := float(intent_damage())
			if parried:
				dmg *= float(cfg.get("timing", {}).get("parry_mult", 0.4))
			var total := int(floor(dmg))
			var absorbed := mini(int(p["block"]), total)
			p["block"] = int(p["block"]) - absorbed
			var through := total - absorbed
			p["hp"] = maxi(0, int(p["hp"]) - through)
			var note := ""
			if parried:
				note += " (받아쳤다!)"
			if absorbed > 0:
				note += " (호신 %d 막음)" % absorbed
			var ev := _ev("%s %d의 피해를 입었다!%s" % [KText.josa(p["name"], "은/는"), through, note], "player", through, 0, "parry" if parried else "hit")
			ev["block"] = absorbed
			events.append(ev)
			if int(p["thorns"]) > 0 and int(e["hp"]) > 0:
				e["hp"] = maxi(0, int(e["hp"]) - int(p["thorns"]))
				events.append(_ev("반격! %s에게 %d의 피해!" % [e["name"], p["thorns"]], "enemy", int(p["thorns"]), 0, "hit"))
				_check_enemy_down(events)
			if int(p["hp"]) <= 0:
				state = State.LOST
				events.append(_ev("%s 쓰러졌다..." % KText.josa(p["name"], "은/는"), "player", 0, 0, "down"))
		"block":
			e["block"] = int(a.get("block", 0))
		"buff":
			e["strength"] = int(e["strength"]) + int(a.get("strength", 0))
	_tick(e)
	return events


# ------------------------------------------------------------------ 자동 전투
## 이번에 낼 카드의 손패 인덱스 (-1 = 턴 종료)
func auto_pick() -> int:
	var incoming := intent_damage()
	var best := -1
	var best_score := 0.0
	for i in hand.size():
		if not can_play(i):
			continue
		var s := card_stats(hand[i])
		var c: Dictionary = cards_db.get(hand[i], {})
		var score := 0.0
		var dmg := float(s["damage"] * s["hits"])
		if dmg > 0:
			score = dmg * charge_mult
			if dmg * charge_mult >= int(e["hp"]) + int(e["block"]):
				score += 100.0  # 마무리 가능하면 최우선
		if s["block"] > 0:
			var need := maxi(0, incoming - int(p["block"]))
			score = maxf(score, minf(float(s["block"]), float(need)) * (1.6 if float(p["hp"]) / float(p["max_hp"]) < 0.5 else 1.0))
		if c.has("charge") and charge_mult <= 1.0:
			score = 9.0 if _has_attack_after(i) else 0.0
		if c.has("strength"):
			score = 8.0
		if c.has("draw") and s["cost"] == 0:
			score = maxf(score, 5.0)
		if int(s["restore_mp"]) > 0 and int(p["mp"]) < int(p["max_mp"]) / 2:
			score = maxf(score, 6.0)
		score -= s["cost"] * 0.5
		if score > best_score:
			best_score = score
			best = i
	return best


func _has_attack_after(skip: int) -> bool:
	for i in hand.size():
		if i == skip:
			continue
		var s := card_stats(hand[i])
		if int(s["damage"]) > 0 and int(p["energy"]) - 1 >= int(s["cost"]):
			return true
	return false


# ------------------------------------------------------------------ 보상
## 전투 보상 후보 카드 (서로 다른 n장)
func reward_choices(n: int = 3) -> Array:
	var pool: Array = []
	for id in cards_db:
		if str(id).begins_with("_"):
			continue
		if str(cards_db[id].get("pool", "")) == "reward":
			pool.append(id)
	_shuffle(pool)
	return pool.slice(0, mini(n, pool.size()))


func _ev(text: String, target: String, damage: int, heal: int, fx: String) -> Dictionary:
	return {"text": text, "target": target, "damage": damage, "heal": heal, "block": 0, "fx": fx}
