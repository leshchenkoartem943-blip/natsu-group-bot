import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel
import asyncio
import threading
from telethon import TelegramClient, functions, types
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError
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
from datetime import datetime, timedelta, timezone

# 🛑 Глобальные переменные
stop_flag = threading.Event()
root = None
log_widget = None
check_vars = []
guest_account_index = None 
var_send_greeting = None

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
        
        # Отправляем запрос на создание
        self.session.post(f"{self.BASE_URL}/apps/create", data=create_data)
        
        # === ИСПРАВЛЕНИЕ ===
        time.sleep(1) # Небольшая пауза для БД Телеграма
        # Принудительно обновляем страницу, чтобы точно увидеть ключи
        resp = self.session.get(f"{self.BASE_URL}/apps", timeout=10) 
        # ===================

        keys = find_keys_in_text(resp.text)
        if keys: return keys
        
        # Если ключей все еще нет, возможно, была ошибка при создании (например, имя занято)
        # Можно вывести текст ответа для отладки, если нужно: print(resp.text)
        raise Exception("Не удалось прочитать ключи после создания (возможно, ошибка валидации).")

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
        "words": "Chat", "use_random_words": "1",
        "send_greeting": "1"
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
        # Окно поверх всех окон, чтобы пользователь точно увидел
        win.attributes('-topmost', True) 
        
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
    
    # Ждем пока пользователь введет код
    while not wait_event.is_set() and not stop_flag.is_set():
        time.sleep(0.5)
        
    return res.get()

# === WORKER LOGIC (MAKER) ===

async def add_and_clean_strict(client, chat_entity, user):
    """
    СТРОГАЯ ЛОГИКА: Добавить -> Полностью почистить.
    """
    try:
        log_msg("INFO", f"   👤 Инвайт контакта: {user.first_name}...")
        
        # 1. Инвайт
        input_user = await client.get_input_entity(user)
        from telethon.tl.types import Channel
        is_broadcast = isinstance(chat_entity, Channel) or getattr(chat_entity, 'megagroup', False)
        
        if is_broadcast:
             await client(functions.channels.InviteToChannelRequest(channel=chat_entity, users=[input_user]))
        else:
             await client(functions.messages.AddChatUserRequest(chat_id=chat_entity.id, user_id=input_user, fwd_limit=100))
        
        log_msg("SUCCESS", f"   ✅ Контакт добавлен.")
        
        # 2. Очистка 
        await asyncio.sleep(1)
        msgs = await client.get_messages(chat_entity, limit=None)
        ids = [m.id for m in msgs]
        
        if ids:
            await client.delete_messages(chat_entity, ids, revoke=True)
            log_msg("INFO", f"   🧹 История очищена (удалено {len(ids)} шт).")
        
        return True

    except UserPrivacyRestrictedError:
         log_msg("WARN", "   🚫 Приватность: пользователь запретил инвайт.")
         return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Телеграм запретил инвайт.")
        raise
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Ошибка (add_and_clean): {e}")
        return False

async def safe_add_guest(client, chat_entity, user_entity):
    try:
        log_msg("INFO", f"   👤 Добавляем Гостя (@{user_entity.username})...")
        input_user = await client.get_input_entity(user_entity)
        from telethon.tl.types import Channel
        is_broadcast = isinstance(chat_entity, Channel) or getattr(chat_entity, 'megagroup', False)
        if is_broadcast:
            await client(functions.channels.InviteToChannelRequest(channel=chat_entity, users=[input_user]))
        else:
            await client(functions.messages.AddChatUserRequest(chat_id=chat_entity.id, user_id=input_user, fwd_limit=100))
        log_msg("SUCCESS", "   ✅ Гость успешно добавлен!")
        return True
    except Exception as e:
        log_msg("ERROR", f"   🆘 Не удалось добавить Гостя: {e}")
        return False

async def worker_task(session, names, delays, target_username):
    """
    Задача Мейкера:
    1. Авторизация (если слетела - просит код)
    2. Создание всех групп + Инвайт Гостя
    3. (Если режим "После") Проход по всем созданным + Инвайт Контакта + Чистка
    """
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    created_chats = [] 
    created_chat_ids = [] 
    my_id = None

    try:
        await client.connect()
        
        # === ВОЗВРАЩЕНА ПОЛНАЯ АВТОРИЗАЦИЯ ===
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! Отправляю код...")
            try:
                await client.send_code_request(phone)
                code = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, False)
                if not code:
                    log_msg("WARN", f"⚠️ {phone}: Код не введен. Пропуск аккаунта.")
                    return None
                
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    log_msg("WARN", f"🔐 {phone}: Нужен 2FA пароль!")
                    pwd = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, True)
                    await client.sign_in(password=pwd)
            except Exception as auth_e:
                log_msg("ERROR", f"❌ {phone}: Ошибка входа: {auth_e}")
                return None
        # ========================================

        me = await client.get_me()
        my_id = me.id
        log_msg("INFO", f"🚀 {phone} (ID: {my_id}): Maker начал работу.")

        # Поиск сущности Гостя
        target_user_entity = None
        if target_username:
            try:
                target_user_entity = await client.get_entity(target_username)
            except:
                log_msg("WARN", f"   ⚠️ Гость @{target_username} НЕ НАЙДЕН!")

        # Загрузка контактов
        contact_users = []
        if delays['add_contacts']:
            try:
                cts = await client(functions.contacts.GetContactsRequest(hash=0))
                contact_users = [u for u in cts.users if not u.bot and not u.deleted and u.id != me.id]
                random.shuffle(contact_users)
                log_msg("INFO", f"   📋 Контактов доступно: {len(contact_users)}")
            except: pass

        # === ЭТАП 1: СОЗДАНИЕ ВСЕХ ГРУПП ===
        log_msg("INFO", f"--- ЭТАП 1: СОЗДАНИЕ ГРУПП ({len(names)} шт) ---")
        
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            
            try:
                res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                chat_id = res.chats[0].id if hasattr(res, 'chats') and res.chats else res.updates.chats[0].id
                chat_entity = await client.get_entity(chat_id)
                
                created_chats.append(chat_entity)
                created_chat_ids.append(chat_id)
                
                log_msg("SUCCESS", f"   ✅ Группа '{name}' создана (ID: {chat_id})")
                
                if target_user_entity:
                    await safe_add_guest(client, chat_entity, target_user_entity)

                # Режим "Сразу"
                if delays['add_contacts'] and delays['contact_mode'] == 0:
                    if contact_users:
                        u = contact_users.pop(0)
                        await asyncio.sleep(1)
                        await add_and_clean_strict(client, chat_entity, u)
                
                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: FLOOD WAIT. Стоп.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка создания: {e}")

        # === ЭТАП 2: ДОБАВЛЕНИЕ КОНТАКТОВ И ЧИСТКА (МАССОВО) ===
        if delays['add_contacts'] and delays['contact_mode'] == 1 and not stop_flag.is_set():
            if created_chats:
                log_msg("INFO", f"\n--- ЭТАП 2: ОБРАБОТКА ГРУПП (Контакты + Чистка) ---")
                
                for chat in created_chats:
                    if stop_flag.is_set(): break
                    if not contact_users:
                        log_msg("WARN", "   ⚠️ Контакты закончились!")
                        break
                    
                    user_to_add = contact_users.pop(0)
                    
                    try:
                        await add_and_clean_strict(client, chat, user_to_add)
                        await smart_sleep(delays['contact'], delays['random'])
                    except Exception as e:
                        log_msg("WARN", f"   ⚠️ Ошибка этапа 2: {e}")

        log_msg("SUCCESS", f"🏁 {phone}: Мейкер полностью завершил работу.")
        return {'maker_id': my_id, 'chats': created_chat_ids}

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка Maker: {e}")
        return None
    finally:
        if client.is_connected(): await client.disconnect()

# === GUEST LOGIC ===

async def guest_execution_final(session, all_maker_ids, target_group_ids, greeting_text):
    if not target_group_ids:
        log_msg("WARN", "⚠️ Нет новых групп для приветствия.")
        return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    try:
        await client.connect()
        
        # === ВОЗВРАЩЕНА ПОЛНАЯ АВТОРИЗАЦИЯ ===
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 ГОСТЬ {phone}: Требуется вход! Отправляю код...")
            try:
                await client.send_code_request(phone)
                code = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, False)
                if not code:
                    log_msg("WARN", "⚠️ Гость не ввел код. Отмена.")
                    return
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    log_msg("WARN", f"🔐 ГОСТЬ {phone}: Нужен 2FA пароль!")
                    pwd = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, True)
                    await client.sign_in(password=pwd)
            except Exception as auth_e:
                log_msg("ERROR", f"❌ Ошибка входа гостя: {auth_e}")
                return
        # ========================================

        me = await client.get_me()
        log_msg("GUEST", f"😎 ГОСТЬ ({me.first_name}) обновляет список диалогов...")

        dialogs = await client.get_dialogs(limit=100, ignore_migrated=True)
        
        count_sent = 0
        
        for gid in target_group_ids:
            if stop_flag.is_set(): break
            
            target_entity = None
            for d in dialogs:
                if abs(d.id) == abs(gid):
                    target_entity = d.entity
                    break
            
            if not target_entity:
                try:
                    target_entity = await client.get_entity(types.PeerChat(gid))
                except:
                    log_msg("WARN", f"   ⚠️ Гость пока не видит группу {gid}. Пропуск.")
                    continue

            try:
                title = getattr(target_entity, 'title', str(gid))
                try:
                    participants = await client.get_participants(target_entity, limit=20)
                    found_maker = False
                    for p in participants:
                        if p.id in all_maker_ids:
                            found_maker = True
                            break
                except:
                     found_maker = True 
                
                if found_maker:
                    log_msg("DEBUG", f"   ✅ Группа '{title}' найдена. Пишем...")
                    await client.send_message(target_entity, greeting_text)
                    log_msg("SUCCESS", f"   📨 Приветствие отправлено!")
                    count_sent += 1
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                else:
                    log_msg("WARN", f"   🚫 В группе '{title}' нет создателя. Пропуск.")

            except Exception as e:
                log_msg("WARN", f"   ⚠️ Ошибка отправки в {gid}: {e}")
                await asyncio.sleep(1)

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count_sent} успешных).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === THREAD RUNNER ===

def run_thread(main_sessions, guest_session, names, delays, target_username_manual, greeting_text, need_greet):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    target_username = target_username_manual
    if guest_session and guest_session.get('username'):
        target_username = guest_session['username']
    
    log_msg("INFO", f"🎯 Цель для инвайта (Гость): @{target_username}")
    if need_greet:
        log_msg("INFO", "✉️ Режим отправки приветствия: ВКЛЮЧЕН")
    else:
        log_msg("INFO", "🔕 Режим отправки приветствия: ВЫКЛЮЧЕН")

    maker_tasks = []
    for s in main_sessions:
        maker_tasks.append(worker_task(s, names, delays, target_username))
    
    try:
        if maker_tasks:
            log_msg("INFO", "=== ЗАПУСК МЕЙКЕРОВ ===")
            
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            all_maker_ids = []
            all_created_groups = []
            
            for res in results:
                if res:
                    if res.get('maker_id'): all_maker_ids.append(res['maker_id'])
                    if res.get('chats'): all_created_groups.extend(res['chats'])
            
            log_msg("INFO", f"📊 МЕЙКЕРЫ ЗАКОНЧИЛИ. Создано {len(all_created_groups)} групп.")

            if guest_session and not stop_flag.is_set():
                if all_created_groups:
                    if need_greet:
                        log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ (Приветствие) ===")
                        log_msg("WAIT", "⏳ Синхронизация 3 сек...")
                        time.sleep(3)
                        loop.run_until_complete(guest_execution_final(guest_session, all_maker_ids, all_created_groups, greeting_text))
                    else:
                        log_msg("INFO", "\n🛑 Приветствие отключено галочкой.")
                else:
                    log_msg("WARN", "⚠️ Группы не были созданы.")
            
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
    
    if guest_idx != -1:
        guest_session = sessions_data[guest_idx]
        if guest_idx in selected_indices:
            selected_indices.remove(guest_idx)
    
    main_sessions = [sessions_data[i] for i in selected_indices]

    if not main_sessions:
        messagebox.showwarning("Ошибка", "Выберите хотя бы одного Мейкера (галочкой)!")
        return
    
    greeting_text = txt_greeting.get("1.0", tk.END).strip()
    need_greet = var_send_greeting.get() 

    if guest_session and need_greet and not greeting_text:
        messagebox.showwarning("Внимание", "Вы включили отправку приветствия, но текст пустой!")
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
    try: count_per_maker = int(ent_count.get())
    except: return

    manual_username = ent_user.get().strip().replace('@', '')
    
    names = generate_group_names(base_name, count_per_maker)
    
    start_btn.config(state='disabled')
    threading.Thread(
        target=run_thread, 
        args=(main_sessions, guest_session, names, delays, manual_username, greeting_text, need_greet), 
        daemon=True
    ).start()

def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Завершение текущих операций)")
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
    ttk.Checkbutton(lf2, text="Инвайт юзера (Гостя)", variable=v_add_user).pack(anchor="w")
    v_add_cont = tk.IntVar(value=int(cfg["add_contacts"]))
    ttk.Checkbutton(lf2, text="Инвайт контактов", variable=v_add_cont).pack(anchor="w")
    
    ttk.Label(lf2, text="Режим контактов:").pack(anchor="w", pady=(5,0))
    v_mode = tk.IntVar(value=int(cfg["contact_mode"]))
    ttk.Radiobutton(lf2, text="Сразу (При создании)", variable=v_mode, value=0).pack(anchor="w")
    ttk.Radiobutton(lf2, text="После (Сначала все группы, потом контакты)", variable=v_mode, value=1).pack(anchor="w")
    
    def save():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get()); new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get(); new_cfg["delay_cleanup"] = e3.get()
        new_cfg["add_username"] = str(v_add_user.get()); new_cfg["add_contacts"] = str(v_add_cont.get())
        new_cfg["use_random_words"] = str(v_use_words.get()); new_cfg["contact_mode"] = str(v_mode.get())
        save_config(new_cfg); win.destroy()

    ttk.Button(win, text="Сохранить", command=save).pack(fill="x", padx=10, pady=20)

# === ACCOUNT MANAGER ===

def open_accounts():
    win = Toplevel(root); win.title("Аккаунты"); win.geometry("600x500")
    fr = ttk.Frame(win); fr.pack(fill="both", expand=True, padx=10, pady=10)
    lb = tk.Listbox(fr, selectmode=tk.SINGLE)
    sc = ttk.Scrollbar(fr, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sc.set)
    lb.pack(side="left", fill="both", expand=True); sc.pack(side="right", fill="y")
    
    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            txt = f"{s['phone']} | {name}"
            if uname: txt += f" (@{uname})"
            lb.insert(tk.END, txt)
    refresh()
    
    fr_b = ttk.Frame(win); fr_b.pack(fill="x", padx=10, pady=10)
    
    def login_selected_account():
        sel = lb.curselection()
        if not sel: messagebox.showwarning("!", "Выберите аккаунт!"); return
        idx = sel[0]
        s_data = load_sessions()[idx]
        phone = s_data['phone']
        
        def auth_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
            
            async def process():
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        try:
                            await client.send_code_request(phone)
                            code = await loop.run_in_executor(None, ask_code_gui, phone, False)
                            if not code: return
                            try:
                                await client.sign_in(phone, code)
                            except SessionPasswordNeededError:
                                pwd = await loop.run_in_executor(None, ask_code_gui, phone, True)
                                await client.sign_in(password=pwd)
                        except Exception as ex:
                            messagebox.showerror("Ошибка входа", str(ex))
                            return
                    
                    me = await client.get_me()
                    update_session_info(phone, f"{me.first_name} {me.last_name or ''}", me.username or "")
                    messagebox.showinfo("Успех", f"Аккаунт {phone} обновлен!\nUsername: @{me.username}")
                    win.after(0, refresh)
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))
                finally:
                    # ГАРАНТИРОВАННОЕ ОТКЛЮЧЕНИЕ
                    if client.is_connected():
                        await client.disconnect()

            try:
                loop.run_until_complete(process())
            finally:
                loop.close()
                
        threading.Thread(target=auth_thread, daemon=True).start()

    def add():
        d = Toplevel(win); d.title("Добавление аккаунта"); d.geometry("350x450") # Чуть увеличили высоту
        
        ttk.Label(d, text="Номер телефона (например +7999...):").pack(pady=(10,0))
        e_phone = ttk.Entry(d, width=30); e_phone.pack(pady=5)
        
        # === ДОБАВИЛИ ЛЕЙБЛ СТАТУСА ===
        lbl_status = ttk.Label(d, text="", foreground="blue")
        lbl_status.pack(pady=5)
        # ==============================

        res_frame = ttk.LabelFrame(d, text="API Данные", padding=10); res_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(res_frame, text="API ID:").grid(row=0, column=0)
        e_api_id = ttk.Entry(res_frame, width=20); e_api_id.grid(row=0, column=1)
        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0)
        e_api_hash = ttk.Entry(res_frame, width=20); e_api_hash.grid(row=1, column=1)
        
        def auto_get_api_thread(phone, btn):
            try:
                # Обновляем статус
                d.after(0, lambda: lbl_status.config(text="⏳ Подключение к my.telegram.org...", foreground="blue"))
                
                wc = TelegramWebClient()
                wc.send_password(phone)
                
                d.after(0, lambda: lbl_status.config(text="⌨️ Ожидание кода...", foreground="black"))
                code = ask_code_gui(phone, False)
                
                if not code: 
                    d.after(0, lambda: btn.config(state='normal'))
                    d.after(0, lambda: lbl_status.config(text="❌ Отмена ввода кода", foreground="red"))
                    return

                d.after(0, lambda: lbl_status.config(text="🔐 Вход на сайт...", foreground="blue"))
                wc.login(phone, code)
                
                d.after(0, lambda: lbl_status.config(text="📂 Получение API ключей...", foreground="blue"))
                keys = wc.get_app_data()
                
                def finish_saving():
                    if keys is None:
                        lbl_status.config(text="❌ Не удалось получить ключи", foreground="red")
                        messagebox.showerror("Ошибка", "Не удалось найти API ID/Hash на странице.\nВозможно, сайт изменился или требует 2FA пароль.")
                        btn.config(state='normal'); return
                    
                    e_api_id.delete(0, tk.END); e_api_id.insert(0, keys['api_id'])
                    e_api_hash.delete(0, tk.END); e_api_hash.insert(0, keys['api_hash'])
                    
                    lbl_status.config(text="✅ Ключи получены! Сохраняем...", foreground="green")
                    
                    ss = load_sessions()
                    if any(s.get('phone') == phone for s in ss):
                          messagebox.showwarning("Дубликат", "Номер уже в списке!")
                    else:
                        ss.append({
                            "api_id": str(keys['api_id']), 
                            "api_hash": str(keys['api_hash']), 
                            "phone": phone, 
                            "name": "Auto (Требуется вход)", 
                            "username": ""
                        })
                        save_sessions(ss)
                        refresh(); refresh_main_checks()
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!\nТеперь нажмите 'Войти / Обновить' или сразу 'СТАРТ'.")
                        d.destroy()
                        
                d.after(0, finish_saving)
                
            except Exception as e:
                err_msg = str(e)
                print(f"DEBUG ERROR: {err_msg}") # Для отладки в консоли
                d.after(0, lambda: lbl_status.config(text="❌ Ошибка", foreground="red"))
                d.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой авто-получения:\n{err_msg}"))
                d.after(0, lambda: btn.config(state='normal'))

        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone: messagebox.showerror("Ошибка", "Номер?"); return
            btn_auto.config(state='disabled')
            threading.Thread(target=auto_get_api_thread, args=(phone, btn_auto), daemon=True).start()
        
        btn_auto = ttk.Button(d, text="⚡ Получить API ID/Hash автоматически", command=start_auto_process)
        btn_auto.pack(pady=5)
        
        def s():
            if not e_api_id.get() or not e_phone.get(): messagebox.showwarning("!", "Поля пусты"); return
            ss = load_sessions()
            ss.append({"api_id":e_api_id.get(),"api_hash":e_api_hash.get(),"phone":e_phone.get(), "name":"Manual", "username":""})
            save_sessions(ss); d.destroy(); refresh(); refresh_main_checks()
        ttk.Button(d, text="Сохранить вручную", command=s).pack(pady=10)
    
    def delt():
        if not lb.curselection(): return
        ss = load_sessions()
        del ss[lb.curselection()[0]]
        save_sessions(ss); refresh(); refresh_main_checks()
        
    ttk.Button(fr_b, text="Добавить", command=add).pack(side="left")
    ttk.Button(fr_b, text="🔄 Войти / Обновить", command=login_selected_account).pack(side="left", padx=5)
    ttk.Button(fr_b, text="Удалить", command=delt).pack(side="left", padx=5)

## === MAIN UI ===

root = tk.Tk()
root.title("TG Master v22.1 (Guest Scroll Fixed)")
root.geometry("850x700")
style = ttk.Style()
style.theme_use('clam')

guest_account_index = tk.IntVar(value=-1)
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=5, pady=5)

tab1 = ttk.Frame(notebook)
notebook.add(tab1, text=" ЗАПУСК ")
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text=" АККАУНТЫ ")

fr_main = ttk.Frame(tab1)
fr_main.pack(fill="both", expand=True, padx=10, pady=5)

# === ЛЕВАЯ КОЛОНКА (Мейкеры) ===
fr_left = ttk.Frame(fr_main)
fr_left.pack(side="left", fill="both", expand=True, padx=(0, 5))

# --- Настройки ---
fr_top = ttk.LabelFrame(fr_left, text=" Настройки Мейкеров ", padding=10)
fr_top.pack(fill="x", padx=0, pady=5)

ttk.Label(fr_top, text="Имя групп:").grid(row=0, column=0)
ent_name = ttk.Entry(fr_top, width=20)
ent_name.grid(row=0, column=1, padx=5)

ttk.Label(fr_top, text="Кол-во:").grid(row=0, column=2)
ent_count = ttk.Entry(fr_top, width=5)
ent_count.insert(0, "5")
ent_count.grid(row=0, column=3, padx=5)

ttk.Button(fr_top, text="⚙ Опции", command=open_settings).grid(row=0, column=4, padx=10)
ttk.Label(fr_top, text="Ручной ввод @user (если нет Гостя):").grid(row=1, column=0, columnspan=2, pady=(10,0), sticky="w")
ent_user = ttk.Entry(fr_top, width=20)
ent_user.grid(row=1, column=2, columnspan=2, pady=(10,0), sticky="w")

# --- Список Мейкеров ---
fr_acc = ttk.LabelFrame(fr_left, text=" Выберите МЕЙКЕРОВ (кто создает): ", padding=10)
fr_acc.pack(fill="both", expand=True, padx=0, pady=5)

cv = tk.Canvas(fr_acc)
sb = ttk.Scrollbar(fr_acc, command=cv.yview)
cv.configure(yscrollcommand=sb.set)

cv.pack(side="left", fill="both", expand=True)
sb.pack(side="right", fill="y")

sc_fr = ttk.Frame(cv)
cv.create_window((0, 0), window=sc_fr, anchor="nw")
sc_fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))


# === ПРАВАЯ КОЛОНКА (Гость + Приветствие) ===
# ИСПРАВЛЕНИЕ 1: fill="both", expand=True (было fill="y") - теперь правая часть растягивается
fr_right = ttk.Frame(fr_main)
fr_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

# --- Список Гостей ---
fr_guest = ttk.LabelFrame(fr_right, text=" Выберите ГОСТЯ (кто пишет): ", padding=10)
fr_guest.pack(fill="both", expand=True, padx=5, pady=5)

guest_cv = tk.Canvas(fr_guest)
g_sb = ttk.Scrollbar(fr_guest, command=guest_cv.yview)
guest_cv.configure(yscrollcommand=g_sb.set)

guest_cv.pack(side="left", fill="both", expand=True)
g_sb.pack(side="right", fill="y")

guest_group = ttk.Frame(guest_cv)
guest_cv.create_window((0, 0), window=guest_group, anchor="nw")
guest_group.bind("<Configure>", lambda e: guest_cv.configure(scrollregion=guest_cv.bbox("all")))

# --- Приветствие ---
fr_greeting = ttk.LabelFrame(fr_right, text=" Текст ПРИВЕТСТВИЯ ", padding=10)
# ИСПРАВЛЕНИЕ 2: expand=False - поле приветствия прижато к низу, отдавая место списку
fr_greeting.pack(fill="x", expand=False, padx=5, pady=5)

var_send_greeting = tk.IntVar(value=1)
ttk.Checkbutton(fr_greeting, text="Отправлять автоматически", variable=var_send_greeting).pack(anchor="w", pady=(0,5))

txt_greeting = scrolledtext.ScrolledText(fr_greeting, height=8, width=30) 
txt_greeting.pack(fill="both", expand=True)
txt_greeting.insert("1.0", "Привет! Заходите.")


# === ФУНКЦИИ ОБНОВЛЕНИЯ UI ===

def refresh_main_checks():
    # Очистка старых виджетов
    for w in sc_fr.winfo_children(): w.destroy()
    for w in guest_group.winfo_children(): w.destroy()
    check_vars.clear()
    
    # "Без гостя"
    ttk.Radiobutton(guest_group, text="🚫 Без гостя", variable=guest_account_index, value=-1).pack(anchor="w", pady=2)
    
    # Загрузка сессий
    sessions = load_sessions()
    
    for i, s in enumerate(sessions):
        name = s.get('name', '..')
        uname = s.get('username', '..')
        text = f"{s['phone']} | {name}"
        
        # Чекбокс слева
        var = tk.IntVar()
        ttk.Checkbutton(sc_fr, text=text, variable=var).pack(anchor="w", padx=5, pady=2)
        check_vars.append(var)
        
        # Радиокнопка справа
        radio_text = f"{text} (@{uname})"
        ttk.Radiobutton(guest_group, text=radio_text, variable=guest_account_index, value=i).pack(anchor="w", pady=2)

# === КНОПКИ УПРАВЛЕНИЯ ===

fr_btn = ttk.Frame(tab1)
fr_btn.pack(fill="x", padx=10, pady=5)

start_btn = tk.Button(fr_btn, text="🚀 СТАРТ", bg="#dcedc8", command=start_process, height=2)
start_btn.pack(side="left", fill="x", expand=True)

tk.Button(fr_btn, text="🛑 СТОП", bg="#ffcdd2", command=stop_process, height=2).pack(side="left", fill="x", expand=True, padx=5)
tk.Button(fr_btn, text="НОВОЕ ОКНО", bg="#b3e5fc", command=open_new_window, height=2).pack(side="left", fill="x", expand=True)

# Лог
log_widget = scrolledtext.ScrolledText(tab1, height=8, state='disabled')
log_widget.pack(fill="both", expand=True, padx=10, pady=(0, 10))

for t, c in TAG_COLORS.items():
    log_widget.tag_config(t, foreground=c)

# Вкладка 2
ttk.Button(tab2, text="Управление аккаунтами", command=open_accounts).pack(expand=True)

if __name__ == "__main__":
    refresh_main_checks()
    root.mainloop()