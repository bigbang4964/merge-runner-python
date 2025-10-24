# merge_runner_advanced.py
# Full game demo — Merge Runner Advanced
# Requires: arcade (pip install arcade)
# Prepare an assets/ folder with images & sounds referenced below.

import arcade
import arcade.gui
import random
import json
import os
from typing import List, Tuple

# -------------------------
# Config
# -------------------------
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Merge Runner — Advanced"

ASSET_DIR = "assets"
DATA_DIR = "data"
PLAYER_SAVE = os.path.join(DATA_DIR, "player_data.json")
LEADERBOARD_FILE = os.path.join(DATA_DIR, "leaderboard.json")

# Parallax speed factors
PARALLAX = {"far": 0.2, "mid": 0.5, "near": 0.85}
DISTANCE_FOR_BOSS = 2000
BASE_SPEED = 180  # pixels per second baseline
EXPLOSION_PARTICLES = 48

# -------------------------
# Utils: save/load JSON
# -------------------------
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def save_player(data):
    ensure_data_dir()
    with open(PLAYER_SAVE, "w") as f:
        json.dump(data, f, indent=2)

def load_player():
    try:
        with open(PLAYER_SAVE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_score(name: str, score: int):
    ensure_data_dir()
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = []
    data.append({"name": name, "score": int(score)})
    data = sorted(data, key=lambda x: x["score"], reverse=True)[:10]
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_leaderboard():
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

# -------------------------
# AnimatedSprite (sprite-sheet)
# -------------------------
class AnimatedSprite(arcade.Sprite):
    def __init__(self, sprite_sheet: str, frames: int, scale: float = 1.0, frame_time: float = 0.08):
        super().__init__()
        self.textures = []
        sheet = arcade.load_texture(sprite_sheet)
        frame_w = sheet.width // frames
        for i in range(frames):
            tex = arcade.load_texture(sprite_sheet,
                                      x=i * frame_w, y=0,
                                      width=frame_w, height=sheet.height)
            self.textures.append(tex)
        self.texture = self.textures[0]
        self.scale = scale
        self.frames = len(self.textures)
        self.current_frame = 0
        self.frame_time = frame_time
        self.timer = 0.0

    def update_animation(self, delta_time: float = 1/60):
        self.timer += delta_time
        if self.timer >= self.frame_time:
            self.current_frame = (self.current_frame + 1) % self.frames
            self.texture = self.textures[self.current_frame]
            self.timer = 0.0

# -------------------------
# Projectile
# -------------------------
class Projectile(arcade.Sprite):
    def __init__(self, texture: str, x: float, y: float, vx: float, vy: float, scale: float = 0.6):
        super().__init__(texture, scale=scale)
        self.center_x = x
        self.center_y = y
        self.vx = vx
        self.vy = vy

    def update(self):
        self.center_x += self.vx
        self.center_y += self.vy
        # kill if off bounds far away
        if self.center_x < -1000 or self.center_x > 10000 or self.center_y < -1000 or self.center_y > 3000:
            self.remove_from_sprite_lists()

# -------------------------
# Boss with phases
# -------------------------
class Boss(AnimatedSprite):
    def __init__(self, sprite_sheet: str, frames: int = 6, scale: float = 2.0):
        super().__init__(sprite_sheet, frames, scale)
        self.max_health = 100
        self.health = self.max_health
        self.shoot_timer = 0.0
        self.phase = 1
        self.center_x = 0
        self.center_y = 220

    def update_behavior(self, dt: float, player_x: float, projectiles_list: arcade.SpriteList, shoot_sound=None):
        self.shoot_timer += dt
        ratio = self.health / max(1, self.max_health)
        # determine phase
        if ratio > 0.66:
            self.phase = 1
            interval = 1.2
            speed = 5.0
            move_speed = 0.0
        elif ratio > 0.33:
            self.phase = 2
            interval = 0.9
            speed = 6.0
            move_speed = 0.8  # advance a bit
            self.center_x -= move_speed
        else:
            self.phase = 3
            interval = 0.5
            speed = 7.0
            move_speed = 1.4
            self.center_x -= move_speed

        if self.shoot_timer >= interval:
            self.shoot_timer = 0.0
            # aim at player
            dx = player_x - self.center_x
            dy = (200) - self.center_y
            dist = max(abs(dx), 1)
            vx = (dx / dist) * speed * (1 + (3 - self.phase) * 0.2)
            vy = (dy / dist) * random.uniform(0.8, 2.0)
            p = Projectile(os.path.join(ASSET_DIR, "projectile.png"), self.center_x - 30, self.center_y, vx, vy, scale=0.6)
            projectiles_list.append(p)
            if self.phase == 3:
                # double shot
                p2 = Projectile(os.path.join(ASSET_DIR, "projectile.png"), self.center_x - 30, self.center_y + 50, vx, vy + 1.0, scale=0.6)
                projectiles_list.append(p2)
            if shoot_sound:
                arcade.play_sound(shoot_sound)

    def draw_health_bar(self):
        bar_w = 360
        left = self.center_x - bar_w / 2
        top = SCREEN_HEIGHT - 40
        # world coords: we will draw in world space (called when camera active)
        arcade.draw_lrtb_rectangle_filled(left, left + bar_w, top, top - 18, arcade.color.DARK_GRAY)
        health_ratio = max(0.0, self.health / self.max_health)
        arcade.draw_lrtb_rectangle_filled(left, left + bar_w * health_ratio, top, top - 18, arcade.color.RED)
        arcade.draw_text(f"Boss HP: {int(self.health)}/{int(self.max_health)}", left + 10, top - 16, arcade.color.WHITE, 12)

# -------------------------
# Parallax background
# -------------------------
class ParallaxBackground:
    def __init__(self, far_path, mid_path, near_path):
        self.far_tex = arcade.load_texture(far_path)
        self.mid_tex = arcade.load_texture(mid_path)
        self.near_tex = arcade.load_texture(near_path)
        self.w_far = self.far_tex.width
        self.w_mid = self.mid_tex.width
        self.w_near = self.near_tex.width

    def draw(self, cam_x: float):
        # draw far, mid, near with vertical offsets for depth
        self._draw_layer(self.far_tex, self.w_far, cam_x * PARALLAX["far"], y_offset=60)
        self._draw_layer(self.mid_tex, self.w_mid, cam_x * PARALLAX["mid"], y_offset=35)
        self._draw_layer(self.near_tex, self.w_near, cam_x * PARALLAX["near"], y_offset=15)

    def _draw_layer(self, tex, width, offset_x, y_offset=0):
        start_x = - (offset_x % width) - width
        x = start_x
        while x < SCREEN_WIDTH + width:
            arcade.draw_lrwh_rectangle_textured(x, y_offset, width, SCREEN_HEIGHT - y_offset, tex)
            x += width

# -------------------------
# Main Game View
# -------------------------
class GameView(arcade.View):
    def __init__(self, sprite_path: str):
        super().__init__()
        self.sprite_path = sprite_path

        # cameras
        self.camera = arcade.Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.gui_camera = arcade.Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

        # background
        self.bg = ParallaxBackground(
            os.path.join(ASSET_DIR, "bg_far.png"),
            os.path.join(ASSET_DIR, "bg_mid.png"),
            os.path.join(ASSET_DIR, "bg_near.png"),
        )

        # sprites and lists
        self.player: AnimatedSprite = None
        self.obstacles = arcade.SpriteList()
        self.coins = arcade.SpriteList()
        self.projectiles = arcade.SpriteList()  # boss projectiles
        self.explosions = []  # emitters

        # boss
        self.boss: Boss = None
        self.boss_active = False

        # metrics
        self.distance = 0.0
        self.next_boss_at = DISTANCE_FOR_BOSS
        self.speed = BASE_SPEED  # px/sec
        self.score = 0.0

        # player stats
        self.player_health = 100
        self.player_max_health = 100
        self.damage_popups: List[Tuple[float, float, int, float]] = []  # x,y, val, timeleft

        # action cooldowns
        self.skill_cd = 0.0

        # timers
        self.obstacle_timer = 0.0
        self.coin_timer = 0.0

        # sounds
        self.snd_win = None
        self.snd_lose = None
        self.snd_shoot = None
        self.snd_punch = None
        self.snd_hit = None
        self.snd_bgm = None

        # game state
        self.game_over = False
        self.result_text = ""
        self.paused = False

    def setup(self):
        # load sounds (optional)
        def s(name):
            try:
                return arcade.load_sound(os.path.join(ASSET_DIR, name))
            except Exception:
                return None
        self.snd_win = s("win.wav")
        self.snd_lose = s("lose.wav")
        self.snd_shoot = s("shoot.wav")
        self.snd_punch = s("punch.wav")
        self.snd_hit = s("hit.wav")
        try:
            self.snd_bgm = s("bgm.mp3")
            if self.snd_bgm:
                arcade.play_sound(self.snd_bgm, looping=True)
        except Exception:
            pass

        # player sprite (choose strong if distance large - optional)
        player_sheet = self.sprite_path
        self.player = AnimatedSprite(player_sheet, frames=6, scale=1.2)
        self.player.center_x = 200
        self.player.center_y = 200

        # initial obstacles & coins
        for _ in range(6):
            self.spawn_obstacle()
        for _ in range(5):
            self.spawn_coin()

        self.projectiles = arcade.SpriteList()
        self.obstacles = arcade.SpriteList(self.obstacles)
        self.coins = arcade.SpriteList(self.coins)
        self.explosions = []

    # spawning
    def spawn_obstacle(self):
        x = int(self.player.center_x + random.randint(600, 3000))
        obs = arcade.Sprite(os.path.join(ASSET_DIR, "obstacle.png"), scale=0.8)
        obs.center_x = x
        obs.center_y = 200
        self.obstacles.append(obs)

    def spawn_coin(self):
        x = int(self.player.center_x + random.randint(500, 2600))
        c = arcade.Sprite(os.path.join(ASSET_DIR, "coin.png"), scale=0.4)
        c.center_x = x
        c.center_y = random.randint(240, 320)
        self.coins.append(c)

    def spawn_boss(self):
        self.boss = Boss(os.path.join(ASSET_DIR, "boss_run.png"), frames=6, scale=2.0)
        # scale boss health with distance
        self.boss.max_health = 80 + int(self.distance / 500) * 10
        self.boss.health = self.boss.max_health
        self.boss.center_x = self.player.center_x + 900
        self.boss.center_y = 220
        self.boss_active = True
        self.projectiles = arcade.SpriteList()
        # faster shooting as distance grows
        self.boss.shoot_timer = 0.0

    def create_explosion(self, x, y):
        try:
            emitter = arcade.Emitter(
                center_xy=(x, y),
                emit_controller=arcade.EmitBurst(EXPLOSION_PARTICLES),
                particle_factory=lambda emitter:
                    arcade.LifetimeParticle(
                        filename_or_texture=os.path.join(ASSET_DIR, "explosion_particle.png"),
                        change_xy=(random.uniform(-6, 6), random.uniform(-8, 8)),
                        lifetime=random.uniform(0.6, 1.6),
                        scale=random.uniform(0.04, 0.18)
                    )
            )
            self.explosions.append(emitter)
        except Exception:
            pass

    # drawing
    def on_draw(self):
        arcade.start_render()
        # world camera
        self.camera.use()

        cam_x = self.camera.position[0]
        self.bg.draw(cam_x)

        # ground
        arcade.draw_lrtb_rectangle_filled(-10000, 100000, 180, 0, arcade.color.DARK_BROWN)

        # draw sprites
        self.obstacles.draw()
        self.coins.draw()
        if self.boss_active and self.boss:
            self.boss.draw()
            self.boss.draw_health_bar()
        self.player.draw()
        self.projectiles.draw()

        # draw particle emitters in world coords
        for e in self.explosions:
            e.draw()

        # GUI camera
        self.gui_camera.use()
        arcade.draw_text(f"Score: {int(self.score)}", 12, SCREEN_HEIGHT - 30, arcade.color.WHITE, 16)
        arcade.draw_text(f"Distance: {int(self.distance)} m", 12, SCREEN_HEIGHT - 56, arcade.color.LIGHT_GRAY, 14)

        # player health bar
        bar_w = 220
        x_left = 120
        top = SCREEN_HEIGHT - 28
        arcade.draw_lrtb_rectangle_filled(x_left - bar_w / 2, x_left + bar_w / 2, top, top - 20, arcade.color.DARK_GRAY)
        health_ratio = max(0, self.player_health / self.player_max_health)
        arcade.draw_lrtb_rectangle_filled(x_left - bar_w / 2, x_left - bar_w / 2 + bar_w * health_ratio, top, top - 20, arcade.color.GREEN)
        arcade.draw_text(f"HP: {int(self.player_health)}/{int(self.player_max_health)}", x_left - 40, top - 18, arcade.color.WHITE, 12)

        # damage popups
        for (x, y, val, t) in self.damage_popups:
            # t goes down; shift upward
            arcade.draw_text(f"-{val}", x - cam_x, y + (1 - t) * 40, arcade.color.RED, 16, bold=True)

        if self.game_over:
            arcade.draw_text(self.result_text, SCREEN_WIDTH // 2 - 180, SCREEN_HEIGHT // 2 + 30, arcade.color.YELLOW, 28, bold=True)
            arcade.draw_text("Press [R] to restart  |  [ESC] to Menu", SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 10, arcade.color.WHITE, 16)

    # update loop
    def on_update(self, dt: float):
        if self.game_over:
            for e in self.explosions:
                e.update()
            return

        # update animations
        self.player.update_animation(dt)
        if self.boss_active and self.boss:
            self.boss.update_animation(dt)

        # update emitters
        for e in self.explosions:
            e.update()

        # cooldowns
        if self.skill_cd > 0:
            self.skill_cd = max(0.0, self.skill_cd - dt)

        # movement & distance
        # speed pixels/sec; convert dt to delta_x
        dx = self.speed * dt
        self.player.center_x += dx
        self.distance += dx * 0.6
        self.score += dx * 0.05

        # camera follow (smooth)
        cam_target_x = self.player.center_x - SCREEN_WIDTH * 0.3
        self.camera.move_to((cam_target_x, 0), 0.08)

        # spawn obstacles & coins gradually
        self.obstacle_timer += dt
        self.coin_timer += dt
        if self.obstacle_timer > max(0.6, 2.4 - (self.distance / 8000)):
            self.spawn_obstacle()
            self.obstacle_timer = 0.0
        if self.coin_timer > max(0.8, 2.3 - (self.distance / 9000)):
            self.spawn_coin()
            self.coin_timer = 0.0

        # cleanup behind
        for s in list(self.obstacles):
            if s.center_x < self.player.center_x - 900:
                s.remove_from_sprite_lists()
        for c in list(self.coins):
            if c.center_x < self.player.center_x - 900:
                c.remove_from_sprite_lists()

        # collisions: coins
        hit_coins = arcade.check_for_collision_with_list(self.player, self.coins)
        for c in hit_coins:
            c.remove_from_sprite_lists()
            self.score += 25

        # collisions: obstacles
        hit_obs = arcade.check_for_collision_with_list(self.player, self.obstacles)
        for o in hit_obs:
            o.remove_from_sprite_lists()
            self.score = max(0, self.score - 40)
            self.player.center_x = max(200, self.player.center_x - 140)

        # boss spawn
        if not self.boss_active and self.distance >= self.next_boss_at:
            self.spawn_boss()
            # schedule next boss further out
            self.next_boss_at += DISTANCE_FOR_BOSS * (1 + self.distance / 8000)

        # boss behavior
        if self.boss_active and self.boss:
            self.boss.update_behavior(dt, self.player.center_x, self.projectiles, shoot_sound=self.snd_shoot)
            # update projectiles list
            self.projectiles.update()
            # projectile collisions with player
            for p in list(self.projectiles):
                if arcade.check_for_collision(p, self.player):
                    p.remove_from_sprite_lists()
                    # damage player
                    dmg = random.randint(8, 18)
                    self.player_health -= dmg
                    self.damage_popups.append((self.player.center_x, self.player.center_y + 80, dmg, 1.0))
                    if self.player_health <= 0:
                        self.player_health = 0
                        self.lose_game()
            # boss collision with player (massive hit)
            if arcade.check_for_collision(self.player, self.boss):
                # both take damage
                dmg = 18 + int(self.distance / 1000)
                self.player_health -= dmg
                self.boss.health -= 40
                self.damage_popups.append((self.player.center_x, self.player.center_y + 80, dmg, 1.0))
                if self.player_health <= 0:
                    self.lose_game()
                if self.boss.health <= 0:
                    self.win_boss()

            # allow player to damage boss by being close (melee)
            # No auto-damage here; damage via punch/skill is processed in input

            # if boss HP depleted
            if self.boss and self.boss.health <= 0:
                self.win_boss()

        # update damage popups timers
        self.damage_popups = [(x, y, v, t - dt) for (x, y, v, t) in self.damage_popups if t - dt > 0]

    def win_boss(self):
        self.create_explosion(self.boss.center_x, self.boss.center_y)
        self.score += 700
        if self.snd_win:
            arcade.play_sound(self.snd_win)
        self.boss_active = False
        self.boss = None

    def lose_game(self):
        self.game_over = True
        self.result_text = "💀 YOU DIED"
        if self.snd_lose:
            arcade.play_sound(self.snd_lose)
        # save score to leaderboard
        try:
            save_score("Player", int(self.score))
        except Exception:
            pass

    # input
    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            self.window.show_view(MenuView())
        if self.game_over:
            if key == arcade.key.R:
                # restart
                new = GameView(self.sprite_path)
                new.setup()
                self.window.show_view(new)
            return

        if key == arcade.key.SPACE:
            # jump (visual) - small vertical change then fall sim
            # simple approach: teleport up slightly then down
            self.player.center_y += 90
            # small falling back scheduled via engine (we'll just lerp in update: not implemented heavy)
        elif key == arcade.key.Z:
            # punch melee
            if self.boss_active and self.boss and abs(self.boss.center_x - self.player.center_x) < 140:
                dmg = random.randint(8, 16)
                self.boss.health -= dmg
                self.damage_popups.append((self.boss.center_x, self.boss.center_y + 100, dmg, 0.9))
                if self.snd_punch:
                    arcade.play_sound(self.snd_punch)
                if self.boss.health <= 0:
                    self.win_boss()
        elif key == arcade.key.X:
            # skill with cooldown
            if self.skill_cd <= 0.0:
                self.skill_cd = 3.0
                # ranged skill: damages boss if exists
                dmg = 40 + int(self.distance / 1000)
                if self.boss_active and self.boss:
                    self.boss.health -= dmg
                    self.damage_popups.append((self.boss.center_x, self.boss.center_y + 100, dmg, 1.2))
                    if self.snd_hit:
                        arcade.play_sound(self.snd_hit)
                    if self.boss.health <= 0:
                        self.win_boss()
                else:
                    # small area effect: remove nearby obstacles
                    removed = 0
                    for o in list(self.obstacles):
                        if abs(o.center_x - self.player.center_x) < 220:
                            o.remove_from_sprite_lists()
                            removed += 1
                    if removed and self.snd_hit:
                        arcade.play_sound(self.snd_hit)

# -------------------------
# Menu & Character Select & Leaderboard
# -------------------------
class MenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        self.v_box = arcade.gui.UIBoxLayout()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
        self.manager.enable()
        self.v_box = arcade.gui.UIBoxLayout()
        title = arcade.gui.UITextArea(text="MERGE RUNNER — Advanced", width=420, height=60, font_size=24, text_color=arcade.color.WHITE)
        self.v_box.add(title.with_space_around(bottom=30))

        start = arcade.gui.UIFlatButton(text="Start New", width=220)
        start.on_click = self.start_new
        self.v_box.add(start.with_space_around(bottom=12))

        load = arcade.gui.UIFlatButton(text="Load Last Save", width=220)
        load.on_click = self.load_game
        self.v_box.add(load.with_space_around(bottom=12))

        leader = arcade.gui.UIFlatButton(text="Leaderboard", width=220)
        leader.on_click = lambda e: self.window.show_view(LeaderboardView())
        self.v_box.add(leader.with_space_around(bottom=12))

        quitb = arcade.gui.UIFlatButton(text="Quit", width=220)
        quitb.on_click = lambda e: arcade.close_window()
        self.v_box.add(quitb)

        self.manager.add(arcade.gui.UIAnchorWidget(anchor_x="center_x", anchor_y="center_y", child=self.v_box))

    def start_new(self, event):
        self.window.show_view(CharacterSelectView())

    def load_game(self, event):
        data = load_player()
        if data:
            sprite = data.get("sprite_path", os.path.join(ASSET_DIR, "runner_male_run.png"))
            g = GameView(sprite)
            g.setup()
            self.window.show_view(g)
        else:
            # beep
            try:
                arcade.play_sound(arcade.load_sound(":resources:sounds/error1.wav"))
            except Exception:
                pass

    def on_draw(self):
        arcade.start_render()
        self.manager.draw()

    def on_hide_view(self):
        self.manager.disable()

class CharacterSelectView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        self.v_box = arcade.gui.UIBoxLayout()

    def on_show(self):
        arcade.set_background_color(arcade.color.GRAY)
        self.manager.enable()
        self.v_box = arcade.gui.UIBoxLayout()
        title = arcade.gui.UITextArea(text="Choose Character", width=360, height=40, text_color=arcade.color.WHITE)
        self.v_box.add(title.with_space_around(bottom=20))

        male = arcade.gui.UIFlatButton(text="Male", width=220)
        female = arcade.gui.UIFlatButton(text="Female", width=220)
        male.on_click = lambda e: self.start(os.path.join(ASSET_DIR, "runner_male_run.png"))
        female.on_click = lambda e: self.start(os.path.join(ASSET_DIR, "runner_female_run.png"))
        self.v_box.add(male.with_space_around(bottom=12))
        self.v_box.add(female.with_space_around(bottom=12))

        back = arcade.gui.UIFlatButton(text="Back", width=220)
        back.on_click = lambda e: self.window.show_view(MenuView())
        self.v_box.add(back)

        self.manager.add(arcade.gui.UIAnchorWidget(anchor_x="center_x", anchor_y="center_y", child=self.v_box))

    def start(self, sprite_path):
        save_player({"sprite_path": sprite_path})
        g = GameView(sprite_path)
        g.setup()
        self.window.show_view(g)

    def on_draw(self):
        arcade.start_render()
        self.manager.draw()

    def on_hide_view(self):
        self.manager.disable()

class LeaderboardView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        self.v_box = arcade.gui.UIBoxLayout()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)
        self.manager.enable()
        self.v_box = arcade.gui.UIBoxLayout()
        title = arcade.gui.UITextArea(text="Leaderboard - Top Scores", width=360, height=40, font_size=20, text_color=arcade.color.WHITE)
        self.v_box.add(title.with_space_around(bottom=18))

        scores = load_leaderboard()
        if scores:
            for i, s in enumerate(scores[:10], start=1):
                txt = f"{i}. {s['name']} — {s['score']}"
                self.v_box.add(arcade.gui.UITextArea(text=txt, width=320, height=24))
        else:
            self.v_box.add(arcade.gui.UITextArea(text="No scores yet.", width=320, height=24))

        back = arcade.gui.UIFlatButton(text="Back", width=220)
        back.on_click = lambda e: self.window.show_view(MenuView())
        self.v_box.add(back.with_space_around(top=20))
        self.manager.add(arcade.gui.UIAnchorWidget(anchor_x="center_x", anchor_y="center_y", child=self.v_box))

    def on_draw(self):
        arcade.start_render()
        self.manager.draw()

    def on_hide_view(self):
        self.manager.disable()

# -------------------------
# Run
# -------------------------
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    menu = MenuView()
    window.show_view(menu)
    arcade.run()

if __name__ == "__main__":
    main()
