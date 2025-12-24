import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog, Toplevel
import asyncio
import threading
import re
import random
import os
import hashlib
import sys
import json
import time

# === ИМПОРТЫ (Как в вашем файле) ===
try:
    import requests
    from bs4 import BeautifulSoup
    from telethon import TelegramClient, functions, types
    from telethon.tl.types import InputCheckPasswordSRP, ChatAdminRights, InputPhoneContact
    from telethon.errors import (
        FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError, 
        ApiIdInvalidError, PhoneNumberInvalidError, UserDeactivatedError, AuthKeyError
    )
except ImportError:
    messagebox.showerror("Ошибка", "Не найдены библиотеки!\nУстановите: pip install telethon requests beautifulsoup4")
    sys.exit()

ACCOUNTS_FILE = "accounts.json"

# ==============================================================================
# === КЛАСС ДЛЯ ПОЛУЧЕНИЯ КЛЮЧЕЙ (ИЗ ВАШЕГО ФАЙЛА) ===
# ==============================================================================
class TelegramWebClient:
    BASE_URL = "https://my.telegram.org"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://my.telegram.org/auth',
            'Origin': 'https://my.telegram.org',
            'X-Requested-With': 'XMLHttpRequest',
        })
        self.random_hash = None

    def send_password(self, phone):
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        time.sleep(1)
        try:
            self.session.get(f"{self.BASE_URL}/auth", timeout=10)
            resp = self.session.post(f"{self.BASE_URL}/auth/send_password", data={"phone": clean_phone}, timeout=10)
        except Exception as e:
            raise Exception(f"Ошибка сети: {e}")
            
        try:
            data = resp.json()
            if "random_hash" not in data:
                raise Exception(data.get("error", resp.text))
            self.random_hash = data["random_hash"]
            return clean_phone
        except:
            if "Too many tries" in resp.text:
                raise Exception("БАН IP (Too many tries). Включите VPN или подождите.")
            raise Exception("Сайт вернул ошибку (не JSON).")

    def login(self, phone, code):
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        time.sleep(0.5)
        data = {"phone": clean_phone, "random_hash": self.random_hash, "password": code}
        try:
            resp = self.session.post(f"{self.BASE_URL}/auth/login", data=data, timeout=10)
        except Exception as e:
            raise Exception(f"Ошибка сети при входе: {e}")
        
        if resp.text.strip() == "true": return True
        if "invalid code" in resp.text.lower(): raise Exception("Неверный код!")
        raise Exception(f"Ошибка входа: {resp.text[:50]}")

    def get_app_data(self):
        time.sleep(1)
        try:
            resp = self.session.get(f"{self.BASE_URL}/apps", timeout=10)
        except Exception as e:
            raise Exception(f"Ошибка получения Apps: {e}")
            
        html = resp.text
        if "Login" in html: raise Exception("Авторизация слетела.")

        def find_keys_in_text(html_content):
            soup = BeautifulSoup(html_content, 'html.parser')
            api_id = None
            api_hash = None
            id_input = soup.find('input', {'name': 'api_id'})
            hash_input = soup.find('input', {'name': 'api_hash'})
            if id_input and hash_input:
                return {'api_id': id_input.get('value'), 'api_hash': hash_input.get('value')}
            
            # Если нет инпутов, ищем в span (старый дизайн)
            spans = soup.find_all('span', attrs={'onclick': 'this.select();'})
            for span in spans:
                text = span.get_text(strip=True)
                if text.isdigit() and not api_id: api_id = text
                elif len(text) == 32 and all(c in '0123456789abcdef' for c in text.lower()): api_hash = text
            if api_id and api_hash: return {'api_id': api_id, 'api_hash': api_hash}
            return None
            
        keys = find_keys_in_text(html)
        if keys: return keys

        # Если ключей нет, создаем приложение
        soup = BeautifulSoup(html, 'html.parser')
        hash_input = soup.find('input', {'name': 'hash'})
        if not hash_input: raise Exception("Не найдена форма создания и ключи не найдены.")
        app_hash = hash_input.get('value')
        
        import string
        r_str = ''.join(random.choices(string.ascii_lowercase, k=8))
        create_data = {
            "hash": app_hash, "app_title": "Android App", "app_shortname": f"android{r_str}",
            "app_url": "", "app_platform": "android", "app_desc": "User application"
        }
        time.sleep(2)
        self.session.post(f"{self.BASE_URL}/apps/create", data=create_data)
        
        time.sleep(1) 
        resp = self.session.get(f"{self.BASE_URL}/apps", timeout=10) 
        keys = find_keys_in_text(resp.text)
        if keys: return keys
        
        raise Exception("Не удалось прочитать ключи после создания.")

# ==============================================================================
# === РУЧНОЙ РАСЧЕТ SRP (ДЛЯ PYTHON 3.14) ===
# ==============================================================================
def compute_srp_check_manual(algo, password):
    def get_byte_array(integer):
        return int.to_bytes(integer, (integer.bit_length() + 7) // 8, 'big')

    p = int.from_bytes(algo.p, 'big'); g = algo.g
    salt1 = algo.salt1; salt2 = algo.salt2
    g_b = int.from_bytes(algo.g_b, 'big')

    p_bytes = get_byte_array(p); g_bytes = get_byte_array(g)
    k = int.from_bytes(hashlib.sha256(p_bytes + g_bytes).digest(), 'big')

    password_bytes = password.encode('utf-8')
    x = int.from_bytes(hashlib.sha256(salt2 + hashlib.sha256(salt1 + password_bytes).digest()).digest(), 'big')

    v = pow(g, x, p); a = int.from_bytes(os.urandom(256), 'big')
    g_a = pow(g, a, p)

    g_a_bytes = get_byte_array(g_a); g_b_bytes = get_byte_array(g_b)
    u = int.from_bytes(hashlib.sha256(g_a_bytes + g_b_bytes).digest(), 'big')

    if g_b < k * v: base = g_b + p * ((k * v) // p + 1) - k * v
    else: base = g_b - k * v
        
    s = pow(base, a + u * x, p)
    k_hash = hashlib.sha256(get_byte_array(s)).digest()

    p_hash = hashlib.sha256(p_bytes).digest()
    g_hash = hashlib.sha256(g_bytes).digest()
    h_xor = bytes(x ^ y for x, y in zip(p_hash, g_hash))
    
    m1 = hashlib.sha256(h_xor + hashlib.sha256(salt1).digest() + hashlib.sha256(salt2).digest() + g_a_bytes + g_b_bytes + k_hash).digest()

    return InputCheckPasswordSRP(srp_id=algo.srp_id, A=g_a_bytes, M1=m1)

# ==============================================================================
# === ВВОД КОДА (GUI ИЗ ВАШЕГО ФАЙЛА) ===
# ==============================================================================
def ask_code_gui(root_window, phone, is_password=False):
    """
    Показывает стильное темное окно для ввода кода или пароля.
    """
    prompt = f"🔐 Введите ОБЛАЧНЫЙ ПАРОЛЬ (2FA) для {phone}:" if is_password else f"📩 Введите код из Telegram для {phone}:"
    result_data = {"value": None}
    wait_event = threading.Event()

    def show():
        try:
            win = Toplevel(root_window)
            win.title("Авторизация Telegram")
            
            # Размеры
            w, h = 420, 240
            try:
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
            except: win.geometry(f"{w}x{h}")
                
            win.resizable(False, False)
            win.configure(bg="#1E1E1E")      # Темный фон
            win.attributes('-topmost', True) # Поверх всех окон

            # Заголовок
            tk.Label(win, text=prompt, justify="center", bg="#1E1E1E", fg="#00E676", 
                     font=("Segoe UI", 11, "bold"), wraplength=380).pack(pady=(25, 15))
            
            show_char = "*" if is_password else ""
            input_var = tk.StringVar()
            
            # Поле ввода (Черное с белым текстом)
            e = tk.Entry(win, textvariable=input_var, font=("Consolas", 16), show=show_char, justify="center",
                         bg="#252526", fg="white", insertbackground="white", relief="flat", bd=5)
            e.pack(fill="x", padx=50, pady=5, ipady=3)
            e.focus_force()

            def submit(*args):
                val = input_var.get().strip()
                if val:
                    result_data["value"] = val
                wait_event.set()
                win.destroy()

            def on_close():
                wait_event.set()
                win.destroy()

            # Кнопка (Зеленая)
            btn = tk.Button(win, text="ПОДТВЕРДИТЬ ВХОД", command=submit, 
                            bg="#00E676", fg="black", font=("Segoe UI", 10, "bold"), 
                            activebackground="#00C853", activeforeground="black",
                            relief="flat", cursor="hand2")
            btn.pack(fill="x", padx=50, pady=25, ipady=5)

            e.bind('<Return>', submit)
            win.protocol("WM_DELETE_WINDOW", on_close)
            
            win.transient(root_window)
            win.grab_set()
            
        except Exception as e:
            print(f"Ошибка GUI: {e}")
            wait_event.set()

    root_window.after(0, show)
    wait_event.wait()
    return result_data["value"]

# ==============================================================================
# === ГЛАВНОЕ ПРИЛОЖЕНИЕ ===
# ==============================================================================
class TapokManagerApp:
    def __init__(self, root):
        self.root = root
        # Если класс используется как часть большого приложения (Sidebar), 
        # то root может быть фреймом, поэтому title/geometry могут не сработать, 
        # но оставим для совместимости с отдельным запуском.
        try:
            self.root.title("👟 ТАПОК: Менеджер Аккаунтов")
            self.root.geometry("650x800")
            self.root.configure(bg="#1E1E1E")
        except: pass
        
        self.accounts = self.load_accounts()
        self.stop_event = threading.Event()
        self.setup_ui()

    def load_accounts(self):
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return []
        return []

    def save_accounts(self):
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.accounts, f, indent=4, ensure_ascii=False)

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#1E1E1E", foreground="#FFFFFF", font=("Segoe UI", 10))
        style.configure("Green.TButton", background="#00E676", foreground="black", font=("Segoe UI", 10, "bold"))
        style.map("Green.TButton", background=[("active", "#00C853")])
        style.configure("Treeview", background="#252526", foreground="white", fieldbackground="#252526", font=("Consolas", 10))
        style.configure("Treeview.Heading", background="#333", foreground="white", font=("Segoe UI", 9, "bold"))
        
        main_frame = tk.Frame(self.root, bg="#1E1E1E", padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        # === 1. ВЫБОР АККАУНТА ===
        tk.Label(main_frame, text="1. Аккаунты (Мейкеры):", bg="#1E1E1E", fg="#00E676", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        
        acc_btn_frame = tk.Frame(main_frame, bg="#1E1E1E")
        acc_btn_frame.pack(fill="x", pady=5)
        
        # Кнопка вызывает окно добавления (новое)
        tk.Button(acc_btn_frame, text="➕ Добавить (Получить ключи)", command=self.open_add_account_window, bg="#00E676", fg="black", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
        tk.Button(acc_btn_frame, text="❌ Удалить", command=self.delete_account, bg="#D32F2F", fg="white").pack(side="right")

        columns = ("phone", "name", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=6)
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("name", text="Имя")
        self.tree.heading("status", text="Статус")
        
        self.tree.column("phone", width=140)
        self.tree.column("name", width=200)
        self.tree.column("status", width=100)
        self.tree.pack(fill="x", pady=5)
        
        # === КОНТЕКСТНОЕ МЕНЮ (ДЛЯ ВХОДА) ===
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg="#252526", fg="white", activebackground="#00E676", activeforeground="black")
        self.ctx_menu.add_command(label="🔄 Войти / Проверить валид", command=self.context_login_check)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="❌ Удалить", command=self.delete_account)
        
        self.tree.bind("<Button-3>", self.show_context_menu)

        self.refresh_table()
        tk.Frame(main_frame, height=1, bg="#333").pack(fill="x", pady=15)

        # === 2. НАСТРОЙКИ ТАПКА ===
        tk.Label(main_frame, text="2. Настройки создания:", bg="#1E1E1E", fg="#00E676", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        f_sets = tk.Frame(main_frame, bg="#1E1E1E")
        f_sets.pack(fill="x")
        
        tk.Label(f_sets, text="Кол-во групп:", bg="#1E1E1E", fg="#AAA").grid(row=0, column=0, sticky="w")
        self.e_count = tk.Entry(f_sets, font=("Consolas", 11), justify="center", bg="#252526", fg="white", width=10)
        self.e_count.insert(0, "5")
        self.e_count.grid(row=0, column=1, padx=10, sticky="w")

        tk.Label(f_sets, text="Пароль 2FA:", bg="#1E1E1E", fg="#FFAB40").grid(row=1, column=0, sticky="w", pady=5)
        self.e_pwd = tk.Entry(f_sets, font=("Consolas", 11), justify="center", show="*", bg="#252526", fg="white", width=20)
        self.e_pwd.grid(row=1, column=1, padx=10, sticky="w", pady=5)
        tk.Label(f_sets, text="(Для передачи владельца)", bg="#1E1E1E", fg="#555").grid(row=1, column=2, sticky="w")

        tk.Label(main_frame, text="Список Якорей:", bg="#1E1E1E", fg="#AAA").pack(anchor="w", pady=(10,0))
        self.txt_anchors = scrolledtext.ScrolledText(main_frame, height=6, font=("Consolas", 10), bg="#252526", fg="#E0E0E0", insertbackground="white", borderwidth=0)
        self.txt_anchors.pack(fill="x", pady=5)

        # === ЗАПУСК ===
        btn_frame = tk.Frame(main_frame, bg="#1E1E1E")
        btn_frame.pack(fill="x", pady=15)
        self.btn_start = ttk.Button(btn_frame, text="🚀 ЗАПУСТИТЬ ТАПОК", command=self.start_tapok_thread, style="Green.TButton")
        self.btn_start.pack(side="left", fill="x", expand=True)
        tk.Button(btn_frame, text="СТОП", command=self.stop_process, bg="#D32F2F", fg="white").pack(side="right", padx=(5,0))

        self.log_widget = scrolledtext.ScrolledText(main_frame, height=8, font=("Consolas", 9), bg="#111", fg="#00FF00", state='disabled')
        self.log_widget.pack(fill="both", expand=True)

    # === ЛОГИКА МЕНЮ ===
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.ctx_menu.post(event.x_root, event.y_root)

    def context_login_check(self):
        """Запускает проверку/вход для выбранного аккаунта."""
        sel = self.tree.selection()
        if not sel: return
        
        phone = self.tree.item(sel[0])['values'][0]
        # Ищем полные данные аккаунта (включая ключи)
        # Очищаем телефон от форматирования для поиска
        search_phone = str(phone).replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        
        acc_data = next((a for a in self.accounts if str(a['phone']) == search_phone), None)
        
        if acc_data:
            threading.Thread(target=self.run_login_check_thread, args=(acc_data,), daemon=True).start()
        else:
            messagebox.showerror("Ошибка", "Данные аккаунта не найдены в памяти.")

    def run_login_check_thread(self, acc_data):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        phone = acc_data['phone']
        api_id = int(acc_data['api_id'])
        api_hash = acc_data['api_hash']

        client = TelegramClient(f"session_{phone}", api_id, api_hash, loop=loop)

        async def _check():
            self.log(f"🔄 Проверка входа для {phone}...")
            try:
                await client.connect()
                
                if not await client.is_user_authorized():
                    self.log(f"⚠️ {phone}: Не авторизован. Запрашиваю код...")
                    try:
                        await client.send_code_request(phone)
                    except FloodWaitError as e:
                        self.log(f"❌ Флуд! Ждать {e.seconds} сек.", "red"); return
                    except Exception as e:
                        self.log(f"❌ Ошибка отправки кода: {e}", "red"); return

                    # ВВОД КОДА
                    code = await loop.run_in_executor(None, ask_code_gui, self.root, phone, False)
                    if not code:
                        self.log("❌ Ввод отменен.", "red"); return

                    try:
                        await client.sign_in(phone, code)
                    except SessionPasswordNeededError:
                        self.log("🔐 Нужен 2FA пароль...")
                        pwd = await loop.run_in_executor(None, ask_code_gui, self.root, phone, True)
                        if not pwd: return
                        
                        pwd_req = await client(functions.account.GetPasswordRequest())
                        check_hash = compute_srp_check_manual(pwd_req.current_algo, pwd)
                        await client(functions.auth.CheckPasswordRequest(password=check_hash))
                
                # УСПЕХ
                me = await client.get_me()
                self.log(f"✅ {phone} ВАЛИД! Юзер: @{me.username}", "#00E676")
                
                # Обновляем статус
                acc_data['status'] = "Active"
                acc_data['username'] = me.username or ""
                acc_data['name'] = f"{me.first_name} {me.last_name or ''}".strip()
                
                self.root.after(0, self.save_accounts)
                self.root.after(0, self.refresh_table)
                self.root.after(0, lambda: messagebox.showinfo("Успех", f"Аккаунт {phone} активен!\nUser: {me.first_name}"))

            except Exception as e:
                self.log(f"❌ Ошибка проверки: {e}", "red")
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось войти:\n{e}"))
            finally:
                if client.is_connected(): await client.disconnect()

        loop.run_until_complete(_check())
        loop.close()

    # ==========================================================================
    # === ОКНО ДОБАВЛЕНИЯ (ИСПРАВЛЕНО: ТОЛЬКО СОХРАНЕНИЕ) ===
    # ==========================================================================
    def open_add_account_window(self):
        d = Toplevel(self.root)
        d.title("Добавить аккаунт (Web Auto)")
        d.geometry("400x550")
        d.configure(bg="#2E3440")
        
        try:
            sw = d.winfo_screenwidth(); sh = d.winfo_screenheight()
            d.geometry(f"+{(sw-400)//2}+{(sh-550)//2}")
        except: pass
        
        cf = ttk.Frame(d, padding=20)
        cf.pack(fill="both", expand=True)
        
        ttk.Label(cf, text="Номер телефона (+7...):").pack(anchor="w")
        e_ph = ttk.Entry(cf, font=("Consolas", 12))
        e_ph.pack(fill="x", pady=(5, 15))
        e_ph.focus_set()
        
        lbl_st = ttk.Label(cf, text="Нажмите кнопку для авто-получения ключей", foreground="#88C0D0", font=("Segoe UI", 9), wraplength=350)
        lbl_st.pack(pady=5)

        lf_api = ttk.LabelFrame(cf, text=" API Keys ", padding=10)
        lf_api.pack(fill="x", pady=10)
        
        ttk.Label(lf_api, text="API ID:").pack(anchor="w")
        e_id = ttk.Entry(lf_api)
        e_id.pack(fill="x", pady=(0,5))
        ttk.Label(lf_api, text="API Hash:").pack(anchor="w")
        e_hash = ttk.Entry(lf_api)
        e_hash.pack(fill="x")

        # --- АВТОМАТИКА WEB ---
        def run_auto():
            phone = e_ph.get().strip()
            if not phone:
                messagebox.showerror("Ошибка", "Введите номер!")
                return
            
            lbl_st.config(text="🚀 Запуск Web-парсера...", foreground="white")
            btn_auto.config(state="disabled")
            
            def thread_auto():
                def update_ui(text, color="white", is_error=False):
                    try:
                        if d.winfo_exists(): lbl_st.config(text=text, foreground=color)
                        if is_error: messagebox.showerror("Ошибка", text)
                    except: pass

                try:
                    update_ui("⏳ Подключение к my.telegram.org...", "#88C0D0")
                    wc = TelegramWebClient()
                    
                    clean_phone = wc.send_password(phone)
                    update_ui("⌨ Введите Web-код (из Telegram)...", "white")
                    
                    # Окно ввода кода
                    code = ask_code_gui(d, clean_phone, False)
                    if not code: 
                        update_ui("❌ Отмена.", "#BF616A")
                        try: d.after(0, lambda: btn_auto.config(state="normal"))
                        except: pass
                        return

                    update_ui("🔐 Входим на сайт...", "#88C0D0")
                    wc.login(clean_phone, code)
                    
                    update_ui("📂 Получаем ключи...", "#88C0D0")
                    keys = wc.get_app_data()
                    
                    def finish_success():
                        try:
                            if not d.winfo_exists(): return
                            e_id.delete(0, tk.END); e_id.insert(0, keys['api_id'])
                            e_hash.delete(0, tk.END); e_hash.insert(0, keys['api_hash'])
                            
                            update_ui("✅ Ключи получены! Сохраняю...", "#A3BE8C")
                            self.save_manual_logic(clean_phone, str(keys['api_id']), str(keys['api_hash']), d)
                        except Exception as fin_e: print(f"ERR: {fin_e}")
                        finally:
                            try: btn_auto.config(state="normal")
                            except: pass

                    d.after(0, finish_success)

                except Exception as e:
                    d.after(0, lambda: update_ui(f"❌ {e}", "#BF616A", True))
                    try: d.after(0, lambda: btn_auto.config(state="normal"))
                    except: pass

            threading.Thread(target=thread_auto, daemon=True).start()

        btn_auto = ttk.Button(cf, text="⚡ Получить ключи (Web Auto)", command=run_auto)
        btn_auto.pack(fill="x", pady=20)
        
        # --- РУЧНОЕ СОХРАНЕНИЕ ---
        def manual_save_wrapper():
            p = e_ph.get().strip()
            i = e_id.get().strip()
            h = e_hash.get().strip()
            if p and i and h:
                self.save_manual_logic(p, i, h, d)
            else:
                messagebox.showwarning("Внимание", "Заполните все поля!")

        ttk.Label(cf, text="— ИЛИ ВРУЧНУЮ —", foreground="#4C566A", font=("Segoe UI", 8)).pack(pady=2)
        btn_save = ttk.Button(cf, text="💾 Просто сохранить", command=manual_save_wrapper)
        btn_save.pack(fill="x")

    def save_manual_logic(self, phone, api_id, api_hash, dialog):
        """
        Только сохраняет данные. БЕЗ АВТО-ВХОДА.
        """
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        session_file = f"session_{clean_phone}.session"
        
        # 1. Проверяем дубликат
        if any(s.get('phone') == clean_phone for s in self.accounts):
            messagebox.showwarning("Дубликат", f"Номер {clean_phone} уже есть в списке.")
            return

        # 2. Сохраняем "черновик" аккаунта
        new_acc = {
            "phone": clean_phone,
            "session_file": session_file,
            "api_id": api_id,
            "api_hash": api_hash,
            "name": "Не авторизован",
            "status": "Wait Auth"
        }
        self.accounts.append(new_acc)
        self.save_accounts()
        self.refresh_table()
        
        dialog.destroy()

        # 3. ПРОСТО СООБЩЕНИЕ
        messagebox.showinfo("Сохранено", f"Аккаунт {clean_phone} добавлен!\n\n👉 Нажмите ПКМ по нему в таблице и выберите 'Войти', чтобы авторизоваться.")

    # === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
    def log(self, text, color="white"):
        self.root.after(0, lambda: self._log_gui(text))

    def _log_gui(self, text):
        self.log_widget.config(state='normal')
        self.log_widget.insert(tk.END, f"{text}\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state='disabled')

    def refresh_table(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        for acc in self.accounts:
            # Красивый вывод
            ph = acc['phone']
            nm = acc.get('name', 'Unknown')
            st = acc.get('status', '?')
            self.tree.insert("", "end", values=(ph, nm, st))

    def delete_account(self):
        sel = self.tree.selection()
        if not sel: return
        phone = self.tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Удаление", f"Удалить {phone}?"):
            self.accounts = [a for a in self.accounts if str(a['phone']) != str(phone)]
            self.save_accounts(); self.refresh_table()

    def stop_process(self):
        self.stop_event.set()
        self.log("🛑 Остановка...")

    def start_tapok_thread(self):
        sel = self.tree.selection()
        if not sel: messagebox.showerror("Ошибка", "Выберите Мейкера!"); return
        phone = self.tree.item(sel[0])['values'][0]
        acc = next((a for a in self.accounts if str(a['phone']) == str(phone)), None)
        if not acc: return

        try: cnt = int(self.e_count.get().strip())
        except: messagebox.showerror("Ошибка", "Число групп неверно!"); return
        
        anchors = [l.strip() for l in self.txt_anchors.get("1.0", tk.END).splitlines() if l.strip()]
        if not anchors: messagebox.showerror("Ошибка", "Нет якорей!"); return

        pwd = self.e_pwd.get().strip()
        
        self.stop_event.clear()
        self.btn_start.config(state='disabled')
        self.log_widget.config(state='normal'); self.log_widget.delete("1.0", tk.END); self.log_widget.config(state='disabled')
        
        threading.Thread(target=self.run_worker, args=(acc, cnt, anchors, pwd), daemon=True).start()

    def run_worker(self, acc, count, anchors, password):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.worker(acc, count, anchors, password))
        loop.close()
        self.root.after(0, lambda: self.btn_start.config(state='normal'))

    async def worker(self, acc, group_count, anchors_raw, password_2fa):
        self.log(f"🚀 Запуск Тапка...")
        client = TelegramClient(f"session_{acc['phone']}", int(acc['api_id']), acc['api_hash'])
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                self.log("❌ Сессия не авторизована! Удалите её и добавьте заново.", "red"); return

            # 1. Проверка пароля (если введен)
            if password_2fa:
                self.log("🔐 Проверяем 2FA...")
                try:
                    pwd_req = await client(functions.account.GetPasswordRequest())
                    check_hash = compute_srp_check_manual(pwd_req.current_algo, password_2fa)
                    check_hash.srp_id = pwd_req.srp_id
                    await client(functions.auth.CheckPasswordRequest(password=check_hash))
                    self.log("✅ Пароль ОК.")
                except Exception as e:
                    self.log(f"⚠️ Пароль не подошел ({e}). Права владельца не передадим.")
                    password_2fa = None

            # 2. Якоря
            resolved = []
            self.log("🔍 Якоря...")
            for a_str in anchors_raw:
                a_str = a_str.replace("@", "").strip()
                ent = None
                if re.match(r'^\+?\d+$', a_str):
                    try:
                        phone = a_str if a_str.startswith("+") else f"+{a_str}"
                        cont = InputPhoneContact(client_id=random.randint(10000,99999), phone=phone, first_name=f"A_{a_str[-4:]}", last_name="B")
                        res = await client(functions.contacts.ImportContactsRequest([cont]))
                        if res.users: ent = res.users[0]
                    except: pass
                else:
                    try: ent = await client.get_input_entity(a_str)
                    except: pass
                if ent: resolved.append(ent)

            if not resolved: self.log("❌ Нет якорей."); return

            # 3. Создание
            for i in range(1, group_count + 1):
                if self.stop_event.is_set(): break
                title = f"{i:02d}"
                try:
                    primary = resolved[0]
                    res = await client(functions.channels.CreateChannelRequest(title=title, about="", megagroup=True))
                    chat = res.chats[0]
                    self.log(f"📁 [{title}] Создана.")

                    try: await client(functions.channels.InviteToChannelRequest(channel=chat, users=[primary]))
                    except: pass

                    rights = ChatAdminRights(change_info=True, post_messages=True, edit_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=True, anonymous=False, manage_call=True, other=True)
                    await client(functions.channels.EditAdminRequest(channel=chat, user_id=primary, admin_rights=rights, rank="Owner"))
                    self.log("   👮 Админ выдан.")

                    if password_2fa:
                        try:
                            req = await client(functions.account.GetPasswordRequest())
                            h = compute_srp_check_manual(req.current_algo, password_2fa)
                            await client(functions.channels.EditCreatorRequest(channel=chat, user_id=primary, password=h))
                            self.log("   👑 ВЛАДЕЛЕЦ ПЕРЕДАН!")
                        except Exception as e:
                            self.log(f"   ❌ Сбой владельца: {e}")

                    if len(resolved) > 1:
                        try: await client(functions.channels.InviteToChannelRequest(channel=chat, users=resolved[1:]))
                        except: pass
                    
                    self.log("⏳ Пауза 60 сек...")
                    await asyncio.sleep(60)
                except FloodWaitError as e:
                    self.log(f"⏳ FLOOD: {e.seconds} сек!")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    self.log(f"❌ Ошибка: {e}")

        except Exception as e:
            self.log(f"CRITICAL: {e}")
        finally:
            if client.is_connected(): await client.disconnect()
            self.log("🏁 Готово.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TapokManagerApp(root)
    root.mainloop()