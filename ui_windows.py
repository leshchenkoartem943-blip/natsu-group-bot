import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, scrolledtext
import config
import sys
import subprocess

# ==========================================
# 1. ДИАЛОГ ВВОДА КОДА (Login / 2FA)
# ==========================================

def ask_code_gui(phone, title="Ввод кода Telegram"):
    """
    Модальное окно для ввода кода из SMS или 2FA пароля.
    Блокирует выполнение программы, пока пользователь не введет код.
    """
    win = Toplevel()
    win.title(title)
    win.geometry("350x220")
    win.configure(bg="#111111")
    win.resizable(False, False)
    
    # Центрируем окно относительно экрана
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    # Переменная для результата
    result_code = tk.StringVar(value="")
    
    # Лейбл с телефоном
    tk.Label(win, text=f"Введите код для:", bg="#111111", fg="#AAAAAA", font=("Segoe UI", 10)).pack(pady=(20, 5))
    tk.Label(win, text=phone, bg="#111111", fg="#00E676", font=("Segoe UI", 12, "bold")).pack(pady=0)

    # Поле ввода
    e_code = tk.Entry(win, font=("Consolas", 16, "bold"), justify='center', bg="#222", fg="white", insertbackground="white")
    e_code.pack(pady=15, ipadx=10, ipady=5)
    e_code.focus_set()

    # Логика подтверждения
    def on_confirm(event=None):
        code = e_code.get().strip()
        if code:
            result_code.set(code)
            win.destroy()
        else:
            messagebox.showwarning("Внимание", "Поле кода пустое!", parent=win)

    # Кнопка подтверждения
    btn_ok = tk.Button(win, text="ПОДТВЕРДИТЬ", command=on_confirm, 
                      bg="#00E676", fg="black", font=("Segoe UI", 10, "bold"), cursor="hand2")
    btn_ok.pack(pady=10, ipadx=20)

    # Биндим Enter для удобства
    win.bind('<Return>', on_confirm)
    
    # Делаем окно модальным (ждем закрытия)
    win.transient()
    win.grab_set()
    win.wait_window(win)
    
    return result_code.get() if result_code.get() else None


# ==========================================
# 2. ОКНО ПОДТВЕРЖДЕНИЯ ЗАПУСКА (MatchReview)
# ==========================================

class MatchReviewWindow:
    """
    Окно перед созданием групп. Показывает таблицу найденных контактов,
    позволяет ввести имя группы и выбрать, кого добавлять.
    """
    def __init__(self, parent, contacts):
        self.win = Toplevel(parent)
        self.win.title("🚀 Подтверждение запуска")
        self.win.geometry("550x600")
        self.win.configure(bg="#121212")
        
        self.contacts = contacts
        self.result_data = None # Сюда положим результат: {group_name, contacts}

        # --- ЗАГОЛОВОК ---
        tk.Label(self.win, text="Настройка задачи", font=("Segoe UI", 16, "bold"), 
                 bg="#121212", fg="#00E676").pack(pady=15)

        # --- НАЗВАНИЕ ГРУППЫ ---
        frame_name = tk.Frame(self.win, bg="#121212")
        frame_name.pack(fill="x", padx=20, pady=5)
        
        tk.Label(frame_name, text="Базовое название групп (добавится 01, 02...):", bg="#121212", fg="#CCCCCC").pack(anchor="w")
        self.e_name = tk.Entry(frame_name, font=("Segoe UI", 12), bg="#222", fg="white", insertbackground="white")
        self.e_name.pack(fill="x", pady=5, ipady=3)
        self.e_name.insert(0, "WorkGroup")

        # --- СПИСОК КОНТАКТОВ ---
        tk.Label(self.win, text=f"Найдено контактов для добавления: {len(contacts)}", bg="#121212", fg="gray").pack(pady=(15,5))
        
        # Фрейм для таблицы
        frame_list = tk.Frame(self.win, bg="#121212")
        frame_list.pack(fill="both", expand=True, padx=20, pady=5)

        # Таблица (Treeview)
        style = ttk.Style()
        style.configure("Treeview", background="#222", foreground="white", fieldbackground="#222", rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        cols = ("phone", "name")
        self.tree = ttk.Treeview(frame_list, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("name", text="Имя")
        self.tree.column("phone", width=140)
        self.tree.column("name", width=250)

        # Скроллбар
        sb = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Заполняем таблицу данными
        for c in contacts:
            # c = {'phone':..., 'name':...}
            self.tree.insert("", "end", values=(c.get('phone'), c.get('name', 'Unknown')))
        
        # Выделяем все строки по умолчанию
        self.tree.selection_set(self.tree.get_children())

        # --- КНОПКА ЗАПУСКА ---
        btn_start = tk.Button(self.win, text="🚀 ЗАПУСТИТЬ ПРОЦЕСС", command=self.confirm, 
                              bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), pady=10, cursor="hand2")
        btn_start.pack(fill="x", side="bottom", padx=20, pady=20)

        # Блокируем родительское окно
        self.win.transient(parent)
        self.win.grab_set()
        parent.wait_window(self.win)

    def confirm(self):
        # 1. Проверяем название
        g_name = self.e_name.get().strip()
        if not g_name:
            messagebox.showwarning("Ошибка", "Введите название группы!", parent=self.win)
            return

        # 2. Собираем выбранные контакты
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Ошибка", "Выберите хотя бы один контакт!", parent=self.win)
            return
        
        sel_list = []
        for iid in selected_items:
            vals = self.tree.item(iid)['values']
            sel_list.append({"phone": str(vals[0]), "name": str(vals[1])})
        
        # Сохраняем результат и закрываем окно
        self.result_data = {
            "group_name": g_name,
            "contacts": sel_list
        }
        self.win.destroy()


# ==========================================
# 3. НАСТРОЙКА СЛОВ (Shtrudirovka Words)
# ==========================================

def open_word_settings():
    """Окно для ввода слов."""
    win = Toplevel(root)
    win.title("Настройка слов")
    win.geometry("400x500")
    win.configure(bg="#1E1E1E")
    
    tk.Label(win, text="Введите слова (каждое с новой строки):", 
             bg="#1E1E1E", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=10)
             
    tk.Label(win, text="Пример:\nВажное\nСотрудникам\nИнфо", 
             bg="#1E1E1E", fg="#888", justify="left").pack(pady=5)

    txt = scrolledtext.ScrolledText(win, width=40, height=15, font=("Consolas", 10))
    txt.pack(padx=10, pady=5, fill="both", expand=True)
    
    # Загружаем текущие
    cfg = load_config()
    txt.insert("1.0", cfg.get("random_words_list", ""))

    def _save():
        val = txt.get("1.0", tk.END).strip()
        cfg = load_config()
        cfg["random_words_list"] = val
        save_config(cfg)
        messagebox.showinfo("Готово", "Список слов сохранен!")
        win.destroy()

    tk.Button(win, text="💾 СОХРАНИТЬ", command=_save, bg="#00E676", fg="black").pack(fill="x", padx=20, pady=20)


def create_note_tab(notebook, title, content=""):
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=title)
    
    # === КРАСИВЫЙ РЕДАКТОР ===
    # bg: Фон редактора
    # fg: Цвет текста
    # insertbackground: Цвет курсора (мигающей палочки)
    # selectbackground: Цвет выделения текста мышкой
    txt = scrolledtext.ScrolledText(frame, font=("Consolas", 11), 
                                    bg="#1E1E1E",           # Темно-серый фон VS Code
                                    fg="#E0E0E0",           # Светлый текст
                                    insertbackground="#9D00FF", # Фиолетовый курсор
                                    selectbackground="#512DA8", # Цвет выделения
                                    selectforeground="white",
                                    borderwidth=0,
                                    padx=10, pady=10)       # Отступы внутри
    txt.pack(fill="both", expand=True)
    txt.insert("1.0", content)
    
    # Нижняя панель с кнопками
    btn_frame = ttk.Frame(frame, style="Sidebar.TFrame", padding=5) # Темная подложка
    btn_frame.pack(fill="x")
    
    def _save():
        current_data = load_notes()
        current_data[title] = txt.get("1.0", tk.END)
        save_notes_to_file(current_data)
        messagebox.showinfo("Сохранено", f"Заметка '{title}' сохранена!")

    def _delete():
        if messagebox.askyesno("Удаление", f"Удалить вкладку '{title}'?"):
            current_data = load_notes()
            if title in current_data:
                del current_data[title]
                save_notes_to_file(current_data)
            notebook.forget(frame)

    # Стильные кнопки
    ttk.Button(btn_frame, text="💾 Сохранить", command=_save, style="Green.TButton").pack(side="left", padx=5)
    ttk.Button(btn_frame, text="🗑 Удалить вкладку", command=_delete, style="Red.TButton").pack(side="right", padx=5)

def set_freeze_mode(enable):
    """
    Полная заморозка программы.
    enable=True: Создает экран-блокировщик, отключает крестик, останавливает потоки.
    enable=False: Удаляет блокировщик, возвращает управление.
    """
    global REMOTE_PAUSE, pause_overlay, root
    
    # 1. Останавливаем/Запускаем фоновые процессы (ваши воркеры это уже умеют)
    REMOTE_PAUSE = enable 

    if enable:
        # Если уже заблокировано - выходим
        if pause_overlay and pause_overlay.winfo_exists(): return

        # --- СОЗДАЕМ ОКНО-БЛОКИРОВЩИК ---
        pause_overlay = Toplevel(root)
        pause_overlay.title("PAUSE")
        
        # Размеры окна блокировки (чуть меньше главного или такое же)
        w, h = 400, 200
        # Центрируем
        try:
            x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
            y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
            pause_overlay.geometry(f"{w}x{h}+{x}+{y}")
        except:
            pause_overlay.geometry(f"{w}x{h}")

        pause_overlay.configure(bg="#1E1E1E")
        
        # УБИРАЕМ РАМКИ ОКНА (Нет крестика, нет заголовка)
        pause_overlay.overrideredirect(True)
        
        # Делаем его поверх всех окон
        pause_overlay.attributes('-topmost', True)
        
        # Текст
        tk.Label(pause_overlay, text="⏸ ПРОГРАММА НА ПАУЗЕ", 
                 font=("Segoe UI", 16, "bold"), fg="#FF5252", bg="#1E1E1E").pack(expand=True)
        tk.Label(pause_overlay, text="Ожидайте включения администратором...", 
                 font=("Segoe UI", 10), fg="#888", bg="#1E1E1E").pack(pady=(0, 20))

        # --- САМОЕ ГЛАВНОЕ: ЗАХВАТ УПРАВЛЕНИЯ ---
        # grab_set делает так, что нажать можно ТОЛЬКО на это окно.
        # Поскольку на нем нет кнопок, пользователь не может ничего сделать в основном окне.
        pause_overlay.grab_set()
        
        # БЛОКИРУЕМ ЗАКРЫТИЕ ГЛАВНОГО ОКНА
        # Переназначаем крестик главного окна на пустую функцию
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        print("❄️ Программа заморожена.")

    else:
        # --- РАЗМОРОЗКА ---
        if pause_overlay:
            try:
                pause_overlay.grab_release() # Отпускаем управление
                pause_overlay.destroy()
            except: pass
            pause_overlay = None

        # ВОЗВРАЩАЕМ РАБОТУ КРЕСТИКА ГЛАВНОГО ОКНА
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        
        print("🔥 Программа разморожена.")


def open_new_window():
    try: subprocess.Popen([sys.executable, __file__])
    except Exception as e: messagebox.showerror("Ошибка", f"Не удалось открыть новое окно: {e}")

def enable_hotkeys(window):
    """
    Универсальный метод: перехватывает нажатие клавиш с Ctrl.
    ИСПРАВЛЕНИЕ: Проверяет раскладку, чтобы не было двойной вставки на английском.
    """
    def check_key(event):
        # Если Tkinter распознал латинскую букву, значит раскладка EN.
        # В этом случае стандартная вставка сработает сама, нам не нужно дублировать событие.
        if event.keysym.lower() in ['c', 'v', 'x', 'a']:
            return

        # Если мы здесь, значит раскладка другая (например, RU), и Tkinter может не отработать.
        # Форсируем событие через коды клавиш.
        try:
            # 67=C, 86=V, 88=X, 65=A (Коды клавиш Windows)
            if event.keycode == 67: event.widget.event_generate("<<Copy>>")
            elif event.keycode == 86: event.widget.event_generate("<<Paste>>")
            elif event.keycode == 88: event.widget.event_generate("<<Cut>>")
            elif event.keycode == 65: event.widget.event_generate("<<SelectAll>>")
        except: pass

    try:
        window.bind_all("<Control-Key>", check_key)
    except Exception as e:
        print(f"Ошибка бинда: {e}")

def setup_scroll_canvas(canvas, inner_frame):
    """
    Настраивает скролл, который работает ВЕЗДЕ: 
    на канвасе, на фрейме и подготавливает функцию для дочерних элементов.
    """
    
    # 1. Функция самого скролла
    def _on_wheel(event):
        # Для Windows/MacOS (MouseWheel) и Linux (Button-4/5)
        if event.num == 5 or event.delta < 0:
            canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            canvas.yview_scroll(-1, "units")

    # 2. Функция, которая "включает" скролл при наведении мыши
    def _bind_to_mouse(event):
        # Биндим глобально на всё окно при наведении на элемент
        canvas.bind_all("<MouseWheel>", _on_wheel)
        canvas.bind_all("<Button-4>", _on_wheel)
        canvas.bind_all("<Button-5>", _on_wheel)

    # 3. Функция, которая "выключает" скролл, когда мышь уходит
    def _unbind_from_mouse(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    # 4. Применяем сразу к самому канвасу и главному фрейму
    for widget in [canvas, inner_frame]:
        widget.bind('<Enter>', _bind_to_mouse)
        widget.bind('<Leave>', _unbind_from_mouse)
        
    # 5. ВАЖНО: Сохраняем эти функции внутри inner_frame, 
    # чтобы потом "навесить" их на каждый чекбокс в refresh_main_checks
    inner_frame.scroll_handlers = (_bind_to_mouse, _unbind_from_mouse)

# ==========================================
# 4. ВЫБОР РЕЖИМА / СЕКЦИИ (Универсальный)
# ==========================================

def ask_section_gui(sections_dict):
    """
    Показывает окно с ЧЕКБОКСАМИ для выбора одной или нескольких секций.
    Возвращает склеенный текст выбранных секций.
    """
    if not sections_dict: return None
    
    result = {"selected_text": None, "name": None}
    section_vars = {} # Словарь для хранения состояний галочек {имя_секции: IntVer}
    
    # Создаем окно
    win = Toplevel(root)
    win.title(f"Найдено секций: {len(sections_dict)}")
    win.geometry("450x600") 
    win.configure(bg="#1F1F1F")

    # Заголовок
    tk.Label(win, text="📂 Выберите секции для работы\n(можно несколько):", 
             bg="#1F1F1F", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=10)

    # Панель управления (Выбрать все)
    ctrl_frame = tk.Frame(win, bg="#1F1F1F")
    ctrl_frame.pack(fill="x", padx=15, pady=5)
    
    def toggle_all(state):
        for var in section_vars.values():
            var.set(state)

    tk.Button(ctrl_frame, text="✅ Выбрать все", command=lambda: toggle_all(1), 
              bg="#2E3440", fg="#A3BE8C", font=("Consolas", 9), bd=0, padx=10).pack(side="left")
    
    tk.Button(ctrl_frame, text="❌ Снять все", command=lambda: toggle_all(0), 
              bg="#2E3440", fg="#BF616A", font=("Consolas", 9), bd=0, padx=10).pack(side="right")

    # === КОНТЕЙНЕР ДЛЯ СКРОЛЛА ===
    container = ttk.Frame(win)
    container.pack(fill="both", expand=True, padx=10, pady=5)
    
    canvas = tk.Canvas(container, bg="#1F1F1F", highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=400)
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Скролл мышкой
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # === ГЕНЕРАЦИЯ ЧЕКБОКСОВ ===
    # Стиль для чекбоксов
    style = ttk.Style()
    style.configure("Dark.TCheckbutton", background="#1F1F1F", foreground="#E0E0E0", font=("Consolas", 11))

    for sec_name in sections_dict.keys():
        var = tk.IntVar()
        section_vars[sec_name] = var
        
        # Фрейм для красивого отступа
        row = tk.Frame(scrollable_frame, bg="#1F1F1F")
        row.pack(fill="x", pady=2, padx=5)
        
        chk = ttk.Checkbutton(row, text=f" {sec_name}", variable=var, style="Dark.TCheckbutton")
        chk.pack(side="left", fill="x", expand=True, padx=5, pady=5)

    # === ЛОГИКА ПОДТВЕРЖДЕНИЯ ===
    def confirm_selection():
        selected_keys = [k for k, v in section_vars.items() if v.get() == 1]
        
        if not selected_keys:
            messagebox.showwarning("!", "Выберите хотя бы одну секцию!")
            return
        
        # 1. Склеиваем текст всех выбранных секций
        combined_text = ""
        for k in selected_keys:
            # Добавляем разделитель на всякий случай, если его нет
            combined_text += sections_dict[k] + "\n"

        # 2. Формируем красивое название для логов/отчета
        if len(selected_keys) == 1:
            final_name = selected_keys[0]
        elif len(selected_keys) == len(sections_dict):
            final_name = "Все секции"
        else:
            # Если выбрано несколько, перечисляем (Секция 1 + Секция 3)
            # Или диапазон, если хочется короче
            final_name = " + ".join(selected_keys)
            if len(final_name) > 50: # Если слишком длинное название
                final_name = f"{selected_keys[0]} ... {selected_keys[-1]} ({len(selected_keys)} шт)"

        result["selected_text"] = combined_text
        result["name"] = final_name
        
        canvas.unbind_all("<MouseWheel>")
        win.destroy()

    # Кнопка подтверждения внизу
    btn_confirm = tk.Button(win, text="🚀 ПРОДОЛЖИТЬ С ВЫБРАННЫМИ", command=confirm_selection, 
                            bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), pady=10)
    btn_confirm.pack(fill="x", padx=20, pady=15)

    # Центрируем и ждем
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = win.winfo_width()
    h = win.winfo_height()
    win.geometry(f"+{(sw - w)//2}+{(sh - h)//2}")

    win.transient(root)
    win.grab_set()
    root.wait_window(win)
    
    canvas.unbind_all("<MouseWheel>") # Чистим бинды
    
    return result


# ==========================================
# 5. ОКНО ОБЗОРА ШТРУДИРОВКИ (ShtrudirovkaReview)
# ==========================================

class ShtrudirovkaReviewWindow:
    """
    Окно для просмотра найденных групп/каналов при парсинге.
    Позволяет выбрать галочками нужные сущности для обработки.
    """
    def __init__(self, parent, items, title="Результаты поиска"):
        self.win = Toplevel(parent)
        self.win.title(title)
        self.win.geometry("650x500")
        self.win.configure(bg="#121212")
        
        self.items = items
        self.selected_items = [] # Результат

        tk.Label(self.win, text=f"Найдено: {len(items)}", bg="#121212", fg="#00E676", font=("Segoe UI", 12, "bold")).pack(pady=10)

        # Таблица
        cols = ("id", "title")
        self.tree = ttk.Treeview(self.win, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("id", text="Username / ID")
        self.tree.heading("title", text="Название")
        self.tree.column("id", width=200)
        self.tree.column("title", width=400)
        
        sb = ttk.Scrollbar(self.win, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        sb.pack(side="right", fill="y", pady=5)

        # Заполнение
        for item in items:
            # item может быть словарем или объектом, адаптируем:
            if isinstance(item, dict):
                val_id = item.get('username') or item.get('id', 'Unknown')
                val_title = item.get('title', 'No Title')
            else:
                # Если это Telethon entity
                val_id = getattr(item, 'username', getattr(item, 'id', 'Unknown'))
                val_title = getattr(item, 'title', 'No Title')
                
            self.tree.insert("", "end", values=(val_id, val_title))
            
        # Выделить всё
        self.tree.selection_set(self.tree.get_children())

        # Кнопка подтверждения
        btn = tk.Button(self.win, text="ПРОДОЛЖИТЬ С ВЫБРАННЫМИ", command=self.confirm,
                       bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), pady=8)
        btn.pack(side="bottom", fill="x", padx=10, pady=10)

        self.win.transient(parent)
        self.win.grab_set()
        parent.wait_window(self.win)

    def confirm(self):
        # Собираем индексы выбранных элементов
        selected_iids = self.tree.selection()
        all_iids = self.tree.get_children()
        
        # Сопоставляем iid с исходным списком self.items
        # (Т.к. порядок вставки совпадал с порядком списка)
        for iid in selected_iids:
            index = all_iids.index(iid)
            self.selected_items.append(self.items[index])
            
        self.win.destroy()