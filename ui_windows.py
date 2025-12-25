import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, scrolledtext
import config

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

def open_word_settings(parent, filename="words.txt", title="Список слов"):
    """
    Простой текстовый редактор для редактирования файла со словами.
    """
    win = Toplevel(parent)
    win.title(title)
    win.geometry("400x500")
    win.configure(bg="#1E1E1E")

    # Текстовое поле с прокруткой
    txt_area = scrolledtext.ScrolledText(win, width=40, height=20, font=("Consolas", 10),
                                        bg="#252525", fg="#00E676", insertbackground="white", bd=0)
    txt_area.pack(fill="both", expand=True, padx=10, pady=10)

    # Попытка загрузить существующий файл
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            txt_area.insert("1.0", content)
    except FileNotFoundError:
        pass # Если файла нет, поле будет пустым

    def save_and_close():
        content = txt_area.get("1.0", tk.END).strip()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Успех", "Список сохранен!", parent=win)
            win.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}", parent=win)

    # Кнопка сохранения
    btn_save = tk.Button(win, text="💾 СОХРАНИТЬ И ЗАКРЫТЬ", command=save_and_close,
                        bg="#448AFF", fg="white", font=("Segoe UI", 10, "bold"), cursor="hand2")
    btn_save.pack(fill="x", padx=10, pady=10)


# ==========================================
# 4. ВЫБОР РЕЖИМА / СЕКЦИИ (Универсальный)
# ==========================================

def ask_section_gui(parent, sections):
    """
    Показывает окно с кнопками для выбора одного из вариантов.
    sections: список строк ["Вариант 1", "Вариант 2"]
    """
    win = Toplevel(parent)
    win.title("Сделайте выбор")
    win.geometry("300x400")
    win.configure(bg="#222")
    
    selected = tk.StringVar(value="")
    
    tk.Label(win, text="Выберите действие:", bg="#222", fg="white", font=("Segoe UI", 11)).pack(pady=15)

    for sec in sections:
        b = tk.Button(win, text=sec, 
                     command=lambda s=sec: [selected.set(s), win.destroy()],
                     bg="#333", fg="white", font=("Segoe UI", 10),
                     activebackground="#00E676", activeforeground="black",
                     anchor="w", padx=20, pady=5, cursor="hand2")
        b.pack(fill="x", padx=20, pady=5)

    # Модальность
    win.transient(parent)
    win.grab_set()
    parent.wait_window(win)
    
    return selected.get()


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