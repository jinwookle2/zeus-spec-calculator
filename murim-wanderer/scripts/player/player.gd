extends CharacterBody2D
## 플레이어(도윤): 4방향 이동, 걷기 애니메이션, 충돌, 상호작용.

signal interacted(target: Node)

@export var speed: float = 140.0
@export var interact_reach: float = 24.0
@export var interact_tolerance: float = 20.0

var facing: String = "down"
var _axis_started := {"x": 0, "y": 0}
var _prev_axis := Vector2.ZERO
var _interact_cooldown := 0.0

@onready var sprite: AnimatedSprite2D = $Sprite


func _ready() -> void:
	add_to_group("player")
	sprite.sprite_frames = SpriteFramesBuilder.from_sheet(DataDB.player_def.get("sprite", "res://assets/characters/doyun.png"))
	set_facing(GameState.facing)


func set_facing(dir: String) -> void:
	facing = dir
	sprite.play("idle_" + facing)


func _physics_process(delta: float) -> void:
	_interact_cooldown = maxf(0.0, _interact_cooldown - delta)
	if GameState.is_input_locked():
		velocity = Vector2.ZERO
		_interact_cooldown = 0.12
		if sprite.animation.begins_with("walk_"):
			sprite.play("idle_" + facing)
		return
	var dir := read_direction()
	velocity = dir * speed
	move_and_slide()
	if dir != Vector2.ZERO:
		facing = SpriteFramesBuilder.dir_name(dir)
		if sprite.animation != "walk_" + facing:
			sprite.play("walk_" + facing)
	elif sprite.animation != "idle_" + facing:
		sprite.play("idle_" + facing)
	GameState.player_position = global_position
	GameState.facing = facing


## 대각선 입력은 나중에 누른 축을 우선해 4방향으로 만든다.
func read_direction() -> Vector2:
	var x := Input.get_axis("move_left", "move_right")
	var y := Input.get_axis("move_up", "move_down")
	var now := Time.get_ticks_msec()
	if x != 0 and _prev_axis.x == 0:
		_axis_started["x"] = now
	if y != 0 and _prev_axis.y == 0:
		_axis_started["y"] = now
	_prev_axis = Vector2(x, y)
	if x != 0 and y != 0:
		if _axis_started["y"] >= _axis_started["x"]:
			x = 0
		else:
			y = 0
	return Vector2(signf(x), signf(y))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("interact") and not GameState.is_input_locked() and _interact_cooldown <= 0.0:
		var target := find_interactable()
		if target:
			get_viewport().set_input_as_handled()
			interacted.emit(target)
			target.interact(self)


func find_interactable() -> Node:
	var probe := global_position + SpriteFramesBuilder.dir_vector(facing) * interact_reach
	var best: Node = null
	var best_d := interact_tolerance
	for n in get_tree().get_nodes_in_group("interactable"):
		if not n.visible or not n.has_method("interact"):
			continue
		var d: float = (n as Node2D).global_position.distance_to(probe)
		if d <= best_d:
			best_d = d
			best = n
	return best
