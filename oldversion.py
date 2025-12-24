import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel, filedialog
import asyncio
import threading
from telethon import TelegramClient, functions, types, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError
)
# ... твои стандартные импорты ...
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
from datetime import datetime

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
            s['last_used'] = time.time() # <--- ОБНОВЛЯЕМ ВРЕМЯ
            updated = True
            break
    if updated:
        save_sessions(sessions)
        if root: root.after(0, lambda: refresh_main_checks())

# 1. КЛАСС ОКНА С ЧЕКБОКСАМИ
class MatchReviewWindow(Toplevel):
    def __init__(self, parent, matches_list):
        super().__init__(parent)
        self.matches = matches_list
        self.result = None
        
        # Настройка окна
        self.title(f"Проверка совпадений ({len(matches_list)} чел.)")
        self.geometry("1100x600")
        self.minsize(900, 500)
        self.configure(bg="#121212")
        
        # Центрируем
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{(sw-1100)//2}+{(sh-600)//2}")
        except: pass

        self.transient(parent)
        self.grab_set()

        # === СТИЛИЗАЦИЯ ТАБЛИЦЫ (Фиолетовая тема) ===
        style = ttk.Style()
        style.theme_use("clam") # Важно для корректного цвета заголовков
        
        # Цвета
        bg_color ="#101010"
        fg_color = "white"
        select_bg = "#9D00FF" # Ярко-фиолетовый (как на скрине)
        select_fg = "white"
        
        style.configure("Review.Treeview", 
                        background=bg_color, 
                        foreground=fg_color, 
                        fieldbackground=bg_color,
                        rowheight=30,
                        font=("Segoe UI", 10),
                        borderwidth=0)
        
        style.map("Review.Treeview", 
                  background=[('selected', select_bg)], 
                  foreground=[('selected', select_fg)])
        
        # Стиль заголовков
        style.configure("Review.Treeview.Heading", 
                        background="#2E2E2E", 
                        foreground="#9D00FF", 
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=1, 
                        relief="flat")
        
        style.map("Review.Treeview.Heading",
                  background=[('active', '#3E3E3E')])

        # === 1. ВЕРХНЯЯ ЧАСТЬ: ИНСТРУКЦИЯ ===
        top_frame = tk.Frame(self, bg="#121212", pady=10)
        top_frame.pack(fill="x")
        
        lbl_instr = tk.Label(top_frame, 
                             text="Выберите (выделите) контакты, которые СОВПАДАЮТ.\nОстальные будут проигнорированы.",
                             font=("Segoe UI", 11), fg="#00E676", bg="#121212")
        lbl_instr.pack()
        
        lbl_hint = tk.Label(top_frame, 
                            text="[Клик] - выбор одного   |   [Ctrl + Клик] - выбор нескольких   |   [Shift + Клик] - выбор диапазона",
                            font=("Consolas", 9), fg="#888", bg="#121212")
        lbl_hint.pack(pady=(5,0))

        # === 2. ТАБЛИЦА (TREEVIEW) ===
        table_frame = tk.Frame(self, bg="#121212")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        cols = ("fio_file", "name_tg", "phone", "username")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended", style="Review.Treeview")
        
        # Настройка колонок
        self.tree.heading("fio_file", text="ФИО из Файла")
        self.tree.heading("name_tg", text="Имя в Telegram")
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("username", text="Username")
        
        self.tree.column("fio_file", width=250, anchor="w")
        self.tree.column("name_tg", width=250, anchor="w")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("username", width=120, anchor="w")
        
        # Скроллбар
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # === 3. ЗАПОЛНЕНИЕ ДАННЫМИ ===
        for i, item in enumerate(self.matches):
            tg_u = item['user']
            tg_name = f"{tg_u.first_name or ''} {tg_u.last_name or ''}".strip()
            uname = f"@{tg_u.username}" if tg_u.username else "-"
            
            # iid (id строки) делаем равным индексу в списке, чтобы потом легко достать
            self.tree.insert("", "end", iid=str(i), values=(
                item['target_fio'],
                tg_name,
                item['phone'],
                uname
            ))

        # Выделяем все по умолчанию (опционально, можно убрать если хочешь пустое выделение)
        all_ids = self.tree.get_children()
        self.tree.selection_set(all_ids)

        # === 4. КНОПКИ СНИЗУ ===
        btn_frame = tk.Frame(self, bg="#121212", pady=15)
        btn_frame.pack(fill="x")
        
        # Левые кнопки (Управление выделением)
        tk.Button(btn_frame, text="Выделить все", command=self.select_all, 
                  bg="#333", fg="white", bd=0, padx=15, pady=5, cursor="hand2").pack(side="left", padx=20)
        
        tk.Button(btn_frame, text="Снять выделение", command=self.deselect_all, 
                  bg="#333", fg="white", bd=0, padx=15, pady=5, cursor="hand2").pack(side="left")

        # Правая кнопка (Подтвердить)
        tk.Button(btn_frame, text="✅ ПОДТВЕРДИТЬ И ЗАПУСТИТЬ", command=self.confirm, 
                  bg="#00E676", fg="black", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=8, cursor="hand2").pack(side="right", padx=20)

    def select_all(self):
        ids = self.tree.get_children()
        self.tree.selection_set(ids)

    def deselect_all(self):
        self.tree.selection_remove(self.tree.selection())

    def confirm(self):
        # Получаем ID выделенных строк
        selected_iids = self.tree.selection()
        
        if not selected_iids:
            messagebox.showwarning("Внимание", "Вы никого не выбрали!", parent=self)
            return

        # Собираем реальные объекты из списка self.matches по индексам
        self.result = [self.matches[int(iid)] for iid in selected_iids]
        self.destroy()

# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def mark_account_active(phone):
    try:
        sessions = load_sessions()
        changed = False
        for s in sessions:
            if s.get('phone') == phone:
                s['last_used'] = time.time()
                changed = True
                break
        if changed: save_sessions(sessions)
    except: pass

async def hide_maker_phone(client):
    try:
        await client(functions.account.SetPrivacyRequest(
            key=types.InputPrivacyKeyPhoneNumber(), rules=[types.InputPrivacyValueDisallowAll()]
        ))
    except: pass

def start_update_all():
    def _runner():
        sessions = load_sessions()
        log_msg("INFO", f"🔄 Обновление {len(sessions)} аккаунтов...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for s in sessions:
            if stop_flag.is_set(): break
            phone = s.get('phone', '').replace(" ", "").replace("-", "")
            try:
                client = TelegramClient(f"session_{phone}", int(s['api_id']), s['api_hash'], loop=loop)
                async def _check():
                    try:
                        await client.connect()
                        if await client.is_user_authorized():
                            me = await client.get_me()
                            s['name'] = f"{me.first_name} {me.last_name or ''}".strip()
                            s['username'] = me.username or ""
                    except: pass
                    finally:
                        if client.is_connected(): await client.disconnect()
                loop.run_until_complete(_check())
            except: pass
        save_sessions(sessions)
        log_msg("SUCCESS", "✅ Все аккаунты обновлены.")
        if root: root.after(0, lambda: refresh_main_checks())
    threading.Thread(target=_runner, daemon=True).start()

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
                # Используем run_in_executor для GUI ввода, чтобы не блокировать цикл
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

        # Получаем диалоги для обновления кэша
        dialogs = await client.get_dialogs(limit=100, ignore_migrated=True)
        
        count_sent = 0
        
        for gid in target_group_ids:
            if stop_flag.is_set(): break
            
            target_entity = None
            # 1. Ищем в загруженных диалогах
            for d in dialogs:
                if abs(d.id) == abs(gid):
                    target_entity = d.entity
                    break
            
            # 2. Если не нашли, пробуем получить напрямую как PeerChat (для обычных групп)
            if not target_entity:
                try:
                    target_entity = await client.get_entity(types.PeerChat(gid))
                except:
                    log_msg("WARN", f"   ⚠️ Гость пока не видит группу {gid}. Пропуск.")
                    continue

            try:
                # Определяем название для лога
                title = getattr(target_entity, 'title', str(gid))
                
                # Проверка на наличие Мейкера (чтобы не писать в чужие группы)
                try:
                    participants = await client.get_participants(target_entity, limit=20)
                    found_maker = False
                    for p in participants:
                        if p.id in all_maker_ids:
                            found_maker = True
                            break
                except:
                    # Если не удалось получить участников (например, нет прав), считаем что можно писать
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

def start_update_all():
    """Обновляет имена и юзернеймы всех аккаунтов."""
    def _runner():
        sessions = load_sessions()
        log_msg("INFO", f"🔄 Обновление {len(sessions)} аккаунтов...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for s in sessions:
            if stop_flag.is_set(): break
            phone = s.get('phone', '').replace(" ", "").replace("-", "")
            try:
                client = TelegramClient(f"session_{phone}", int(s['api_id']), s['api_hash'], loop=loop)
                async def _check():
                    try:
                        await client.connect()
                        if await client.is_user_authorized():
                            me = await client.get_me()
                            s['name'] = f"{me.first_name} {me.last_name or ''}".strip()
                            s['username'] = me.username or ""
                    except: pass
                    finally:
                        if client.is_connected(): await client.disconnect()
                loop.run_until_complete(_check())
            except: pass
            
        save_sessions(sessions)
        log_msg("SUCCESS", "✅ Все аккаунты обновлены.")
        if root: root.after(0, lambda: refresh_main_checks())

    threading.Thread(target=_runner, daemon=True).start()

async def guest_execution_final(guest_session, maker_ids, group_ids, text):
    """
    Логика работы Гостя (Директора).
    ИСПРАВЛЕНО: Добавлена синхронизация диалогов, чтобы Гость 'увидел' новые группы.
    """
    if not group_ids: return

    log_msg("GUEST", f"👤 Директор начинает рассылку приветствия в {len(group_ids)} групп...")
    
    g_phone = guest_session['phone'].replace(" ", "").replace("-", "")
    client = TelegramClient(f"session_{g_phone}", int(guest_session['api_id']), guest_session['api_hash'])

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("ERROR", "❌ Директор не авторизован! Рассылка отменена.")
            return

        # === ВАЖНО: СИНХРОНИЗАЦИЯ ДИАЛОГОВ ===
        log_msg("DEBUG", "   ⟳ Синхронизация диалогов (получаем ключи доступа)...")
        # Мы скачиваем список диалогов, чтобы Telethon закешировал access_hash для новых групп
        # limit=50 достаточно, так как группы новые и будут сверху
        dialogs = await client.get_dialogs(limit=50)
        
        # Создаем карту {id: entity} для быстрого поиска
        dialogs_map = {}
        for d in dialogs:
            dialogs_map[d.id] = d.entity
            # Телеграм иногда меняет ID (добавляет -100), сохраним варианты
            dialogs_map[abs(d.id)] = d.entity
            dialogs_map[-abs(d.id)] = d.entity

        success_count = 0
        
        for chat_id in group_ids:
            if stop_flag.is_set(): break
            
            # 1. Пытаемся найти чат в загруженных диалогах (Самый надежный способ)
            target_entity = dialogs_map.get(chat_id)
            
            # 2. Если не нашли, пробуем стандартный get_entity (может упасть, если чат совсем новый)
            if not target_entity:
                try:
                    target_entity = await client.get_entity(chat_id)
                except:
                    log_msg("WARN", f"      ⚠️ Группа {chat_id} не найдена (пропуск).")
                    continue

            try:
                log_msg("INFO", f"   📤 Отправка в группу {target_entity.title}...")
                await client.send_message(target_entity, text)
                
                log_msg("SUCCESS", "      ✅ Отправлено.")
                success_count += 1
                
                await asyncio.sleep(random.uniform(3, 6))
                
            except Exception as e:
                log_msg("WARN", f"      ⚠️ Ошибка отправки: {e}")
                await asyncio.sleep(1)

        log_msg("GUEST", f"🏁 Рассылка завершена. Успешно: {success_count} из {len(group_ids)}")

    except Exception as e:
        log_msg("ERROR", f"Guest Critical Error: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

def mark_account_active(phone):
    """Обновляет время последней активности аккаунта."""
    try:
        sessions = load_sessions()
        changed = False
        for s in sessions:
            if s.get('phone') == phone:
                s['last_used'] = time.time()
                changed = True
                break
        if changed: save_sessions(sessions)
    except: pass

async def hide_maker_phone(client):
    """Скрывает номер телефона (Privacy: Nobody)."""
    try:
        await client(functions.account.SetPrivacyRequest(
            key=types.InputPrivacyKeyPhoneNumber(),
            rules=[types.InputPrivacyValueDisallowAll()]
        ))
    except: pass

def start_update_all():
    """Фоновое обновление имен всех аккаунтов."""
    def _runner():
        sessions = load_sessions()
        log_msg("INFO", f"🔄 Обновление {len(sessions)} аккаунтов...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for s in sessions:
            if stop_flag.is_set(): break
            phone = s.get('phone', '').replace(" ", "").replace("-", "")
            try:
                client = TelegramClient(f"session_{phone}", int(s['api_id']), s['api_hash'], loop=loop)
                async def _check():
                    try:
                        await client.connect()
                        if await client.is_user_authorized():
                            me = await client.get_me()
                            s['name'] = f"{me.first_name} {me.last_name or ''}".strip()
                            s['username'] = me.username or ""
                    except: pass
                    finally:
                        if client.is_connected(): await client.disconnect()
                loop.run_until_complete(_check())
            except: pass
        save_sessions(sessions)
        log_msg("SUCCESS", "✅ Все аккаунты обновлены.")
        if root: root.after(0, lambda: refresh_main_checks())
    threading.Thread(target=_runner, daemon=True).start()
def parse_target_file(file_content):
    """
    Парсер: сохраняет шапку в original_header и ищет кандидатов.
    """
    # Добавили ключ "original_header"
    data = {"company_name": "Unknown_Company", "director_name": None, "candidates": [], "original_header": ""}

    # 1. ГЛАВНОЕ РАЗДЕЛЕНИЕ
    parts = re.split(r'\+?={10,}', file_content)

    if len(parts) > 1:
        header_content = parts[0]
        candidates_content = "\n".join(parts[1:])
    else:
        header_content = file_content
        candidates_content = ""

    # === СОХРАНЯЕМ ШАПКУ ДЛЯ ОТЧЕТА ===
    data["original_header"] = header_content.strip()

    # --- ЧАСТЬ 1: ПАРСИНГ ДАННЫХ ИЗ ШАПКИ ---
    
    # Ищем название компании (AO, OOO, ПАО, ИП и т.д.)
    header_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', header_content)
    
    if header_match: 
        data["company_name"] = header_match.group(1).strip()
    else:
        # Запасной вариант: просто текст в кавычках
        fallback_match = re.search(r'["«“]([^"»”]+)["»”]', header_content)
        if fallback_match:
             data["company_name"] = fallback_match.group(1).strip()
    
    # Ищем Директора
    try:
        director_match = re.search(r'(?:Руководитель|ГЕНЕРАЛЬНЫЙ ДИРЕКТОР)[\s\S]*?([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)', header_content)
        if director_match:
            parts = director_match.group(1).split()
            if len(parts) >= 2:
                data["director_name"] = f"{parts[0]} {parts[1]}"
    except Exception as e:
        print(f"Ошибка парсинга директора: {e}")


    # --- ЧАСТЬ 2: КАНДИДАТЫ ---
    if candidates_content:
        candidate_sections = re.split(r'-{5,}', candidates_content)
        
        for sec in candidate_sections:
            if not sec.strip(): continue
            
            phones = []
            for line in sec.split('\n'):
                cl = re.sub(r'\D', '', line)
                if (len(cl)==10 or len(cl)==11) and not cl.startswith('19') and not cl.startswith('20'):
                    phones.append(cl)
            
            if phones:
                name = "Unknown"
                nm = re.search(r'^([А-ЯЁ\s]+)\s+(\d{2}\.\d{2}\.\d{4})', sec, re.MULTILINE)
                if nm: 
                    name = nm.group(1).strip()
                else:
                    nm2 = re.search(r'^([А-ЯЁ]{2,}\s+[А-ЯЁ]{2,}\s+[А-ЯЁ]{2,})', sec, re.MULTILINE)
                    if nm2: name = nm2.group(1).strip()
                
                data["candidates"].append({"full_name": name, "phones": phones})

    return data


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
    prompt = f"Введите ОБЛАЧНЫЙ ПАРОЛЬ (2FA) для {phone}:" if is_password else f"Дайте буквы из смс:) для {phone}:"
    
    # Используем словарь для хранения результата, чтобы он был доступен из вложенной функции
    result_data = {"value": None}
    # Событие для ожидания ввода
    wait_event = threading.Event()

    def show():
        try:
            win = Toplevel(root)
            win.title("Ввод кода")
            
            # Центрируем окно
            w, h = 350, 180
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
            win.resizable(False, False)
            win.configure(bg="#2E3440") # Под цвет вашей темы

            # Интерфейс
            ttk.Label(win, text=prompt, wraplength=330, background="#2E3440", foreground="white", font=("Arial", 10, "bold")).pack(pady=(15, 10))
            
            show_char = "*" if is_password else ""
            input_var = tk.StringVar()
            
            e = ttk.Entry(win, textvariable=input_var, font=("Arial", 12), show=show_char)
            e.pack(fill="x", padx=20, pady=5)
            e.focus_force()

            def submit(*args):
                val = input_var.get().strip()
                if val:
                    result_data["value"] = val
                wait_event.set() # Разблокируем поток
                win.destroy()

            def on_close():
                wait_event.set() # Разблокируем поток (значение останется None)
                win.destroy()

            ttk.Button(win, text="ОТПРАВИТЬ", command=submit).pack(pady=15)
            
            # Бинды
            e.bind('<Return>', submit)
            win.protocol("WM_DELETE_WINDOW", on_close)
            
            # Делаем окно модальным и поверх всех
            win.transient(root)
            win.attributes('-topmost', True)
            win.lift()
            win.grab_set() # Захватываем фокус
            
        except Exception as e:
            print(f"Ошибка GUI: {e}")
            wait_event.set()

    # Запускаем GUI в главном потоке
    root.after(0, show)
    
    # ВАЖНО: Останавливаем выполнение скрипта здесь и ждем, пока wait_event не станет True
    # (это произойдет, когда вы нажмете кнопку или закроете окно)
    wait_event.wait()
    
    return result_data["value"]

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

# ==========================================
# ИСПРАВЛЕННАЯ ЛОГИКА ВХОДА (CHECK)
# ==========================================
def run_login_check(s_data, callback_refresh):
    # 1. Чистим номер телефона ЖЕСТКО
    raw_phone = s_data.get('phone', '')
    phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    
    print(f"DEBUG: Начинаем вход для {phone} (Файл: session_{phone}.session)")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Используем ЧИСТЫЙ номер для имени файла
    client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
    
    async def process():
        try:
            print("DEBUG: Подключение к серверу Telegram...")
            await client.connect()
            
            if not await client.is_user_authorized():
                print("DEBUG: Требуется авторизация. Запрашиваю код...")
                try:
                    await client.send_code_request(phone)
                    print("DEBUG: СМС отправлено.")
                except Exception as e:
                    # Часто бывает FloodWait, выводим его юзеру
                    root.after(0, lambda: messagebox.showerror("Ошибка API", f"Telegram не дал отправить код:\n{e}"))
                    return

                # Спрашиваем код (запуск в отдельном экзекуторе, чтобы не морозить loop)
                code = await loop.run_in_executor(None, ask_code_gui, phone, False)
                
                if not code:
                    print("DEBUG: Код не введен.")
                    return
                
                print(f"DEBUG: Пробую войти с кодом {code}...")
                
                try:
                    await client.sign_in(phone, code)
                    print("DEBUG: Вход выполнен!")
                    
                except SessionPasswordNeededError:
                    print("DEBUG: Обнаружен 2FA (Облачный пароль)!")
                    # Спрашиваем пароль
                    pwd = await loop.run_in_executor(None, ask_code_gui, phone, True)
                    if not pwd:
                        print("DEBUG: Пароль не введен.")
                        return
                    await client.sign_in(password=pwd)
                    print("DEBUG: Вход с паролем выполнен!")
                    
                except PhoneCodeInvalidError:
                    root.after(0, lambda: messagebox.showerror("Ошибка", "Неверный код!"))
                    return
                except Exception as e:
                    print(f"DEBUG: Ошибка при sign_in: {e}")
                    root.after(0, lambda: messagebox.showerror("Ошибка входа", f"{e}"))
                    return
            
            # Если дошли сюда - значит авторизованы
            me = await client.get_me()
            print(f"DEBUG: Успех! User: {me.username}")
            
            update_session_info(raw_phone, f"{me.first_name} {me.last_name or ''}", me.username or "")
            
            root.after(0, lambda: messagebox.showinfo("Успех", f"Аккаунт {phone} подключен!\n@{me.username}"))
            if root: root.after(0, callback_refresh)
            
        except Exception as e:
            print(f"DEBUG: Критическая ошибка process: {e}")
            root.after(0, lambda: messagebox.showerror("Сбой", f"Критическая ошибка:\n{e}"))
        finally:
            if client.is_connected(): await client.disconnect()

    try:
        loop.run_until_complete(process())
    except Exception as e:
        print(f"Loop Error: {e}")
    finally:
        loop.close()

async def add_and_clean(client, chat, user, delays):
    try:
        # === ИСПРАВЛЕНИЕ: БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ИМЕНИ ===
        # Если это InputPeerUser (технический объект), у него нет имени, берем ID
        if hasattr(user, 'first_name'):
            u_name = user.first_name
        else:
            u_id = getattr(user, 'user_id', 'Unknown')
            u_name = f"User_ID_{u_id}"
            
        log_msg("INFO", f"   👤 Инвайт контакта: {u_name}...")
        # ===============================================

        # Используем прямой запрос
        await client(functions.messages.AddChatUserRequest(
            chat_id=chat.id, user_id=user, fwd_limit=100
        ))
        log_msg("SUCCESS", f"   ✅ Контакт добавлен.")
        
        # Пауза перед чисткой
        await asyncio.sleep(1)
        
        # Чистка сообщений о вступлении
        msgs = await client.get_messages(chat, limit=5)
        ids = [m.id for m in msgs if m.action] 
        if ids: 
            await client.delete_messages(chat, ids, revoke=True)
            log_msg("INFO", "   🧹 История очищена.")
            
        return True
    except UserPrivacyRestrictedError:
        log_msg("WARN", f"   🚫 Приватность: {u_name} запретил инвайт.")
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
async def process_smart_target_file(maker_client, guest_client, file_path, guest_session_dict=None):
    try:
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
        parsed_data = parse_target_file(content)
        
        # Исходное имя из файла (для отчета и предзаполнения)
        original_company_name = parsed_data.get('company_name', 'Unknown_Company')
        
        # Переименование мейкера/гостя (используем данные из файла)
        if guest_client and parsed_data['director_name']:
            try:
                d_name = parsed_data['director_name']
                d_parts = d_name.split()
                if len(d_parts) >= 2:
                    new_first = d_parts[1]
                    new_last = d_parts[0]
                else:
                    new_first = d_name
                    new_last = ""

                await guest_client(functions.account.UpdateProfileRequest(first_name=new_first, last_name=new_last))
                log_msg("GUEST", f"👤 Гость переименован: {new_first} {new_last}")
            except: pass

        if maker_client and original_company_name:
            try:
                await maker_client(functions.account.UpdateProfileRequest(first_name=original_company_name, last_name=""))
                log_msg("INFO", f"🤖 Мейкер переименован: {original_company_name}")
            except: pass

        log_msg("WAIT", f"🚀 Запуск пробива с ID-отслеживанием...")
        
        # === ПОДГОТОВКА СПИСКА ===
        batch_list = []
        tracking_map = {} 
        
        for candidate in parsed_data['candidates']:
            for raw in candidate['phones']:
                d = re.sub(r'\D', '', raw)
                if len(d) == 11 and d.startswith('8'): import_phone = "+7" + d[1:]
                elif len(d) == 10 and d.startswith('9'): import_phone = "+7" + d
                else: import_phone = "+" + d
                
                my_client_id = random.randint(10000000, 999999999)
                tracking_map[my_client_id] = {'fio': candidate['full_name'], 'orig_phone': raw.strip()}

                inp = types.InputPhoneContact(
                    client_id=my_client_id, 
                    phone=import_phone, 
                    first_name=candidate['full_name'][:20], 
                    last_name=""
                )
                batch_list.append(inp)

        # === ЗАПУСК ПРОВЕРКИ ===
        found_matches = []
        chunk_size = 15
        total_checked = 0
        
        for i in range(0, len(batch_list), chunk_size):
            chunk = batch_list[i : i + chunk_size]
            log_msg("INFO", f"   📤 Проверка пачки {i+1}-{i+len(chunk)}...")
            
            try:
                res = await maker_client(functions.contacts.ImportContactsRequest(contacts=chunk))
                
                tg_id_to_client_id = {}
                for imported_entry in res.imported:
                    tg_id_to_client_id[imported_entry.user_id] = imported_entry.client_id
                
                users_to_refetch = []
                for u in res.users:
                    c_id = tg_id_to_client_id.get(u.id)
                    if c_id and hasattr(u, 'access_hash'):
                        users_to_refetch.append(types.InputUser(user_id=u.id, access_hash=u.access_hash))

                if res.users:
                    del_ids = [u.id for u in res.users]
                    try:
                        await maker_client(functions.contacts.DeleteContactsRequest(id=del_ids))
                    except: pass

                if users_to_refetch:
                    clean_users = await maker_client(functions.users.GetUsersRequest(id=users_to_refetch))
                    for u in clean_users:
                        my_c_id = tg_id_to_client_id.get(u.id)
                        if not my_c_id: continue
                        orig_data = tracking_map.get(my_c_id)
                        if not orig_data: continue
                        
                        found_matches.append({
                            'target_fio': orig_data['fio'],
                            'user': u,
                            'phone': orig_data['orig_phone']
                        })
                        log_msg("SUCCESS", f"      ✅ {orig_data['fio']} -> найден ID {u.id}")

                total_checked += len(chunk)
                await asyncio.sleep(random.uniform(3.0, 6.0))

            except FloodWaitError as e:
                log_msg("ERROR", f"⛔ FLOOD WAIT: Ждем {e.seconds} сек.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log_msg("ERROR", f"❌ Ошибка: {e}")

        if not found_matches:
            log_msg("WARN", "⚠️ Никого не нашли.")
            return [], None

        # Окно выбора контактов
        future_gui = asyncio.get_running_loop().create_future()
        def show_gui():
            win = MatchReviewWindow(root, found_matches)
            root.wait_window(win)
            if win.result is not None: future_gui.set_result(win.result)
            else: future_gui.set_result([])
        root.after(0, show_gui)
        
        selected_matches = await future_gui
        if not selected_matches: return [], None

        # ==========================================
        # === НОВОЕ: ЗАПРОС НАЗВАНИЯ ГРУППЫ ===
        # ==========================================
        future_name = asyncio.get_running_loop().create_future()

        def ask_group_name_step():
            # Предлагаем то, что нашли в файле, но даем изменить
            user_input = simpledialog.askstring(
                "Название групп", 
                "Введите название для создаваемых групп:", 
                initialvalue=original_company_name,
                parent=root
            )
            future_name.set_result(user_input)

        root.after(0, ask_group_name_step)
        
        # Ждем ввода
        manual_group_name = await future_name
        
        # Если нажали Отмена или оставили пустым -> используем из файла, 
        # но лучше использовать то, что ввел юзер.
        final_group_name = manual_group_name if manual_group_name else original_company_name
        
        log_msg("INFO", f"📝 Название для групп установлено: {final_group_name}")
        # ==========================================


        # === СОХРАНЕНИЕ ОТЧЕТА ===
        # Сохраняем под именем из ФАЙЛА (original_company_name), чтобы не терять связь с исходником
        try:
            folder_name = "прописанные базы"
            if not os.path.exists(folder_name): os.makedirs(folder_name)
            safe = re.sub(r'[\\/*?:"<>|]', "", original_company_name).strip() or "Report"
            full_path = os.path.join(folder_name, f"{safe}.txt")

            with open(full_path, "w", encoding="utf-8") as f:
                orig_head = parsed_data.get('original_header', '')
                if orig_head:
                    f.write(orig_head + "\n")
                    f.write("="*50 + "\n\n")
                
                f.write(f"ОТЧЕТ: {original_company_name}\n")
                f.write(f"ИСПОЛЬЗУЕМОЕ ИМЯ ГРУПП: {final_group_name}\n") # Добавили инфо о выбранном имени
                f.write("="*50 + "\n\n")

                for m in selected_matches:
                    u = m['user']
                    real_tg_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                    uname = f"@{u.username}" if u.username else "Нет юзернейма"
                    
                    f.write(f"👤 ИСКОМЫЙ:  {m['target_fio']}\n")
                    f.write(f"📱 ТЕЛЕФОН:  {m['phone']}\n")
                    f.write(f"✅ TELEGRAM: {real_tg_name} ({uname})\n")
                    f.write("-" * 40 + "\n\n")
            
            log_msg("SUCCESS", f"📄 Отчет сохранен: {full_path}")
        except Exception as e: 
            log_msg("ERROR", f"Ошибка сохранения: {e}")

        # === ЛОГИКА ПОДТВЕРЖДЕНИЯ (ФИНАЛЬНАЯ ПАУЗА) ===
        future_confirm = asyncio.get_running_loop().create_future()
        
        def ask_go_dialog():
            ans = messagebox.askyesno(
                "ФИНАЛЬНАЯ ПРОВЕРКА", 
                f"Выбрано {len(selected_matches)} чел.\n"
                f"Группы будут названы: '{final_group_name}'\n\n"
                "⚠️ ПРОВЕРЬТЕ АВАТАРКИ И ИМЕНА В ТЕЛЕГРАМЕ!\n\n"
                "ДА -> Запустить процесс СРАЗУ.\n"
                "НЕТ -> Я изменил данные. ОБНОВИТЬ ИХ и запустить."
            )
            future_confirm.set_result(ans)

        root.after(0, ask_go_dialog)
        
        is_immediate_start = await future_confirm
        
        if not is_immediate_start:
            log_msg("WAIT", "🔄 Обновляем данные сессий (Гость/Мейкер)...")
            
            if guest_client and guest_session_dict:
                try:
                    me_g = await guest_client.get_me()
                    new_name = f"{me_g.first_name} {me_g.last_name or ''}".strip()
                    new_username = me_g.username or ""
                    
                    guest_session_dict['name'] = new_name
                    guest_session_dict['username'] = new_username
                    update_session_info(guest_session_dict['phone'], new_name, new_username)
                    log_msg("INFO", f"   👤 Гость ОБНОВЛЕН: {new_name} (@{new_username})")
                except Exception as e:
                     log_msg("WARN", f"⚠️ Ошибка обновления Гостя: {e}")

            try:
                me_m = await maker_client.get_me()
                nm = f"{me_m.first_name} {me_m.last_name or ''}".strip()
                log_msg("INFO", f"   🤖 Мейкер актуален: {nm}")
            except: pass
                
            log_msg("SUCCESS", "✅ Данные сохранены. Запуск через 2 сек...")
            await asyncio.sleep(2)
        else:
            log_msg("INFO", "🚀 Запуск без обновления кэша...")

        log_msg("SUCCESS", f"🚀 ПОЕХАЛИ! Работаем с {len(selected_matches)} чел.")
        
        valid_input_users = []
        for m in selected_matches:
            try: valid_input_users.append(await maker_client.get_input_entity(m['user']))
            except: pass
        
        # ВАЖНО: Возвращаем final_group_name, который ввел пользователь
        return valid_input_users, final_group_name

    except Exception as e:
        log_msg("ERROR", f"Smart error: {e}")
        return [], None


### Полностью исправленный `worker_task` (замени весь блок этой функции на приведённый код)
async def worker_task(session, names, delays, target_username, smart_file_path=None, guest_session=None):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    # Создаем клиент
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    created_chat_ids = [] 
    my_id = None

    try:
        await client.connect()
        
        # === АВТОРИЗАЦИЯ (ИЗ ТВОЕГО КОДА - ЛУЧШИЙ ВАРИАНТ) ===
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! Отправляю код...")
            try:
                await client.send_code_request(phone)
                # Вызываем GUI для ввода кода
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
        await asyncio.get_running_loop().run_in_executor(None, mark_account_active, phone)
        await hide_maker_phone(client) # Скрываем номер
        
        log_msg("INFO", f"🚀 {phone} (ID: {my_id}): Maker начал работу.")

        # === ЛОГИКА SMART MODE (ФАЙЛЫ И ПАПКИ) ===
        smart_users = []
        detected_company_name = None

        if smart_file_path:
            log_msg("INFO", f"🧠 {phone}: Smart Mode (Работа по файлу).")
            # Нужен клиент гостя для переименования (если есть)
            g_client = None
            if guest_session:
                try:
                    # Чистим номер так же жестко, как при логине
                    raw_gp = guest_session['phone']
                    gp = raw_gp.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
                    
                    g_client = TelegramClient(f"session_{gp}", int(guest_session['api_id']), guest_session['api_hash'])
                    await g_client.connect()
                    
                    if not await g_client.is_user_authorized():
                        log_msg("WARN", f"⚠️ Гость {gp} не авторизован (проверьте вход)!")
                except Exception as e: 
                    log_msg("WARN", f"⚠️ Ошибка подключения Гостя: {e}")

            # Запускаем парсер (он сам сохранит отчет в папку "прописанные базы")
            res = await process_smart_target_file(client, g_client, smart_file_path, guest_session)
            
            if isinstance(res, tuple): smart_users, detected_company_name = res
            else: smart_users = res

            if g_client and g_client.is_connected(): await g_client.disconnect()
            
            if not smart_users:
                log_msg("WARN", "⚠️ Кандидаты из файла не выбраны или не найдены.")
                return []

            # Если нашли компанию, используем её имя для групп
            count_needed = len(smart_users)
            if detected_company_name:
                names = [detected_company_name for _ in range(count_needed)]
            else:
                # Генерируем имена, если название компании не нашли
                base = names[0].split()[0] if names else "Group"
                names = generate_group_names(base, count_needed)

        # === 1. ПРЕДВАРИТЕЛЬНЫЙ ПОИСК ГОСТЯ ===
        target_user_entity = None
        
        # Если есть сессия гостя, берем юзернейм оттуда (приоритет)
        real_target_username = target_username
        if guest_session and guest_session.get('username'):
             real_target_username = guest_session['username']

        if delays.get('add_username', 1) and real_target_username:
            clean_user = real_target_username.strip().replace('@', '')
            try:
                # Ищем сущность один раз
                target_user_entity = await client.get_input_entity(clean_user)
                log_msg("INFO", f"   🎯 Гость кэширован: @{clean_user}")
            except Exception as e:
                log_msg("WARN", f"   ⚠️ Гость @{clean_user} НЕ НАЙДЕН: {e}")

        # === 2. ПОЛУЧЕНИЕ КОНТАКТОВ (ЕСЛИ НЕ SMART MODE) ===
        contact_users = []
        if not smart_users and delays.get('add_contacts', 1):
            try:
                cts = await client(functions.contacts.GetContactsRequest(hash=0))
                contact_users = [u for u in cts.users if not u.bot and not u.deleted and u.id != me.id]
                random.shuffle(contact_users)
                log_msg("INFO", f"   📋 Контактов из книги: {len(contact_users)}")
            except: pass

        delayed_invites = [] 

        # === 3. ЦИКЛ СОЗДАНИЯ ГРУПП ===
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            log_msg("INFO", f"🛠 ({i+1}/{len(names)}) {name}")
            
            # Определяем кого инвайтить: из файла (Smart) или из книги (Обычный)
            curr_contact = None
            if smart_users:
                if i < len(smart_users): curr_contact = smart_users[i]
            elif contact_users:
                curr_contact = contact_users.pop(0)

            try:
                # Создаем чат
                res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                created_chat_ids.append(chat.id)
                log_msg("SUCCESS", f"   ✅ Группа создана.")

                # А. Добавляем ГОСТЯ
                if target_user_entity:
                    try:
                        # ВАЖНО: Используем safe_add_guest (твоя функция из файла, она надежнее)
                        await safe_add_guest(client, chat, target_user_entity)
                    except Exception as e: 
                        log_msg("ERROR", f"   🆘 Ошибка добавления Гостя: {e}")

                # Б. Добавляем КОНТАКТ (Человека из базы или книги)
                if curr_contact:
                    # Для Smart Mode curr_contact уже является InputEntity (подготовленным) или User
                    # Для обычного режима это User
                    
                    if delays.get('contact_mode', 0) == 0: # Режим "Сразу"
                        await smart_sleep(delays['contact'], delays['random'])
                        # Используем твою функцию add_and_clean
                        await add_and_clean(client, chat, curr_contact, delays)
                    else: # Режим "После"
                        delayed_invites.append((chat, curr_contact))
                        log_msg("INFO", f"   ⏳ Контакт отложен (Режим 'После')")
                
                await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: FLOOD WAIT. Стоп.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Флуд, ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка цикла: {e}")

        # === 4. ОБРАБОТКА ОТЛОЖЕННЫХ ===
        if delayed_invites and not stop_flag.is_set():
            log_msg("INFO", f"📥 {phone}: Добавление отложенных контактов...")
            for idx, (chat_obj, user_obj) in enumerate(delayed_invites):
                if stop_flag.is_set(): break
                await add_and_clean(client, chat_obj, user_obj, delays)
                await smart_sleep(delays['contact'], delays['random'])

        log_msg("SUCCESS", f"🏁 {phone}: Завершено.")
        return {'maker_id': my_id, 'chats': created_chat_ids}

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка {phone}: {e}")
        return None
    finally:
        if client.is_connected(): await client.disconnect()

# === УЛУЧШЕННЫЙ GUEST LOGIC (С ПРОВЕРКОЙ МЕЙКЕРА) ===

async def guest_execution_final(session, all_maker_ids, target_group_ids, greeting_text):
    if not target_group_ids: return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 ГОСТЬ {phone}: Не авторизован!")
            return

        me = await client.get_me()
        log_msg("GUEST", f"😎 ГОСТЬ ({me.first_name}) начинает рассылку...")

        # Даем секунду на синхронизацию
        await asyncio.sleep(2)
        
        count_sent = 0
        
        for gid in target_group_ids:
            if stop_flag.is_set(): break
            
            # === АГРЕССИВНЫЙ ПОИСК СУЩНОСТИ ===
            target_entity = None
            
            # Телеграм может хранить ID в трех видах. Пробуем все.
            # 1. Как есть (Positive)
            # 2. Как чат (Negative)
            # 3. Как канал/супергруппа (-100...)
            possible_ids = [gid, -gid, int(f"-100{gid}"), int(f"-100{abs(gid)}")]
            
            for pid in possible_ids:
                try:
                    target_entity = await client.get_entity(pid)
                    if target_entity:
                        break # НАШЛИ!
                except:
                    continue
            
            if not target_entity:
                # Последний шанс: ищем перебором диалогов (медленно, но надежно)
                try:
                    async for d in client.iter_dialogs(limit=50):
                        if abs(d.id) == abs(gid) or abs(d.id) == abs(int(f"-100{gid}")):
                            target_entity = d.entity
                            break
                except: pass

            if not target_entity:
                log_msg("WARN", f"   ⚠️ Гость не может найти группу ID {gid} (даже перебором).")
                continue

            try:
                # Пробуем отправить
                title = getattr(target_entity, 'title', 'Group')
                log_msg("DEBUG", f"   ✍️ Пишем в '{title}'...")
                
                await client.send_message(target_entity, greeting_text)
                
                log_msg("SUCCESS", f"   📨 Приветствие отправлено!")
                count_sent += 1
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except Exception as e:
                log_msg("WARN", f"   ⚠️ Ошибка отправки: {e}")
                await asyncio.sleep(1)

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count_sent} шт).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === ОБНОВЛЕННЫЙ ЗАПУСК ПОТОКОВ ===

def run_thread(main_sessions, guest_session, names, delays, target_username_manual, greeting_text, need_greet, smart_file_path=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Определяем цель
    target_username = target_username_manual
    if guest_session and guest_session.get('username'):
        target_username = guest_session['username']
    
    log_msg("INFO", f"🎯 Цель для инвайта: @{target_username}")
    if smart_file_path:
        log_msg("INFO", f"📂 Выбран файл базы: {os.path.basename(smart_file_path)}")

    maker_tasks = []
    for s in main_sessions:
        # Передаем smart_file_path (он будет None, если обычный режим, или путем к файлу, если Smart)
        maker_tasks.append(worker_task(s, names, delays, target_username, smart_file_path, guest_session))
    
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
            
            log_msg("INFO", f"📊 ИТОГ: Создано {len(all_created_groups)} групп.")

            if guest_session and not stop_flag.is_set() and all_created_groups and need_greet:
                log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ ===")
                log_msg("WAIT", "⏳ Ждем 3 сек...")
                time.sleep(3)
                loop.run_until_complete(guest_execution_final(guest_session, all_maker_ids, all_created_groups, greeting_text))
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка потока: {e}")
    finally:
        loop.close()
        # Возвращаем кнопки в активное состояние
        if root: 
            root.after(0, lambda: start_btn.config(state='normal'))
            root.after(0, lambda: smart_btn.config(state='normal'))


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

# Найдите функцию start_process и замените её полностью:
def start_process(mode="standard"):
    try:
        # ЛОГИКА ВЫБОРА РЕЖИМА
        smart_path = None
        if mode == "smart":
            # Спрашиваем файл
            smart_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
            if not smart_path:
                return # Если нажали отмену, выходим

        stop_flag.clear()
        log_widget.config(state='normal')
        log_widget.delete("1.0", tk.END)
        log_widget.config(state='disabled')

        sessions_data = load_sessions()
        
        selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
        if not selected_indices:
            messagebox.showwarning("Ошибка", "Выберите хотя бы одного Мейкера (галочкой)!")
            return

        guest_idx = guest_account_index.get()
        guest_session = None
        if guest_idx != -1:
            if guest_idx < len(sessions_data):
                guest_session = sessions_data[guest_idx]
                if guest_idx in selected_indices:
                    selected_indices.remove(guest_idx)

        main_sessions = [sessions_data[i] for i in selected_indices]
        if not main_sessions:
            messagebox.showwarning("Ошибка", "Список мейкеров пуст!")
            return

        greeting_text = txt_greeting.get("1.0", tk.END).strip()
        need_greet = var_send_greeting.get()

        if guest_session and need_greet and not greeting_text:
            messagebox.showwarning("Внимание", "Текст приветствия пустой!")
            return

        cfg = load_config()
        try:
            delays = {
                "creation": float(cfg.get("delay_creation", 180)),
                "contact": float(cfg.get("delay_contact", 20)),
                "cleanup": float(cfg.get("delay_cleanup", 10)),
                "random": int(cfg.get("random_delay", 1)),
                "add_username": int(cfg.get("add_username", 1)),
                "add_contacts": int(cfg.get("add_contacts", 1)),
                "contact_mode": int(cfg.get("contact_mode", 1))
            }
        except ValueError as ve:
            messagebox.showerror("Ошибка настроек", f"Проверьте числа в настройках: {ve}")
            return

        base_name = ent_name.get().strip()
        try:
            count_per_maker = int(ent_count.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество групп должно быть числом!")
            return

        use_words_flag = int(cfg.get("use_random_words", "1"))
        if not base_name and not use_words_flag:
            base_name = "Group"
            ent_name.delete(0, tk.END)
            ent_name.insert(0, base_name)

        manual_username = ent_user.get().strip().replace('@', '')

        # Генерация имен (если не Smart mode)
        # В Smart mode имена часто берутся из файла, но генерация нужна как fallback
        names = generate_group_names(base_name, count_per_maker)
        
        # Блокируем кнопки
        start_btn.config(state='disabled')
        smart_btn.config(state='disabled') # Блокируем вторую кнопку тоже
        
        threading.Thread(
            target=run_thread,
            # Передаем smart_path последним аргументом
            args=(main_sessions, guest_session, names, delays, manual_username, greeting_text, need_greet, smart_path),
            daemon=True
        ).start()
        
    except Exception as e:
        messagebox.showerror("Критическая ошибка запуска", str(e))
        start_btn.config(state='normal')
        smart_btn.config(state='normal')


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
    

def on_tab_changed(event):
    nb = event.widget
    try:
        # Количество вкладок всего
        total_tabs = nb.index("end")
        if total_tabs == 0: return

        # Индекс текущей выбранной вкладки
        current_tab_index = nb.index("current")
        
        # Индекс вкладки "+" (она всегда последняя)
        plus_tab_index = total_tabs - 1
        
        # Если выбрали последнюю вкладку (которая "+")
        if current_tab_index == plus_tab_index:
            
            # Сразу прыгаем на первую вкладку (0), чтобы визуально уйти с плюса
            # Если вкладок больше одной (плюс и еще что-то), идем на 0.
            if total_tabs > 1:
                nb.select(0)
            
            # Запускаем диалог ввода имени с небольшой задержкой, чтобы интерфейс успел прогрузиться
            def ask_name():
                new_title = simpledialog.askstring("Новая заметка", "Название вкладки:", parent=root)
                
                # Если нажали "Отмена" или ввели пустоту
                if not new_title or not new_title.strip():
                    return # Мы уже переключились на вкладку 0 выше, так что просто выходим
                
                clean_title = new_title.strip()
                
                # Проверка на дубликаты
                notes = load_notes()
                if clean_title in notes:
                    messagebox.showwarning("Ошибка", "Такое имя уже есть!", parent=root)
                    return

                # Создаем новую вкладку
                frame = ttk.Frame(nb)
                
                # Текстовое поле с темной темой
                txt = scrolledtext.ScrolledText(frame, font=("Consolas", 11), bg="#0F0F0F", fg="#E0E0E0", insertbackground="#9D00FF")                
                txt.pack(fill="both", expand=True, padx=5, pady=5)
                
                # Кнопки
                btn_frame = ttk.Frame(frame)
                btn_frame.pack(fill="x", padx=5, pady=5)
                
                def _save():
                    d = load_notes()
                    d[clean_title] = txt.get("1.0", tk.END)
                    save_notes_to_file(d)
                    messagebox.showinfo("Сохранено", f"Заметка '{clean_title}' сохранена!")
                
                def _delete():
                    if messagebox.askyesno("Удаление", f"Удалить '{clean_title}'?", parent=root):
                        d = load_notes()
                        if clean_title in d: del d[clean_title]
                        save_notes_to_file(d)
                        nb.forget(frame)

                ttk.Button(btn_frame, text="💾 Сохранить", command=_save).pack(side="left")
                ttk.Button(btn_frame, text="🗑 Удалить", command=_delete).pack(side="right")

                # Вставляем ПЕРЕД плюсом
                nb.insert(plus_tab_index, frame, text=clean_title)
                # Переключаемся на новую вкладку
                nb.select(plus_tab_index)
            
            # Вызываем диалог через 100мс (решает проблему зависания при клике)
            root.after(100, ask_name)

    except Exception as e:
        print(f"Ошибка логики вкладок: {e}")

def stop_process():
    stop_flag.set()
    log_msg("WARN", "⛔ ОСТАНОВКА... (Завершение текущих операций)")
    # Возвращаем кнопку старт в активное состояние через секунду
    if root: root.after(1000, lambda: start_btn.config(state='normal'))

# ===  ОКНА (НАСТРОЙКИ И АККАУНТЫ) ===

# ==========================================
# === НОВЫЙ ПРОФЕССИОНАЛЬНЫЙ ИНТЕРФЕЙС ===
# ==========================================

# Глобальные ссылки на элементы UI для логики
tree_accounts = None
ent_name = None
ent_count = None
ent_user = None
txt_greeting = None
start_btn = None

# --- СТИЛИЗАЦИЯ (DARK MODE) ---
# --- СТИЛИЗАЦИЯ (NEXUS PURPLE DARK) ---
def setup_dark_theme():
    style = ttk.Style()
    style.theme_use('clam')
    
    # Цвета Nexus
    bg_main = "#121212"       # Основной черный фон
    bg_sidebar = "#0F0F0F"    # Очень темный фон меню
    bg_input = "#1E1E1E"      # Поля ввода
    fg_text = "#E0E0E0"       # Текст
    accent = "#9D00FF"        # Фиолетовый неон
    
    # 1. Основные элементы
    style.configure(".", background=bg_main, foreground=fg_text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg_main)
    style.configure("Sidebar.TFrame", background=bg_sidebar) # Стиль для боковой панели
    style.configure("TLabel", background=bg_main, foreground=fg_text)
    
    # 2. Поля ввода (Консольный стиль)
    style.configure("TEntry", fieldbackground=bg_input, foreground="white", insertcolor=accent, borderwidth=0)
    style.map("TEntry", fieldbackground=[('focus', bg_input)], bordercolor=[('focus', accent)])
    
    # 3. Рамки
    style.configure("TLabelframe", background=bg_main, bordercolor="#333333", borderwidth=1)
    style.configure("TLabelframe.Label", background=bg_main, foreground=accent, font=("Segoe UI", 9, "bold"))
    
    # 4. Кнопки (Обычные, внутри контента)
    style.configure("TButton", background=accent, foreground="white", borderwidth=0, padding=6)
    style.map("TButton", background=[('active', "#B540FF"), ('pressed', "#7A00C7")])
    
    # Цветные кнопки
    style.configure("Green.TButton", background="#00E676", foreground="#121212")
    style.map("Green.TButton", background=[('active', "#69F0AE")])
    style.configure("Red.TButton", background="#FF5252", foreground="white")
    style.map("Red.TButton", background=[('active', "#FF8A80")])

    # 5. Скроллбары (Тонкие)
    style.configure("Vertical.TScrollbar", troughcolor=bg_main, background="#333", borderwidth=0, arrowcolor="white")

    # 6. Внутренние вкладки (ТОЛЬКО ДЛЯ ЗАМЕТОК)
    # Для заметок мы оставим табы, но сделаем их минималистичными
    style.configure("TNotebook", background=bg_main, borderwidth=0)
    style.configure("TNotebook.Tab", background="#1E1E1E", foreground="#888", padding=[10, 5])
    style.map("TNotebook.Tab", background=[('selected', accent)], foreground=[('selected', 'white')])

    # 7. Дерево списка
    style.configure("Treeview", background=bg_input, fieldbackground=bg_input, foreground="white", borderwidth=0, rowheight=28)
    style.configure("Treeview.Heading", background="#252525", foreground=accent, borderwidth=0, font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[('selected', accent)], foreground=[('selected', 'white')])

    return bg_main, bg_input

# === ЛОГИКА ВКЛАДКИ НАСТРОЕК (ВСТРОЕННАЯ) ===
def create_settings_tab(parent):
    cfg = load_config()
    fr = ttk.Frame(parent, padding=20)
    fr.pack(fill="both", expand=True)

    # 1. ВЕРХНИЙ ФРЕЙМ ДЛЯ КНОПКИ (Размещаем его первым, чтобы был сверху)
    top_btn_frame = ttk.Frame(fr)
    top_btn_frame.pack(side="top", fill="x", pady=(0, 20))

    # 2. ФРЕЙМ ДЛЯ КОЛОНОК С НАСТРОЙКАМИ (Размещаем под кнопкой)
    cols_frame = ttk.Frame(fr)
    cols_frame.pack(side="top", fill="both", expand=True)

    # --- Левая колонка (Тайминги) ---
    # Важно: теперь parent=cols_frame
    left_col = ttk.LabelFrame(cols_frame, text=" ⏱ Тайминги и Задержки ", padding=15)
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

    var_rand = tk.IntVar(value=int(cfg.get("random_delay", "1")))
    
    def toggle_inputs(*args):
        st = 'disabled' if var_rand.get() else 'normal'
        e1.config(state=st); e2.config(state=st)
    
    var_rand.trace_add("write", toggle_inputs)

    chk_rand = ttk.Checkbutton(left_col, text="Включить случайную задержку (5-15 сек)", variable=var_rand)
    chk_rand.pack(anchor="w", pady=(0, 15))

    f_t1 = ttk.Frame(left_col); f_t1.pack(fill="x", pady=5)
    ttk.Label(f_t1, text="Пауза после создания группы (сек):").pack(side="left")
    e1 = ttk.Entry(f_t1, width=10, font=("Consolas", 10))
    e1.pack(side="right"); e1.insert(0, cfg.get("delay_creation", "180"))

    f_t2 = ttk.Frame(left_col); f_t2.pack(fill="x", pady=5)
    ttk.Label(f_t2, text="Пауза после инвайта контакта (сек):").pack(side="left")
    e2 = ttk.Entry(f_t2, width=10, font=("Consolas", 10))
    e2.pack(side="right"); e2.insert(0, cfg.get("delay_contact", "20"))

    toggle_inputs()

    # --- Правая колонка (Опции) ---
    # Важно: теперь parent=cols_frame
    right_col = ttk.LabelFrame(cols_frame, text=" ⚙ Режимы работы ", padding=15)
    right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

    v_add_user = tk.IntVar(value=int(cfg.get("add_username", "1")))
    ttk.Checkbutton(right_col, text="Добавлять Дира (юзернейм)", variable=v_add_user).pack(anchor="w", pady=5)
    
    v_add_cont = tk.IntVar(value=int(cfg.get("add_contacts", "1")))
    ttk.Checkbutton(right_col, text="Инвайтить контакты из тел. книги", variable=v_add_cont).pack(anchor="w", pady=5)

    ttk.Separator(right_col, orient='horizontal').pack(fill='x', pady=15)

    ttk.Label(right_col, text="Режим инвайта контактов:", foreground="#aaaaaa").pack(anchor="w")
    v_mode = tk.IntVar(value=int(cfg.get("contact_mode", "1")))
    ttk.Radiobutton(right_col, text="Сразу (При создании группы - пока не использовать)", variable=v_mode, value=0).pack(anchor="w", pady=2)
    ttk.Radiobutton(right_col, text="После (Сначала создать все группы, потом все контакты)", variable=v_mode, value=1).pack(anchor="w", pady=2)

    # --- ФУНКЦИЯ СОХРАНЕНИЯ ---
    def save_settings():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get())
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        new_cfg["add_username"] = str(v_add_user.get())
        new_cfg["add_contacts"] = str(v_add_cont.get())
        new_cfg["contact_mode"] = str(v_mode.get())
        save_config(new_cfg)
        messagebox.showinfo("Настройки", "✅ Настройки успешно сохранены!")

    # --- СОЗДАНИЕ КНОПКИ (Помещаем в верхний фрейм) ---
    # anchor="center" ставит её по центру горизонтально
    ttk.Button(top_btn_frame, text="💾 СОХРАНИТЬ НАСТРОЙКИ", command=save_settings, style="Green.TButton", width=30)\
        .pack(anchor="center", ipady=5)
    

# === ЛОГИКА ВКЛАДКИ АККАУНТОВ (МЕНЕДЖЕР) ===
def create_accounts_tab(parent):
    fr = ttk.Frame(parent)
    fr.pack(fill="both", expand=True)

    toolbar = ttk.Frame(fr, padding=10)
    toolbar.pack(fill="x")

    # --- ПАНЕЛЬ ПОИСКА С ПЛЕЙСХОЛДЕРОМ ---
    search_frame = ttk.Frame(fr, padding=(10, 0, 10, 10))
    search_frame.pack(fill="x")
    
    ent_search = ttk.Entry(search_frame, width=30, font=("Consolas", 10))
    ent_search.pack(side="left", padx=0)

    # Логика плейсхолдера
    def on_acc_search_in(e):
        if ent_search.get() == "поиск":
            ent_search.delete(0, "end")
            ent_search.configure(foreground="white")

    def on_acc_search_out(e):
        if not ent_search.get():
            ent_search.insert(0, "поиск")
            ent_search.configure(foreground="#888")

    ent_search.insert(0, "поиск")
    ent_search.configure(foreground="#888")
    ent_search.bind("<FocusIn>", on_acc_search_in)
    ent_search.bind("<FocusOut>", on_acc_search_out)
    
    # --- ФУНКЦИЯ ОБНОВЛЕНИЯ (ИСПРАВЛЕННАЯ) ---
    def _refresh_tree(event=None):
        raw_val = ent_search.get().lower().strip()
        
        # 1. Подготовка фильтров
        search_query = ""      # "Сырой" запрос (для имен и юзернеймов)
        clean_query_phone = "" # Очищенный запрос (для телефонов)

        # Если там не плейсхолдер и не пусто
        if raw_val and raw_val != "поиск":
            search_query = raw_val
            # Убираем мусор из ЗАПРОСА, чтобы "+7 992" превратилось в "+7992"
            clean_query_phone = raw_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # Чистим таблицу
        for i in tree_accounts.get_children(): tree_accounts.delete(i)
        sessions = load_sessions()
        
        for idx, s in enumerate(sessions):
            raw_phone = s.get('phone', '')
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            
            # === ФИЛЬТРАЦИЯ ===
            if search_query:
                # А. Поиск по телефону (сравниваем чистый запрос с чистым номером в базе)
                db_phone_clean = raw_phone.lower().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                in_phone = clean_query_phone in db_phone_clean
                
                # Б. Поиск по имени и юзернейму (сравниваем как есть)
                in_name = search_query in name.lower()
                in_uname = search_query in uname.lower()
                
                # Если ни одно условие не сработало — пропускаем
                if not (in_phone or in_name or in_uname):
                    continue
            # ==================

            last_ts = s.get('last_used', 0)
            if last_ts:
                try: dt_str = datetime.fromtimestamp(float(last_ts)).strftime('%d.%m %H:%M')
                except: dt_str = "-"
            else: dt_str = "Новый"

            row_tags = ()
            display_uname = "-"
            if uname:
                display_uname = f"@{uname}"
                row_tags = ('gold_user',)

            tree_accounts.insert("", "end", iid=str(idx), 
                               values=(raw_phone, name, display_uname, dt_str), 
                               tags=row_tags)

    ent_search.bind("<KeyRelease>", _refresh_tree)

    # КНОПКИ
    def _add_acc():
        open_add_account_window(lambda: (_refresh_tree(), refresh_main_checks()))

    def _login_acc():
        sel = tree_accounts.selection()
        if not sel: messagebox.showwarning("!", "Выберите аккаунт!"); return
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        threading.Thread(target=lambda: run_login_check(s_data, _refresh_tree), daemon=True).start()

    def _delete_acc():
        sel = tree_accounts.selection()
        if not sel: return
        if not messagebox.askyesno("Удаление", f"Удалить {len(sel)} аккаунтов?"): return
        indices = sorted([int(x) for x in sel], reverse=True)
        ss = load_sessions()
        for i in indices: 
            if i < len(ss): del ss[i]
        save_sessions(ss)
        _refresh_tree(); refresh_main_checks()

    def _update_all():
        start_update_all()
        fr.after(2000, _refresh_tree)

    def _clear_contacts():
        sel = tree_accounts.selection()
        if not sel: messagebox.showwarning("!", "Выберите аккаунт!"); return
        idx = int(sel[0]); s_data = load_sessions()[idx]; phone = s_data['phone']
        if not messagebox.askyesno("Внимание", f"УДАЛИТЬ ВСЕ КОНТАКТЫ на {phone}?"): return

        p_win = Toplevel(root); p_win.title("Очистка"); p_win.geometry("300x120")
        p_win.transient(root); p_win.grab_set()
        lbl = ttk.Label(p_win, text="Удаление...", anchor="center"); lbl.pack(pady=10)
        pb = ttk.Progressbar(p_win, length=250, mode="indeterminate"); pb.pack(); pb.start(10)

        def runner():
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
            try:
                loop.run_until_complete(client.connect())
                if loop.run_until_complete(client.is_user_authorized()):
                    cts = loop.run_until_complete(client(functions.contacts.GetContactsRequest(hash=0)))
                    u_ids = [u.id for u in cts.users if not u.self]
                    if u_ids: 
                        for i in range(0, len(u_ids), 50):
                            loop.run_until_complete(client(functions.contacts.DeleteContactsRequest(id=u_ids[i:i+50])))
                    p_win.after(0, lambda: messagebox.showinfo("Готово", f"Удалено {len(u_ids)} контактов."))
                else: p_win.after(0, lambda: messagebox.showerror("Ошибка", "Нет входа!"))
            except Exception as e: p_win.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
            finally: 
                if client.is_connected(): loop.run_until_complete(client.disconnect())
                loop.close(); p_win.after(0, p_win.destroy)
        threading.Thread(target=runner, daemon=True).start()

    f_left = ttk.Frame(toolbar); f_left.pack(side="left")
    ttk.Button(f_left, text="➕ Добавить", command=_add_acc).pack(side="left", padx=(0, 5))
    ttk.Button(f_left, text="🔄 Войти/Обновить", command=_login_acc).pack(side="left", padx=5)
    
    f_mid = ttk.Frame(toolbar); f_mid.pack(side="left", padx=20)
    ttk.Button(f_mid, text="🧹 Удалить контакты", command=_clear_contacts).pack(side="left")
    ttk.Button(f_mid, text="⚡ Чекнуть ВСЕХ", command=_update_all).pack(side="left", padx=5)
    ttk.Button(f_mid, text="❐ Новое окно", command=open_new_window).pack(side="left", padx=5)

    ttk.Button(toolbar, text="❌ Удалить", command=_delete_acc, style="Red.TButton").pack(side="right")

    columns = ("phone", "name", "username", "last_active")
    global tree_accounts
    tree_accounts = ttk.Treeview(fr, columns=columns, show="headings", selectmode="extended")
    
    tree_accounts.heading("phone", text="Телефон")
    tree_accounts.heading("name", text="Имя")
    tree_accounts.heading("username", text="Username")
    tree_accounts.heading("last_active", text="Обновлен/Добавлен")
    
    tree_accounts.column("phone", width=140, anchor="center")
    tree_accounts.column("name", width=180, anchor="w")
    tree_accounts.column("username", width=140, anchor="w")
    tree_accounts.column("last_active", width=130, anchor="center")

    tree_accounts.tag_configure('gold_user', foreground='#FFD700')

    sb = ttk.Scrollbar(fr, orient="vertical", command=tree_accounts.yview)
    tree_accounts.configure(yscrollcommand=sb.set)
    tree_accounts.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
    sb.pack(side="right", fill="y", pady=10, padx=(0,10))

    _refresh_tree()

# Хелпер для проверки аккаунта (из старого кода, вынесен отдельно)
def run_login_check(s_data, callback_refresh):
    # 1. Сначала берем "грязный" номер для отображения
    raw_phone = s_data.get('phone', '')
    
    # 2. ЖЕСТКАЯ ОЧИСТКА: Удаляем пробелы, скобки, дефисы. Оставляем только цифры и плюс.
    # Это самое важное исправление!
    phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    
    print(f"DEBUG: Попытка входа для {phone} (в базе: {raw_phone})")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Создаем клиент, используя ЧИСТЫЙ номер в имени файла сессии
    client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
    
    async def process():
        try:
            await client.connect()
            
            # Если файл сессии уже был (от старой версии), он подхватится (если имя файла совпадает)
            # Если нет - скрипт попытается авторизоваться заново
            
            if not await client.is_user_authorized():
                try:
                    # Запрашиваем код на ЧИСТЫЙ номер
                    await client.send_code_request(phone)
                    
                    # Спрашиваем код у пользователя
                    code = await loop.run_in_executor(None, ask_code_gui, raw_phone, False)
                    if not code: return
                    
                    try:
                        # Отправляем код
                        await client.sign_in(phone, code)
                    except SessionPasswordNeededError:
                        # Если стоит 2FA (Облачный пароль)
                        pwd = await loop.run_in_executor(None, ask_code_gui, raw_phone, True)
                        await client.sign_in(password=pwd)
                    except PhoneCodeInvalidError:
                        messagebox.showerror("Ошибка", "Неверный код!")
                        return
                        
                except FloodWaitError as e:
                    messagebox.showerror("БАН (FloodWait)", f"Telegram просит подождать {e.seconds} секунд.")
                    return
                except Exception as ex:
                    messagebox.showerror("Ошибка входа", f"Не удалось войти:\n{ex}")
                    return
            
            # Если успешно вошли
            me = await client.get_me()
            
            # Обновляем инфо в базе (используем исходный ключ raw_phone, чтобы не ломать порядок в JSON)
            update_session_info(raw_phone, f"{me.first_name} {me.last_name or ''}", me.username or "")
            
            messagebox.showinfo("Успех", f"Аккаунт {phone} активен!\nUser: @{me.username}")
            
            # Обновляем таблицу интерфейса
            if root: root.after(0, callback_refresh)
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Критический сбой:\n{e}")
        finally:
            if client.is_connected(): await client.disconnect()

    try:
        loop.run_until_complete(process())
    finally:
        loop.close()
        
# Хелпер добавления (упрощенная версия add из старого кода)
def open_add_account_window(on_close_callback):
    d = Toplevel(root)
    d.title("Добавить аккаунт")
    d.geometry("400x550")
    
    try:
        sw = d.winfo_screenwidth()
        sh = d.winfo_screenheight()
        x = (sw - 400) // 2
        y = (sh - 550) // 2
        d.geometry(f"+{x}+{y}")
        d.transient(root)
        d.grab_set()
        d.focus_force()
    except: pass
    
    d.configure(bg="#2E3440")
    
    cf = ttk.Frame(d, padding=20)
    cf.pack(fill="both", expand=True)
    
    ttk.Label(cf, text="Номер телефона:").pack(anchor="w")
    e_ph = ttk.Entry(cf, font=("Consolas", 12))
    e_ph.pack(fill="x", pady=(5, 15))
    e_ph.focus_set()
    
    lbl_st = ttk.Label(cf, text="", foreground="#88C0D0", font=("Segoe UI", 9))
    lbl_st.pack(pady=5)

    lf_api = ttk.LabelFrame(cf, text=" Данные API ", padding=10)
    lf_api.pack(fill="x", pady=10)
    
    ttk.Label(lf_api, text="API ID:").pack(anchor="w")
    e_id = ttk.Entry(lf_api)
    e_id.pack(fill="x", pady=(0,5))
    
    ttk.Label(lf_api, text="API Hash:").pack(anchor="w")
    e_hash = ttk.Entry(lf_api)
    e_hash.pack(fill="x")
    
    # --- ЛОГИКА АВТО-РЕГИСТРАЦИИ ---
    def run_auto():
        phone = e_ph.get().strip()
        if not phone:
            messagebox.showerror("Ошибка", "Сначала введите номер телефона!")
            return
        
        lbl_st.config(text="🚀 Запуск процесса...", foreground="white")
        
        def thread_auto():
            def update_ui(text, color="white", is_error=False):
                try:
                    if d.winfo_exists():
                        lbl_st.config(text=text, foreground=color)
                        if is_error: messagebox.showerror("Ошибка", text)
                except: pass

            try:
                update_ui("⏳ Подключение к my.telegram.org...", "#88C0D0")
                wc = TelegramWebClient()
                
                clean_phone = wc.send_password(phone)
                update_ui("⌨ Дайте цифры из Telegram...", "white")
                
                code = ask_code_gui(clean_phone, False)
                if not code: 
                     update_ui("❌ Ввод кода отменен.", "#BF616A")
                     return

                update_ui("🔐 Входим на сайт...", "#88C0D0")
                wc.login(clean_phone, code)
                
                update_ui("📂 Парсинг API ключей...", "#88C0D0")
                keys = wc.get_app_data()
                
                def finish_success():
                    try:
                        if not d.winfo_exists(): return
                        if keys:
                            e_id.delete(0, tk.END); e_id.insert(0, keys['api_id'])
                            e_hash.delete(0, tk.END); e_hash.insert(0, keys['api_hash'])
                            
                            update_ui("✅ Успешно! Сохраняем...", "#A3BE8C")
                            
                            ss = load_sessions()
                            if any(s.get('phone') == clean_phone for s in ss):
                                 messagebox.showwarning("Дубликат", "Этот номер уже есть в списке!")
                                 return

                            ss.append({
                                "api_id": str(keys['api_id']), 
                                "api_hash": str(keys['api_hash']), 
                                "phone": clean_phone, 
                                "name": "Auto (Нужен вход)", 
                                "username": "",
                                "last_used": time.time() # <--- СОХРАНЯЕМ ВРЕМЯ ДОБАВЛЕНИЯ
                            })
                            save_sessions(ss)
                            
                            if on_close_callback: on_close_callback()
                            messagebox.showinfo("Успех", f"Аккаунт {clean_phone} добавлен!")
                            d.destroy()
                        else:
                            update_ui("❌ Не удалось найти ключи.", "#BF616A", True)
                    except Exception as fin_e: print(f"ERR FINISH: {fin_e}")

                d.after(0, finish_success)

            except Exception as e:
                d.after(0, lambda: update_ui(f"❌ Ошибка: {e}", "#BF616A", True))

        threading.Thread(target=thread_auto, daemon=True).start()

    # --- РУЧНОЕ СОХРАНЕНИЕ ---
    def save_manual():
        phone = e_ph.get().strip()
        aid = e_id.get().strip()
        ahash = e_hash.get().strip()
        
        if not (phone and aid and ahash):
            messagebox.showwarning("!", "Заполните все поля (Номер, ID, Hash)")
            return
        
        ss = load_sessions()
        if any(s.get('phone') == phone for s in ss):
            messagebox.showwarning("!", "Этот номер уже есть в списке!")
            return
        
        ss.append({
            "api_id": aid, 
            "api_hash": ahash, 
            "phone": phone, 
            "name": "Manual New", 
            "username": "",
            "last_used": time.time() # <--- СОХРАНЯЕМ ВРЕМЯ ДОБАВЛЕНИЯ
        })
        save_sessions(ss)
        
        if on_close_callback: on_close_callback()
        d.destroy()

    btn_auto = ttk.Button(cf, text="⚡ Авто-получение (Web)", command=run_auto)
    btn_auto.pack(fill="x", pady=5)
    
    btn_save = ttk.Button(cf, text="💾 Сохранить", command=save_manual, style="Green.TButton")
    btn_save.pack(fill="x", pady=(10,0))


# === ГЛАВНАЯ ВКУЛАДКА (DASHBOARD) ===
def create_dashboard_tab(parent):
    # Разделяем на 3 зоны: Верх (Конфиг), Центр (Списки), Низ (Лог и Старт)
    
    top_frame = ttk.Frame(parent, padding=15)
    top_frame.pack(fill="x")
    
    tf_grid = ttk.LabelFrame(top_frame, text=" 📝 Параметры новой группы ", padding=15)
    tf_grid.pack(fill="x")

    global ent_name, ent_count, ent_user
    
    ttk.Label(tf_grid, text="Название группы:").grid(row=0, column=0, sticky="w", padx=(0,10))
    ent_name = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10))
    ent_name.grid(row=0, column=1, sticky="w")
    
    ttk.Label(tf_grid, text="Количество:").grid(row=0, column=2, sticky="w", padx=(20,10))
    ent_count = ttk.Entry(tf_grid, width=10, font=("Segoe UI", 10))
    ent_count.insert(0, "5")
    ent_count.grid(row=0, column=3, sticky="w")

    ttk.Label(tf_grid, text="Юзернейм дира - если дир не выбран в списке").grid(row=1, column=0, sticky="w", pady=(15,0))
    ent_user = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10))
    ent_user.grid(row=1, column=1, sticky="w", pady=(15,0))
    
    ttk.Label(tf_grid, text="* Оставьте пустым, если выбираете дира ниже", font=("Segoe UI", 8), foreground="#888").grid(row=1, column=2, columnspan=2, sticky="w", pady=(15,0), padx=20)

    # 2. ЦЕНТР - СПИСКИ
    center_frame = ttk.Frame(parent, padding=(15, 0))
    center_frame.pack(fill="both", expand=True)
    
    # Левая часть - Мейкеры
    lf_makers = ttk.LabelFrame(center_frame, text=" 🤖 1. Расходка (Создает группы) ", padding=10)
    lf_makers.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    c_makers = tk.Canvas(lf_makers, bg="#121212", highlightthickness=0)
    sb_makers = ttk.Scrollbar(lf_makers, command=c_makers.yview)
    c_makers.configure(yscrollcommand=sb_makers.set)
    c_makers.pack(side="left", fill="both", expand=True)
    sb_makers.pack(side="right", fill="y")
    
    global sc_fr
    sc_fr = ttk.Frame(c_makers)
    c_makers.create_window((0,0), window=sc_fr, anchor="nw")
    sc_fr.bind("<Configure>", lambda e: c_makers.configure(scrollregion=c_makers.bbox("all")))
    setup_scroll_canvas(c_makers, sc_fr)

    # Правая часть - Гость
    lf_guest = ttk.LabelFrame(center_frame, text=" 👤 2. Дир (Пишет приветствие) ", padding=10)
    lf_guest.pack(side="right", fill="both", expand=True, padx=(5, 0))
    
    # === ПОИСК С ПЛЕЙСХОЛДЕРОМ ===
    f_search_g = ttk.Frame(lf_guest)
    f_search_g.pack(fill="x", pady=(0, 5))
    
    global ent_guest_search
    ent_guest_search = ttk.Entry(f_search_g, font=("Consolas", 10))
    ent_guest_search.pack(fill="x")

    # Логика плейсхолдера
    def on_entry_in(e):
        if ent_guest_search.get() == "поиск":
            ent_guest_search.delete(0, "end")
            ent_guest_search.configure(foreground="white") # Белый при вводе

    def on_entry_out(e):
        if not ent_guest_search.get():
            ent_guest_search.insert(0, "поиск")
            ent_guest_search.configure(foreground="#888") # Серый когда пусто

    # Инициализация
    ent_guest_search.insert(0, "поиск")
    ent_guest_search.configure(foreground="#888")
    ent_guest_search.bind("<FocusIn>", on_entry_in)
    ent_guest_search.bind("<FocusOut>", on_entry_out)
    ent_guest_search.bind("<KeyRelease>", lambda e: refresh_main_checks())
    # ============================

    c_guest = tk.Canvas(lf_guest, bg="#121212", highlightthickness=0)
    sb_guest = ttk.Scrollbar(lf_guest, command=c_guest.yview)
    c_guest.configure(yscrollcommand=sb_guest.set)
    c_guest.pack(side="left", fill="both", expand=True)
    sb_guest.pack(side="right", fill="y")
    
    global guest_group
    guest_group = ttk.Frame(c_guest)
    c_guest.create_window((0,0), window=guest_group, anchor="nw")
    guest_group.bind("<Configure>", lambda e: c_guest.configure(scrollregion=c_guest.bbox("all")))
    setup_scroll_canvas(c_guest, guest_group)

    # 3. НИЗ
    bottom_frame = ttk.Frame(parent, padding=15)
    bottom_frame.pack(fill="both")
    
    lf_greet = ttk.LabelFrame(bottom_frame, text=" 💬 Текст приветствия ", padding=10)
    lf_greet.pack(fill="x", pady=(0, 10))
    
    f_gr_opt = ttk.Frame(lf_greet)
    f_gr_opt.pack(fill="x")
    
    global var_send_greeting, txt_greeting
    var_send_greeting = tk.IntVar(value=1)
    ttk.Checkbutton(f_gr_opt, text="Включить отправку приветствия", variable=var_send_greeting).pack(side="left")
    
    txt_greeting = scrolledtext.ScrolledText(lf_greet, height=3, font=("Consolas", 10), bg="#0F0F0F", fg="#00FF00", insertbackground="#9D00FF", borderwidth=0)
    txt_greeting.pack(fill="x", pady=(5,0))
    txt_greeting.insert("1.0", "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?")

    btn_area = ttk.Frame(bottom_frame)
    btn_area.pack(fill="x", pady=5)
     
    global start_btn, smart_btn
    start_btn = ttk.Button(btn_area, text="🚀 СТАРТ (Обычный)", command=lambda: start_process("standard"), style="Green.TButton")
    start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)

    smart_btn = ttk.Button(btn_area, text="📂 СТАРТ ПО БАЗЕ (Smart)", command=lambda: start_process("smart"), style="Green.TButton")
    smart_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
    
    ttk.Button(btn_area, text="🛑 СТОП", command=stop_process, style="Red.TButton").pack(side="left", padx=(5, 0), fill="x")
    
    lf_log = ttk.LabelFrame(bottom_frame, text=" Лог событий ", padding=5)
    lf_log.pack(fill="x", pady=(10, 0))
    
    global log_widget
    log_widget = scrolledtext.ScrolledText(lf_log, height=8, state='disabled', font=("Consolas", 10), bg="#050505", fg="#CCCCCC", insertbackground="#9D00FF", borderwidth=0)
    log_widget.pack(fill="both", expand=True, padx=2, pady=2)
    
    for t, c in TAG_COLORS.items():
        if t == "ERROR": c = "#FF5555"
        if t == "SUCCESS": c = "#50FA7B"
        if t == "WARN": c = "#FFB86C"
        if t == "WAIT": c = "#8BE9FD"
        if t == "INFO": c = "#F8F8F2"
        if t == "GUEST": c = "#BD93F9"
        if t == "DEBUG": c = "#6272A4"
        log_widget.tag_config(t, foreground=c)


# === ЛОГИКА БОКОВОГО МЕНЮ ===
class SidebarApp:
    def __init__(self, root):
        self.root = root
        self.current_frame = None
        self.frames = {}
        self.buttons = {}
        
        # Настройка сетки: Слева меню (узкое), Справа контент (широкий)
        root.grid_columnconfigure(0, weight=0) # Меню фиксировано
        root.grid_columnconfigure(1, weight=1) # Контент растягивается
        root.grid_rowconfigure(0, weight=1)

        # 1. Боковая панель (Sidebar)
        self.sidebar = tk.Frame(root, bg="#0F0F0F", width=200, padx=0, pady=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False) # Фиксируем ширину
        self.sidebar.configure(width=200)

        # Логотип / Заголовок в меню
        lbl_logo = tk.Label(self.sidebar, text="Dark\nGroup", bg="#0F0F0F", fg="#9D00FF", 
                           font=("Segoe UI Black", 16, "bold"), pady=20)
        lbl_logo.pack(fill="x")

        # 2. Область контента (Content)
        self.content_area = tk.Frame(root, bg="#121212")
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # 3. Инициализация экранов
        # Мы создаем фреймы для каждого раздела, но не показываем их сразу
        self.frames["Главная"] = ttk.Frame(self.content_area)
        self.frames["Accounts"] = ttk.Frame(self.content_area)
        self.frames["Settings"] = ttk.Frame(self.content_area)
        self.frames["Notes"] = ttk.Frame(self.content_area)

        # Наполняем экраны контентом (используем ваши существующие функции!)
        create_dashboard_tab(self.frames["Главная"])
        create_accounts_tab(self.frames["Accounts"])
        create_settings_tab(self.frames["Settings"])
        
        # Логика заметок (чуть сложнее, так как там свой Notebook)
        self._init_notes_screen(self.frames["Notes"])

        # 4. Кнопки меню
        self._add_menu_btn("🏠 Главня", "Главная")
        self._add_menu_btn("👥 Accounts", "Accounts")
        self._add_menu_btn("⚙ Settings", "Settings")
        self._add_menu_btn("📝 Notes", "Notes")

        # Футер в меню
        tk.Label(self.sidebar, text="v24.0 Pro", bg="#0F0F0F", fg="#555", font=("Consolas", 8)).pack(side="bottom", pady=10)

        # Показываем первый экран
        self.show_screen("Главная")

    def _add_menu_btn(self, text, screen_name):
        # Используем tk.Button, так как он позволяет гибко менять цвет фона (activebackground)
        # в отличие от ttk, который требует сложных стилей.
        btn = tk.Button(self.sidebar, text=text, font=("Segoe UI", 11), 
                        bg="#0F0F0F", fg="#888", 
                        activebackground="#1E1E1E", activeforeground="white",
                        bd=0, cursor="hand2", anchor="w", padx=20, pady=12,
                        command=lambda: self.show_screen(screen_name))
        
        btn.pack(fill="x", pady=2)
        self.buttons[screen_name] = btn

    def show_screen(self, screen_name):
        # 1. Скрываем текущий
        if self.current_frame:
            self.current_frame.pack_forget()
        
        # 2. Обновляем кнопки (Подсветка активной)
        for name, btn in self.buttons.items():
            if name == screen_name:
                # Активный стиль: Фиолетовая полоска слева (эмуляция) и светлый текст
                btn.config(bg="#1E1E1E", fg="#9D00FF", font=("Segoe UI", 11, "bold"))
            else:
                # Неактивный стиль
                btn.config(bg="#0F0F0F", fg="#888", font=("Segoe UI", 11))

        # 3. Показываем новый
        frame = self.frames[screen_name]
        frame.pack(fill="both", expand=True)
        self.current_frame = frame

    def _init_notes_screen(self, parent):
        # Внутри экрана заметок создаем локальный Notebook (вкладки заметок)
        note_nb = ttk.Notebook(parent)
        note_nb.pack(fill="both", expand=True, padx=10, pady=10)
        
        saved_notes = load_notes()
        if not saved_notes:
            saved_notes = {"General": ""}
            save_notes_to_file(saved_notes)

        for title, content in saved_notes.items():
            create_note_tab(note_nb, title, content)
        
        fr_plus = ttk.Frame(note_nb)
        note_nb.add(fr_plus, text="  ➕  ")
        note_nb.select(0)
        note_nb.bind("<<NotebookTabChanged>>", on_tab_changed)
def refresh_main_checks():
    # Очистка старых виджетов
    if 'sc_fr' in globals() and sc_fr:
        for w in sc_fr.winfo_children(): w.destroy()
    if 'guest_group' in globals() and guest_group:
        for w in guest_group.winfo_children(): w.destroy()
    
    check_vars.clear()
    
    # Хелпер скролла
    def apply_scroll(widget, parent):
        if hasattr(parent, 'scroll_handlers'):
            bind_func, unbind_func = parent.scroll_handlers
            widget.bind('<Enter>', bind_func)
            widget.bind('<Leave>', unbind_func)

    # --- ЧИТАЕМ ПОИСК ---
    raw_filter = ""
    clean_filter = ""
    
    if 'ent_guest_search' in globals() and ent_guest_search:
        val = ent_guest_search.get().strip()
        # Если в поле слово "поиск" (наш плейсхолдер), считаем, что фильтра нет
        if val.lower() != "поиск":
            raw_filter = val.lower()
            clean_filter = raw_filter.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Радио-кнопка "Без гостя"
    if 'guest_group' in globals() and guest_group:
        if not raw_filter or "без" in raw_filter:
            rb0 = ttk.Radiobutton(guest_group, text="🚫 Без дира / Пропустить шаг", variable=guest_account_index, value=-1)
            rb0.pack(anchor="w", pady=5)
            apply_scroll(rb0, guest_group) 
    
    sessions = load_sessions()
    
    for i, s in enumerate(sessions):
        name = s.get('name', 'Без имени')
        uname = s.get('username', '')
        phone = s.get('phone', '..')
       
        # Левая колонка (Мейкеры)
        if 'sc_fr' in globals() and sc_fr:
            text_maker = f"{phone}  | {name}"
            var = tk.IntVar()
            cb = ttk.Checkbutton(sc_fr, text=text_maker, variable=var)
            cb.pack(anchor="w", padx=5, pady=3)
            apply_scroll(cb, sc_fr) 
            check_vars.append(var)
        
        # Правая колонка (Гости) С УМНЫМ ФИЛЬТРОМ
        if 'guest_group' in globals() and guest_group:
            
            # === ФИЛЬТРАЦИЯ ===
            if raw_filter:
                db_phone_clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").lower()
                
                match_phone = clean_filter in db_phone_clean
                match_name = raw_filter in name.lower()
                match_uname = raw_filter in uname.lower()
                
                if not (match_phone or match_name or match_uname):
                    continue
            # ==================

            display_uname = f"@{uname}" if uname else ""
            radio_text = f"{phone} | {name} | {display_uname}"
            
            rb = ttk.Radiobutton(guest_group, text=radio_text, variable=guest_account_index, value=i)
            rb.pack(anchor="w", pady=3)
            
            apply_scroll(rb, guest_group)

# === ГЛАВНАЯ ФУНКЦИЯ СБОРКИ UI ===
def build_modern_ui():
    global root, guest_account_index
    
    root = tk.Tk()
    root.title("GroupMega")
    root.geometry("1100x700")
    
    # === ИСПРАВЛЕНИЕ: РАЗРЕШАЕМ РАСТЯГИВАНИЕ ===
    root.minsize(900, 600) # Минимальный размер, меньше нельзя
    # Говорим сетке, что колонка 1 (контент) должна растягиваться
    root.grid_columnconfigure(1, weight=1) 
    root.grid_rowconfigure(0, weight=1)
    
    # Инициализация глобальных переменных
    guest_account_index = tk.IntVar(value=-1)

    # Применяем тему
    bg, fg = setup_dark_theme()
    root.configure(bg=bg)
    enable_hotkeys(root)

    # Запускаем приложение с боковым меню
    app = SidebarApp(root)

    refresh_main_checks()

    root.mainloop()

# ЗАПУСК
if __name__ == "__main__":
    build_modern_ui()