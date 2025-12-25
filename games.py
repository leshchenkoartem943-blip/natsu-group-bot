import tkinter as tk
from tkinter import messagebox, scrolledtext
import random
import threading
import multiprocessing
import math
import time
import requests
import config

from utils import firebase_patch, firebase_get, get_hwid
import pygame
from collections import deque

def run_snake_game_process(user_name, user_hwid, db_url):
    """
    OPTIMIZED GAME ENGINE: 60 FPS RENDER, LOGIC DELAY, CACHED SURFACES
    """
    # --- СЕТЕВАЯ ЧАСТЬ ---
    def send_score_to_firebase(final_score):
        try:
            # 1. Проверяем текущий рекорд юзера
            url_user = f"{db_url}/snake_leaderboard/{user_hwid}.json"
            resp = requests.get(url_user, timeout=3)
            current_data = resp.json() if resp.status_code == 200 else None

            # Если рекорда нет или новый счет больше — обновляем
            save_needed = False
            if not current_data:
                save_needed = True
            elif final_score > current_data.get("score", 0):
                save_needed = True
            
            if save_needed:
                payload = {
                    "name": user_name,
                    "score": final_score,
                    "hwid": user_hwid
                }
                requests.patch(url_user, json=payload, timeout=3)
                print(f"Score {final_score} saved to Firebase!")
        except Exception as e: 
            print(f"Save Error: {e}")

    # --- ИНИЦИАЛИЗАЦИЯ ---
    pygame.init()
    WIDTH, HEIGHT = 900, 700
    CELL = 25
    FPS = 120 # Высокий FPS для плавности анимации
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"🐍 CyberSnake Ultra Smooth | Pilot: {user_name}")
    clock = pygame.time.Clock()
    
    font_score = pygame.font.SysFont("Impact", 24)
    font_main = pygame.font.SysFont("Verdana", 20, bold=True)
    font_big = pygame.font.SysFont("Verdana", 60, bold=True)

    # ЦВЕТА
    COL_BG = (10, 10, 18)
    COL_GRID = (25, 25, 40)
    COL_SNAKE_HEAD = (0, 255, 200)
    COL_SNAKE_TAIL = (0, 100, 150)
    COL_FOOD_GLOW = (255, 0, 80)
    
    class Particle:
        __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'color', 'size')
        def __init__(self, x, y, color):
            self.x = x
            self.y = y
            self.vx = random.uniform(-2, 2)
            self.vy = random.uniform(-2, 2)
            self.life = 255.0
            self.color = color
            self.size = random.randint(3, 6)

        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.life -= 5 # Медленнее исчезают
            self.size = max(0, self.size - 0.05)

        def draw(self, surf):
            if self.life > 0:
                s = pygame.Surface((int(self.size)*2, int(self.size)*2), pygame.SRCALPHA)
                alpha = int(self.life)
                if alpha < 0: alpha = 0
                pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
                surf.blit(s, (self.x - self.size, self.y - self.size))

    def lerp(a, b, t):
        """Линейная интерполяция между точками a и b"""
        return a + (b - a) * t

    def lerp_color(c1, c2, t):
        return (int(c1[0] + (c2[0]-c1[0])*t), int(c1[1] + (c2[1]-c1[1])*t), int(c1[2] + (c2[2]-c1[2])*t))

    def draw_eye(surf, cx, cy, direction):
        # Глаза немного смещаются в сторону движения
        off_x = 2 if direction[0] > 0 else (-2 if direction[0] < 0 else 0)
        off_y = 2 if direction[1] > 0 else (-2 if direction[1] < 0 else 0)
        pygame.draw.circle(surf, (255, 255, 255), (int(cx), int(cy)), 4)
        pygame.draw.circle(surf, (0, 0, 0), (int(cx + off_x), int(cy + off_y)), 2)

    def get_random_pos(snake_body):
        while True:
            x = random.randrange(0, WIDTH, CELL)
            y = random.randrange(50, HEIGHT, CELL)
            if (x, y) not in snake_body: return (x, y)

    # --- ПЕРЕМЕННЫЕ ИГРЫ ---
    snake = [(WIDTH//2, HEIGHT//2), (WIDTH//2-CELL, HEIGHT//2), (WIDTH//2-CELL*2, HEIGHT//2)]
    # Для интерполяции храним предыдущее состояние змейки
    prev_snake = list(snake)
    
    direction = (CELL, 0)
    input_queue = deque() # Очередь нажатий (Input Buffer)
    
    food = get_random_pos(snake)
    score = 0
    particles = []
    
    last_move_time = pygame.time.get_ticks()
    move_delay = 140 # Стартовая скорость
    
    running = True
    game_over = False
    paused = False
    score_sent = False
    pulse_val = 0

    grid_surface = pygame.Surface((WIDTH, HEIGHT))
    grid_surface.fill(COL_BG)
    for x in range(0, WIDTH, CELL): pygame.draw.line(grid_surface, COL_GRID, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, CELL): pygame.draw.line(grid_surface, COL_GRID, (0, y), (WIDTH, y))

    while running:
        clock.tick(FPS) 
        current_time = pygame.time.get_ticks()

        # 1. ОБРАБОТКА ВВОДА (Заполняем буфер)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
            # --- НОВОЕ: ПАУЗА ПО КЛИКУ ЛКМ ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # 1 = Левая кнопка мыши
                    if not game_over:
                        paused = not paused
                        # Сбрасываем таймер движения при снятии с паузы, чтобы не было рывка
                        if not paused: last_move_time = pygame.time.get_ticks()
            # ---------------------------------

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                
                # Пауза по кнопке P
                if event.key == pygame.K_p and not game_over:
                    paused = not paused
                    if not paused: last_move_time = pygame.time.get_ticks()

                if not game_over and not paused:
                    # Определяем последнее запланированное направление
                    last_dir = input_queue[-1] if input_queue else direction
                    
                    new_dir = None
                    
                    # УПРАВЛЕНИЕ: WASD или СТРЕЛКИ
                    # Вверх
                    if (event.key == pygame.K_w or event.key == pygame.K_UP) and last_dir != (0, CELL): 
                        new_dir = (0, -CELL)
                    # Вниз
                    elif (event.key == pygame.K_s or event.key == pygame.K_DOWN) and last_dir != (0, -CELL): 
                        new_dir = (0, CELL)
                    # Влево
                    elif (event.key == pygame.K_a or event.key == pygame.K_LEFT) and last_dir != (CELL, 0): 
                        new_dir = (-CELL, 0)
                    # Вправо
                    elif (event.key == pygame.K_d or event.key == pygame.K_RIGHT) and last_dir != (-CELL, 0): 
                        new_dir = (CELL, 0)
                    
                    # Добавляем в очередь (максимум 2 хода вперед)
                    if new_dir and len(input_queue) < 2:
                        input_queue.append(new_dir)

                elif event.key == pygame.K_SPACE and game_over:
                    # RESTART (Перезапуск игры)
                    snake = [(WIDTH//2, HEIGHT//2), (WIDTH//2-CELL, HEIGHT//2), (WIDTH//2-CELL*2, HEIGHT//2)]
                    prev_snake = list(snake)
                    direction = (CELL, 0)
                    input_queue.clear()
                    food = get_random_pos(snake)
                    score = 0
                    particles = []
                    move_delay = 140
                    game_over, score_sent, paused = False, False, False
                    last_move_time = pygame.time.get_ticks()

        # 2. ЛОГИКА ИГРЫ (ОБНОВЛЕНИЕ КООРДИНАТ)
        if not game_over and not paused:
            # Вычисляем прогресс времени для интерполяции (от 0.0 до 1.0)
            time_since_move = current_time - last_move_time
            
            if time_since_move >= move_delay:
                # ВРЕМЯ ШАГА!
                
                # Запоминаем текущее положение как "предыдущее" для интерполяции
                prev_snake = list(snake)
                
                # Берем направление из очереди, если есть
                if input_queue:
                    direction = input_queue.popleft()

                head = snake[0]
                new_head = (head[0] + direction[0], head[1] + direction[1])

                # Проверка столкновений
                if (new_head[0] < 0 or new_head[0] >= WIDTH or 
                    new_head[1] < 50 or new_head[1] >= HEIGHT or new_head in snake):
                    game_over = True
                    for _ in range(50): 
                        particles.append(Particle(head[0]+CELL//2, head[1]+CELL//2, (255, 50, 50)))
                else:
                    snake.insert(0, new_head)
                    
                    if new_head == food:
                        score += 1
                        move_delay = max(60, 140 - int(score * 2)) # Ускорение
                        food = get_random_pos(snake)
                        # Змейка растет, поэтому хвост в prev_snake нужно скорректировать
                        # Хак: добавляем в конец prev_snake дубликат хвоста, чтобы новый сегмент "вырастал" из него
                        prev_snake.append(prev_snake[-1]) 
                        
                        for _ in range(25):
                            particles.append(Particle(new_head[0]+CELL//2, new_head[1]+CELL//2, (255, 215, 0)))
                    else:
                        snake.pop()
                
                last_move_time = current_time # Сброс таймера

            # Обновление частиц
            particles = [p for p in particles if p.life > 0]
            for p in particles: p.update()
            pulse_val += 0.15

        # 3. ОТРИСОВКА (ИНТЕРПОЛЯЦИЯ)
        screen.blit(grid_surface, (0, 0))

        # Вычисляем фактор интерполяции (t)
        if not game_over and not paused:
            alpha = (current_time - last_move_time) / move_delay
            alpha = min(max(alpha, 0), 1.0) # Ограничиваем от 0 до 1
        else:
            alpha = 1.0 # Если пауза или конец игры, рисуем статику

        # РИСУЕМ ЕДУ (С пульсацией)
        glow_radius = CELL//2 + math.sin(pulse_val) * 3
        glow_surf = pygame.Surface((CELL*4, CELL*4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*COL_FOOD_GLOW, 60), (CELL*2, CELL*2), int(glow_radius) + 5)
        screen.blit(glow_surf, (food[0] - CELL*1.5, food[1] - CELL*1.5))
        pygame.draw.circle(screen, COL_FOOD_GLOW, (food[0]+CELL//2, food[1]+CELL//2), CELL//2 - 2)
        pygame.draw.circle(screen, (255, 255, 255), (food[0]+CELL//2 - 2, food[1]+CELL//2 - 2), 3)

        # РИСУЕМ ЗМЕЙКУ (С интерполяцией)
        for i in range(len(snake)):
            curr_pos = snake[i]
            # Если сегмент существовал в прошлом кадре, берем его старую позицию.
            # Если это новый хвост (вырос), он берется из конца prev_snake (см. логику выше)
            old_pos = prev_snake[i] if i < len(prev_snake) else curr_pos
            
            # Интерполируем координаты
            draw_x = lerp(old_pos[0], curr_pos[0], alpha)
            draw_y = lerp(old_pos[1], curr_pos[1], alpha)
            
            color = lerp_color(COL_SNAKE_HEAD, COL_SNAKE_TAIL, min(1, i/len(snake)))
            
            # Рисуем
            pygame.draw.rect(screen, color, (draw_x+1, draw_y+1, CELL-2, CELL-2), border_radius=6)
            
            if i == 0: # Глаза рисуем на интерполированной голове
                # Направление для глаз берем текущее
                draw_eye(screen, draw_x + CELL//2, draw_y + CELL//2, direction)

        # Частицы
        for p in particles: p.draw(screen)

        # HUD
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, 40)) 
        pygame.draw.line(screen, (0, 255, 200), (0, 40), (WIDTH, 40), 2)
        
        screen.blit(font_score.render(f"SCORE: {score}", True, (255, 255, 255)), (20, 5))
        screen.blit(font_main.render(f"PILOT: {user_name} | [P] PAUSE", True, (200, 200, 200)), (WIDTH - 420, 8))

        # ЭКРАНЫ
        if paused and not game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            t_p = font_big.render("PAUSED", True, (255, 255, 0))
            screen.blit(t_p, (WIDTH//2 - t_p.get_width()//2, HEIGHT//2 - 30))

        if game_over:
            if not score_sent:
                threading.Thread(target=send_score_to_firebase, args=(score,), daemon=True).start()
                score_sent = True
            
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            t1 = font_big.render("SYSTEM FAILURE", True, (255, 50, 50))
            t2 = font_main.render(f"FINAL SCORE: {score}", True, (255, 255, 255))
            t3 = font_main.render("[SPACE] TO REBOOT", True, (0, 255, 200))
            
            cx, cy = WIDTH // 2, HEIGHT // 2
            screen.blit(t1, (cx - t1.get_width()//2, cy - 60))
            screen.blit(t2, (cx - t2.get_width()//2, cy + 10))
            screen.blit(t3, (cx - t3.get_width()//2, cy + 50))

        pygame.display.flip()

    pygame.quit()

class SeaBattleLogic:
    """Чистая логика: проверка убийства корабля и окружения"""
    
    @staticmethod
    def get_ship_cells(start_x, start_y, board):
        ship_cells = set()
        stack = [(start_x, start_y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in ship_cells: continue
            ship_cells.add((cx, cy))
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    val = board[ny][nx]
                    if val == 1 or val == 3: # 1-целый, 3-ранен
                        if (nx, ny) not in ship_cells: stack.append((nx, ny))
        return list(ship_cells)

    @staticmethod
    def is_ship_sunk(ship_cells, board):
        for x, y in ship_cells:
            if board[y][x] == 1: return False
        return True

    @staticmethod
    def mark_halo(ship_cells, board):
        for sx, sy in ship_cells:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = sx + dx, sy + dy
                    if 0 <= nx < 10 and 0 <= ny < 10:
                        if board[ny][nx] == 0: board[ny][nx] = 2

# 2. ТЕПЕРЬ МОЖНО ОБЪЯВЛЯТЬ ОКНО
class SeaBattleWindow(tk.Toplevel):
    def __init__(self, parent, my_hwid, my_name):
        super().__init__(parent)
        
        self.my_hwid = my_hwid
        self.my_name = my_name

        self.title("⚓ M.O.R.S.K.O.Y. B.O.Y. | TURBO ⚓")
        self.geometry("950x550")
        self.configure(bg="#0F0F0F")
        self.resizable(False, False)
        
        self.game_id = None
        self.enemy_hwid = None
        self.stop_polling = False
        self.is_my_turn = False
        
        # 0=Вода, 1=Корабль, 2=Мимо, 3=Ранен, 4=Убит
        self.my_board = self.generate_random_board()
        self.game_state = "LOBBY" 
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_ui()
        
        # Безопасный вопрос через таймер
        self.after(200, self.ask_debug_mode)

    def check_alive(self):
        """Проверяет, жива ли еще программа, чтобы не крашиться"""
        try:
            return self.winfo_exists()
        except:
            return False

    def ask_debug_mode(self):
        if not self.check_alive(): return
        if messagebox.askyesno("DEBUG", "Тестируете сами с собой?\n(Нажмите ДА во втором окне)", parent=self):
            self.my_hwid += "_FAKE"
            self.my_name += " (2)"
            self.title(self.title() + " [РЕЖИМ ФЕЙКА]")

    def generate_random_board(self):
        board = [[0]*10 for _ in range(10)]
        ships = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
        for length in ships:
            placed = False
            while not placed:
                x, y = random.randint(0, 9), random.randint(0, 9)
                orient = random.choice(['H', 'V'])
                fit = True
                ship_coords = []
                for i in range(length):
                    nx, ny = (x + i, y) if orient == 'H' else (x, y + i)
                    if nx >= 10 or ny >= 10: fit = False; break
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            tx, ty = nx+dx, ny+dy
                            if 0 <= tx < 10 and 0 <= ty < 10:
                                if board[ty][tx] == 1: fit = False
                    ship_coords.append((nx, ny))
                if fit:
                    for cx, cy in ship_coords: board[cy][cx] = 1
                    placed = True
        return board

    def setup_ui(self):
        self.bg_color = "#0F0F0F"
        self.color_water = "#1E1E1E"
        self.color_ship_me = "#00E676"
        self.color_miss = "#555555"
        self.color_hit = "#FFD700"
        self.color_dead = "#D50000"

        # ЛОББИ
        self.frame_lobby = tk.Frame(self, bg=self.bg_color)
        self.frame_lobby.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(self.frame_lobby, text="⚓ МОРСКОЙ БОЙ ⚓", font=("Segoe UI Black", 32), bg=self.bg_color, fg="#00E676").pack(pady=(40, 20))
        tk.Button(self.frame_lobby, text="СОЗДАТЬ КОМНАТУ", command=self.create_game, font=("Segoe UI", 16, "bold"), bg="#00E676", fg="black", width=25).pack(pady=10)
        
        tk.Label(self.frame_lobby, text="— КОД КОМНАТЫ —", bg=self.bg_color, fg="#666").pack(pady=10)
        self.e_code = tk.Entry(self.frame_lobby, font=("Consolas", 24), justify="center", width=6, bg="#222", fg="white", insertbackground="white")
        self.e_code.pack(pady=5)
        
        tk.Button(self.frame_lobby, text="ПОДКЛЮЧИТЬСЯ", command=self.join_game, font=("Segoe UI", 16, "bold"), bg="#2979FF", fg="white", width=25).pack(pady=20)

        # ИГРА
        self.frame_game = tk.Frame(self, bg=self.bg_color)
        self.top_panel = tk.Frame(self.frame_game, bg="#111", pady=15)
        self.top_panel.pack(fill="x")
        self.lbl_turn = tk.Label(self.top_panel, text="ПОДГОТОВКА...", font=("Segoe UI Black", 20), bg="#111", fg="#888")
        self.lbl_turn.pack()

        center_frame = tk.Frame(self.frame_game, bg=self.bg_color)
        center_frame.pack(expand=True, fill="both", padx=10, pady=10) 
        
        # Левая
        f_left = tk.Frame(center_frame, bg=self.bg_color)
        f_left.pack(side="left", padx=10)
        tk.Label(f_left, text="МОЙ ФЛОТ", font=("Segoe UI", 12, "bold"), bg=self.bg_color, fg="#00E676").pack(pady=(0,5))
        self.my_btns = self.create_grid(f_left, is_enemy=False)

        # Лог
        f_log = tk.Frame(center_frame, bg=self.bg_color, width=220)
        f_log.pack(side="left", fill="y", padx=10)
        tk.Label(f_log, text="ЖУРНАЛ БОЯ", font=("Consolas", 10), bg=self.bg_color, fg="#888").pack(pady=(0,5))
        
        try:
            self.log_text = scrolledtext.ScrolledText(f_log, width=28, height=20, bg="#151515", fg="#EEE", font=("Consolas", 9), bd=0)
        except:
            self.log_text = tk.Text(f_log, width=28, height=20, bg="#151515", fg="#EEE", font=("Consolas", 9), bd=0)
            
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("ME", foreground="#00E676")
        self.log_text.tag_config("ENEMY", foreground="#FF5252")

        # Правая
        f_right = tk.Frame(center_frame, bg=self.bg_color)
        f_right.pack(side="right", padx=10)
        tk.Label(f_right, text="ВРАЖЕСКИЕ ВОДЫ", font=("Segoe UI", 12, "bold"), bg=self.bg_color, fg="#FF5252").pack(pady=(0,5))
        self.enemy_btns = self.create_grid(f_right, is_enemy=True)

    def create_grid(self, parent, is_enemy):
        frame = tk.Frame(parent, bg="#333", bd=1)
        frame.pack()
        btns = []
        for y in range(10):
            row = []
            for x in range(10):
                cmd = lambda xx=x, yy=y: self.shoot(xx, yy) if is_enemy else None
                b = tk.Button(frame, width=3, height=1, command=cmd, bg=self.color_water, bd=0, relief="flat", activebackground="#333")
                b.grid(row=y, column=x, padx=1, pady=1)
                if not is_enemy and self.my_board[y][x] == 1: b.config(bg=self.color_ship_me)
                row.append(b)
            btns.append(row)
        return btns

    def log(self, text, tag="INFO"):
        if not self.check_alive(): return # ЗАЩИТА ОТ ВЫЛЕТА
        try:
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"> {text}\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        except: pass

    # --- СЕТЬ ---
    def on_closing(self):
        self.stop_polling = True # Сначала останавливаем цикл
        if self.game_id and self.game_state == "PLAYING" and self.enemy_hwid:
            threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", {
                "winner": self.enemy_hwid, "status": "finished", "log_msg": f"{self.my_name} сбежал!"
            }), daemon=True).start()
        elif self.game_id and self.game_state == "WAITING":
            threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", {
                "status": "closed", "host_name": "Закрыто"
            }), daemon=True).start()
        
        self.destroy()

    def create_game(self):
        self.game_id = str(random.randint(1000, 9999))
        self.is_my_turn = True
        data = { "host": self.my_hwid, "host_name": self.my_name, "guest": "", "status": "waiting", "turn": self.my_hwid, "winner": "", "host_board": self.my_board, "guest_board": [], "last_action": "" }
        threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", data), daemon=True).start()
        self.start_game_ui(f"Комната: {self.game_id}")
        self.log(f"Код: {self.game_id}. Ждем...", "INFO")
        self.game_state = "WAITING"
        self.start_polling()

    def join_game(self):
        code = self.e_code.get().strip()
        if len(code) != 4: return messagebox.showerror("Ошибка", "Неверный код")
        self.game_id = code
        self.is_my_turn = False
        def _join():
            game = firebase_get(f"/battleship/{code}")
            if not game: return messagebox.showerror("!", "Нет комнаты")
            if game.get("status") == "closed": return messagebox.showerror("!", "Комната удалена")
            if game.get("guest") and game.get("guest") != self.my_hwid: return messagebox.showerror("!", "Занято")
            
            update = { "guest": self.my_hwid, "guest_name": self.my_name, "guest_board": self.my_board, "status": "playing" }
            firebase_patch(f"/battleship/{code}", update)
            self.game_state = "PLAYING"
            self.enemy_hwid = game.get("host")
            self.after(0, lambda: self.start_game_ui(f"VS {game.get('host_name')}"))
            self.start_polling()
        threading.Thread(target=_join, daemon=True).start()

    def start_game_ui(self, title_msg):
        if not self.check_alive(): return
        self.frame_lobby.pack_forget()
        self.frame_game.pack(fill="both", expand=True)
        self.title(title_msg)

    def start_polling(self):
        self.stop_polling = False
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        last_log = ""
        while not self.stop_polling:
            if not self.check_alive(): break # ЗАЩИТА: Если окно закрыто - выход
            try:
                if not self.game_id: break
                data = firebase_get(f"/battleship/{self.game_id}")
                if not data: break
                
                status = data.get("status")
                turn = data.get("turn")
                winner = data.get("winner")
                act = data.get("last_action", "")

                if status == "closed":
                    if self.check_alive():
                        self.after(0, lambda: messagebox.showinfo("Инфо", "Админ комнаты вышел."))
                        self.stop_polling = True
                        self.after(0, self.destroy)
                    return

                if act and act != last_log:
                    last_log = act
                    if not act.startswith(self.my_name): self.after(0, lambda m=act: self.log(m, "ENEMY"))

                if winner:
                    is_win = (winner == self.my_hwid)
                    msg = "🏆 ПОБЕДА!" if is_win else "💀 ПОРАЖЕНИЕ"
                    col = "#00E676" if is_win else "#FF5252"
                    self.after(0, lambda: self.finish_game(msg, col))
                    if data.get("log_msg"): self.after(0, lambda: self.log(data.get("log_msg"), "INFO"))
                    self.stop_polling = True
                    return

                if self.game_state == "WAITING" and data.get("guest"):
                    self.game_state = "PLAYING"
                    self.enemy_hwid = data.get("guest")
                    self.after(0, lambda: self.log("Враг найден!", "INFO"))

                if self.game_state == "PLAYING":
                    self.is_my_turn = (turn == self.my_hwid)
                    if self.check_alive():
                        if self.is_my_turn:
                            self.after(0, lambda: self.safe_config(self.lbl_turn, text="🔥 ВАШ ХОД! 🔥", fg="#00E676"))
                        else:
                            self.after(0, lambda: self.safe_config(self.lbl_turn, text="⏳ ХОД ВРАГА...", fg="#FFD700"))

                    my_r = "host" if self.my_hwid == data.get("host") else "guest"
                    en_r = "guest" if my_r == "host" else "host"
                    if data.get(f"{my_r}_board"): self.after(0, lambda: self.redraw_board(self.my_btns, data[f"{my_r}_board"], False))
                    if data.get(f"{en_r}_board"): self.after(0, lambda: self.redraw_board(self.enemy_btns, data[f"{en_r}_board"], True))

            except Exception as e: 
                if not self.stop_polling: print(f"Poll: {e}")
            time.sleep(0.3) 

    def safe_config(self, widget, **kwargs):
        """Безопасная настройка виджета"""
        try:
            if self.check_alive(): widget.config(**kwargs)
        except: pass

    def finish_game(self, msg, color):
        if not self.check_alive(): return
        self.lbl_turn.config(text=msg, fg=color)
        self.log(msg, "ME" if "ПОБЕДА" in msg else "ENEMY")
        for row in self.enemy_btns:
            for b in row: b.config(state="disabled")

    def redraw_board(self, btns, board, is_enemy):
        if not self.check_alive(): return # ЗАЩИТА
        try:
            for y in range(10):
                for x in range(10):
                    val = board[y][x]
                    btn = btns[y][x]
                    
                    # Проверяем, существует ли кнопка (защита от TclError)
                    try:
                        if val == 2 and btn['text'] != "•": 
                            btn.config(text="•", fg=self.color_miss, bg=self.color_water)
                        elif val == 3: 
                            btn.config(text="X", bg=self.color_hit, fg="black")
                        elif val == 4: 
                            btn.config(text="☠", bg=self.color_dead, fg="white")
                        
                        if not is_enemy and val in [3,4]: 
                            btn.config(bg=self.color_dead if val==4 else self.color_hit)
                    except: pass
        except: pass

    def shoot(self, x, y):
        if not self.is_my_turn: return
        if self.enemy_btns[y][x]['text'] != "": return 
        try:
            self.enemy_btns[y][x].config(bg="#444") 
            self.lbl_turn.config(text="⏳ ОБРАБОТКА...", fg="#FFD700")
        except: pass
        threading.Thread(target=lambda: self._process_shot(x, y), daemon=True).start()

    def _process_shot(self, x, y):
        try:
            data = firebase_get(f"/battleship/{self.game_id}")
            if not data or data.get("turn") != self.my_hwid: return
            
            my_role = "host" if self.my_hwid == data.get("host") else "guest"
            enemy_role = "guest" if my_role == "host" else "host"
            enemy_board = data.get(f"{enemy_role}_board")
            if not enemy_board: return 

            cell_val = enemy_board[y][x]
            next_turn = data.get("guest") if my_role == "host" else data.get("host")
            log_msg = ""
            skip_update = False

            if cell_val == 0: 
                enemy_board[y][x] = 2
                log_msg = f"{self.my_name}: МИМО ({chr(65+x)}{y+1})"
            
            elif cell_val == 1: 
                next_turn = self.my_hwid
                enemy_board[y][x] = 3
                
                # ВОТ ЗДЕСЬ ТЕПЕРЬ ОШИБКИ НЕ БУДЕТ (КЛАСС ОБЪЯВЛЕН ВЫШЕ)
                ship_cells = SeaBattleLogic.get_ship_cells(x, y, enemy_board)
                if SeaBattleLogic.is_ship_sunk(ship_cells, enemy_board):
                    log_msg = f"{self.my_name}: УНИЧТОЖИЛ КОРАБЛЬ!"
                    for cx, cy in ship_cells: enemy_board[cy][cx] = 4
                    SeaBattleLogic.mark_halo(ship_cells, enemy_board)
                    skip_update = True
                else:
                    log_msg = f"{self.my_name}: ПОПАЛ!"

            elif cell_val >= 2: return 

            if not skip_update and cell_val == 1: pass 
            
            has_ships = any(1 in row for row in enemy_board)
            winner = self.my_hwid if not has_ships else ""
            
            firebase_patch(f"/battleship/{self.game_id}", {
                f"{enemy_role}_board": enemy_board, "turn": next_turn,
                "winner": winner, "last_action": log_msg
            })
            if log_msg: self.after(0, lambda: self.log(log_msg, "ME"))
            
        except Exception as e: print(f"Shot: {e}")