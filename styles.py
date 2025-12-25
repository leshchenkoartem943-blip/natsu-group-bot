import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageSequence

def setup_new_year_theme():
    style = ttk.Style()
    style.theme_use('clam')
    
    bg_main = "#000000"
    bg_input = "#000000"
    fg_text = "#E3F2FD"
    
    style.configure(".", background=bg_main, foreground=fg_text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg_main)
    style.configure("TLabel", background=bg_main, foreground=fg_text)
    style.configure("TButton", background="#000000", foreground="white", borderwidth=1, bordercolor="#333")
    style.map("TButton", background=[('active', "#222")])
    
    style.configure("Green.TButton", bordercolor="#00E676", foreground="#00E676")
    style.configure("Red.TButton", bordercolor="#FF5252", foreground="#FF5252")
    
    style.configure("Treeview", background=bg_input, fieldbackground=bg_input, foreground="white", borderwidth=0)
    style.configure("Treeview.Heading", background="#111", foreground="#FFD700", borderwidth=0)
    
    return bg_main, bg_input

class AnimatedGifLabel(tk.Label):
    def __init__(self, master, filename, width, height, bg="#000000"):
        super().__init__(master, bg=bg, borderwidth=0)
        self.master = master
        self.filename = filename
        self.target_size = (width, height)
        self.frames = []
        self.delays = []
        self.idx = 0
        self.cancel_id = None

        try:
            # Открываем изображение через Pillow
            original_img = Image.open(filename)
            
            # Проходимся по всем кадрам
            for frame in ImageSequence.Iterator(original_img):
                # 1. Сжимаем кадр до нужного размера (LANCZOS - для качества)
                resized_frame = frame.resize(self.target_size, Image.Resampling.LANCZOS)
                
                # 2. Конвертируем для Tkinter
                photo = ImageTk.PhotoImage(resized_frame)
                self.frames.append(photo)
                
                # 3. Пытаемся узнать длительность кадра (скорость)
                self.delays.append(frame.info.get('duration', 100))

        except Exception as e:
            print(f"Ошибка загрузки/ресайза GIF: {e}")
            self.configure(text="GIF ERROR", fg="red")

        if self.frames:
            self.animate()

    def animate(self):
        # Ставим текущий кадр
        self.configure(image=self.frames[self.idx])
        
        # Узнаем задержку для текущего кадра
        delay = self.delays[self.idx]
        
        # Переключаем индекс
        self.idx = (self.idx + 1) % len(self.frames)
        
        # Запланировать следующий кадр
        self.cancel_id = self.after(delay, self.animate)

    def destroy(self):
        if self.cancel_id:
            self.after_cancel(self.cancel_id)
        super().destroy()

def position_near_cursor(win, width=None, height=None):
    try:
        x, y = win.winfo_pointerxy()
        win.geometry(f"+{x}+{y}")
    except: pass