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
import tkinter.simpledialog as simpledialog
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

# === ГОРЯЧИЕ КЛАВИШИ И СКРОЛЛ (ИСПРАВЛЕНО) ===

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

def setup_scroll_canvas(canvas):
    """Утилита для настройки скролла в Канвасе"""
    def _bound_to_mousewheel(event):
        canvas.bind_all("<MouseWheel>", lambda e: _on_mousewheel(e, canvas))
        canvas.bind_all("<Button-4>", lambda e: _on_mousewheel(e, canvas))
        canvas.bind_all("<Button-5>", lambda e: _on_mousewheel(e, canvas))

    def _unbound_to_mousewheel(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    def _on_mousewheel(event, widget):
        if event.num == 5 or event.delta < 0:
            widget.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            widget.yview_scroll(-1, "units")

    canvas.bind('<Enter>', _bound_to_mousewheel)
    canvas.bind('<Leave>', _unbound_to_mousewheel)

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
        
        self.session.post(f"{self.BASE_URL}/apps/create", data=create_data)
        
        time.sleep(1) 
        resp = self.session.get(f"{self.BASE_URL}/apps", timeout=10) 

        keys = find_keys_in_text(resp.text)
        if keys: return keys
        
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

    # Подготовка источников слов
    seps = [s.strip() for s in cfg.get("separators", "|").splitlines() if s.strip()] or ["|"]
    words = [w.strip() for w in cfg.get("words", "Chat").splitlines() if w.strip()] or ["Chat"]

    names = []

    # Если база пустая — подставим дефолт
    base_clean = (base or "").strip()
    if not base_clean and not use_words:
        base_clean = "Group"

    for _ in range(count):
        if use_words:
            name = f"{base_clean} {random.choice(seps)} {random.choice(words)}".strip()
        else:
            name = base_clean
        names.append(sanitize_title(name))

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

    def show():
        win = Toplevel(root)
        win.title("Telegram Auth")
        win.resizable(False, False)
        enable_hotkeys(win)

        container = ttk.Frame(win, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text=prompt, wraplength=330, font=("Arial", 10, "bold")).pack(pady=(0, 10))
        show_char = "*" if is_password else ""
        e = ttk.Entry(container, textvariable=res, font=("Arial", 12), show=show_char)
        e.pack(fill="x")
        e.focus()
        ttk.Button(container, text="ОТПРАВИТЬ", command=lambda: win.destroy()).pack(pady=10)

        def on_close():
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        # Модальность и позиционирование рядом с курсором
        make_modal(win, parent=root, near_cursor=True, width=350, height=180)
        # Ожидание закрытия окна (настоящая модальность)
        win.wait_window()

    root.after(0, show)
    time.sleep(0.05)  # дать шанс after(0) поставить окно
    return res.get().strip()

def sanitize_title(name):
    """Приводит название к валидному формату для CreateChatRequest."""
    t = (name or "").strip()
    # Удаляем лишние пробелы
    t = re.sub(r"\s+", " ", t)
    # Если пусто — дефолт
    if not t:
        t = f"Group {random.randint(1000, 9999)}"
    # Телеграм ограничивает длину (берём безопасно до 128)
    if len(t) > 128:
        t = t[:128]
    return t

# === WORKER LOGIC ===

async def add_and_clean(client, chat, user, delays):
    try:
        log_msg("INFO", f"   👤 Инвайт контакта: {user.first_name}...")
        # Используем прямой запрос, так как объект user получен из GetContactsRequest и имеет hash
        await client(functions.messages.AddChatUserRequest(
            chat_id=chat.id, user_id=user.id, fwd_limit=100
        ))
        log_msg("SUCCESS", f"   ✅ Контакт добавлен.")
        
        # Пауза перед чисткой (чтобы сервер успел обработать)
        await asyncio.sleep(1)
        
        # Чистка сообщений о вступлении
        msgs = await client.get_messages(chat, limit=5)
        ids = [m.id for m in msgs if m.action] # Удаляем только сервисные сообщения
        if ids: 
            await client.delete_messages(chat, ids, revoke=True)
            log_msg("INFO", "   🧹 История очищена.")
            
        return True
    except UserPrivacyRestrictedError:
        log_msg("WARN", f"   🚫 Приватность: {user.first_name} запретил инвайт.")
        return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Телеграм запретил инвайт.")
        raise
    except Exception as e:
        if "USER_ALREADY_PARTICIPANT" in str(e): return True
        log_msg("WARN", f"   ⚠️ Ошибка инвайта контакта: {e}")
        return False

async def safe_add_guest(client, chat_entity, user_entity, username_str=None):
    try:
        # Определяем имя для логов
        target_name = username_str if username_str else getattr(user_entity, 'username', 'Guest')
        log_msg("INFO", f"   👤 Добавляем Гостя (@{target_name})...")
        
        input_user = None
        
        # === ГЛАВНОЕ ИСПРАВЛЕНИЕ ===
        # 1. Сначала пробуем найти "свежий" InputEntity по строке юзернейма.
        # Это заставляет Телеграм выдать нам актуальный access_hash.
        if username_str:
            try:
                input_user = await client.get_input_entity(username_str)
            except Exception:
                input_user = None

        # 2. Если по строке не вышло (или её нет), пробуем старый метод через объект
        if not input_user and user_entity:
            try:
                input_user = await client.get_input_entity(user_entity)
            except Exception:
                pass

        # Если так и не нашли — ошибка
        if not input_user:
            log_msg("ERROR", f"   ❌ Не удалось найти пользователя @{target_name} (нет access_hash).")
            return False

        # Определение типа группы (канал/чат) и добавление
        from telethon.tl.types import Channel
        is_broadcast = isinstance(chat_entity, Channel) or getattr(chat_entity, 'megagroup', False)
        
        if is_broadcast:
            await client(functions.channels.InviteToChannelRequest(channel=chat_entity, users=[input_user]))
        else:
            await client(functions.messages.AddChatUserRequest(chat_id=chat_entity.id, user_id=input_user, fwd_limit=100))
            
        log_msg("SUCCESS", "   ✅ Гость успешно добавлен!")
        return True

    except UserPrivacyRestrictedError:
        log_msg("WARN", "   🚫 Приватность: Гость запретил инвайт в группы.")
        return False
    except UserNotMutualContactError:
        log_msg("WARN", "   🚫 Спам-блок: Гость не является взаимным контактом.")
        return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT при добавлении гостя.")
        return False
    except Exception as e:
        log_msg("ERROR", f"   🆘 Ошибка добавления Гостя: {e}")
        return False

### Полностью исправленный `worker_task` (замени весь блок этой функции на приведённый код)

async def worker_task(session, names, delays, target_username):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    # Создаем клиент
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    created_chat_ids = [] 
    my_id = None

    try:
        await client.connect()
        
        # === АВТОРИЗАЦИЯ ===
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! Отправляю код...")
            try:
                await client.send_code_request(phone)
                # Вызываем GUI для ввода кода в главном потоке
                code = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, False)
                if not code:
                    log_msg("WARN", f"⚠️ {phone}: Код не введен. Пропуск.")
                    return []
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    log_msg("WARN", f"🔐 {phone}: Нужен 2FA пароль!")
                    pwd = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, True)
                    await client.sign_in(password=pwd)
            except Exception as auth_e:
                log_msg("ERROR", f"❌ {phone}: Ошибка входа: {auth_e}")
                return []

        me = await client.get_me()
        my_id = me.id
        log_msg("INFO", f"🚀 {phone} (ID: {my_id}): Maker начал работу.")

        # === 1. ПРЕДВАРИТЕЛЬНЫЙ ПОИСК ГОСТЯ ===
        target_user_entity = None
        # Проверяем, нужно ли добавлять гостя и задан ли юзернейм
        if delays.get('add_username', 1) and target_username:
            clean_user = target_username.strip().replace('@', '')
            try:
                # Получаем сущность ОДИН РАЗ перед циклом. 
                # Telethon закэширует hash в сессии.
                target_user_entity = await client.get_entity(clean_user)
                log_msg("INFO", f"   🎯 Гость найден: @{clean_user} (ID: {target_user_entity.id})")
            except Exception as e:
                log_msg("WARN", f"   ⚠️ Гость @{clean_user} НЕ НАЙДЕН: {e}")

        # === 2. ПОЛУЧЕНИЕ КОНТАКТОВ ===
        contact_users = []
        if delays.get('add_contacts', 1):
            try:
                cts = await client(functions.contacts.GetContactsRequest(hash=0))
                # Исключаем ботов, удаленных и себя
                contact_users = [u for u in cts.users if not u.bot and not u.deleted and u.id != me.id]
                random.shuffle(contact_users)
                log_msg("INFO", f"   📋 Контактов доступно: {len(contact_users)}")
            except: pass

        delayed_invites = [] # Список для режима "После"

        # === 3. ЦИКЛ СОЗДАНИЯ ГРУПП ===
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            log_msg("INFO", f"🛠 ({i+1}/{len(names)}) Создаю: {name}")
            
            try:
                # Создаем чат (пустой список юзеров)
                res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                created_chat_ids.append(chat.id)
                log_msg("SUCCESS", f"   ✅ Группа создана (ID: {chat.id})")

                # А. Добавляем ГОСТЯ (если он был найден ранее)
                if target_user_entity:
                    try:
                        log_msg("INFO", f"   👤 Инвайт Гостя...")
                        await client(functions.messages.AddChatUserRequest(
                            chat_id=chat.id, 
                            user_id=target_user_entity.id, # Используем ID уже найденной сущности
                            fwd_limit=100
                        ))
                        log_msg("SUCCESS", "   ✅ Гость добавлен.")
                    except Exception as e: 
                        log_msg("ERROR", f"   🆘 Не удалось добавить Гостя: {e}")

                # Б. Добавляем КОНТАКТ (если включено)
                if delays.get('add_contacts', 1) and contact_users:
                    user_to_add = contact_users.pop(0)
                    
                    if delays.get('contact_mode', 0) == 0: # Режим "Сразу"
                        await smart_sleep(delays['contact'], delays['random'])
                        await add_and_clean(client, chat, user_to_add, delays)
                    else: # Режим "После"
                        delayed_invites.append((chat, user_to_add))
                        log_msg("INFO", f"   ⏳ Контакт отложен (Режим 'После')")
                
                # Пауза между созданием групп
                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: FLOOD WAIT. Останавливаю работу.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Флуд, ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка создания: {e}")

        # === 4. ОБРАБОТКА ОТЛОЖЕННЫХ КОНТАКТОВ ===
        if delayed_invites and not stop_flag.is_set():
            log_msg("INFO", f"📥 {phone}: Группы созданы. Начинаю добавление контактов...")
            for idx, (chat_obj, user_obj) in enumerate(delayed_invites):
                if stop_flag.is_set(): break
                log_msg("INFO", f"   ➕ ({idx+1}/{len(delayed_invites)}) Обработка группы...")
                
                await add_and_clean(client, chat_obj, user_obj, delays)
                await smart_sleep(delays['contact'], delays['random'])

        log_msg("SUCCESS", f"🏁 {phone}: Мейкер завершил работу.")
        # Возвращаем словарь, чтобы соответствовать формату вашего основного кода v23
        return {'maker_id': my_id, 'chats': created_chat_ids}

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка {phone}: {e}")
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

# === UI MODAL & POSITIONING HELPERS ===

def get_cursor_screen_pos():
    try:
        x, y = root.winfo_pointerxy()
        return x, y
    except Exception:
        return 200, 200  # fallback

def position_near_cursor(win, width=None, height=None, offset=(12, 12)):
    """Позиционирует окно рядом с курсором, с ограничением в пределах экрана."""
    try:
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        cx, cy = get_cursor_screen_pos()
        win.update_idletasks()
        w = width or win.winfo_width() or 350
        h = height or win.winfo_height() or 200
        x = max(0, min(screen_w - w, cx + offset[0]))
        y = max(0, min(screen_h - h, cy + offset[1]))
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass

def make_modal(win, parent=None, near_cursor=True, width=None, height=None):
    """
    Делает окно по-настоящему модальным и видимым:
    - transient к родителю
    - всегда поверх
    - перехватывает ввод (grab_set)
    - фокус сразу
    - опционально ставит рядом с курсором
    """
    try:
        if parent:
            win.transient(parent)
        win.attributes('-topmost', True)
        win.lift()
        win.focus_force()
        win.grab_set()
        if near_cursor:
            position_near_cursor(win, width=width, height=height)
    except Exception:
        pass

def open_new_window():
    try: subprocess.Popen([sys.executable, __file__])
    except Exception as e: messagebox.showerror("Ошибка", f"Не удалось открыть новое окно: {e}")

def start_process():
    stop_flag.clear()
    log_widget.config(state='normal')
    log_widget.delete("1.0", tk.END)
    log_widget.config(state='disabled')

    sessions_data = load_sessions()
    selected_indices = [i for i, v in enumerate(check_vars) if v.get()]

    guest_idx = guest_account_index.get()
    guest_session = None

    if guest_idx != -1:
        if guest_idx < len(sessions_data):
            guest_session = sessions_data[guest_idx]
            # Удаляем гостя из списка мейкеров, если он там был выбран
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
    except:
        return

    # Имя и количество
    base_name = ent_name.get().strip()
    try:
        count_per_maker = int(ent_count.get())
    except:
        return

    # Гарантия непустого имени при выключенных случайных словах
    use_words_flag = int(cfg.get("use_random_words", "1"))
    if not base_name and not use_words_flag:
        base_name = "Group"
        ent_name.delete(0, tk.END)
        ent_name.insert(0, base_name)

    manual_username = ent_user.get().strip().replace('@', '')

    # Генерация и проверка имён (один раз)
    names = generate_group_names(base_name, count_per_maker)
    if not names or any(not n.strip() for n in names):
        messagebox.showerror("Ошибка", "Не удалось сгенерировать валидные имена групп. Проверьте настройки слов/разделителей.")
        start_btn.config(state='normal')
        return

    start_btn.config(state='disabled')
    threading.Thread(
        target=run_thread,
        args=(main_sessions, guest_session, names, delays, manual_username, greeting_text, need_greet),
        daemon=True
    ).start()


# 📝 ЛОГИКА ЗАМЕТОК
NOTES_FILE = "notes_data.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_notes_to_file(data):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        messagebox.showerror("Ошибка сохранения", str(e))

def create_note_tab(notebook, title, content=""):
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=title)
    
    # Текстовое поле
    txt = scrolledtext.ScrolledText(frame, font=("Arial", 11))
    txt.pack(fill="both", expand=True, padx=5, pady=5)
    txt.insert("1.0", content)
    
    # Панель кнопок снизу
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill="x", padx=5, pady=5)
    
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

    ttk.Button(btn_frame, text="💾 Сохранить", command=_save).pack(side="left")
    ttk.Button(btn_frame, text="🗑 Удалить вкладку", command=_delete).pack(side="right")
    
    # Возвращаем фокус на главную вкладку, чтобы не "залипать"
    notebook.select(frame)

def on_tab_changed(event):
    nb = event.widget
    try:
        # Получаем имя текущей вкладки
        current_tab_index = nb.index("current")
        tab_title = nb.tab(current_tab_index, "text")
        
        if tab_title == "  ➕  ":
            # Спрашиваем имя новой вкладки
            new_title = simpledialog.askstring("Новая заметка", "Введите название вкладки:")
            
            # Возвращаемся на первую вкладку пока создаем новую
            nb.select(0) 
            
            if new_title:
                # Проверка на дубликаты
                notes = load_notes()
                if new_title in notes:
                    messagebox.showwarning("Ошибка", "Такое имя уже есть!")
                    return

                # Создаем вкладку (вставляем ПЕРЕД плюсом)
                last_index = nb.index("end") - 1
                frame = ttk.Frame(nb)
                
                # Текстовое поле
                txt = scrolledtext.ScrolledText(frame, font=("Arial", 11))
                txt.pack(fill="both", expand=True, padx=5, pady=5)
                
                # Кнопки
                btn_frame = ttk.Frame(frame)
                btn_frame.pack(fill="x", padx=5, pady=5)
                
                def _save():
                    d = load_notes()
                    d[new_title] = txt.get("1.0", tk.END)
                    save_notes_to_file(d)
                
                def _delete():
                    if messagebox.askyesno("Удаление", f"Удалить '{new_title}'?"):
                        d = load_notes()
                        if new_title in d: del d[new_title]
                        save_notes_to_file(d)
                        nb.forget(frame)

                ttk.Button(btn_frame, text="💾 Сохранить текст", command=_save).pack(side="left")
                ttk.Button(btn_frame, text="🗑 Удалить", command=_delete).pack(side="right")

                nb.insert(last_index, frame, text=new_title)
                nb.select(last_index) # Переключаемся на новую
    except:
        pass

# ===  ОКНА (НАСТРОЙКИ И АККАУНТЫ) ===

def open_settings():
    win = Toplevel(root)
    win.title("Настройки")
    enable_hotkeys(win)

    cfg = load_config()

    main_frame = ttk.Frame(win, padding=15)
    main_frame.pack(fill="both", expand=True)

    lf = ttk.LabelFrame(main_frame, text=" ⏱ Тайминги (сек) ", padding=10)
    lf.pack(fill="x", pady=5)

    def toggle_inputs(*args):
        st = 'disabled' if var_rand.get() else 'normal'
        e1.config(state=st); e2.config(state=st)

    var_rand = tk.IntVar(value=int(cfg["random_delay"]))
    var_rand.trace_add("write", toggle_inputs)

    ttk.Checkbutton(lf, text="⚡ Рандомная задержка (5-15 сек)", variable=var_rand).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

    ttk.Label(lf, text="Создание группы:").grid(row=1, column=0, sticky="w", pady=2)
    e1 = ttk.Entry(lf, width=10); e1.grid(row=1, column=1, sticky="e", pady=2); e1.insert(0, cfg["delay_creation"])

    ttk.Label(lf, text="Инвайт контакта:").grid(row=2, column=0, sticky="w", pady=2)
    e2 = ttk.Entry(lf, width=10); e2.grid(row=2, column=1, sticky="e", pady=2); e2.insert(0, cfg["delay_contact"])

    toggle_inputs()

    lf2 = ttk.LabelFrame(main_frame, text=" ⚙ Опции ", padding=10)
    lf2.pack(fill="x", pady=10)

    v_use_words = tk.IntVar(value=int(cfg.get("use_random_words", "1")))
    ttk.Checkbutton(lf2, text="Добавлять случайные слова к названию", variable=v_use_words).pack(anchor="w", pady=2)

    v_add_user = tk.IntVar(value=int(cfg["add_username"]))
    ttk.Checkbutton(lf2, text="Инвайт юзера (Гостя)", variable=v_add_user).pack(anchor="w", pady=2)

    v_add_cont = tk.IntVar(value=int(cfg["add_contacts"]))
    ttk.Checkbutton(lf2, text="Инвайт контактов", variable=v_add_cont).pack(anchor="w", pady=2)

    ttk.Separator(lf2, orient='horizontal').pack(fill='x', pady=5)

    ttk.Label(lf2, text="Режим контактов:").pack(anchor="w")
    v_mode = tk.IntVar(value=int(cfg["contact_mode"]))
    ttk.Radiobutton(lf2, text="Сразу (При создании)", variable=v_mode, value=0).pack(anchor="w")
    ttk.Radiobutton(lf2, text="После (Сначала все группы)", variable=v_mode, value=1).pack(anchor="w")

    def save():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get())
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        new_cfg["delay_cleanup"] = "10"
        new_cfg["add_username"] = str(v_add_user.get())
        new_cfg["add_contacts"] = str(v_add_cont.get())
        new_cfg["use_random_words"] = str(v_use_words.get())
        new_cfg["contact_mode"] = str(v_mode.get())
        save_config(new_cfg)
        win.destroy()

    ttk.Button(main_frame, text="💾 Сохранить", command=save).pack(fill="x", pady=10)

    win.update_idletasks()
    make_modal(win, parent=root, near_cursor=True, width=450, height=550)

def open_accounts():
    win = Toplevel(root)
    win.title("Управление аккаунтами")
    enable_hotkeys(win)

    main_fr = ttk.Frame(win, padding=10)
    main_fr.pack(fill="both", expand=True)

    lb_frame = ttk.Frame(main_fr)
    lb_frame.pack(fill="both", expand=True)

    lb = tk.Listbox(lb_frame, selectmode=tk.EXTENDED, font=("Consolas", 10), activestyle="none")
    sc = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sc.set)
    lb.pack(side="left", fill="both", expand=True)
    sc.pack(side="right", fill="y")

    try:
        def _listbox_wheel(event):
            lb.yview_scroll(int(-1*(event.delta/120)), "units")
        lb.bind("<MouseWheel>", _listbox_wheel)
    except:
        pass

    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            txt = f"{s['phone']} | {name}"
            if uname: txt += f" (@{uname})"
            lb.insert(tk.END, txt)
    refresh()

    btn_frame = ttk.Frame(main_fr, padding=(0, 10))
    btn_frame.pack(fill="x")

    def login_selected_account():
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("!", "Выберите аккаунт!")
            win.lift(); win.focus_force()
            return
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
                            if not code:
                                return
                            try:
                                await client.sign_in(phone, code)
                            except SessionPasswordNeededError:
                                pwd = await loop.run_in_executor(None, ask_code_gui, phone, True)
                                await client.sign_in(password=pwd)
                        except Exception as ex:
                            messagebox.showerror("Ошибка входа", str(ex))
                            win.lift(); win.focus_force()
                            return

                    me = await client.get_me()
                    update_session_info(phone, f"{me.first_name} {me.last_name or ''}", me.username or "")
                    messagebox.showinfo("Успех", f"Аккаунт {phone} обновлен!\nUsername: @{me.username}")
                    win.after(0, refresh)
                    win.after(0, lambda: (win.lift(), win.focus_force()))
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))
                    win.lift(); win.focus_force()
                finally:
                    if client.is_connected():
                        await client.disconnect()

            try:
                loop.run_until_complete(process())
            finally:
                loop.close()
        threading.Thread(target=auth_thread, daemon=True).start()

    def add():
        d = Toplevel(win)
        d.title("Добавление аккаунта")
        enable_hotkeys(d)

        c_frame = ttk.Frame(d, padding=15)

        c_frame.pack(fill="both", expand=True)

        ttk.Label(c_frame, text="Номер телефона (+7...):").pack(anchor="w")
        e_phone = ttk.Entry(c_frame, width=35)
        e_phone.pack(fill="x", pady=(0, 10))

        lbl_status = ttk.Label(c_frame, text="", foreground="blue")
        lbl_status.pack(pady=5)

        res_frame = ttk.LabelFrame(c_frame, text=" API Данные ", padding=10)
        res_frame.pack(fill="x", pady=10)

        ttk.Label(res_frame, text="API ID:").grid(row=0, column=0, sticky="w")
        e_api_id = ttk.Entry(res_frame, width=25); e_api_id.grid(row=0, column=1, padx=5, sticky="e")

        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0, sticky="w", pady=5)
        e_api_hash = ttk.Entry(res_frame, width=25); e_api_hash.grid(row=1, column=1, padx=5, sticky="e", pady=5)

        def auto_get_api_thread(phone, btn):
            try:
                d.after(0, lambda: lbl_status.config(text="⏳ Подключение...", foreground="blue"))
                wc = TelegramWebClient()
                wc.send_password(phone)

                d.after(0, lambda: lbl_status.config(text="⌨️ Ожидание кода...", foreground="black"))
                code = ask_code_gui(phone, False)
                if not code:
                    d.after(0, lambda: btn.config(state='normal'))
                    d.after(0, lambda: lbl_status.config(text="❌ Отмена", foreground="red"))
                    d.after(0, lambda: (d.lift(), d.focus_force()))
                    return

                d.after(0, lambda: lbl_status.config(text="🔐 Вход...", foreground="blue"))
                wc.login(phone, code)

                d.after(0, lambda: lbl_status.config(text="📂 Получение ключей...", foreground="blue"))
                keys = wc.get_app_data()

                def finish_saving():
                    if keys is None:
                        lbl_status.config(text="❌ Ошибка ключей", foreground="red")
                        messagebox.showerror("Ошибка", "Не удалось найти API ID/Hash.")
                        btn.config(state='normal')
                        d.lift(); d.focus_force()
                        return

                    e_api_id.delete(0, tk.END); e_api_id.insert(0, keys['api_id'])
                    e_api_hash.delete(0, tk.END); e_api_hash.insert(0, keys['api_hash'])

                    lbl_status.config(text="✅ Ключи получены!", foreground="green")

                    ss = load_sessions()
                    if any(s.get('phone') == phone for s in ss):
                        messagebox.showwarning("Дубликат", "Номер уже в списке!")
                        d.lift(); d.focus_force()
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
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!")
                        d.destroy()
                        win.after(0, lambda: (win.lift(), win.focus_force()))

                d.after(0, finish_saving)
            except Exception as e:
                err_msg = str(e)
                d.after(0, lambda: lbl_status.config(text="❌ Ошибка", foreground="red"))
                d.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой:\n{err_msg}"))
                d.after(0, lambda: btn.config(state='normal'))
                d.after(0, lambda: (d.lift(), d.focus_force()))

        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone:
                messagebox.showerror("Ошибка", "Номер?")
                d.lift(); d.focus_force()
                return
            btn_auto.config(state='disabled')
            threading.Thread(target=auto_get_api_thread, args=(phone, btn_auto), daemon=True).start()

        btn_auto = ttk.Button(c_frame, text="⚡ Авто-получение API (my.telegram.org)", command=start_auto_process)
        btn_auto.pack(fill="x", pady=5)

        def manual_save():
            if not e_api_id.get() or not e_phone.get():
                messagebox.showwarning("!", "Поля пусты")
                d.lift(); d.focus_force()
                return
            ss = load_sessions()
            ss.append({"api_id": e_api_id.get(), "api_hash": e_api_hash.get(), "phone": e_phone.get(), "name": "Manual", "username": ""})
            save_sessions(ss)
            d.destroy(); refresh(); refresh_main_checks()
            win.after(0, lambda: (win.lift(), win.focus_force()))

        ttk.Button(c_frame, text="💾 Сохранить вручную", command=manual_save).pack(fill="x", pady=10)

        d.update_idletasks()
        make_modal(d, parent=win, near_cursor=True, width=380, height=500)

    ttk.Button(btn_frame, text="➕ Добавить аккаунт", command=add).pack(side="left", fill="x", expand=True, padx=(0,5))
    ttk.Button(btn_frame, text="🔄 Войти / Проверить", command=login_selected_account).pack(side="left", fill="x", expand=True, padx=5)

    def delt():
        selected_indices = lb.curselection()
        if not selected_indices:
            win.lift(); win.focus_force()
            return
        count = len(selected_indices)
        if not messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить {count} аккаунтов?"):
            win.lift(); win.focus_force()
            return

        ss = load_sessions()
        for index in reversed(selected_indices):
            if index < len(ss):
                del ss[index]
        save_sessions(ss)
        refresh()
        refresh_main_checks()
        win.after(0, lambda: (win.lift(), win.focus_force()))
    ttk.Button(btn_frame, text="❌ Удалить выбранные", command=delt).pack(side="left", fill="x", expand=True, padx=(5,0))

    win.update_idletasks()
    make_modal(win, parent=root, near_cursor=True, width=600, height=500)

# === MAIN UI CONSTRUCTION ===

root = tk.Tk()
root.title("TG Master v23.0 (Update UI Fix)")
root.geometry("1000x700")
enable_hotkeys(root) 

style = ttk.Style()
style.theme_use('clam')
style.configure("TButton", padding=5, font=("Arial", 10))
style.configure("TLabel", font=("Arial", 10))
style.configure("TLabelframe", font=("Arial", 10, "bold"))
style.configure("TLabelframe.Label", foreground="#333")

guest_account_index = tk.IntVar(value=-1)

# Главный контейнер (Вкладки)
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

# 1. Основная вкладка (ЗАПУСК)
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="  🚀 ПАНЕЛЬ ЗАПУСКА  ")

# 2. НОВАЯ ЗАКРЕПЛЕННАЯ ВКЛАДКА (ИНСТРУКЦИЯ)
tab_help = ttk.Frame(notebook)
notebook.add(tab_help, text=" 📘 (Инструкция) ")

# --- Текст инструкции на китайском ---
help_cn_text = """欢迎使用 TG Master 群组管理工具！
此工具用于批量创建 Telegram 群组、邀请用户并进行管理。

📌 快速开始指南 (Quick Start):

1️⃣ 添加账号 (Accounts):
   - 点击 "👥 Аккаунты" (账户管理)。
   - 点击 "➕ Добавить аккаунт" (添加)。
   - 输入手机号，点击 "⚡ Авто-получение API" (自动获取 API)。
   - 输入验证码完成登录。

2️⃣ 设置制造者 (Makers):
   - 在左侧 "2. Выберите Мейкеров" 列表中，勾选用于创建群组的账号。
   - 在上方 "1. Настройки Мейкера" 设置群组名称 (Имя групп) 和数量 (Кол-во)。

3️⃣ 设置访客 (Guest):
   - 在右侧 "3. Выберите Гостя" 列表中，选择一个账号（单选）。
   - 此账号将负责向群组发送欢迎消息 (需设置 @username)。

4️⃣ 启动 (Start):
   - 在右下角 "4. Текст приветствия" 输入欢迎语。
   - 点击底部的 "🚀 ЗАПУСТИТЬ ПРОЦЕСС" (启动进程)。

⚠️ 注意事项:
- 首次使用请确保网络畅通。
- "Makers" 是创建群组的小号。
- "Guest" 是主要用于发言的大号。
- 建议开启 "Рандомная задержка" (随机延迟) 以防封号。

祝您使用愉快！
"""

# Текстовое поле для инструкции (только для чтения)
txt_help = scrolledtext.ScrolledText(tab_help, font=("Microsoft YaHei", 10), state='normal')
txt_help.pack(fill="both", expand=True, padx=5, pady=5)
txt_help.insert("1.0", help_cn_text)
txt_help.config(state='disabled') # Блокируем редактирование

# --- ЗАГРУЗКА СОХРАНЕННЫХ ЗАМЕТОК ---
saved_notes = load_notes()
for title, content in saved_notes.items():
    # Создаем фрейм для существующей заметки
    n_frame = ttk.Frame(notebook)
    notebook.add(n_frame, text=title)
    
    txt_area = scrolledtext.ScrolledText(n_frame, font=("Arial", 11))
    txt_area.pack(fill="both", expand=True, padx=5, pady=5)
    txt_area.insert("1.0", content)
    
    b_frame = ttk.Frame(n_frame)
    b_frame.pack(fill="x", padx=5, pady=5)
    
    # Важно: используем замыкания (defaults), чтобы закрепить переменные
    def _save_ex(t=title, tx=txt_area):
        d = load_notes()
        d[t] = tx.get("1.0", tk.END)
        save_notes_to_file(d)
        messagebox.showinfo("OK", "Сохранено!")

    def _del_ex(t=title, fr=n_frame):
        if messagebox.askyesno("Удалить", f"Удалить '{t}'?"):
            d = load_notes()
            if t in d: del d[t]
            save_notes_to_file(d)
            notebook.forget(fr)

    ttk.Button(b_frame, text="💾 Сохранить", command=_save_ex).pack(side="left")
    ttk.Button(b_frame, text="🗑 Удалить", command=_del_ex).pack(side="right")

# Вкладка-кнопка ПЛЮС
frame_plus = ttk.Frame(notebook)
notebook.add(frame_plus, text="  ➕  ")

# Биндим переключение вкладок для обработки нажатия на ПЛЮС
notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

# --- СТРУКТУРА ВКЛАДКИ ЗАПУСКА ---

paned = ttk.PanedWindow(tab1, orient="horizontal")
paned.pack(fill="both", expand=True, padx=5, pady=5)

# ЛЕВАЯ ПАНЕЛЬ (МЕЙКЕРЫ)
frame_left = ttk.Frame(paned)
paned.add(frame_left, weight=1)

# Настройки Мейкера
lf_maker_settings = ttk.LabelFrame(frame_left, text=" 1. Настройки Мейкера ", padding=10)
lf_maker_settings.pack(fill="x", pady=(0, 10))

grid_fr = ttk.Frame(lf_maker_settings)
grid_fr.pack(fill="x")

ttk.Label(grid_fr, text="Имя групп:").grid(row=0, column=0, sticky="w")
ent_name = ttk.Entry(grid_fr, width=20)
ent_name.grid(row=0, column=1, padx=5, sticky="w")

ttk.Label(grid_fr, text="Кол-во:").grid(row=0, column=2, sticky="w", padx=(10, 0))
ent_count = ttk.Entry(grid_fr, width=5)
ent_count.insert(0, "5")
ent_count.grid(row=0, column=3, padx=5, sticky="w")

ttk.Button(grid_fr, text="🛠 Опции", command=open_settings, width=10).grid(row=0, column=4, padx=10)

ttk.Label(grid_fr, text="Цель (если нет Гостя):").grid(row=1, column=0, columnspan=2, pady=(10,0), sticky="w")
ent_user = ttk.Entry(grid_fr, width=25)
ent_user.grid(row=1, column=2, columnspan=3, pady=(10,0), sticky="w")

ttk.Button(lf_maker_settings, text="👥 Аккаунты", command=open_accounts).pack(anchor="ne", pady=(0,5), padx=5)


# Список Мейкеров
lf_makers = ttk.LabelFrame(frame_left, text=" 2. Выберите Мейкеров (Кто создает) ", padding=10)
lf_makers.pack(fill="both", expand=True)

canvas_makers = tk.Canvas(lf_makers, bg="white", highlightthickness=0)
sb_makers = ttk.Scrollbar(lf_makers, command=canvas_makers.yview)
canvas_makers.configure(yscrollcommand=sb_makers.set)

canvas_makers.pack(side="left", fill="both", expand=True)
sb_makers.pack(side="right", fill="y")

sc_fr = ttk.Frame(canvas_makers) # Фрейм внутри канваса
canvas_makers.create_window((0, 0), window=sc_fr, anchor="nw")
sc_fr.bind("<Configure>", lambda e: canvas_makers.configure(scrollregion=canvas_makers.bbox("all")))
setup_scroll_canvas(canvas_makers)

# ПРАВАЯ ПАНЕЛЬ (ГОСТИ)
frame_right = ttk.Frame(paned)
paned.add(frame_right, weight=1)

# Список Гостей
lf_guest = ttk.LabelFrame(frame_right, text=" 3. Выберите Гостя (Кто пишет) - обязательно с юзом ", padding=10)
lf_guest.pack(fill="both", expand=True, pady=(0, 10))

canvas_guest = tk.Canvas(lf_guest, bg="white", highlightthickness=0)
sb_guest = ttk.Scrollbar(lf_guest, command=canvas_guest.yview)
canvas_guest.configure(yscrollcommand=sb_guest.set)

canvas_guest.pack(side="left", fill="both", expand=True)
sb_guest.pack(side="right", fill="y")

guest_group = ttk.Frame(canvas_guest)
canvas_guest.create_window((0, 0), window=guest_group, anchor="nw")
guest_group.bind("<Configure>", lambda e: canvas_guest.configure(scrollregion=canvas_guest.bbox("all")))
setup_scroll_canvas(canvas_guest) 

# Приветствие
lf_greet = ttk.LabelFrame(frame_right, text=" 4. Текст приветствия ", padding=10)
lf_greet.pack(fill="x", expand=False)

var_send_greeting = tk.IntVar(value=1)
ttk.Checkbutton(lf_greet, text="Отправлять сообщение при входе", variable=var_send_greeting).pack(anchor="w", pady=(0,5))

txt_greeting = scrolledtext.ScrolledText(lf_greet, height=5, width=30, font=("Arial", 10)) 
txt_greeting.pack(fill="both", expand=True)
txt_greeting.insert("1.0", "Привет! Заходите.")

# --- НИЖНЯЯ ПАНЕЛЬ (КНОПКИ И ЛОГ) ---
bottom_frame = ttk.Frame(tab1)
bottom_frame.pack(fill="both", padx=5, pady=5)

# Контейнер для кнопок
btn_frame = ttk.Frame(bottom_frame)
btn_frame.pack(fill="x", pady=(0, 10))

# Обработчик остановки процесса (не создаёт виджеты, только логика)
def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Завершение текущих операций)")
    # Безопасно вернуть кнопку Старт в активное состояние через главный поток
    if root:
        root.after(1000, lambda: start_btn.config(state='normal'))

# Кнопка запуска (start_btn используется в stop_process, это нормально — имя будет разрешено при вызове)
start_btn = tk.Button(
    btn_frame,
    text="🚀 ЗАПУСТИТЬ ПРОЦЕСС",
    bg="#4caf50",
    fg="white",
    font=("Arial", 12, "bold"),
    command=start_process,
    height=2
)
start_btn.pack(side="left", fill="x", expand=True)

# Кнопка стоп — привязываем к stop_process (функция уже определена выше)
stop_btn = tk.Button(
    btn_frame,
    text="🛑 СТОП",
    bg="#f44336",
    fg="white",
    font=("Arial", 12, "bold"),
    command=stop_process,
    height=2
)
stop_btn.pack(side="left", fill="x", expand=True, padx=5)

# Кнопка "Новое окно"
newwin_btn = tk.Button(
    btn_frame,
    text="НОВОЕ ОКНО",
    bg="#2196f3",
    fg="white",
    font=("Arial", 12, "bold"),
    command=open_new_window,
    height=2
)
newwin_btn.pack(side="left", fill="x", expand=True)

# Лог
log_frame = ttk.LabelFrame(bottom_frame, text=" Лог событий ", padding=5)
log_frame.pack(fill="both", expand=True)

log_widget = scrolledtext.ScrolledText(log_frame, height=8, state='disabled', font=("Consolas", 9))
log_widget.pack(fill="both", expand=True)

for t, c in TAG_COLORS.items():
    log_widget.tag_config(t, foreground=c)

# --- ФУНКЦИИ ОБНОВЛЕНИЯ UI ---
def refresh_main_checks():
    for w in sc_fr.winfo_children(): w.destroy()
    for w in guest_group.winfo_children(): w.destroy()
    check_vars.clear()
    
    ttk.Radiobutton(guest_group, text="🚫 Без гостя", variable=guest_account_index, value=-1).pack(anchor="w", pady=2)
    
    sessions = load_sessions()
    
    for i, s in enumerate(sessions):
        name = s.get('name', '..')
        uname = s.get('username', '..')
        
        # Левая колонка
        text_maker = f"{s['phone']} | {name}"
        var = tk.IntVar()
        cb = ttk.Checkbutton(sc_fr, text=text_maker, variable=var)
        cb.pack(anchor="w", padx=5, pady=2)
        check_vars.append(var)
        
        # Правая колонка
        radio_text = f"{text_maker} (@{uname})"
        ttk.Radiobutton(guest_group, text=radio_text, variable=guest_account_index, value=i).pack(anchor="w", pady=2)

if __name__ == "__main__":
    refresh_main_checks()
    root.mainloop()