import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel
import asyncio
import threading
from telethon import TelegramClient, functions, types, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError
)
from tkinter import filedialog # Добавить этот импорт
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

import google.generativeai as genai

# ==== конфиги ====
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

# === AI ASSISTANT CLASS ===
class SmartAssistant:
    def __init__(self):
        self.api_key = None
        self.model = None
        # Пытаемся загрузить ключ из конфига сразу
        cfg = load_config()
        if cfg.get("ai_api_key"):
            self.setup(cfg["ai_api_key"])

    def setup(self, key):
        self.api_key = key
        try:
            genai.configure(api_key=key)
            
            # 1. Спрашиваем у Google список ВСЕХ доступных моделей для этого ключа
            all_models = []
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        all_models.append(m.name)
            except: pass

            # 2. Список желаемых моделей (от лучшей к худшей)
            # models/gemini-1.5-flash - самая быстрая и дешевая (бесплатная)
            priority_list = [
                "gemini-1.5-flash", 
                "gemini-1.5-pro", 
                "gemini-1.0-pro", 
                "gemini-pro"
            ]
            
            chosen_model_name = None

            # 3. Ищем совпадение
            for priority in priority_list:
                for real_model in all_models:
                    if priority in real_model:
                        chosen_model_name = real_model
                        break
                if chosen_model_name: break
            
            # Если ничего из списка не нашли, берем ПЕРВУЮ попавшуюся из доступных
            if not chosen_model_name and all_models:
                chosen_model_name = all_models[0]

            # 4. Подключаем
            if chosen_model_name:
                # Убираем префикс models/ если он есть, библиотека иногда любит чистое имя
                clean_name = chosen_model_name.replace("models/", "")
                self.model = genai.GenerativeModel(clean_name)
                print(f"✅ ИИ успешно подключен к модели: {clean_name}")
            else:
                print("❌ Ошибка: Не найдено доступных моделей Gemini для этого ключа.")
                self.model = None

        except Exception as e:
            print(f"❌ Критическая ошибка подключения ИИ: {e}")
            self.model = None

# Создаем глобальный экземпляр помощника
ai_assistant = SmartAssistant()

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
        
        # Центрирование окна
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w, h = 350, 180
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.resizable(False, False)
        
        # === ЗАХВАТ УПРАВЛЕНИЯ ===
        win.attributes('-topmost', True) # Поверх всех окон
        win.lift()
        
        def force_focus():
            try:
                win.grab_set()       # Блокируем доступ к основному окну
                win.focus_force()    # Ставим курсор в это окно
            except: pass
        
        win.after(200, force_focus) # Небольшая задержка для надежности
        # ==========================

        enable_hotkeys(win) 
        
        ttk.Label(win, text=prompt, wraplength=330, font=("Arial", 10, "bold")).pack(pady=10)
        
        show_char = "*" if is_password else ""
        e = ttk.Entry(win, textvariable=res, font=("Arial", 14, "bold"), show=show_char, justify='center')
        e.pack(pady=5, padx=20, fill='x')
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
        time.sleep(0.2)
        
    return res.get().strip()

async def add_and_clean_strict(client, chat_entity, user):
    """Добавляет контакт и ПОЛНОСТЬЮ чистит историю (включая 'User joined')."""
    try:
        log_msg("INFO", f"   👤 Инвайт контакта: {user.first_name}...")
        
        try:
            input_user = await client.get_input_entity(user)
        except:
            input_user = user.id

        # 1. Инвайт
        from telethon.tl.types import Channel
        is_broadcast = isinstance(chat_entity, Channel) or getattr(chat_entity, 'megagroup', False)
        
        if is_broadcast:
             await client(functions.channels.InviteToChannelRequest(channel=chat_entity, users=[input_user]))
        else:
             await client(functions.messages.AddChatUserRequest(chat_id=chat_entity.id, user_id=input_user, fwd_limit=100))
        
        log_msg("SUCCESS", f"   ✅ Контакт добавлен.")
        
        # 2. Пауза (ВАЖНО: ждем 4 сек, чтобы сервер создал сообщение о вступлении)
        await asyncio.sleep(4)
        
        # 3. Полная очистка
        try:
            if is_broadcast:
                # Для каналов удаляем всю историю
                await client(functions.channels.DeleteHistoryRequest(channel=chat_entity, max_id=0))
            else:
                # Для групп удаляем последние 100 сообщений (хватит для системных)
                messages = await client.get_messages(chat_entity, limit=100)
                msg_ids = [m.id for m in messages]
                if msg_ids:
                    await client.delete_messages(chat_entity, msg_ids, revoke=True)
            
            log_msg("INFO", f"   🧹 История очищена (системные сообщения удалены).")
        except Exception as e_clean:
            log_msg("WARN", f"   ⚠️ Не удалось почистить: {e_clean}")
        
        return True

    except UserPrivacyRestrictedError:
         log_msg("WARN", "   🚫 Приватность: запрет на инвайт.")
         return False
    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Пауза аккаунта.")
        raise
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Ошибка инвайта: {e}")
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
    
# === AI MONITOR & AUTO-REPLY LOGIC ===

# === AI MONITOR & AUTO-REPLY LOGIC (С ПОДДЕРЖКОЙ ФАЙЛОВ) ===

async def ai_message_handler(event, client, prompt_template, attachment_path):
    """Обработчик с ПАМЯТЬЮ и ОТПРАВКОЙ ФАЙЛОВ"""
    try:
        chat = await event.get_chat()
        sender = await event.get_sender()
        msg_text = event.raw_text
        chat_title = getattr(chat, 'title', getattr(chat, 'first_name', 'ЛС'))

        me = await client.get_me()
        if sender and (sender.id == me.id or sender.bot): return

        log_msg("DEBUG", f"📩 Входящее в '{chat_title}': {msg_text[:20]}...")

        # 1. ИСТОРИЯ ЧАТА
        history_text = ""
        try:
            messages = await client.get_messages(chat, limit=6)
            for m in reversed(messages):
                if not m.text: continue
                role = "Я (AI)" if m.out else "СОБЕСЕДНИК"
                history_text += f"{role}: {m.text}\n"
        except: 
            history_text = f"СОБЕСЕДНИК: {msg_text}"

        # 2. ЗАДЕРЖКА (10-30 сек)
        delay = random.randint(10, 30)
        log_msg("WAIT", f"⏳ Думаем... ({delay} сек)")
        await asyncio.sleep(delay)

        # 3. ГЕНЕРАЦИЯ ОТВЕТА
        try:
            # Добавляем инструкцию про файл, если он есть
            file_instruction = ""
            if attachment_path:
                file_instruction = (
                    "\n[ВАЖНО]: У тебя есть файл-документ (описан выше). "
                    "Если по контексту разговора пора показать этот документ собеседнику, "
                    "добавь в конец ответа тег [SEND_FILE]. "
                    "Не пиши 'я отправляю файл', просто добавь тег."
                )

            full_prompt = (
                f"Твоя роль и инструкция: {prompt_template}\n"
                f"{file_instruction}\n\n"
                f"=== ИСТОРИЯ ПЕРЕПИСКИ ===\n"
                f"{history_text}\n"
                f"=========================\n"
                f"ЗАДАЧА: Напиши ответ. Не повторяйся."
            )
            
            if ai_assistant.model:
                response = ai_assistant.model.generate_content(full_prompt).text.strip()
                
                # Check for file tag
                should_send_file = False
                if "[SEND_FILE]" in response:
                    should_send_file = True
                    response = response.replace("[SEND_FILE]", "").strip()

                # Send text
                async with client.action(chat, 'typing'):
                    await asyncio.sleep(random.randint(2, 5))
                
                if response:
                    await event.reply(response)
                    log_msg("SUCCESS", f"🤖 AI: {response[:30]}...")

                
                if should_send_file and attachment_path and os.path.exists(attachment_path):
                    log_msg("INFO", "📂 AI decided to send a document!")
                    async with client.action(chat, 'document'): 
                        await asyncio.sleep(2)
                    await client.send_file(chat, attachment_path)
                    log_msg("SUCCESS", "   📄 File sent.")
            else:
                log_msg("WARN", "⚠️ No AI key.")
            
        except Exception as e:
            log_msg("ERROR", f"Ошибка ответа ИИ: {e}")

    except Exception as main_e:
        print(f"Сбой обработчика: {main_e}")

def run_ai_monitor_thread(guest_session, system_instruction):
    if not guest_session: return
    if not ai_assistant.api_key: return

    api_id = int(guest_session['api_id'])
    api_hash = guest_session['api_hash']
    phone = guest_session['phone']
    
    # Загружаем путь к файлу из конфига
    cfg = load_config()
    attachment_path = cfg.get("ai_attachment", "")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(f"session_{phone}", api_id, api_hash, loop=loop)
    
    async def monitor():
        try:
            await client.connect()
            if not await client.is_user_authorized():
                log_msg("WARN", "Гость не авторизован!")
                return
            
            me = await client.get_me()
            log_msg("SUCCESS", f"🎧 ИИ-Автоответчик ЗАПУЩЕН для {me.first_name}!")
            
            # === ПРЕДВАРИТЕЛЬНЫЙ АНАЛИЗ ФАЙЛА (ЕСЛИ ЕСТЬ) ===
            final_instruction = system_instruction
            if attachment_path and os.path.exists(attachment_path):
                log_msg("WAIT", "🧐 ИИ изучает прикрепленный документ...")
                try:
                    # Загружаем картинку в PIL
                    import PIL.Image
                    img = PIL.Image.open(attachment_path)
                    
                    # Просим Gemini описать, что это
                    analysis_prompt = "Проанализируй это изображение/документ детально. Что здесь написано? Какой смысл? Выдай краткое содержание, чтобы я (ИИ) знал, что отвечать клиентам по этому документу."
                    
                    # Используем vision-модель (flash или pro поддерживают картинки)
                    vision_resp = ai_assistant.model.generate_content([analysis_prompt, img])
                    doc_desc = vision_resp.text
                    
                    log_msg("INFO", "✅ Документ проанализирован.")
                    
                    # Добавляем знания о документе в системную инструкцию
                    final_instruction += f"\n\n[КОНТЕКСТ ДОКУМЕНТА, КОТОРЫЙ У ТЕБЯ ЕСТЬ]:\n{doc_desc}\n"
                    
                except Exception as e:
                    log_msg("WARN", f"⚠️ Не удалось прочитать документ через ИИ: {e}")
            # ==================================================

            log_msg("INFO", "Ожидание сообщений...")
            
            @client.on(events.NewMessage(incoming=True))
            async def _wrapper(event):
                asyncio.create_task(ai_message_handler(event, client, final_instruction, attachment_path))
            
            while not stop_flag.is_set():
                await asyncio.sleep(1)
            
            log_msg("WARN", "🛑 Мониторинг остановлен.")
            
        except Exception as e:
            log_msg("ERROR", f"Ошибка монитора: {e}")
        finally:
            if client.is_connected(): await client.disconnect()

    threading.Thread(target=lambda: loop.run_until_complete(monitor()), daemon=True).start()

async def worker_task(session, names, delays, target_username):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    # Читаем настройки из конфига (галочки)
    do_add_contacts = delays.get('add_contacts', 1)
    mode_contacts = delays.get('contact_mode', 1) # 0 = Сразу, 1 = После
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    created_chats = [] 
    created_chat_ids = []
    my_id = None

    try:
        await client.connect()
        # ... (Блок авторизации остается стандартным, сокращен для краткости, он у вас рабочий) ...
        if not await client.is_user_authorized():
            # [Здесь ваш стандартный блок авторизации из прошлого кода]
            # Если нужно, скопируйте его из старого файла, он там верный.
            # Для надежности вставлю минимальный:
            try:
                await client.send_code_request(phone)
                code = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, False)
                if not code: return None
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pwd = await asyncio.get_running_loop().run_in_executor(None, ask_code_gui, phone, True)
                await client.sign_in(password=pwd)
            except Exception as e:
                log_msg("ERROR", f"❌ Ошибка входа {phone}: {e}")
                return None

        me = await client.get_me()
        my_id = me.id
        log_msg("INFO", f"🚀 {phone}: Начал работу.")

        # --- ПОИСК ГОСТЯ (Для добавления в группу) ---
        target_user_entity = None
        if target_username:
            clean_target = target_username.strip().replace('@', '').replace(' ', '')
            try:
                target_user_entity = await client.get_entity(clean_target)
                log_msg("INFO", f"   ✅ Гость найден: {target_user_entity.id}")
            except:
                if clean_target.replace('+', '').isdigit():
                    try:
                        contact = types.InputPhoneContact(
                             client_id=random.randint(0, 99999999), phone=clean_target,
                             first_name="Guest", last_name="Target"
                        )
                        result = await client(functions.contacts.ImportContactsRequest([contact]))
                        if result.users: target_user_entity = result.users[0]
                    except: pass

        # --- ПОДГОТОВКА КОНТАКТОВ ---
        contact_users = []
        if do_add_contacts:
            try:
                cts = await client(functions.contacts.GetContactsRequest(hash=0))
                guest_id = target_user_entity.id if target_user_entity else 0
                contact_users = [u for u in cts.users if not u.bot and not u.deleted and u.id != me.id and u.id != guest_id]
                random.shuffle(contact_users)
                log_msg("INFO", f"   📋 Контактов для работы: {len(contact_users)}")
            except: pass

        # --- ЦИКЛ СОЗДАНИЯ ГРУПП ---
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            
            try:
                # 1. Создаем группу (сразу с Гостем, если он есть)
                users_init = []
                if target_user_entity:
                    try:
                        input_guest = await client.get_input_entity(target_user_entity)
                        users_init.append(input_guest)
                    except: pass

                log_msg("INFO", f"🛠 ({i+1}/{len(names)}) Создаю: {name}...")
                res = await client(functions.messages.CreateChatRequest(users=users_init, title=name))
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                chat_entity = await client.get_entity(chat.id)
                
                created_chats.append(chat_entity)
                created_chat_ids.append(chat.id)
                
                guest_status = "с Гостем" if users_init else "БЕЗ Гостя"
                log_msg("SUCCESS", f"   ✅ Группа создана ({guest_status}). ID: {chat.id}")

                # Если Гость не добавился сразу (баг Телеграм), пробуем добавить еще раз
                if target_user_entity and not users_init:
                    await safe_add_guest(client, chat_entity, target_user_entity)

                # 2. Обработка контактов (РЕЖИМ 0: СРАЗУ)
                # Работает, если стоит галочка "Инвайт контактов" и режим "Сразу"
                if do_add_contacts and mode_contacts == 0:
                    if contact_users:
                        u = contact_users.pop(0)
                        await asyncio.sleep(2)
                        await add_and_clean_strict(client, chat_entity, u)
                    else:
                        log_msg("WARN", "   ⚠️ Контакты закончились!")

                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: ФЛУД! Стоп.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка создания: {e}")
                
                # === ИИ АНАЛИЗ (ВСТАВИТЬ СЮДА) ===
                def ask_ai_create():
                    # Проверка, инициализирован ли ИИ (чтобы не было ошибки, если ключа нет)
                    if 'ai_assistant' in globals() and ai_assistant.api_key:
                        advice = ai_assistant.analyze_error("Создание группы Telethon", str(e))
                        if advice: log_msg("DEBUG", f"🤖 ИИ: {advice}")
                
                # Запускаем в потоке, только если библиотека подключена
                try:
                    threading.Thread(target=ask_ai_create, daemon=True).start()
                except: pass

        # --- ЭТАП 2: КОНТАКТЫ ПОСЛЕ (РЕЖИМ 1) ---
        # Работает после создания всех групп, если стоит галочка и режим "После"
        if do_add_contacts and mode_contacts == 1 and not stop_flag.is_set():
            if created_chats and contact_users:
                log_msg("INFO", f"📥 {phone}: Добив контактов (Режим 'После')...")
                for chat in created_chats:
                    if stop_flag.is_set() or not contact_users: break
                    u = contact_users.pop(0)
                    try:
                        await add_and_clean_strict(client, chat, u)
                        await smart_sleep(delays['contact'], delays['random'])
                    except: pass

        log_msg("SUCCESS", f"🏁 {phone}: Завершил.")
        return {'maker_id': my_id, 'chats': created_chat_ids}

    except Exception as e:
        err_msg = str(e)
        log_msg("ERROR", f"❌ Критическая ошибка Maker: {err_msg}")
        
        # === ИИ АНАЛИЗ ===
        # Запускаем анализ в отдельном потоке, чтобы не морозить интерфейс
        def ask_ai():
            advice = ai_assistant.analyze_error("Работа Мейкера (создание/инвайт)", err_msg)
            if advice:
                log_msg("DEBUG", f"🤖 ИИ Советует: {advice}")
        
        threading.Thread(target=ask_ai, daemon=True).start()
        # =================
        
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
        
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 ГОСТЬ {phone}: Требуется вход! (Пропуск)")
            return

        me = await client.get_me()
        log_msg("GUEST", f"😎 ГОСТЬ ({me.first_name}) начинает рассылку...")

        # Обновляем кэш диалогов
        await client.get_dialogs(limit=50)
        
        count_sent = 0
        
        for gid in target_group_ids:
            if stop_flag.is_set(): break
            
            try:
                # Попытка 1: Найти группу по ID напрямую
                target_entity = None
                try:
                    # Пробуем как обычный чат (PeerChat)
                    target_entity = await client.get_entity(types.PeerChat(int(gid)))
                except:
                    # Если не вышло, пробуем просто по ID (Telethon сам разберется)
                    try:
                        target_entity = await client.get_entity(int(gid))
                    except:
                        pass

                if not target_entity:
                    log_msg("WARN", f"   ⚠️ Гость не может найти группу ID {gid}. Пропуск.")
                    continue

                # Отправка сообщения (БЕЗ ПРОВЕРОК УЧАСТНИКОВ)
                title = getattr(target_entity, 'title', str(gid))
                log_msg("DEBUG", f"   ✍️ Пишем в '{title}'...")
                
                await client.send_message(target_entity, greeting_text)
                log_msg("SUCCESS", f"   📨 Сообщение отправлено!")
                count_sent += 1
                
                # Пауза, чтобы Телеграм не забанил за спам
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except Exception as e:
                log_msg("WARN", f"   ⚠️ Ошибка отправки в {gid}: {e}")
                # Если ошибка FloodWait, ждем дольше
                if "FloodWait" in str(e):
                    await asyncio.sleep(10)

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count_sent} из {len(target_group_ids)}).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === THREAD RUNNER ===

def run_thread(main_sessions, guest_session, names, delays, target_username_manual, greeting_text, need_greet):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Определяем цель (Гостя)
    target_username = target_username_manual
    if guest_session:
        # Если выбран аккаунт гостя, берем его юзернейм/телефон
        g_user = guest_session.get('username', '').strip()
        g_phone = guest_session.get('phone', '').strip()
        target_username = g_user if g_user else g_phone

    # Логируем, что будем делать
    if need_greet:
        log_msg("INFO", "✉️ Приветствия: ВКЛЮЧЕНЫ")
    else:
        log_msg("INFO", "🔕 Приветствия: ВЫКЛЮЧЕНЫ (только создание и контакты)")

    # 1. ЗАПУСК МЕЙКЕРОВ (Они создают, добавляют гостя, добавляют контакты, чистят)
    maker_tasks = []
    for s in main_sessions:
        maker_tasks.append(worker_task(s, names, delays, target_username))
    
    try:
        if maker_tasks:
            log_msg("INFO", "=== ЗАПУСК МЕЙКЕРОВ ===")
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            # Собираем данные для Гостя
            all_maker_ids = []
            all_created_groups = []
            for res in results:
                if res:
                    if res.get('maker_id'): all_maker_ids.append(res['maker_id'])
                    if res.get('chats'): all_created_groups.extend(res['chats'])
            
            log_msg("INFO", f"📊 МЕЙКЕРЫ ГОТОВЫ. Групп: {len(all_created_groups)}")

            # 2. ЗАПУСК ГОСТЯ (ТОЛЬКО ДЛЯ ПРИВЕТСТВИЯ)
            # Запускаем только если есть галочка need_greet
            if guest_session and not stop_flag.is_set() and all_created_groups:
                if need_greet:
                    log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ (Приветствие) ===")
                    log_msg("WAIT", "⏳ Ждем 3 сек...")
                    time.sleep(3)
                    loop.run_until_complete(guest_execution_final(guest_session, all_maker_ids, all_created_groups, greeting_text))
                else:
                    log_msg("INFO", "\n🛑 Приветствия пропущены (галочка снята).")
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка: {e}")
    finally:
        loop.close()
        if root: root.after(0, lambda: start_btn.config(state='normal'))
def update_all_sessions_thread():
    sessions = load_sessions()
    if not sessions:
        messagebox.showinfo("Info", "Нет аккаунтов для обновления.")
        return

    # Отключаем кнопку старта во избежание конфликтов
    if root: root.after(0, lambda: start_btn.config(state='disabled'))
    log_msg("INFO", "🔄 --- ЗАПУСК ОБНОВЛЕНИЯ ДАННЫХ АККАУНТОВ ---")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    updated_count = 0

    for s in sessions:
        if stop_flag.is_set(): break
        
        phone = s.get('phone')
        api_id = s.get('api_id')
        api_hash = s.get('api_hash')

        if not (phone and api_id and api_hash): continue

        client = TelegramClient(f"session_{phone}", int(api_id), api_hash, loop=loop)
        
        async def work():
            try:
                await client.connect()
                if await client.is_user_authorized():
                    me = await client.get_me()
                    full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                    username = me.username or ""
                    
                    # Сохраняем (функция сама обновит JSON)
                    update_session_info(phone, full_name, username)
                    log_msg("SUCCESS", f"   ✅ {phone}: {full_name} (@{username})")
                    return True
                else:
                    log_msg("WARN", f"   ⚠️ {phone}: Требуется вход (не авторизован).")
            except Exception as e:
                log_msg("ERROR", f"   ❌ {phone}: Ошибка: {e}")
            finally:
                if client.is_connected(): await client.disconnect()
            return False

        try:
            res = loop.run_until_complete(work())
            if res: updated_count += 1
        except Exception as e:
             log_msg("ERROR", f"Loop Error: {e}")
        
        # Небольшая пауза между подключениями
        time.sleep(1)

    loop.close()
    log_msg("INFO", f"🏁 Обновление завершено. Обновлено: {updated_count}")
    
    # Возвращаем кнопку старт
    if root: 
        root.after(0, lambda: start_btn.config(state='normal'))
        root.after(0, refresh_main_checks)

def start_update_all():
    threading.Thread(target=update_all_sessions_thread, daemon=True).start()


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

def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Завершение текущих операций)")
    # Возвращаем кнопку старт в активное состояние через секунду
    if root: root.after(1000, lambda: start_btn.config(state='normal'))

# ===  ОКНА (НАСТРОЙКИ И АККАУНТЫ) ===

def open_settings():
    win = Toplevel(root)
    win.title("Настройки")
    win.geometry("450x700") # Чуть выше для файла
    enable_hotkeys(win)
    
    cfg = load_config()
    
    main_frame = ttk.Frame(win, padding=15)
    main_frame.pack(fill="both", expand=True)

    # # === 1. БЛОК ИИ (GOOGLE GEMINI) ===
    # lf_ai = ttk.LabelFrame(main_frame, text=" 🤖 ИИАссистент ", padding=10)
    # lf_ai.pack(fill="x", pady=5)
    
    # # API Key
    # ttk.Label(lf_ai, text="API Key (Google AI Studio):").pack(anchor="w")
    # e_ai_key = ttk.Entry(lf_ai, width=40)
    # e_ai_key.pack(fill="x", pady=(0, 5))
    # e_ai_key.insert(0, cfg.get("ai_api_key", ""))

    # # Выбор файла
    # ttk.Label(lf_ai, text="Документ для отправки (ИИ изучит его):").pack(anchor="w")
    
    # f_file = ttk.Frame(lf_ai)
    # f_file.pack(fill="x", pady=(0, 5))
    
    # e_file_path = ttk.Entry(f_file)
    # e_file_path.pack(side="left", fill="x", expand=True)
    # e_file_path.insert(0, cfg.get("ai_attachment", ""))
    
    # def choose_file():
    #     path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.png;*.jpeg"), ("All", "*.*")])
    #     if path:
    #         e_file_path.delete(0, tk.END)
    #         e_file_path.insert(0, path)
            
    # ttk.Button(f_file, text="📂", width=4, command=choose_file).pack(side="right", padx=(5,0))

    # # Инструкция (ТОЛЬКО ОДНА!)
    # ttk.Label(lf_ai, text="Инструкция (Роль) для ИИ:").pack(anchor="w")
    # txt_ai_prompt = scrolledtext.ScrolledText(lf_ai, height=4, font=("Arial", 9), width=40)
    # txt_ai_prompt.pack(fill="x", pady=2)
    # txt_ai_prompt.insert("1.0", cfg.get("ai_prompt", "Ты менеджер. Твоя цель - убедить клиента ознакомиться с документом."))

    # === 2. ТАЙМИНГИ (СТАРОЕ) ===
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
    
    # === 3. ОПЦИИ (СТАРОЕ) ===
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
    
    # === СОХРАНЕНИЕ ===
    def save():
        new_cfg = cfg.copy()
        
        # # Сохраняем ИИ настройки
        # new_cfg["ai_api_key"] = e_ai_key.get().strip()
        # new_cfg["ai_prompt"] = txt_ai_prompt.get("1.0", tk.END).strip()
        # new_cfg["ai_attachment"] = e_file_path.get().strip()
        
        # # Обновляем помощника
        # if 'ai_assistant' in globals():
        #     ai_assistant.setup(new_cfg["ai_api_key"])
        
        # Сохраняем старые настройки
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

def open_accounts():
    win = Toplevel(root)
    win.title("Управление аккаунтами")
    win.geometry("600x500")
    enable_hotkeys(win) # Хоткеи
    
    main_fr = ttk.Frame(win, padding=10)
    main_fr.pack(fill="both", expand=True)

    # Список
    lb_frame = ttk.Frame(main_fr)
    lb_frame.pack(fill="both", expand=True)
    
    # МНОЖЕСТВЕННЫЙ ВЫБОР
    lb = tk.Listbox(lb_frame, selectmode=tk.EXTENDED, font=("Consolas", 10), activestyle="none")
    
    sc = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sc.set)
    lb.pack(side="left", fill="both", expand=True)
    sc.pack(side="right", fill="y")
    
    # Скролл колесиком
    try:
        def _listbox_wheel(event):
            lb.yview_scroll(int(-1*(event.delta/120)), "units")
        lb.bind("<MouseWheel>", _listbox_wheel)
    except: pass
    
    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            txt = f"{s['phone']} | {name}"
            if uname: txt += f" (@{uname})"
            lb.insert(tk.END, txt)
    refresh()

    # === ФУНКЦИИ УПРАВЛЕНИЯ ===

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
                    if client.is_connected(): await client.disconnect()

            try:
                loop.run_until_complete(process())
            finally:
                loop.close()
        threading.Thread(target=auth_thread, daemon=True).start()

    def add():
        d = Toplevel(win); d.title("Добавление аккаунта"); d.geometry("380x500")
        enable_hotkeys(d)
        
        # Пытаемся сделать модальным (безопасно)
        try:
            d.transient(win)
            d.grab_set()
            d.focus_set()
        except: pass

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
        e_api_id = ttk.Entry(res_frame, width=25)
        e_api_id.grid(row=0, column=1, padx=5, sticky="e")
        
        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0, sticky="w", pady=5)
        e_api_hash = ttk.Entry(res_frame, width=25)
        e_api_hash.grid(row=1, column=1, padx=5, sticky="e", pady=5)
        
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
                    return

                d.after(0, lambda: lbl_status.config(text="🔐 Вход...", foreground="blue"))
                wc.login(phone, code)
                
                d.after(0, lambda: lbl_status.config(text="📂 Получение ключей...", foreground="blue"))
                keys = wc.get_app_data()
                
                def finish_saving():
                    if keys is None:
                        lbl_status.config(text="❌ Ошибка ключей", foreground="red")
                        messagebox.showerror("Ошибка", "Не удалось найти API ID/Hash.")
                        btn.config(state='normal'); return
                    
                    e_api_id.delete(0, tk.END); e_api_id.insert(0, keys['api_id'])
                    e_api_hash.delete(0, tk.END); e_api_hash.insert(0, keys['api_hash'])
                    
                    lbl_status.config(text="✅ Ключи получены!", foreground="green")
                    
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
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!")
                        d.destroy()
                        
                d.after(0, finish_saving)
            except Exception as e:
                err_msg = str(e)
                d.after(0, lambda: lbl_status.config(text="❌ Ошибка", foreground="red"))
                d.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой:\n{err_msg}"))
                d.after(0, lambda: btn.config(state='normal'))

        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone: messagebox.showerror("Ошибка", "Номер?"); return
            btn_auto.config(state='disabled')
            threading.Thread(target=auto_get_api_thread, args=(phone, btn_auto), daemon=True).start()
        
        btn_auto = ttk.Button(c_frame, text="⚡ Авто-получение API (my.telegram.org)", command=start_auto_process)
        btn_auto.pack(fill="x", pady=5)
        
        def manual_save():
            if not e_api_id.get() or not e_phone.get(): messagebox.showwarning("!", "Поля пусты"); return
            ss = load_sessions()
            ss.append({"api_id":e_api_id.get(),"api_hash":e_api_hash.get(),"phone":e_phone.get(), "name":"Manual", "username":""})
            save_sessions(ss)
            d.destroy(); refresh(); refresh_main_checks()

        ttk.Button(c_frame, text="💾 Сохранить вручную", command=manual_save).pack(fill="x", pady=10)

    def delt():
        selected_indices = lb.curselection()
        if not selected_indices: return
        count = len(selected_indices)
        if not messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить {count} аккаунтов?"):
            return
        ss = load_sessions()
        for index in reversed(selected_indices):
            if index < len(ss):
                del ss[index]
        save_sessions(ss)
        refresh()
        refresh_main_checks()

    # === ОЧИСТКА КОНТАКТОВ (ИСПРАВЛЕННАЯ) ===
    def clear_contacts_action():
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("!", "Выберите аккаунт для очистки контактов!")
            return
        
        idx = sel[0]
        s_data = load_sessions()[idx]
        phone = s_data['phone']

        if not messagebox.askyesno("Подтверждение", f"Вы точно хотите УДАЛИТЬ ВСЕ КОНТАКТЫ на аккаунте {phone}?\nЭто действие необратимо!"):
            return

        # 1. Создаем переменные (окно, бар) ЗДЕСЬ
        p_win = Toplevel(win)
        p_win.title("Очистка контактов")
        p_win.geometry("350x150")
        p_win.resizable(False, False)
        
        try:
            make_modal(p_win, parent=win, near_cursor=True)
        except NameError:
            p_win.transient(win)
            p_win.grab_set()

        lbl_info = ttk.Label(p_win, text="Подключение...", anchor="center")
        lbl_info.pack(pady=(20, 10), fill="x")

        pb = ttk.Progressbar(p_win, orient="horizontal", length=280, mode="determinate")
        pb.pack(pady=10)

        # 2. Функция runner находится ВНУТРИ (с отступом), поэтому видит p_win и pb
        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)

            async def work():
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        p_win.after(0, lambda: messagebox.showerror("Ошибка", "Аккаунт не авторизован! Сначала войдите."))
                        p_win.after(0, p_win.destroy)
                        return

                    p_win.after(0, lambda: lbl_info.config(text="Получение списка контактов..."))
                    
                    contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                    me = await client.get_me()
                    
                    # Формируем список InputUser для удаления
                    users_to_del = []
                    for u in contacts.users:
                        if u.id != me.id:
                            if hasattr(u, 'access_hash'):
                                users_to_del.append(types.InputUser(user_id=u.id, access_hash=u.access_hash))

                    total = len(users_to_del)

                    if total == 0:
                        p_win.after(0, lambda: messagebox.showinfo("Info", "Список контактов уже пуст."))
                        p_win.after(0, p_win.destroy)
                        return

                    p_win.after(0, lambda: pb.config(maximum=total, value=0))
                    p_win.after(0, lambda: lbl_info.config(text=f"Найдено контактов: {total}. Удаление..."))

                    chunk_size = 50
                    for i in range(0, total, chunk_size):
                        chunk = users_to_del[i : i + chunk_size]
                        try:
                            await client(functions.contacts.DeleteContactsRequest(id=chunk))
                        except Exception as e_del:
                            print(f"Ошибка удаления пачки: {e_del}")
                        
                        current_progress = min(i + chunk_size, total)
                        p_win.after(0, lambda v=current_progress: pb.config(value=v))
                        p_win.after(0, lambda v=current_progress, t=total: lbl_info.config(text=f"Удалено {v} из {t}..."))
                        await asyncio.sleep(0.5)

                    p_win.after(0, lambda: messagebox.showinfo("Успех", f"Успешно удалено {total} контактов!"))
                    p_win.after(0, p_win.destroy)

                except Exception as e:
                    p_win.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой: {str(e)}"))
                    p_win.after(0, p_win.destroy)
                finally:
                    if client.is_connected(): await client.disconnect()

            try:
                loop.run_until_complete(work())
            finally:
                loop.close()

        threading.Thread(target=runner, daemon=True).start()

    # === НОВАЯ ФУНКЦИЯ: ПЕРЕСЫЛКА КОНТАКТОВ ===
def open_forward_contacts_window(session_data, parent_win):
    phone = session_data['phone']
    api_id = int(session_data['api_id'])
    api_hash = session_data['api_hash']

    # 1. Создаем окно
    fw_win = Toplevel(parent_win)
    fw_win.title(f"Пересылка контактов: {phone}")
    fw_win.geometry("450x600")
    
    try:
        fw_win.transient(parent_win)
        fw_win.grab_set()
        fw_win.focus_set()
    except: pass

    # UI Элементы
    lbl_title = ttk.Label(fw_win, text="1. Выберите чат, КУДА отправить контакты:", font=("Arial", 10, "bold"))
    lbl_title.pack(pady=5)

    search_var = tk.StringVar()
    entry_search = ttk.Entry(fw_win, textvariable=search_var)
    entry_search.pack(fill="x", padx=10, pady=(0, 5))
    entry_search.insert(0, "Поиск...")

    list_frame = ttk.Frame(fw_win)
    list_frame.pack(fill="both", expand=True, padx=10)

    lb_chats = tk.Listbox(list_frame, font=("Consolas", 10), exportselection=False)
    scr = ttk.Scrollbar(list_frame, orient="vertical", command=lb_chats.yview)
    lb_chats.config(yscrollcommand=scr.set)
    lb_chats.pack(side="left", fill="both", expand=True)
    scr.pack(side="right", fill="y")

    pb = ttk.Progressbar(fw_win, orient="horizontal", mode="determinate")
    pb.pack(fill="x", padx=10, pady=5)
    
    lbl_status = ttk.Label(fw_win, text="Ожидание подключения...", foreground="blue")
    lbl_status.pack(pady=5)

    btn_start = ttk.Button(fw_win, text="🚀 ОТПРАВИТЬ ВСЕ КОНТАКТЫ", state="disabled")
    btn_start.pack(fill="x", padx=10, pady=10)

    # Хранилище диалогов
    dialogs_map = {}
    all_dialogs_cache = []

    # Фильтр поиска
    def filter_chats(*args):
        search_text = search_var.get().lower()
        if search_text == "поиск...": search_text = ""
        lb_chats.delete(0, tk.END)
        dialogs_map.clear()
        idx = 0
        for d in all_dialogs_cache:
            name = d['name']
            if search_text in name.lower():
                lb_chats.insert(tk.END, name)
                dialogs_map[idx] = d['entity']
                idx += 1
    search_var.trace("w", filter_chats)

    # Ссылка на loop, чтобы закрыть его при выходе
    loop_ref = None

    # Основная логика в потоке
    def start_logic():
        nonlocal loop_ref
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_ref = loop
        
        client = TelegramClient(f"session_{phone}", api_id, api_hash, loop=loop)

        async def load_chats_async():
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    fw_win.after(0, lambda: messagebox.showerror("Ошибка", "Аккаунт не авторизован!"))
                    fw_win.after(0, fw_win.destroy)
                    return

                fw_win.after(0, lambda: lbl_status.config(text="Загрузка списка чатов..."))
                dialogs = await client.get_dialogs(limit=500)
                
                all_dialogs_cache.clear()
                for d in dialogs:
                    if d.is_group or d.is_channel or d.is_user:
                        name = d.name if d.name else "Unknown"
                        tid = d.entity.id
                        type_str = "[ЛС]" if d.is_user else "[ГРУППА]" if d.is_group else "[КАНАЛ]"
                        display_name = f"{type_str} {name} (ID: {tid})"
                        all_dialogs_cache.append({'name': display_name, 'entity': d.entity})

                fw_win.after(0, filter_chats)
                fw_win.after(0, lambda: lbl_status.config(text="Выберите чат из списка выше", foreground="green"))
                
                # Активируем кнопку. Важно: используем тот же loop!
                def on_click():
                    asyncio.run_coroutine_threadsafe(send_contacts_async(), loop)
                
                fw_win.after(0, lambda: btn_start.config(state="normal", command=on_click))

            except Exception as e:
                fw_win.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой загрузки: {e}"))

        async def send_contacts_async():
            try:
                sel = lb_chats.curselection()
                if not sel:
                    fw_win.after(0, lambda: messagebox.showwarning("!", "Сначала выберите чат!"))
                    return

                target_entity = dialogs_map[sel[0]]
                
                fw_win.after(0, lambda: btn_start.config(state="disabled"))
                fw_win.after(0, lambda: lbl_status.config(text="Получение списка контактов..."))

                contacts_obj = await client(functions.contacts.GetContactsRequest(hash=0))
                users = contacts_obj.users
                me = await client.get_me()
                valid_contacts = [u for u in users if not u.deleted and u.id != me.id]

                total = len(valid_contacts)
                if total == 0:
                    fw_win.after(0, lambda: messagebox.showinfo("Пусто", "Список контактов пуст!"))
                    fw_win.after(0, lambda: btn_start.config(state="normal"))
                    return

                fw_win.after(0, lambda: pb.config(maximum=total, value=0))

                for i, user in enumerate(valid_contacts):
                    try:
                        name_str = f"{user.first_name or ''} {user.last_name or ''}".strip()
                        phone_str = user.phone or ""
                        fw_win.after(0, lambda t=name_str: lbl_status.config(text=f"Отправка: {t}"))
                        
                        contact_media = types.InputMediaContact(
                            phone_number=phone_str,
                            first_name=user.first_name or "",
                            last_name=user.last_name or "",
                            vcard=""
                        )
                        await client.send_message(target_entity, file=contact_media)
                        fw_win.after(0, lambda v=i+1: pb.config(value=v))
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                    except Exception as e:
                        print(f"Err: {e}")
                        await asyncio.sleep(5)

                fw_win.after(0, lambda: messagebox.showinfo("Готово", f"Отправлено {total} контактов!"))
                fw_win.after(0, fw_win.destroy)

            except Exception as e:
                fw_win.after(0, lambda: messagebox.showerror("Ошибка отправки", str(e)))
                fw_win.after(0, lambda: btn_start.config(state="normal"))

        # Запускаем задачу загрузки
        loop.create_task(load_chats_async())
        
        # ЗАПУСКАЕМ ВЕЧНЫЙ ЦИКЛ (чтобы loop не умирал и ждал кнопку)
        loop.run_forever()

    # Запускаем поток
    t = threading.Thread(target=start_logic, daemon=True)
    t.start()

    # Корректное закрытие окна и потока
    def on_close():
        if loop_ref and loop_ref.is_running():
            loop_ref.call_soon_threadsafe(loop_ref.stop)
        fw_win.destroy()

    fw_win.protocol("WM_DELETE_WINDOW", on_close)

    # === НОВОЕ МЕНЮ ИНСТРУМЕНТОВ (ЧИСТКА) ===

def open_accounts():
    win = Toplevel(root)
    win.title("Управление аккаунтами")
    win.geometry("600x500")
    enable_hotkeys(win) 
    
    # === СОЗДАНИЕ main_fr ===
    main_fr = ttk.Frame(win, padding=10)
    main_fr.pack(fill="both", expand=True)

    # Список аккаунтов
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
    except: pass
    
    def refresh():
        lb.delete(0, tk.END)
        for s in load_sessions():
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            txt = f"{s['phone']} | {name}"
            if uname: txt += f" (@{uname})"
            lb.insert(tk.END, txt)
    refresh()

    # === ВНУТРЕННИЕ ФУНКЦИИ УПРАВЛЕНИЯ ===

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
                    if client.is_connected(): await client.disconnect()

            try:
                loop.run_until_complete(process())
            finally:
                loop.close()
        threading.Thread(target=auth_thread, daemon=True).start()

    def add():
        d = Toplevel(win); d.title("Добавление аккаунта"); d.geometry("380x500")
        enable_hotkeys(d)
        try:
            d.transient(win)
            d.grab_set()
            d.focus_set()
        except: pass

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
        e_api_id = ttk.Entry(res_frame, width=25)
        e_api_id.grid(row=0, column=1, padx=5, sticky="e")
        
        ttk.Label(res_frame, text="API Hash:").grid(row=1, column=0, sticky="w", pady=5)
        e_api_hash = ttk.Entry(res_frame, width=25)
        e_api_hash.grid(row=1, column=1, padx=5, sticky="e", pady=5)
        
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
                    return

                d.after(0, lambda: lbl_status.config(text="🔐 Вход...", foreground="blue"))
                wc.login(phone, code)
                
                d.after(0, lambda: lbl_status.config(text="📂 Получение ключей...", foreground="blue"))
                keys = wc.get_app_data()
                
                def finish_saving():
                    if keys is None:
                        lbl_status.config(text="❌ Ошибка ключей", foreground="red")
                        messagebox.showerror("Ошибка", "Не удалось найти API ID/Hash.")
                        btn.config(state='normal'); return
                    
                    e_api_id.delete(0, tk.END); e_api_id.insert(0, keys['api_id'])
                    e_api_hash.delete(0, tk.END); e_api_hash.insert(0, keys['api_hash'])
                    
                    lbl_status.config(text="✅ Ключи получены!", foreground="green")
                    
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
                        messagebox.showinfo("Успех", f"Аккаунт {phone} добавлен!")
                        d.destroy()
                        
                d.after(0, finish_saving)
        
            except Exception as e:
                err_msg = str(e)
                d.after(0, lambda: lbl_status.config(text="❌ Ошибка", foreground="red"))
                d.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой:\n{err_msg}"))
                d.after(0, lambda: btn.config(state='normal'))

        def start_auto_process():
            phone = e_phone.get().strip()
            if not phone: messagebox.showerror("Ошибка", "Номер?"); return
            btn_auto.config(state='disabled')
            threading.Thread(target=auto_get_api_thread, args=(phone, btn_auto), daemon=True).start()
        
        btn_auto = ttk.Button(c_frame, text="⚡ Авто-получение API (my.telegram.org)", command=start_auto_process)
        btn_auto.pack(fill="x", pady=5)
        
        def manual_save():
            if not e_api_id.get() or not e_phone.get(): messagebox.showwarning("!", "Поля пусты"); return
            ss = load_sessions()
            ss.append({"api_id":e_api_id.get(),"api_hash":e_api_hash.get(),"phone":e_phone.get(), "name":"Manual", "username":""})
            save_sessions(ss)
            d.destroy(); refresh(); refresh_main_checks()

        ttk.Button(c_frame, text="💾 Сохранить вручную", command=manual_save).pack(fill="x", pady=10)

    def delt():
        selected_indices = lb.curselection()
        if not selected_indices: return
        count = len(selected_indices)
        if not messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить {count} аккаунтов?"):
            return
        ss = load_sessions()
        for index in reversed(selected_indices):
            if index < len(ss):
                del ss[index]
        save_sessions(ss)
        refresh()
        refresh_main_checks()

    def clear_contacts_action():
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("!", "Выберите аккаунт для очистки контактов!")
            return
        
        idx = sel[0]
        s_data = load_sessions()[idx]
        phone = s_data['phone']

        if not messagebox.askyesno("Подтверждение", f"Вы точно хотите УДАЛИТЬ ВСЕ КОНТАКТЫ на аккаунте {phone}?\nЭто действие необратимо!"):
            return

        p_win = Toplevel(win)
        p_win.title("Очистка контактов")
        p_win.geometry("350x150")
        p_win.resizable(False, False)
        
        try:
            make_modal(p_win, parent=win, near_cursor=True)
        except NameError:
            p_win.transient(win)
            p_win.grab_set()

        lbl_info = ttk.Label(p_win, text="Подключение...", anchor="center")
        lbl_info.pack(pady=(20, 10), fill="x")

        pb = ttk.Progressbar(p_win, orient="horizontal", length=280, mode="determinate")
        pb.pack(pady=10)

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)

            async def work():
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        p_win.after(0, lambda: messagebox.showerror("Ошибка", "Аккаунт не авторизован! Сначала войдите."))
                        p_win.after(0, p_win.destroy)
                        return

                    p_win.after(0, lambda: lbl_info.config(text="Получение списка контактов..."))
                    
                    contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                    me = await client.get_me()
                    
                    users_to_del = []
                    for u in contacts.users:
                        if u.id != me.id:
                            if hasattr(u, 'access_hash'):
                                users_to_del.append(types.InputUser(user_id=u.id, access_hash=u.access_hash))

                    total = len(users_to_del)

                    if total == 0:
                        p_win.after(0, lambda: messagebox.showinfo("Info", "Список контактов уже пуст."))
                        p_win.after(0, p_win.destroy)
                        return

                    p_win.after(0, lambda: pb.config(maximum=total, value=0))
                    p_win.after(0, lambda: lbl_info.config(text=f"Найдено контактов: {total}. Удаление..."))

                    chunk_size = 50
                    for i in range(0, total, chunk_size):
                        chunk = users_to_del[i : i + chunk_size]
                        try:
                            await client(functions.contacts.DeleteContactsRequest(id=chunk))
                        except Exception as e_del:
                            print(f"Ошибка удаления пачки: {e_del}")
                        
                        current_progress = min(i + chunk_size, total)
                        p_win.after(0, lambda v=current_progress: pb.config(value=v))
                        p_win.after(0, lambda v=current_progress, t=total: lbl_info.config(text=f"Удалено {v} из {t}..."))
                        await asyncio.sleep(0.5)

                    p_win.after(0, lambda: messagebox.showinfo("Успех", f"Успешно удалено {total} контактов!"))
                    p_win.after(0, p_win.destroy)

                except Exception as e:
                    p_win.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой: {str(e)}"))
                    p_win.after(0, p_win.destroy)
                finally:
                    if client.is_connected(): await client.disconnect()

            try:
                loop.run_until_complete(work())
            finally:
                loop.close()

        threading.Thread(target=runner, daemon=True).start()

    # === МЕНЮ ИНСТРУМЕНТОВ ===
    def open_actions_menu():
        sel = lb.curselection()
        if not sel:
            messagebox.showwarning("!", "Выберите аккаунт для работы!")
            return
        
        idx = sel[0]
        s_data = load_sessions()[idx]
        phone = s_data['phone']

        t_win = Toplevel(win)
        t_win.title(f"Инструменты: {phone}")
        t_win.geometry("400x420")
        try:
            make_modal(t_win, parent=win, near_cursor=True)
        except: pass

        # Настройки действий
        lbl_f = ttk.LabelFrame(t_win, text=" Выберите действия ", padding=10)
        lbl_f.pack(fill="both", expand=True, padx=10, pady=10)

        var_leave = tk.IntVar()
        var_del_own = tk.IntVar()
        var_del_private = tk.IntVar()

        ttk.Checkbutton(lbl_f, text="🚪 Покинуть все группы/каналы", variable=var_leave).pack(anchor="w", pady=5)
        ttk.Checkbutton(lbl_f, text="🗑 Удалить свои группы (ДЛЯ ВСЕХ)", variable=var_del_own).pack(anchor="w", pady=5)
        ttk.Checkbutton(lbl_f, text="💬 Удалить все личные переписки (ЛС)", variable=var_del_private).pack(anchor="w", pady=5)
        
        # Индикатор прогресса
        pb_action = ttk.Progressbar(t_win, orient="horizontal", mode="determinate")
        pb_action.pack(fill="x", padx=10, pady=(0,5))
        lbl_log = ttk.Label(t_win, text="Ожидание...", font=("Consolas", 8))
        lbl_log.pack(fill="x", padx=10, pady=(0,10))

        # Кнопка ЗАПУСТИТЬ ОЧИСТКУ
        btn_run = ttk.Button(t_win, text="🚀 ЗАПУСТИТЬ ОЧИСТКУ")
        btn_run.pack(fill="x", padx=10, pady=5)

        ttk.Separator(t_win, orient='horizontal').pack(fill='x', padx=10, pady=10)
        
        def run_forwarder():
             t_win.destroy()
             open_forward_contacts_window(s_data, win)

        btn_forward = ttk.Button(t_win, text="📂 Переслать все контакты в чат...", command=run_forwarder)
        btn_forward.pack(fill="x", padx=10, pady=(0, 10))

        # Логика очистки
        def run_cleaner():
            if not any([var_leave.get(), var_del_own.get(), var_del_private.get()]):
                messagebox.showwarning("!", "Выберите хотя бы одно действие!")
                return

            if not messagebox.askyesno("Внимание", "Вы уверены? Это действие необратимо!"):
                return

            btn_run.config(state='disabled')
            
            def runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)

                async def work():
                    try:
                        t_win.after(0, lambda: lbl_log.config(text="Подключение..."))
                        await client.connect()
                        
                        if not await client.is_user_authorized():
                            t_win.after(0, lambda: messagebox.showerror("Ошибка", "Нет авторизации!"))
                            t_win.after(0, t_win.destroy)
                            return

                        t_win.after(0, lambda: lbl_log.config(text="Сканирование чатов..."))
                        dialogs = await client.get_dialogs(limit=None)
                        
                        total = len(dialogs)
                        t_win.after(0, lambda: pb_action.config(maximum=total, value=0))
                        
                        count_left = 0
                        count_deleted = 0
                        count_dms = 0
                        me = await client.get_me()

                        for i, d in enumerate(dialogs):
                            try:
                                entity = d.entity
                                title = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
                                t_win.after(0, lambda t=title: lbl_log.config(text=f"Обработка: {t}..."))
                                
                                if d.is_group or d.is_channel:
                                    is_creator = getattr(entity, 'creator', False) or (hasattr(entity, 'admin_rights') and entity.admin_rights)
                                    if is_creator and var_del_own.get():
                                        try:
                                            await client(functions.channels.DeleteChannelRequest(entity))
                                            count_deleted += 1
                                        except: pass
                                    elif var_leave.get():
                                        try:
                                            await client(functions.channels.LeaveChannelRequest(entity))
                                            count_left += 1
                                        except:
                                            await client.delete_dialog(entity)

                                elif d.is_user and var_del_private.get():
                                    if entity.id != me.id and entity.id != 777000:
                                        try:
                                            await client(functions.messages.DeleteHistoryRequest(peer=entity, max_id=0, just_clear=False, revoke=True))
                                        except: pass
                                        await client.delete_dialog(entity)
                                        count_dms += 1

                            except Exception as e_iter:
                                print(f"Skip {d.id}: {e_iter}")
                            
                            t_win.after(0, lambda v=i+1: pb_action.config(value=v))
                            await asyncio.sleep(0.2)

                        res_msg = f"Готово!\nПокинуто: {count_left}\nУдалено групп: {count_deleted}\nУдалено ЛС: {count_dms}"
                        t_win.after(0, lambda: messagebox.showinfo("Завершено", res_msg))
                        t_win.after(0, t_win.destroy)

                    except Exception as e:
                        t_win.after(0, lambda: messagebox.showerror("Ошибка", f"Сбой: {str(e)}"))
                        t_win.after(0, t_win.destroy)
                    finally:
                        if client.is_connected(): await client.disconnect()

                try:
                    loop.run_until_complete(work())
                finally:
                    loop.close()

            threading.Thread(target=runner, daemon=True).start()

        btn_run.config(command=run_cleaner)

    # === КНОПКИ ГЛАВНОГО ОКНА (ВСТАВЛЕНЫ ПРАВИЛЬНО) ===
    # Они находятся на том же уровне отступа, что и def open_actions_menu
    
    btn_frame = ttk.Frame(main_fr, padding=(0, 10)) 
    btn_frame.pack(fill="x")
    
    # Верхний ряд кнопок
    f_top = ttk.Frame(btn_frame)
    f_top.pack(fill="x", pady=2)
    ttk.Button(f_top, text="➕ Добавить", command=add).pack(side="left", fill="x", expand=True)
    ttk.Button(f_top, text="🔄 Войти/Проверить", command=login_selected_account).pack(side="left", fill="x", expand=True, padx=5)
    
    # Нижний ряд кнопок
    f_bot = ttk.Frame(btn_frame)
    f_bot.pack(fill="x", pady=2)
    ttk.Button(f_bot, text="🧹 Контакты", command=clear_contacts_action).pack(side="left", fill="x", expand=True)
    
    # Инструменты
    ttk.Button(f_bot, text="🛠 Инструменты (Удаление / Пересылка)", command=open_actions_menu).pack(side="left", fill="x", expand=True, padx=5)
    
    ttk.Button(f_bot, text="❌ Удалить акк", command=delt).pack(side="left", fill="x", expand=True)
    
    try:
        make_modal(win, parent=root, near_cursor=True, width=600, height=500)
    except NameError: pass

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

# Кнопка Опции (row=0)
ttk.Button(grid_fr, text="🛠 Опции", command=open_settings, width=15).grid(row=0, column=4, padx=10)

# === НОВАЯ КНОПКА (row=1, под Опциями) ===
ttk.Button(grid_fr, text="🔄 Обновить всех", command=start_update_all, width=15).grid(row=1, column=4, padx=10, pady=(5,0))

# Поле "Цель" сдвигаем или оставляем как было (row=1, col=0..3)
ttk.Label(grid_fr, text="Цель (если нет Гостя):").grid(row=1, column=0, columnspan=2, pady=(10,0), sticky="w")
ent_user = ttk.Entry(grid_fr, width=25)
ent_user.grid(row=1, column=2, columnspan=2, pady=(10,0), sticky="w")

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

# Кнопки
btn_frame = ttk.Frame(bottom_frame)
btn_frame.pack(fill="x", pady=(0, 10))

start_btn = tk.Button(btn_frame, text="🚀 ЗАПУСТИТЬ ПРОЦЕСС", bg="#4caf50", fg="white", font=("Arial", 12, "bold"), command=start_process, height=2)
start_btn.pack(side="left", fill="x", expand=True)

def start_ai_monitor_action():
    guest_idx = guest_account_index.get()
    sessions = load_sessions()
    
    if guest_idx == -1 or guest_idx >= len(sessions):
        messagebox.showwarning("!", "Выберите Гостя (справа), который будет отвечать!")
        return

    cfg = load_config()
    instruction = cfg.get("ai_prompt", "Будь вежлив.")
    
    start_btn.config(state='disabled') # Блокируем кнопку старта
    stop_flag.clear()
    
    guest_session = sessions[guest_idx]
    run_ai_monitor_thread(guest_session, instruction)

# Сама кнопка (вставьте в btn_frame)
#tk.Button(btn_frame, text="🤖 ИИ-Автоответчик (Старт)", bg="#673ab7", fg="white", font=("Arial", 10, "bold"), command=start_ai_monitor_action, height=2).pack(side="left", fill="x", expand=True, padx=5)

tk.Button(btn_frame, text="🛑 СТОП", bg="#f44336", fg="white", font=("Arial", 12, "bold"), command=stop_process, height=2).pack(side="left", fill="x", expand=True, padx=5)
tk.Button(btn_frame, text="НОВОЕ ОКНО", bg="#2196f3", fg="white", font=("Arial", 12, "bold"), command=open_new_window, height=2).pack(side="left", fill="x", expand=True)

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