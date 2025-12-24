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
guest_account_index = None 

# 🎨 ЦВЕТА ДЛЯ ЛОГОВ
TAG_COLORS = {
    "SUCCESS": "#2e7d32", 
    "ERROR": "#c62828",   
    "INFO": "#000000",    
    "WAIT": "#0277bd",    
    "WARN": "#ef6c00",    
    "GUEST": "#6a1b9a",   
    "DEBUG": "#757575"    
}

# === WEB CLIENT CLASS (АВТО-РЕГИСТРАЦИЯ) ===
class TelegramWebClient:
    """
    Класс для автоматического получения API ID и Hash с сайта my.telegram.org
    """
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
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        self.random_hash = None

    def send_password(self, phone):
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        time.sleep(1)
        try:
            self.session.get(f"{self.BASE_URL}/auth")
            resp = self.session.post(f"{self.BASE_URL}/auth/send_password", data={"phone": clean_phone})
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
        resp = self.session.post(f"{self.BASE_URL}/auth/login", data=data)
        if resp.content == b"true": return True
        if "invalid code" in resp.text.lower(): raise Exception("Неверный код!")
        raise Exception(f"Ошибка входа: {resp.text[:50]}")

    def get_app_data(self):
        time.sleep(1)
        resp = self.session.get(f"{self.BASE_URL}/apps")
        html = resp.text
        if "Login" in html: raise Exception("Авторизация слетела.")

        def find_keys_in_text(html_content):
            soup = BeautifulSoup(html_content, 'html.parser')
            clean_text = soup.get_text(" ", strip=True)
            id_match = re.search(r'App\s*api_id\s*[:\-\s]+\s*(\d+)', clean_text, re.IGNORECASE)
            hash_match = re.search(r'App\s*api_hash\s*[:\-\s]+\s*([a-f0-9]{32})', clean_text, re.IGNORECASE)
            if id_match and hash_match:
                return {'api_id': id_match.group(1), 'api_hash': hash_match.group(1)}
            id_input = soup.find('input', {'name': 'api_id'})
            hash_input = soup.find('input', {'name': 'api_hash'})
            if id_input and hash_input:
                 return {'api_id': id_input.get('value'), 'api_hash': hash_input.get('value')}
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
        if "flood" in resp.text.lower(): raise Exception("FLOOD LIMIT: Нельзя создавать App сейчас.")

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
        "delay_creation": "180", "delay_username": "15", "delay_contact": "20",
        "delay_cleanup": "10", "random_delay": "1", "add_username": "1",
        "add_contacts": "1", "contact_mode": "1", "separators": "|",
        "words": "Чат", "use_random_words": "1"
    }
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: defaults.update(json.load(f))
        except: pass
    return defaults

def save_config(config, filepath="config.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e: messagebox.showerror("Ошибка", str(e))

# 📁 SESSIONS
def load_sessions(filepath="sessions.json"):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

def save_sessions(sessions, filepath="sessions.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(sessions, f, indent=4)
    except Exception as e: messagebox.showerror("Ошибка", str(e))

def update_session_info(phone, full_name, username):
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
        if root: root.after(0, lambda: refresh_main_checks())

# 🧠 HELPERS
def generate_group_names(base, count):
    cfg = load_config()
    use_words = int(cfg.get("use_random_words", "1"))
    names = []
    if not use_words:
        raw_names = [base for _ in range(count)]
    else:
        seps = [s.strip() for s in cfg.get("separators", "|").splitlines() if s.strip()] or ["|"]
        words = [w.strip() for w in cfg.get("words", "Chat").splitlines() if w.strip()] or ["Chat"]
        raw_names = []
        for _ in range(count):
            raw_names.append(f"{base} {random.choice(seps)} {random.choice(words)}")
    return raw_names

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
        e.pack(pady=5); e.focus()
        def submit(*args): wait_event.set(); win.destroy()
        e.bind('<Return>', submit)
        ttk.Button(win, text="ОТПРАВИТЬ", command=submit).pack(pady=10)
        def on_close(): wait_event.set(); win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
    
    root.after(0, show)
    while not wait_event.is_set() and not stop_flag.is_set(): time.sleep(0.5)
    return res.get()

# === WORKER LOGIC (MAKER) ===

async def add_and_clean(client, chat, user, delays):
    try:
        log_msg("INFO", f"   👤 Инвайт: {user.first_name}...")
        await client(functions.messages.AddChatUserRequest(
            chat_id=chat.id, user_id=user.id, fwd_limit=100
        ))
        log_msg("SUCCESS", f"   ✅ Успешно.")
        await asyncio.sleep(1)
        msgs = await client.get_messages(chat, limit=5)
        ids = [m.id for m in msgs if m.action]
        if ids: await client.delete_messages(chat, ids, revoke=True)
        return True
    except UserPrivacyRestrictedError:
        log_msg("WARN", f"   🚫 Не удалось добавить: {user.first_name} (Приватность)")
        return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Телеграм запретил инвайт.")
        raise
    except Exception as e:
        if "USER_ALREADY_PARTICIPANT" in str(e): return True
        log_msg("WARN", f"   ⚠️ Ошибка инвайта: {e}")
        return False

async def worker_task(session, names, delays, target_username):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    created_chat_ids = [] 
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход...")
            return []

        me = await client.get_me()
        log_msg("INFO", f"🚀 {phone}: Maker начал работу.")

        target_user_entity = None
        if delays['add_username'] and target_username:
            try:
                target_user_entity = await client.get_entity(target_username)
                log_msg("INFO", f"   🎯 Гость найден: @{target_username}")
            except:
                log_msg("WARN", f"   ⚠️ Гость @{target_username} НЕ НАЙДЕН.")

        contact_users = []
        if delays['add_contacts']:
            cts = await client(functions.contacts.GetContactsRequest(hash=0))
            contact_users = [u for u in cts.users if not u.bot and not u.deleted and u.id != me.id]
            random.shuffle(contact_users)
            log_msg("INFO", f"   📋 Контактов доступно: {len(contact_users)}")

        delayed_invites = [] 

        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            log_msg("INFO", f"🛠 ({i+1}/{len(names)}) Создаю: {name}")
            try:
                res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                chat = res.chats[0] if hasattr(res, 'chats') else res.updates.chats[0]
                created_chat_ids.append(chat.id)
                log_msg("SUCCESS", f"   ✅ Группа {chat.id} создана.")

                if target_user_entity:
                    try:
                        await client(functions.messages.AddChatUserRequest(
                            chat_id=chat.id, user_id=target_user_entity.id, fwd_limit=100
                        ))
                    except Exception as e: log_msg("ERROR", f"   🆘 Не удалось добавить Гостя: {e}")

                if delays['add_contacts'] and contact_users:
                    user_to_add = contact_users.pop(0)
                    if delays['contact_mode'] == 0: # Сразу
                        await smart_sleep(delays['contact'], delays['random'])
                        await add_and_clean(client, chat, user_to_add, delays)
                    else: # После
                        delayed_invites.append((chat, user_to_add))
                        log_msg("INFO", f"   ⏳ Контакт отложен (Режим 'После')")
                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: FLOOD WAIT. Останавливаю.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Флуд, ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e: log_msg("ERROR", f"❌ Ошибка создания: {e}")

        if delayed_invites and not stop_flag.is_set():
            log_msg("INFO", f"📥 {phone}: Группы созданы. Добавляю контакты...")
            for idx, (chat_obj, user_obj) in enumerate(delayed_invites):
                if stop_flag.is_set(): break
                log_msg("INFO", f"   ➕ ({idx+1}/{len(delayed_invites)}) Обработка {chat_obj.title}...")
                await add_and_clean(client, chat_obj, user_obj, delays)
                await smart_sleep(delays['contact'], delays['random'])

        log_msg("SUCCESS", f"🏁 {phone}: Мейкер завершил часть работы.")
        return created_chat_ids

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка {phone}: {e}")
        return []
    finally:
        if client.is_connected(): await client.disconnect()

# === GUEST LOGIC (ПОИСК: ID + ИМЯ) ===

async def guest_execution(session, created_ids, greeting_text, base_name_filter):
    """
    Задача для Гостя. Ищет группы по ID ИЛИ по названию (начинается с base_name_filter).
    """
    if not created_ids and not base_name_filter:
        log_msg("WARN", "⚠️ Гостю нечего искать.")
        return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("ERROR", f"❌ ГОСТЬ {phone} не авторизован! Зайдите вручную.")
            return

        me = await client.get_me()
        log_msg("GUEST", f"😎 ГОСТЬ ({me.first_name}) ищет группы: ID или имя '{base_name_filter}'...")

        targets = []
        # Retry mechanism
        for attempt in range(1, 4):
            log_msg("WAIT", f"🔄 Попытка {attempt}/3: Обновляем диалоги...")
            dialogs = await client.get_dialogs(limit=100) # Увеличили лимит
            
            targets = []
            for d in dialogs:
                # 1. Проверка по ID
                is_id_match = d.entity.id in created_ids
                
                # 2. Проверка по Имени (если задано имя)
                title = getattr(d.entity, 'title', '')
                is_name_match = False
                if base_name_filter and title:
                    # Проверяем, начинается ли имя с нашего базового названия
                    if title.lower().startswith(base_name_filter.lower()):
                        is_name_match = True
                
                if is_id_match or is_name_match:
                    targets.append(d.entity)
            
            if targets:
                break 
            else:
                if attempt == 3:
                     log_msg("DEBUG", f"🔍 Не найдено совпадений по ID или имени '{base_name_filter}'.")
                await asyncio.sleep(5) 

        if not targets:
            log_msg("WARN", "⚠️ ГОСТЬ не нашел новые группы даже по названию.")
            return

        log_msg("GUEST", f"✅ Найдено групп для рассылки: {len(targets)}")

        # Фильтр дубликатов (на случай если нашли одну группу дважды)
        unique_targets = {t.id: t for t in targets}.values()

        count = 0
        for entity in unique_targets:
            if stop_flag.is_set(): break
            
            try:
                await client.send_message(entity, greeting_text)
                
                chat_title = getattr(entity, 'title', str(entity.id))
                log_msg("GUEST", f"   📩 Приветствие отправлено в {chat_title}")
                count += 1
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                log_msg("WARN", f"   ⚠️ ГОСТЬ ошибка отправки: {e}")

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count} / {len(unique_targets)}).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === THREAD RUNNER ===

def run_thread(main_sessions, guest_session, names, delays, target_username, greeting_text, base_name):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    maker_tasks = []
    for s in main_sessions:
        maker_tasks.append(worker_task(s, names, delays, target_username))
    
    try:
        if maker_tasks:
            log_msg("INFO", "=== ЗАПУСК СОЗДАТЕЛЕЙ ===")
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            all_ids = []
            for sublist in results:
                if sublist: all_ids.extend(sublist)
            
            log_msg("INFO", f"📊 Создано групп: {len(all_ids)}. Запуск Гостя...")

            if guest_session and not stop_flag.is_set():
                 log_msg("INFO", "=== ЗАПУСК ГОСТЯ ===")
                 time.sleep(2)
                 # Передаем base_name для поиска по имени
                 loop.run_until_complete(guest_execution(guest_session, all_ids, greeting_text, base_name))
            elif not guest_session:
                 log_msg("WARN", "⚠️ Гость не выбран.")
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка потока: {e}")
    finally:
        loop.close()
        if root: root.after(0, lambda: start_btn.config(state='normal'))

# === GUI UTILS ===

def open_new_window():
    try: subprocess.Popen([sys.executable, __file__])
    except Exception as e: messagebox.showerror("Ошибка", f"Не удалось открыть новое окно: {e}")

def start_process():
    stop_flag.clear()
    log_widget.config(state='normal'); log_widget.delete("1.0", tk.END); log_widget.config(state='disabled')
    
    sessions_data = load_sessions()
    selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
    
    guest_idx = guest_account_index.get()
    guest_session = None
    target_username = ""

    if guest_idx != -1:
        guest_session = sessions_data[guest_idx]
        if not guest_session.get('username'):
             messagebox.showerror("Ошибка", "У Гостя нет @username!")
             return
        target_username = guest_session['username']
        if guest_idx in selected_indices: selected_indices.remove(guest_idx)
    else:
        manual_input = ent_user.get().strip().replace('@', '')
        if manual_input: target_username = manual_input

    if not selected_indices:
        messagebox.showwarning("Ошибка", "Выберите Мейкеров.")
        return
    
    greeting_text = txt_greeting.get("1.0", tk.END).strip()
    if guest_session and not greeting_text:
        messagebox.showwarning("Внимание", "Нет текста приветствия!")
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
    except: return

    base_name = ent_name.get().strip()
    try: count = int(ent_count.get())
    except: return

    main_sessions = [sessions_data[i] for i in selected_indices]
    names = generate_group_names(base_name, count)
    
    start_btn.config(state='disabled')
    threading.Thread(
        target=run_thread, 
        args=(main_sessions, guest_session, names, delays, target_username, greeting_text, base_name), 
        daemon=True
    ).start()

def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Ждем завершения)")
    if root: root.after(1000, lambda: start_btn.config(state='normal'))

# === WINDOWS ===

def open_settings():
    win = Toplevel(root); win.title("Настройки"); win.geometry("450x600")
    cfg = load_config()
    
    lf = ttk.LabelFrame(win, text=" Тайминги ", padding=10); lf.pack(fill="x", padx=10, pady=10)
    
    def toggle_inputs(*args):
        st = 'disabled' if var_rand.get() else 'normal'
        e1.config(state=st); e2.config(state=st); e3.config(state=st)
        
    var_rand = tk.IntVar(value=int(cfg["random_delay"]))
    ttk.Checkbutton(lf, text="✅ Рандом (5-15 сек)", variable=var_rand).grid(row=0, column=0, columnspan=2, sticky="w")
    
    ttk.Label(lf, text="Создание (сек):").grid(row=1, column=0, sticky="w")
    e1 = ttk.Entry(lf, width=10); e1.grid(row=1, column=1, sticky="e"); e1.insert(0, cfg["delay_creation"])
    
    ttk.Label(lf, text="Инвайт (сек):").grid(row=2, column=0, sticky="w")
    e2 = ttk.Entry(lf, width=10); e2.grid(row=2, column=1, sticky="e"); e2.insert(0, cfg["delay_contact"])
    
    ttk.Label(lf, text="Чистка (сек) [ОТКЛЮЧЕНО]:").grid(row=3, column=0, sticky="w")
    e3 = ttk.Entry(lf, width=10); e3.grid(row=3, column=1, sticky="e"); e3.insert(0, cfg["delay_cleanup"]); e3.config(state='disabled')
    
    var_rand.trace("w", toggle_inputs); toggle_inputs()
    
    lf2 = ttk.LabelFrame(win, text=" Опции ", padding=10); lf2.pack(fill="x", padx=10)
    
    v_use_words = tk.IntVar(value=int(cfg.get("use_random_words", "1")))
    ttk.Checkbutton(lf2, text="Добавлять случайные слова к названию", variable=v_use_words).pack(anchor="w")
    
    v_add_user = tk.IntVar(value=int(cfg["add_username"]))
    ttk.Checkbutton(lf2, text="Инвайт юзера по @username", variable=v_add_user).pack(anchor="w")
    
    v_add_cont = tk.IntVar(value=int(cfg["add_contacts"]))
    ttk.Checkbutton(lf2, text="Инвайт контактов", variable=v_add_cont).pack(anchor="w")
    
    ttk.Label(lf2, text="Режим контактов:").pack(anchor="w", pady=(5,0))
    v_mode = tk.IntVar(value=int(cfg["contact_mode"]))
    ttk.Radiobutton(lf2, text="Сразу (При создании)", variable=v_mode, value=0).pack(anchor="w")
    ttk.Radiobutton(lf2, text="После (Когда все созданы)", variable=v_mode, value=1).pack(anchor="w")

    def save():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get()); new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get(); new_cfg["delay_cleanup"] = e3.get()
        new_cfg["add_username"] = str(v_add_user.get()); new_cfg["add_contacts"] = str(v_add_cont.get())
        new_cfg["contact_mode"] = str(v_mode.get()); new_cfg["use_random_words"] = str(v_use_words.get())
        save_config(new_cfg); win.destroy()

    ttk.Button(win, text="Сохранить", command=save).pack(fill="x", padx=10, pady=20)

def open_accounts():
    win = Toplevel(root); win.title("Аккаунты"); win.geometry("600x450")
    fr = ttk.Frame(win); fr.pack(fill="both", expand=True, padx=10, pady=10)
    lb = tk.Listbox(fr, selectmode=tk.SINGLE)
    sc = ttk.Scrollbar(fr, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sc.set)
    lb.pack(side="left", fill="both", expand=True); sc.pack(side="right", fill="y")
    
    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            lb.insert(tk.END, f"{s['phone']} | {name}")
    refresh()
    
    fr_b = ttk.Frame(win); fr_b.pack(fill="x", padx=10, pady=10)
    
    def add():
        d = Toplevel(win); d.title("Добавление"); d.geometry("350x400")
        ttk.Label(d, text="Номер телефона:").pack(pady=(10,0))
        e_phone = ttk.Entry(d, width=30); e_phone.pack()
        
        res_frame = ttk.LabelFrame(d, text="API Данные", padding=10); res_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(res_frame, text="API ID:").grid(row=0, column=0)
        e_api_id = ttk.Entry(res_frame, width=20); e_api_id.grid(row=0, column=1)
        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0)
        e_api_hash = ttk.Entry(res_frame, width=20); e_api_hash.grid(row=1, column=1)

        # === АВТО-ПОЛУЧЕНИЕ + СОХРАНЕНИЕ СЕССИИ ===
        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone: messagebox.showerror("Ошибка", "Номер?"); return
            btn_auto.config(state='disabled')
            
            def auto_thread():
                try:
                    # 1. Парсинг API
                    wc = TelegramWebClient()
                    wc.send_password(phone)
                    code = ask_code_gui(phone, False)
                    if not code: d.after(0, lambda: btn_auto.config(state='normal')); return
                    wc.login(phone, code)
                    keys = wc.get_app_data()
                    
                    # 2. Создание сессии TELETHON (чтобы появился .session файл)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    client = TelegramClient(f"session_{phone}", int(keys['api_id']), keys['api_hash'])
                    
                    # Мы создаем файл сессии, но вход не делаем (юзер уже ввел код на сайте)
                    # Клиент просто сохранит API данные в session файле
                    # При следующем запуске потребуется вход, но аккаунт уже будет в списке
                    
                    def finish():
                        e_api_id.delete(0, tk.END); e_api_id.insert(0, keys['api_id'])
                        e_api_hash.delete(0, tk.END); e_api_hash.insert(0, keys['api_hash'])
                        
                        # АВТО-СОХРАНЕНИЕ В JSON
                        ss = load_sessions()
                        ss.append({
                            "api_id": str(keys['api_id']),
                            "api_hash": str(keys['api_hash']),
                            "phone": phone,
                            "name": "Auto (Требуется вход)"
                        })
                        save_sessions(ss)
                        
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!\nПри первом запуске потребуется код для программы.")
                        d.destroy(); refresh(); refresh_main_checks()
                        
                    d.after(0, finish)
                except Exception as e:
                    d.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
                    d.after(0, lambda: btn_auto.config(state='normal'))
            
            threading.Thread(target=auto_thread, daemon=True).start()

        btn_auto = ttk.Button(d, text="⚡ Авто-регистрация (Web + JSON)", command=start_auto_process)
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

root = tk.Tk(); root.title("TG Master v6.0 (Full Fix)"); root.geometry("850x700")
style = ttk.Style(); style.theme_use('clam')
guest_account_index = tk.IntVar(value=-1)
notebook = ttk.Notebook(root); notebook.pack(fill="both", expand=True, padx=5, pady=5)
tab1 = ttk.Frame(notebook); notebook.add(tab1, text=" ЗАПУСК ")
tab2 = ttk.Frame(notebook); notebook.add(tab2, text=" АККАУНТЫ ")

fr_main = ttk.Frame(tab1); fr_main.pack(fill="both", expand=True, padx=10, pady=5)
fr_left = ttk.Frame(fr_main); fr_left.pack(side="left", fill="both", expand=True, padx=(0, 5))
fr_right = ttk.Frame(fr_main); fr_right.pack(side="right", fill="y", padx=(5, 0))

fr_top = ttk.LabelFrame(fr_left, text=" Настройки Мейкеров ", padding=10); fr_top.pack(fill="x", padx=0, pady=5)
ttk.Label(fr_top, text="Имя групп:").grid(row=0, column=0)
ent_name = ttk.Entry(fr_top, width=20); ent_name.grid(row=0, column=1, padx=5)
ttk.Label(fr_top, text="Кол-во:").grid(row=0, column=2)
ent_count = ttk.Entry(fr_top, width=5); ent_count.insert(0,"5"); ent_count.grid(row=0, column=3, padx=5)
ttk.Button(fr_top, text="⚙ Опции", command=open_settings).grid(row=0, column=4, padx=10)
ttk.Label(fr_top, text="Ручной ввод @user (если нет Гостя):").grid(row=1, column=0, columnspan=2, pady=(10,0), sticky="w")
ent_user = ttk.Entry(fr_top, width=20); ent_user.grid(row=1, column=2, columnspan=2, pady=(10,0), sticky="w")

fr_acc = ttk.LabelFrame(fr_left, text=" Выберите МЕЙКЕРОВ (кто создает): ", padding=10)
fr_acc.pack(fill="both", expand=True, padx=0, pady=5)
cv = tk.Canvas(fr_acc); sb = ttk.Scrollbar(fr_acc, command=cv.yview)
cv.configure(yscrollcommand=sb.set); cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
sc_fr = ttk.Frame(cv); cv.create_window((0,0), window=sc_fr, anchor="nw")
sc_fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

fr_guest = ttk.LabelFrame(fr_right, text=" Выберите ГОСТЯ (кто пишет): ", padding=10)
fr_guest.pack(fill="both", expand=True, padx=5, pady=5)
guest_cv = tk.Canvas(fr_guest, height=150); g_sb = ttk.Scrollbar(fr_guest, command=guest_cv.yview)
guest_cv.configure(yscrollcommand=g_sb.set); guest_cv.pack(side="left", fill="both", expand=True); g_sb.pack(side="right", fill="y")
guest_group = ttk.Frame(guest_cv); guest_cv.create_window((0,0), window=guest_group, anchor="nw")
guest_group.bind("<Configure>", lambda e: guest_cv.configure(scrollregion=guest_cv.bbox("all")))

fr_greeting = ttk.LabelFrame(fr_right, text=" Текст ПРИВЕТСТВИЯ ", padding=10)
fr_greeting.pack(fill="both", expand=True, padx=5, pady=5)
txt_greeting = scrolledtext.ScrolledText(fr_greeting, height=10, width=30)
txt_greeting.pack(fill="both", expand=True); txt_greeting.insert("1.0", "Привет! Заходите.")

def refresh_main_checks():
    for w in sc_fr.winfo_children(): w.destroy()
    check_vars.clear()
    for w in guest_group.winfo_children(): w.destroy()
    ttk.Radiobutton(guest_group, text="🚫 Без гостя", variable=guest_account_index, value=-1).pack(anchor="w")
    for i, s in enumerate(load_sessions()):
        name = s.get('name', '..'); uname = s.get('username', '..'); text = f"{s['phone']} | {name}"
        var = tk.IntVar(); ttk.Checkbutton(sc_fr, text=text, variable=var).pack(anchor="w", padx=5); check_vars.append(var)
        ttk.Radiobutton(guest_group, text=f"{text} (@{uname})", variable=guest_account_index, value=i).pack(anchor="w")

fr_btn = ttk.Frame(tab1); fr_btn.pack(fill="x", padx=10, pady=5)
start_btn = tk.Button(fr_btn, text="🚀 СТАРТ", bg="#dcedc8", command=start_process, height=2)
start_btn.pack(side="left", fill="x", expand=True)
tk.Button(fr_btn, text="🛑 СТОП", bg="#ffcdd2", command=stop_process, height=2).pack(side="left", fill="x", expand=True, padx=5)
tk.Button(fr_btn, text="НОВОЕ ОКНО", bg="#b3e5fc", command=open_new_window, height=2).pack(side="left", fill="x", expand=True)

log_widget = scrolledtext.ScrolledText(tab1, height=8, state='disabled')
log_widget.pack(fill="both", expand=True, padx=10, pady=(0,10))
for t, c in TAG_COLORS.items(): log_widget.tag_config(t, foreground=c)

ttk.Button(tab2, text="Управление аккаунтами", command=open_accounts).pack(expand=True)

if __name__ == "__main__": refresh_main_checks(); root.mainloop()