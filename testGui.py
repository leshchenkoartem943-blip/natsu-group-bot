import customtkinter as ctk
import tkinter as tk

# Настройки глобальной темы
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Цветовая палитра "Cyberpunk / Stealth"
COLOR_BG = "#101010"            # Почти черный фон
COLOR_PANEL = "#1a1a1a"         # Темно-серый для панелей
COLOR_ACCENT = "#6200ea"        # Неоновый фиолетовый
COLOR_ACCENT_HOVER = "#3700b3"  # Темно-фиолетовый при наведении
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#a0a0a0"

class ProExecutor(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Конфигурация окна
        self.title("NEXUS EXECUTOR v2.0")
        self.geometry("900x550")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        # Сетка: Сайдбар (слева) + Основной контент (центр) + Список скриптов (справа)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 1. ЛЕВЫЙ САЙДБАР (Меню) ===
        self.sidebar = ctk.CTkFrame(self, width=60, corner_radius=0, fg_color=COLOR_PANEL)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1) # Распорка снизу

        # Логотип (Текст)
        self.logo = ctk.CTkLabel(self.sidebar, text="NX", font=("Impact", 24), text_color=COLOR_ACCENT)
        self.logo.grid(row=0, column=0, pady=(20, 30))

        # Кнопки навигации (Иконки эмулируются текстом)
        self.create_sidebar_btn("Home", "🏠", 1)
        self.create_sidebar_btn("Editor", "📝", 2, is_active=True)
        self.create_sidebar_btn("Settings", "⚙️", 3)
        self.create_sidebar_btn("Cloud", "☁️", 4)

        # Кнопка Inject (Внизу сайдбара)
        self.btn_inject = ctk.CTkButton(
            self.sidebar, 
            text="💉", 
            width=40, 
            height=40,
            corner_radius=20,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=("Arial", 20),
            command=self.animate_inject
        )
        self.btn_inject.grid(row=6, column=0, pady=20)

        # === 2. ЦЕНТРАЛЬНАЯ ЧАСТЬ (Редактор) ===
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # Заголовок вкладки
        self.lbl_title = ctk.CTkLabel(self.main_area, text="LUA EDITOR", font=("Roboto Medium", 16), text_color=COLOR_TEXT_DIM)
        self.lbl_title.grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Поле редактора кода
        self.editor = ctk.CTkTextbox(
            self.main_area, 
            font=("Consolas", 13), 
            text_color="#00ffcc",  # Цвет текста как у хакеров
            fg_color="#0d0d0d",    # Очень темный фон редактора
            border_width=1,
            border_color="#333333",
            corner_radius=5
        )
        self.editor.grid(row=1, column=0, sticky="nsew")
        self.editor.insert("0.0", "-- Welcome to Nexus\n-- Paste your script here\n\nprint('Nexus Loaded')")

        # Панель действий под редактором
        self.action_bar = ctk.CTkFrame(self.main_area, height=50, fg_color="transparent")
        self.action_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.btn_exec = ctk.CTkButton(self.action_bar, text="EXECUTE", width=120, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.btn_exec.pack(side="right")
        
        self.btn_clear = ctk.CTkButton(self.action_bar, text="CLEAR", width=80, fg_color="#333333", hover_color="#444444")
        self.btn_clear.pack(side="right", padx=10)

        # === 3. ПРАВЫЙ САЙДБАР (Script Hub) ===
        self.hub_frame = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_PANEL)
        self.hub_frame.grid(row=0, column=2, sticky="nsew")
        
        self.lbl_hub = ctk.CTkLabel(self.hub_frame, text="SCRIPT HUB", font=("Roboto Medium", 14), text_color=COLOR_TEXT)
        self.lbl_hub.pack(pady=(20, 10), padx=10, anchor="w")

        # Список скриптов (Scrollable Frame)
        self.scroll_scripts = ctk.CTkScrollableFrame(self.hub_frame, fg_color="transparent")
        self.scroll_scripts.pack(fill="both", expand=True, padx=5, pady=5)

        # Добавляем фейковые скрипты
        scripts = ["Infinite Jump", "Speed Hack v2", "Fly Script", "ESP Box", "Auto Farm", "Aim Assist"]
        for script in scripts:
            btn = ctk.CTkButton(
                self.scroll_scripts, 
                text=script, 
                fg_color="#2b2b2b", 
                hover_color="#3a3a3a", 
                anchor="w",
                height=35
            )
            btn.pack(fill="x", pady=2)

        # === СТАТУС БАР ===
        self.status_bar = ctk.CTkLabel(self.hub_frame, text="Status: Not Injected 🔴", font=("Arial", 11), text_color="#ff5555")
        self.status_bar.pack(side="bottom", pady=10)

    def create_sidebar_btn(self, name, icon, row, is_active=False):
        color = "#2b2b2b" if is_active else "transparent"
        btn = ctk.CTkButton(
            self.sidebar, 
            text=icon, 
            width=40, 
            height=40, 
            fg_color=color, 
            hover_color="#333333",
            font=("Arial", 20)
        )
        btn.grid(row=row, column=0, pady=10)
        return btn

    def animate_inject(self):
        # Имитация процесса инъекции
        self.status_bar.configure(text="Injecting...", text_color="#ffff00")
        self.after(2000, lambda: self.status_bar.configure(text="Status: Ready 🟢", text_color="#00ff00"))

if __name__ == "__main__":
    app = ProExecutor()
    app.mainloop()