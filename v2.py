import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel
import asyncio
import threading
from telethon import TelegramClient, functions, types
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError
)
import os
import json
import random
import time
import subprocess
import sys
import requests
import re
from bs4 import BeautifulSoup

# 🛑 Глобальные переменные
stop_flag = threading.Event()
root = None
log_widget = None
check_vars = []
refresh_ui_callback = None 

# 🎨 ЦВЕТА ДЛЯ ЛОГОВ
TAG_COLORS = {
    "SUCCESS": "#2e7d32", 
    "ERROR": "#c62828",   
    "INFO": "#000000",    
    "WAIT": "#0277bd",    
    "WARN": "#ef6c00"     
}

# === WEB CLIENT CLASS (АВТО-РЕГИСТРАЦИЯ) ===
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
                raise Exception("БАН IP (Too many tries). Включите VPN.")
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
            
            spans = soup.find_all('span', attrs={'onclick': 'this.select();'})
            for span in spans:
                text = span.get_text(strip=True)
                if text.isdigit() and not api_id: api_id = text
                elif len(text) == 32 and all(c in '0123456789abcdef' for c in text.lower()): api_hash = text
            if api_id and api_hash: return {'api_id': api_id, 'api_hash': api_hash}
            return None
            
        keys = find_keys_in_text(html)
        if keys: return keys

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
        resp = self.session.post(f"{self.BASE_URL}/apps/create", data=create_data)
        keys = find_keys_in_text(resp.text)
        if keys: return keys
        raise Exception("Не удалось прочитать ключи после создания.")

# 📝 ЛОГИРОВАНИЕ
def log_msg(tag, text):
    if log_widget:
        def _log():
            log_widget.config(state='normal')
            log_widget.insert(tk.END, text + "\n", tag)
            log_widget.see(tk.END)
            log_widget.config(state='disabled')
        log_widget.after(0, _log)

# ⚙️ CONFIG
def load_config(filepath="config.json"):
    defaults = {
        "delay_creation": "180", 
        "delay_username": "15",
        "delay_contact": "20",
        "delay_cleanup": "10",
        "random_delay": "1",
        "add_username": "1",
        "add_contacts": "1",
        "contact_mode": "1",
        "separators": "|",
        "words": "Чат",
        "use_random_words": "1",
        "use_homoglyphs": "0"
    }
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except: pass
    return defaults

def save_config(config, filepath="config.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))

# 📁 SESSIONS
def load_sessions(filepath="sessions.json"):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def save_sessions(sessions, filepath="sessions.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=4)
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))

def update_session_info(phone, full_name, username):
    """Обновляет имя профиля в JSON файле"""
    sessions = load_sessions()
    updated = False
    for s in sessions:
        if s.get('phone') == phone:
            s['name'] = full_name
            s['username'] = username
            updated = True
            break
    if updated:
        save_sessions(sessions)
        if root:
            root.after(0, lambda: refresh_main_checks())

# 🧠 HELPERS
def apply_homoglyphs(text):
    """Заменяет символы на визуально похожие (Кириллица <-> Латиница)"""
    replacements = {
        'а': 'a', 'a': 'а', 'с': 'c', 'c': 'с', 'е': 'e', 'e': 'е',
        'о': 'o', 'o': 'о', 'р': 'p', 'p': 'р', 'х': 'x', 'x': 'х',
        'у': 'y', 'y': 'у', 'к': 'k', 'k': 'к',
        'А': 'A', 'A': 'А', 'В': 'B', 'B': 'В', 'Е': 'E', 'E': 'Е',
        'К': 'K', 'K': 'К', 'М': 'M', 'M': 'М', 'Н': 'H', 'H': 'Н',
        'О': 'O', 'O': 'О', 'Р': 'P', 'P': 'Р', 'С': 'C', 'C': 'С',
        'Т': 'T', 'T': 'Т', 'Х': 'X', 'X': 'Х'
    }
    result = []
    for char in text:
        if char in replacements and random.random() > 0.1: 
            result.append(replacements[char])
        else:
            result.append(char)
    return "".join(result)

def generate_group_names(base, count):
    cfg = load_config()
    use_words = int(cfg.get("use_random_words", "1"))
    use_homo = int(cfg.get("use_homoglyphs", "0"))
    
    names = []
    if not use_words:
        raw_names = [base for _ in range(count)]
    else:
        seps = [s.strip() for s in cfg.get("separators", "|").splitlines() if s.strip()] or ["|"]
        words = [w.strip() for w in cfg.get("words", "Chat").splitlines() if w.strip()] or ["Chat"]
        raw_names = []
        for _ in range(count):
            raw_names.append(f"{base} {random.choice(seps)} {random.choice(words)}")
    
    for name in raw_names:
        if use_homo:
            names.append(apply_homoglyphs(name))
        else:
            names.append(name)
    return names

async def smart_sleep(base_delay, is_random):
    if is_random:
        delay = random.uniform(5.0, 15.0)
        log_msg("WAIT", f"⏳ Случайная пауза {delay:.1f} сек...")
    else:
        delay = float(base_delay)
        log_msg("WAIT", f"⏳ Пауза {delay:.1f} сек...")
    await asyncio.sleep(delay)

# 🔐 AUTH GUI
def ask_code_gui(phone, is_password=False):
    prompt = f"Введите ОБЛАЧНЫЙ ПАРОЛЬ (2FA) для {phone}:" if is_password else f"Введите код из SMS для {phone}:"
    res = tk.StringVar()
    wait_event = threading.Event()
    
    def show():
        win = Toplevel(root)
        win.title("Telegram Auth")
        win.geometry("350x180")
        win.resizable(False, False)
        
        ttk.Label(win, text=prompt, wraplength=330, font=("Arial", 10, "bold")).pack(pady=10)
        
        show_char = "*" if is_password else ""
        e = ttk.Entry(win, textvariable=res, font=("Arial", 12), show=show_char)
        e.pack(pady=5)
        e.focus()
        
        def submit(*args):
            wait_event.set()
            win.destroy()

        e.bind('<Return>', submit)
        ttk.Button(win, text="ОТПРАВИТЬ", command=submit).pack(pady=10)
        
        def on_close():
            wait_event.set()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
    
    root.after(0, show)
    
    while not wait_event.is_set() and not stop_flag.is_set():
        time.sleep(0.5)
        
    return res.get()

# === WORKER LOGIC ===

async def add_and_clean(client, chat, user, delays):
    try:
        log_msg("INFO", f"   👤 Инвайт: {user.first_name}...")
        await client(functions.messages.AddChatUserRequest(
            chat_id=chat.id, user_id=user.id, fwd_limit=100
        ))
        log_msg("SUCCESS", f"   ✅ Успешно.")
        
        msgs = await client.get_messages(chat, limit=None)
        ids = [m.id for m in msgs]
        
        if ids:
            await client.delete_messages(chat, ids, revoke=True)
            log_msg("INFO", f"   🧹 История очищена ({len(ids)} сообщ).")
        
        return True
            
    except UserPrivacyRestrictedError:
        log_msg("WARN", f"   🚫 Не удалось добавить: {user.first_name} (Блок на группы)")
        return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Телеграм запретил инвайт.")
        raise
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Ошибка инвайта: {e}")
        return False

async def worker_task(session, names, delays, target_username):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Входим в аккаунт...")
            await client.send_code_request(phone)
            
            code = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, False)
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                log_msg("WARN", f"🔐 {phone}: Требуется 2FA пароль!")
                pwd = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, True)
                try:
                    await client.sign_in(password=pwd)
                except PasswordHashInvalidError:
                    log_msg("ERROR", f"❌ {phone}: НЕВЕРНЫЙ ПАРОЛЬ! Попробуйте снова.")
                    return
        
        me = await client.get_me()
        full_name = f"{me.first_name} {me.last_name or ''}".strip()
        log_msg("SUCCESS", f"🚀 {phone}: Вход выполнен ({full_name})")
        update_session_info(phone, full_name, me.username or "")

        target_user = None
        if delays['add_username'] and target_username:
            try:
                target_user = await client.get_entity(target_username)
            except:
                log_msg("WARN", f"⚠️ Пользователь {target_username} не найден.")

        contact_users = []
        total_contacts_start = 0
        contacts_success_count = 0

        if delays['add_contacts']:
            cts = await client(functions.contacts.GetContactsRequest(hash=0))
            contact_users = [u for u in cts.users if not u.bot and not u.deleted]
            random.shuffle(contact_users)
            total_contacts_start = len(contact_users)
            log_msg("INFO", f"📋 Контактов доступно: {total_contacts_start}")

        created_chats = []
        
        # === 1. СОЗДАНИЕ ГРУПП ===
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            
            log_msg("INFO", f"🛠 Группа ({i+1}/{len(names)}): {name}")
            users_init = [target_user] if target_user else []
            
            try:
                res = await client(functions.messages.CreateChatRequest(users=users_init, title=name))
                chat = res.chats[0] if hasattr(res, 'chats') else res.updates.chats[0]
                created_chats.append(chat)
                log_msg("SUCCESS", f"✅ Группа создана ID: {chat.id}")

                if delays['add_contacts'] and delays['contact_mode'] == 0 and contact_users:
                    user_to_add = contact_users.pop(0) if contact_users else None
                    if user_to_add:
                        await smart_sleep(delays['contact'], delays['random'])
                        if await add_and_clean(client, chat, user_to_add, delays):
                            contacts_success_count += 1

                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: СПАМ-БЛОК (Flood). Аккаунт остановлен.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Ждем {e.seconds} сек (FloodWait)...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log_msg("ERROR", f"❌ Ошибка создания: {e}")

        # === 2. ДОБАВЛЕНИЕ КОНТАКТОВ ПОСЛЕ ===
        if delays['add_contacts'] and delays['contact_mode'] == 1 and contact_users and not stop_flag.is_set():
            log_msg("INFO", f"🔄 {phone}: Добиваем контакты в группы...")
            
            for chat in created_chats:
                if stop_flag.is_set() or not contact_users: break
                
                user_to_add = contact_users.pop(0)
                try:
                    if await add_and_clean(client, chat, user_to_add, delays):
                        contacts_success_count += 1
                    await smart_sleep(delays['contact'], delays['random'])
                except Exception:
                    pass

        if delays['add_contacts']:
            log_msg("INFO", f"📊 ИТОГ {phone}: Было добавлено {contacts_success_count} контактов из {total_contacts_start}")

        log_msg("SUCCESS", f"🏁 {phone}: Работа завершена.")
        
    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка клиента {phone}: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()

def run_thread(sessions, names, delays, user):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = []
    for s in sessions:
        tasks.append(worker_task(s, names, delays, user))
    
    try:
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks))
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка потока: {e}")
    finally:
        loop.close()
        if root:
            root.after(0, lambda: start_btn.config(state='normal'))

# === GUI UTILS ===

def open_new_window():
    try:
        subprocess.Popen([sys.executable, __file__])
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось открыть новое окно: {e}")

def start_process():
    stop_flag.clear()
    log_widget.config(state='normal')
    log_widget.delete("1.0", tk.END)
    log_widget.config(state='disabled')
    
    selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
    if not selected_indices:
        messagebox.showwarning("Ошибка", "Выберите аккаунты!")
        return
        
    cfg = load_config()
    try:
        delays = {
            "creation": float(cfg["delay_creation"]),
            "contact": float(cfg["delay_contact"]),
            "cleanup": float(cfg["delay_cleanup"]),
            "random": int(cfg["random_delay"]),
            "add_username": int(cfg["add_username"]),
            "add_contacts": int(cfg["add_contacts"]),
            "contact_mode": int(cfg["contact_mode"])
        }
    except:
        messagebox.showerror("Ошибка", "Проверьте настройки!")
        return

    base_name = ent_name.get().strip()
    if not base_name:
        messagebox.showwarning("Ошибка", "Введите имя группы!")
        return
    
    try:
        count = int(ent_count.get())
    except: return

    sessions = [load_sessions()[i] for i in selected_indices]
    names = generate_group_names(base_name, count)
    target_user = ent_user.get().strip()
    
    start_btn.config(state='disabled')
    threading.Thread(target=run_thread, args=(sessions, names, delays, target_user), daemon=True).start()

def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Ждем завершения текущих операций)")
    root.after(1000, lambda: start_btn.config(state='normal'))

# === WINDOWS ===

def open_settings():
    win = Toplevel(root)
    win.title("Настройки")
    win.geometry("450x600")
    cfg = load_config()
    
    lf = ttk.LabelFrame(win, text=" Тайминги ", padding=10)
    lf.pack(fill="x", padx=10, pady=10)
    
    def toggle_inputs(*args):
        st = 'disabled' if var_rand.get() else 'normal'
        e1.config(state=st); e2.config(state=st); e3.config(state=st)
        
    var_rand = tk.IntVar(value=int(cfg["random_delay"]))
    ttk.Checkbutton(lf, text="✅ Рандом (5-15 сек)", variable=var_rand).grid(row=0, column=0, columnspan=2, sticky="w")
    
    ttk.Label(lf, text="Создание (сек):").grid(row=1, column=0, sticky="w")
    e1 = ttk.Entry(lf, width=10); e1.grid(row=1, column=1, sticky="e")
    e1.insert(0, cfg["delay_creation"])
    
    ttk.Label(lf, text="Инвайт (сек):").grid(row=2, column=0, sticky="w")
    e2 = ttk.Entry(lf, width=10); e2.grid(row=2, column=1, sticky="e")
    e2.insert(0, cfg["delay_contact"])
    
    ttk.Label(lf, text="Чистка (сек) [ОТКЛЮЧЕНО]:").grid(row=3, column=0, sticky="w")
    e3 = ttk.Entry(lf, width=10); e3.grid(row=3, column=1, sticky="e")
    e3.insert(0, cfg["delay_cleanup"])
    e3.config(state='disabled')
    
    var_rand.trace("w", toggle_inputs)
    toggle_inputs()
    
    lf2 = ttk.LabelFrame(win, text=" Опции ", padding=10)
    lf2.pack(fill="x", padx=10)
    
    v_use_words = tk.IntVar(value=int(cfg.get("use_random_words", "1")))
    ttk.Checkbutton(lf2, text="Добавлять случайные слова к названию", variable=v_use_words).pack(anchor="w", pady=(0, 5))

    v_homoglyphs = tk.IntVar(value=int(cfg.get("use_homoglyphs", "0")))
    ttk.Checkbutton(lf2, text="🔀 Заменяшка (Lat/Cyr подмена символов)", variable=v_homoglyphs).pack(anchor="w", pady=(0, 5))

    v_add_user = tk.IntVar(value=int(cfg["add_username"]))
    ttk.Checkbutton(lf2, text="Инвайт юзера по @username", variable=v_add_user).pack(anchor="w")
    
    v_add_cont = tk.IntVar(value=int(cfg["add_contacts"]))
    ttk.Checkbutton(lf2, text="Инвайт контактов", variable=v_add_cont).pack(anchor="w")
    
    ttk.Label(lf2, text="Режим:").pack(anchor="w", pady=(5,0))
    v_mode = tk.IntVar(value=int(cfg["contact_mode"]))
    ttk.Radiobutton(lf2, text="Сразу (Опасно)", variable=v_mode, value=0).pack(anchor="w")
    ttk.Radiobutton(lf2, text="После (Безопасно)", variable=v_mode, value=1).pack(anchor="w")

    def save():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get())
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        new_cfg["delay_cleanup"] = e3.get()
        new_cfg["add_username"] = str(v_add_user.get())
        new_cfg["add_contacts"] = str(v_add_cont.get())
        new_cfg["contact_mode"] = str(v_mode.get())
        new_cfg["use_random_words"] = str(v_use_words.get()) 
        new_cfg["use_homoglyphs"] = str(v_homoglyphs.get())
        
        save_config(new_cfg)
        win.destroy()

    ttk.Button(win, text="Сохранить", command=save).pack(fill="x", padx=10, pady=20)

# === ACCOUNT MANAGER (ИЗМЕНЕНО) ===

def open_accounts():
    win = Toplevel(root)
    win.title("Аккаунты")
    win.geometry("600x500") # Увеличили высоту
    
    fr = ttk.Frame(win); fr.pack(fill="both", expand=True, padx=10, pady=10)
    lb = tk.Listbox(fr, selectmode=tk.SINGLE)
    sc = ttk.Scrollbar(fr, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sc.set)
    lb.pack(side="left", fill="both", expand=True); sc.pack(side="right", fill="y")
    
    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            lb.insert(tk.END, f"{s['phone']} | {name} (API: {s['api_id']})")
    refresh()
    
    fr_b = ttk.Frame(win); fr_b.pack(fill="x", padx=10, pady=10)
    
    def add():
        d = Toplevel(win)
        d.title("Добавление")
        d.geometry("350x400")
        
        ttk.Label(d, text="Номер телефона (например +7999...):").pack(pady=(10,0))
        e_phone = ttk.Entry(d, width=30); e_phone.pack()
        
        res_frame = ttk.LabelFrame(d, text="API Данные", padding=10)
        res_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(res_frame, text="API ID:").grid(row=0, column=0)
        e_api_id = ttk.Entry(res_frame, width=20); e_api_id.grid(row=0, column=1)
        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0)
        e_api_hash = ttk.Entry(res_frame, width=20); e_api_hash.grid(row=1, column=1)

        # === АВТО-ПОЛУЧЕНИЕ API ===
        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone:
                messagebox.showerror("Ошибка", "Введите номер телефона!")
                return
            
            btn_auto.config(state='disabled')
            
            def auto_thread():
                try:
                    # 1. Парсинг API
                    wc = TelegramWebClient()
                    wc.send_password(phone)
                    
                    # GUI запрос кода в главном потоке
                    code = ask_code_gui(phone, False)
                    if not code:
                        d.after(0, lambda: btn_auto.config(state='normal'))
                        return
                        
                    wc.login(phone, code)
                    keys = wc.get_app_data()
                    
                    def finish():
                        e_api_id.delete(0, tk.END)
                        e_api_id.insert(0, keys['api_id'])
                        e_api_hash.delete(0, tk.END)
                        e_api_hash.insert(0, keys['api_hash'])
                        
                        # АВТО-СОХРАНЕНИЕ В JSON
                        ss = load_sessions()
                        ss.append({
                            "api_id": str(keys['api_id']),
                            "api_hash": str(keys['api_hash']),
                            "phone": phone,
                            "name": "Auto (Требуется вход)"
                        })
                        save_sessions(ss)
                        
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!\nПри первом запуске нажмите СТАРТ.")
                        d.destroy()
                        refresh()
                        refresh_main_checks()
                        
                    d.after(0, finish)
                except Exception as e:
                    d.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
                    d.after(0, lambda: btn_auto.config(state='normal'))
            
            threading.Thread(target=auto_thread, daemon=True).start()

        btn_auto = ttk.Button(d, text="⚡ Получить API ID/Hash автоматически", command=start_auto_process)
        btn_auto.pack(pady=5)

        def s():
            ss = load_sessions()
            ss.append({"api_id":e_api_id.get(),"api_hash":e_api_hash.get(),"phone":e_phone.get()})
            save_sessions(ss); d.destroy(); refresh(); refresh_main_checks()
            
        ttk.Button(d, text="Сохранить вручную", command=s).pack(pady=10)
        
    def delt():
        if not lb.curselection(): return
        ss = load_sessions()
        del ss[lb.curselection()[0]]
        save_sessions(ss); refresh(); refresh_main_checks()
            
    ttk.Button(fr_b, text="Добавить", command=add).pack(side="left")
    ttk.Button(fr_b, text="Удалить", command=delt).pack(side="left", padx=5)

# === MAIN UI ===

root = tk.Tk()
root.title("TG Master v3.1 (NoBar + MultiWin)")
root.geometry("750x600")
style = ttk.Style()
style.theme_use('clam')

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=5, pady=5)
tab1 = ttk.Frame(notebook); notebook.add(tab1, text=" ЗАПУСК ")
tab2 = ttk.Frame(notebook); notebook.add(tab2, text=" АККАУНТЫ ")

# Tab 1
fr_top = ttk.LabelFrame(tab1, text=" Настройки ", padding=10)
fr_top.pack(fill="x", padx=10, pady=5)
ttk.Label(fr_top, text="Имя групп:").grid(row=0, column=0)
ent_name = ttk.Entry(fr_top, width=25); ent_name.grid(row=0, column=1, padx=5)
ttk.Label(fr_top, text="Кол-во:").grid(row=0, column=2)
ent_count = ttk.Entry(fr_top, width=5); ent_count.insert(0,"5"); ent_count.grid(row=0, column=3, padx=5)
ttk.Button(fr_top, text="⚙ Опции", command=open_settings).grid(row=0, column=4, padx=20)
ttk.Label(fr_top, text="User для инвайта:").grid(row=1, column=0, pady=10)
ent_user = ttk.Entry(fr_top, width=25); ent_user.grid(row=1, column=1)

fr_acc = ttk.LabelFrame(tab1, text=" Аккаунты ", padding=10)
fr_acc.pack(fill="both", expand=False, padx=10, pady=5)
cv = tk.Canvas(fr_acc, height=120); sb = ttk.Scrollbar(fr_acc, command=cv.yview)
cv.configure(yscrollcommand=sb.set); cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
sc_fr = ttk.Frame(cv); cv.create_window((0,0), window=sc_fr, anchor="nw")
sc_fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

def refresh_main_checks():
    for w in sc_fr.winfo_children(): w.destroy()
    check_vars.clear()
    for s in load_sessions():
        var = tk.IntVar()
        name = s.get('name', 'Нет имени')
        text = f"{s['phone']} | {name}"
        cb = ttk.Checkbutton(sc_fr, text=text, variable=var)
        cb.pack(anchor="w", padx=5)
        check_vars.append(var)

fr_btn = ttk.Frame(tab1)
fr_btn.pack(fill="x", padx=10, pady=10)
start_btn = tk.Button(fr_btn, text="СТАРТ", bg="#dcedc8", command=start_process, height=2)
start_btn.pack(side="left", fill="x", expand=True)
tk.Button(fr_btn, text="СТОП", bg="#ffcdd2", command=stop_process, height=2).pack(side="left", fill="x", expand=True, padx=5)
tk.Button(fr_btn, text="НОВОЕ ОКНО", bg="#b3e5fc", command=open_new_window, height=2).pack(side="left", fill="x", expand=True)

log_widget = scrolledtext.ScrolledText(tab1, height=10, state='disabled')
log_widget.pack(fill="both", expand=True, padx=10, pady=5)
for t, c in TAG_COLORS.items(): log_widget.tag_config(t, foreground=c)

# Tab 2
ttk.Button(tab2, text="Управление аккаунтами", command=open_accounts).pack(expand=True)

if __name__ == "__main__":
    refresh_main_checks()
    root.mainloop()