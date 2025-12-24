import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel, filedialog
import asyncio
import threading
from telethon import TelegramClient, functions, types, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError, UserAlreadyParticipantError
)
from telethon.tl.functions.contacts import DeleteContactsRequest
# ... твои стандартные импорты ...
import tkinter.simpledialog as simpledialog
import os
import json
import python_socks
import random
import time
import subprocess
import sys
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from tkinter import messagebox, filedialog

import google.generativeai as genai

# Твой список прокси (формат IP:PORT:USER:PASS)
MY_PROXIES = [
    "45.153.55.203:62652:FjRHSGVc:FvHfAH5g",
    "45.159.87.9:63436:FjRHSGVc:FvHfAH5g",
    "45.85.66.168:63004:FjRHSGVc:FvHfAH5g",
    "45.150.60.187:64854:FjRHSGVc:FvHfAH5g",
    "45.154.163.52:62848:FjRHSGVc:FvHfAH5g",
    "45.145.91.21:63586:FjRHSGVc:FvHfAH5g",
    "45.149.129.125:63178:FjRHSGVc:FvHfAH5g",
    "45.140.175.134:64990:FjRHSGVc:FvHfAH5g",
    "45.145.169.230:62402:FjRHSGVc:FvHfAH5g",
    "45.94.20.55:63346:FjRHSGVc:FvHfAH5g",
    "45.150.61.206:64106:FjRHSGVc:FvHfAH5g",
    "45.148.242.11:63626:FjRHSGVc:FvHfAH5g",
    "45.141.197.66:62920:FjRHSGVc:FvHfAH5g",
    "45.147.14.7:62946:FjRHSGVc:FvHfAH5g",
    "45.142.75.36:62912:FjRHSGVc:FvHfAH5g",
    "45.202.127.31:63046:FjRHSGVc:FvHfAH5g",
    "45.196.122.69:62292:FjRHSGVc:FvHfAH5g",
    "45.134.25.178:63232:FjRHSGVc:FvHfAH5g",
    "45.138.213.122:63418:FjRHSGVc:FvHfAH5g",
    "45.93.14.24:64608:FjRHSGVc:FvHfAH5g",
    "45.148.241.55:63534:FjRHSGVc:FvHfAH5g",
    "45.156.151.183:64330:FjRHSGVc:FvHfAH5g",
    "45.153.55.225:62972:FjRHSGVc:FvHfAH5g",
    "45.156.148.49:64032:FjRHSGVc:FvHfAH5g",
    "45.152.226.125:63978:FjRHSGVc:FvHfAH5g",
    "45.154.160.140:62794:FjRHSGVc:FvHfAH5g",
    "45.142.72.234:63614:FjRHSGVc:FvHfAH5g",
    "45.144.37.148:62270:FjRHSGVc:FvHfAH5g",
    "45.147.12.185:62260:FjRHSGVc:FvHfAH5g",
    "45.145.89.149:64298:FjRHSGVc:FvHfAH5g",
    "45.153.224.53:63972:FjRHSGVc:FvHfAH5g",
    "45.142.72.214:64108:FjRHSGVc:FvHfAH5g",
    "45.146.24.4:64682:FjRHSGVc:FvHfAH5g",
    "45.15.238.15:63074:FjRHSGVc:FvHfAH5g",
    "45.150.61.87:63244:FjRHSGVc:FvHfAH5g",
    "45.95.28.45:63852:FjRHSGVc:FvHfAH5g",
    "45.134.25.231:62852:FjRHSGVc:FvHfAH5g",
    "45.140.175.13:64304:FjRHSGVc:FvHfAH5g",
    "45.147.15.121:64730:FjRHSGVc:FvHfAH5g"
]
def get_random_proxy():
    """Берет случайный прокси и возвращает словарь для Telethon"""
    if not MY_PROXIES: return None
    proxy_str = random.choice(MY_PROXIES)
    try:
        # Разбиваем строку
        parts = proxy_str.strip().split(":")
        if len(parts) == 4:
            return {
                'proxy_type': 'http', # Обычно твои прокси (IPv4) это socks5
                'addr': parts[0],
                'port': int(parts[1]),
                'username': parts[2],
                'password': parts[3],
                'rdns': True 
            }
    except Exception as e:
        print(f"Ошибка парсинга прокси: {e}")
    return None

# Настройки маскировки под iPhone
DEVICE_CONFIG = {
    "device_model": "iPhone 15 Pro",
    "system_version": "17.5.1",
    "app_version": "10.4",
    "lang_code": "en",
    "system_lang_code": "en-US"
}
# ==================================================

# ==== конфиги ====
def load_config(filepath="config.json"):
    defaults = {
        "delay_creation": "180", "delay_contact": "20", "delay_cleanup": "10", 
        "random_delay": "1",
        "greeting_text": "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?",
        # Оставляем ключи интерфейса
        "smart_add_director": "1", 
        "smart_add_clients": "1",
        "smart_send_greeting": "1"
    }
    
    # Пытаемся загрузить реальный конфиг и обновить дефолтные значения
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)
            defaults.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass # Если файла нет или он битый, используем defaults
        
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
stop_flag = threading.Event()
root = None
log_widget = None
# === ДОБАВЛЕННЫЕ ПЕРЕМЕННЫЕ ===
e_search = None             # Поле поиска делаем глобальным
current_maker_phone = None  # Номер мейкера
current_director_phone = None # Номер директора

# 🎨 ЦВЕТА ДЛЯ ЛОГОВ (Яркие для темной темы)
TAG_COLORS = {
    "SUCCESS": "#00E676", # Ярко-зеленый
    "ERROR": "#FF5252",   # Ярко-красный
    "INFO": "#FFFFFF",    # Белый (БЫЛ ЧЕРНЫЙ, ИЗ-ЗА ЭТОГО НЕ БЫЛО ВИДНО)
    "WAIT": "#40C4FF",    # Голубой
    "WARN": "#FFAB40",    # Оранжевый
    "GUEST": "#E040FB",   # Фиолетовый
    "DEBUG": "#B0BEC5"    # Светло-серый
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
            # Добавляем метку времени
            time_str = datetime.now().strftime("[%H:%M:%S] ")
            
            # Вставляем время серым цветом (можно отдельный тег, но пусть будет просто текст)
            log_widget.insert(tk.END, time_str, "DEBUG") 
            # Вставляем само сообщение
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
        if root: root.after(0, lambda: refresh_dashboard_tree()())

# 1. КЛАСС ОКНА С ЧЕКБОКСАМИ
class MatchReviewWindow(Toplevel):
    def __init__(self, parent, matches_list, default_group_name="Group"):
        super().__init__(parent)
        self.matches = matches_list
        self.result = None
        
        self.title(f"Найдено в Telegram: {len(matches_list)} чел.")
        self.geometry("1100x600")
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set()

        # Верхняя панель
        top_f = tk.Frame(self, bg="#121212", pady=15)
        top_f.pack(fill="x", padx=10)
        
        tk.Label(top_f, text=f"База: {default_group_name}", bg="#121212", fg="#00E676", font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)

        # Таблица
        cols = ("fio_file", "name_tg", "phone", "username")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("fio_file", text="ФИО (из Файла)")
        self.tree.heading("name_tg", text="Имя (в Telegram - Реальное)")
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("username", text="Username")
        
        self.tree.column("fio_file", width=250)
        self.tree.column("name_tg", width=200) 
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("username", width=120)

        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        for i, item in enumerate(self.matches):
            # 1. Данные из файла
            fio_from_file = item['target_fio']
            
            # 2. Данные из Телеграм (реальный объект User)
            u = item['user']
            
            # Склеиваем имя и фамилию
            real_first = u.first_name if u.first_name else ""
            real_last = u.last_name if u.last_name else ""
            tg_name = f"{real_first} {real_last}".strip()
            
            if not tg_name: tg_name = "Без имени"

            uname = f"@{u.username}" if u.username else "-"
            
            # Вставляем строку
            self.tree.insert("", "end", iid=str(i), values=(fio_from_file, tg_name, item['phone'], uname))
        
        # Выбрать все
        self.tree.selection_set(self.tree.get_children())

        # Кнопка ЗАПУСК
        btn_f = tk.Frame(self, bg="#121212", pady=15)
        btn_f.pack(fill="x")
        tk.Button(btn_f, text="🚀 ЗАПУСТИТЬ В РАБОТУ", command=self.confirm, bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), padx=20).pack(side="right", padx=20)

    def confirm(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("!", "Выберите контакты!")
            return
        
        # Возвращаем список словарей данных для тех, кого выбрали
        data = [self.matches[int(iid)] for iid in sel]
        self.result = data
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

async def set_guest_phone_privacy(client):
    """Устанавливает видимость номера телефона: Мои Контакты."""
    try:
        # types.InputPrivacyValueAllowContacts() - это правило, которое дает контактам видеть номер.
        # Это соответствует настройке "Кто видит мой номер телефона" -> "Мои контакты".
        rules = [types.InputPrivacyValueAllowContacts()] 
        await client(functions.account.SetPrivacyRequest(key=types.InputPrivacyKeyPhoneNumber(), rules=rules))
    except Exception as e: 
        print(f"Ошибка установки приватности Гостя: {e}")

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
                client = TelegramClient(
                    f"session_{phone}", 
                    int(s['api_id']), 
                    s['api_hash'], 
                    loop=loop,
                    proxy=get_random_proxy(),
                    **DEVICE_CONFIG
                )
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
        if root: root.after(0, lambda: refresh_dashboard_tree()())
    threading.Thread(target=_runner, daemon=True).start()

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
                client = TelegramClient(
                    f"session_{phone}", 
                    int(s['api_id']), 
                    s['api_hash'], 
                    loop=loop,
                    proxy=get_random_proxy(),
                    **DEVICE_CONFIG
                )
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
        if root: root.after(0, lambda: refresh_dashboard_tree()())

    threading.Thread(target=_runner, daemon=True).start()

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
                client = TelegramClient(
                    f"session_{phone}", 
                    int(s['api_id']), 
                    s['api_hash'], 
                    loop=loop,
                    proxy=get_random_proxy(),
                    **DEVICE_CONFIG
                )
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
        if root: root.after(0, lambda: refresh_dashboard_tree()())
    threading.Thread(target=_runner, daemon=True).start()


def parse_target_file(file_content):
    """
    Парсер: ищет кандидатов, телефоны и ДАТУ РОЖДЕНИЯ.
    Формат: ФИО ДД.ММ.ГГГГ
    """
    data = {"company_name": "Unknown_Company", "director_name": None, "candidates": [], "original_header": ""}

    # 1. Разделение на шапку и кандидатов (по длинной черте)
    parts = re.split(r'\+?={10,}', file_content)

    if len(parts) > 1:
        header_content = parts[0]
        candidates_content = "\n".join(parts[1:])
    else:
        header_content = file_content
        candidates_content = ""

    data["original_header"] = header_content.strip()

    # --- ПАРСИНГ ШАПКИ (Компания) ---
    header_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', header_content)
    if header_match: 
        data["company_name"] = header_match.group(1).strip()
    else:
        fallback_match = re.search(r'["«“]([^"»”]+)["»”]', header_content)
        if fallback_match:
            data["company_name"] = fallback_match.group(1).strip()

    # --- ПАРСИНГ КАНДИДАТОВ ---
    if candidates_content:
        # Разбиваем по разделителям (-----)
        candidate_sections = re.split(r'-{5,}', candidates_content)
        
        for sec in candidate_sections:
            if not sec.strip(): continue
            
            phones = []
            # Ищем телефоны
            for line in sec.split('\n'):
                cl = re.sub(r'\D', '', line)
                # Фильтр: длина 10-11 и не похоже на год (19.. 20..)
                if (len(cl)==10 or len(cl)==11) and not cl.startswith('19') and not cl.startswith('20'):
                    phones.append(cl)
            
            if phones:
                name = "Unknown"
                dob = "" 
                
                # === ГЛАВНОЕ: Ищем ФИО + Дату ===
                # Ищет: Начало строки -> Буквы/Пробелы -> Пробел -> Дата (ДД.ММ.ГГГГ)
                nm = re.search(r'^([А-ЯЁ\s-]+)\s+(\d{2}\.\d{2}\.\d{4})', sec.strip(), re.MULTILINE)
                
                if nm: 
                    name = nm.group(1).strip() # ФИО
                    dob = nm.group(2).strip()  # ДАТА
                else:
                    # Если даты нет, ищем просто ФИО (2 и более слова заглавными)
                    nm2 = re.search(r'^([А-ЯЁ]{2,}\s+[А-ЯЁ]{2,}(?:\s+[А-ЯЁ]{2,})?)', sec.strip(), re.MULTILINE)
                    if nm2: name = nm2.group(1).strip()
                
                data["candidates"].append({"full_name": name, "dob": dob, "phones": phones})

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
# === ЛОГИКА УДАЛЕНИЯ КОНТАКТОВ ===
# ==========================================
async def delete_contacts_logic(session_data):
    phone = session_data['phone'].replace(" ", "").replace("-", "")
    api_id = int(session_data['api_id'])
    api_hash = session_data['api_hash']
    
    client = TelegramClient(
        f"session_{phone}", 
        api_id, 
        api_hash,
        proxy=get_random_proxy(),
        **DEVICE_CONFIG
    )
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return "AuthError"
            
        contacts = await client(functions.contacts.GetContactsRequest(hash=0))
        if not contacts.users:
            return "Empty"
            
        # Собираем ID для удаления
        ids = [u.id for u in contacts.users]
        await client(functions.contacts.DeleteContactsRequest(id=ids))
        
        return "Success"
    except Exception as e:
        return str(e)
    finally:
        if client.is_connected(): await client.disconnect()

def run_delete_contacts_thread(session_data):
    # Запрос подтверждения
    ph = session_data.get('phone')
    if not messagebox.askyesno("Очистка контактов", f"Вы уверены, что хотите удалить ВСЕ контакты на аккаунте {ph}?"):
        return

    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(delete_contacts_logic(session_data))
        loop.close()
        
        if res == "Success":
            messagebox.showinfo("Готово", f"Контакты на {ph} успешно удалены!")
        elif res == "Empty":
            messagebox.showinfo("Инфо", f"Контактов на {ph} нет.")
        elif res == "AuthError":
            messagebox.showerror("Ошибка", f"Аккаунт {ph} не авторизован.")
        else:
            messagebox.showerror("Ошибка", f"Сбой: {res}")

    threading.Thread(target=_thread, daemon=True).start()

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
    client = TelegramClient(
        f"session_{phone}", 
        int(s_data['api_id']), 
        s_data['api_hash'], 
        loop=loop,
        proxy=get_random_proxy(),
        **DEVICE_CONFIG
    )
    
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

async def add_and_clean_strict(client, chat_entity, user):
    """Добавляет контакт и ПОЛНОСТЬЮ чистит историю (Логика из ИИ)."""
    try:
        # Получаем имя для лога
        u_name = f"User {user.user_id}" if hasattr(user, 'user_id') else "Contact"
        if hasattr(user, 'first_name'): u_name = user.first_name

        log_msg("INFO", f"   👤 Инвайт контакта: {u_name}...")
        
        try:
            input_user = await client.get_input_entity(user)
        except:
            input_user = user # Если уже InputUser

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
    except UserAlreadyParticipantError: # Нужно добавить импорт этой ошибки в начале файла!
        log_msg("INFO", "   ℹ️ Уже в группе.")
        return True
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Ошибка инвайта: {e}")
        return False

async def safe_add_guest(client, chat_entity, user_entity, username_str=None):
    """Добавление гостя (Логика из ИИ)."""
    try:
        target_name = username_str if username_str else getattr(user_entity, 'username', 'Guest')
        log_msg("INFO", f"   👤 Добавляем Гостя (@{target_name})...")
        
        input_user = None
        # Сначала пробуем найти "свежий" InputEntity по строке юзернейма
        if username_str:
            try:
                input_user = await client.get_input_entity(username_str)
            except: pass

        if not input_user and user_entity:
            try:
                input_user = await client.get_input_entity(user_entity)
            except: pass

        if not input_user:
            log_msg("ERROR", f"   ❌ Не удалось найти @{target_name} (нет access_hash).")
            return False

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
    

async def process_smart_target_file(maker_client, guest_client, file_path, guest_session_dict=None, pre_approved_data=None, pre_group_name=None):
    try:
        parsed_data = {"candidates": []}
        original_company_name = "Unknown"
        
        if not pre_approved_data:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            raw_parsed = parse_target_file(content)
            if isinstance(raw_parsed, dict):
                parsed_data['candidates'] = raw_parsed.get('candidates', [])
                original_company_name = raw_parsed.get('company_name', 'Group')
            else:
                parsed_data['candidates'] = raw_parsed
        else:
            parsed_data['candidates'] = pre_approved_data
            original_company_name = pre_group_name or "Group"

        candidates_list = parsed_data['candidates']
        log_msg("INFO", f"🔍 Найдено {len(candidates_list)} записей. Проверяем...")

        batch_list = []
        tracking_map = {} 

        for cand in candidates_list:
            phones = cand.get('phones', [])
            fio_file = cand.get('full_name', cand.get('target_fio', cand.get('fio', 'Unknown')))
            # === ДОБАВЛЕНО: Берем дату рождения ===
            dob_file = cand.get('dob', '') 
            
            for raw_phone in phones:
                d = re.sub(r'\D', '', raw_phone)
                if not d: continue
                if len(d) == 11 and d.startswith('8'): ph = "+7" + d[1:]
                elif len(d) == 11 and d.startswith('7'): ph = "+" + d
                elif len(d) == 10 and d.startswith('9'): ph = "+7" + d
                else: ph = "+" + d
                
                my_client_id = random.randint(100000000, 999999999)
                # === ДОБАВЛЕНО: Сохраняем dob в tracking_map ===
                tracking_map[my_client_id] = {
                    'fio_file': fio_file, 
                    'phone_clean': ph,
                    'dob': dob_file 
                }
                
                batch_list.append(types.InputPhoneContact(
                    client_id=my_client_id, phone=ph, first_name=fio_file[:15], last_name=""
                ))

        found_matches = []
        
        # Пачками по 10
        for i in range(0, len(batch_list), 10):
            chunk = batch_list[i : i + 10]
            try:
                # 1. Импорт
                res = await maker_client(functions.contacts.ImportContactsRequest(contacts=chunk))
                
                ids_to_del = []
                users_to_refetch = []
                tg_map = {imp.user_id: imp.client_id for imp in res.imported}
                
                for u in res.users:
                    if u.id in tg_map:
                        ids_to_del.append(u.id)
                        users_to_refetch.append(types.InputUser(user_id=u.id, access_hash=u.access_hash))

                # 2. УДАЛЕНИЕ
                if ids_to_del:
                    await maker_client(functions.contacts.DeleteContactsRequest(id=ids_to_del))
                
                # 3. ЖДЕМ
                await asyncio.sleep(2.0) 
                
                # 4. ЗАПРОС РЕАЛЬНЫХ ДАННЫХ
                if users_to_refetch:
                    try:
                        real_users = await maker_client(functions.users.GetUsersRequest(id=users_to_refetch))
                    except:
                        real_users = res.users

                    for u in real_users:
                        c_id = tg_map.get(u.id)
                        orig = tracking_map.get(c_id)
                        if orig:
                            # === ДОБАВЛЕНО: Передаем dob в результат ===
                            found_matches.append({
                                'target_fio': orig['fio_file'], 
                                'phone': orig['phone_clean'],
                                'dob': orig.get('dob', ''),
                                'user': u 
                            })

            except Exception as e:
                log_msg("ERROR", f"Ошибка пробива: {e}")

        if not found_matches:
            log_msg("WARN", "⚠️ Никто не найден.")
            return [], None, None

        future_gui = asyncio.get_running_loop().create_future()
        def show_gui():
            win = MatchReviewWindow(root, found_matches, original_company_name)
            root.wait_window(win)
            if win.result is not None: future_gui.set_result(win.result)
            else: future_gui.set_result([])
        root.after(0, show_gui)
        
        selected_matches = await future_gui
        if not selected_matches: return [], None, None

        future_name = asyncio.get_running_loop().create_future()
        def ask_name():
            res = simpledialog.askstring("Название", "Введите имя для групп:", initialvalue=original_company_name, parent=root)
            future_name.set_result(res)
        root.after(0, ask_name)
        final_name = await future_name or original_company_name

        tasks = []
        for item in selected_matches:
            tasks.append({
                'name': final_name,
                'user': item['user'],
                'phone': item['phone']
            })

        return tasks, final_name, selected_matches

    except Exception as e:
        log_msg("ERROR", f"Critical Smart Error: {e}")
        return [], None, None

async def setup_privacy_security(client, phone_label):
    """
    1. Кто видит мой номер -> Только контакты (InputPrivacyValueAllowContacts)
    2. Кто может найти по номеру -> Все (InputPrivacyValueAllowAll)
    """
    try:
        # Настройка 1: Кто видит мой номер телефона -> Мои контакты
        await client(functions.account.SetPrivacyRequest(
            key=types.InputPrivacyKeyPhoneNumber(),
            rules=[types.InputPrivacyValueAllowContacts()]
        ))
        
        # Настройка 2: Кто может найти меня по номеру -> Все
        # ЭТО САМОЕ ВАЖНОЕ ИСПРАВЛЕНИЕ, ЧТОБЫ МЕЙКЕР НАШЕЛ ГОСТЯ
        await client(functions.account.SetPrivacyRequest(
            key=types.InputPrivacyKeyAddedByPhone(),
            rules=[types.InputPrivacyValueAllowAll()]
        ))
        
        log_msg("INFO", f"   🛡 {phone_label}: Приватность настроена (Номер: Контакты, Поиск: Все).")
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Не удалось настроить приватность для {phone_label}: {e}")

### Полностью исправленный `worker_task` (замени весь блок этой функции на приведённый код)
async def worker_task(session, delays, guest_session=None, targets_list=None, manual_names=None, target_username_manual=None):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    # Режим работы с контактами (0 = Сразу, 1 = После)
    mode_after = delays.get('contact_mode', 0)
    
    client = TelegramClient(
        f"session_{phone.replace(' ','')}", 
        api_id, 
        api_hash,
        proxy=get_random_proxy(),
        **DEVICE_CONFIG
    )
        
    created_chat_ids = []
    pending_contacts = [] 
    my_id = None

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! (Пропуск)")
            return {'maker_id': None, 'chats': []}

        me = await client.get_me()
        my_id = me.id
        log_msg("INFO", f"🚀 {phone}: Начал работу.")

        # === ЛОГИКА ДИРЕКТОРА: ДОБАВЛЕНИЕ ПО НОМЕРУ (ПОЛУЧЕНИЕ ID) ===
        director_entity = None
        
        if guest_session:
            raw_dir_phone = guest_session.get('phone', '')
            
            # 1. Жесткая очистка и форматирование номера
            # Убираем все нецифровые символы
            clean_digits = re.sub(r'\D', '', raw_dir_phone)
            
            final_dir_phone = ""
            if len(clean_digits) == 11:
                if clean_digits.startswith('8'):
                    final_dir_phone = "+7" + clean_digits[1:]
                elif clean_digits.startswith('7'):
                    final_dir_phone = "+" + clean_digits
            elif len(clean_digits) == 10 and clean_digits.startswith('9'):
                final_dir_phone = "+7" + clean_digits
            else:
                # Если формат нестандартный, пробуем добавить +
                final_dir_phone = "+" + clean_digits

            if final_dir_phone and len(final_dir_phone) > 5:
                try:
                    # 2. Добавляем Директора в контакты, чтобы получить его ID (Entity)
                    log_msg("INFO", f"   📞 {phone}: Добавляю Директора в контакты ({final_dir_phone})...")
                    
                    contact_input = types.InputPhoneContact(
                        client_id=random.randint(1000,99999),
                        phone=final_dir_phone,
                        first_name="Director",
                        last_name=""
                    )
                    
                    result = await client(functions.contacts.ImportContactsRequest(contacts=[contact_input]))
                    
                    # Проверяем, удалось ли найти пользователя
                    if result.users:
                        director_entity = result.users[0] # ЭТО И ЕСТЬ НАШ ОБЪЕКТ С ID
                        d_name = f"{director_entity.first_name} {director_entity.last_name or ''}"
                        log_msg("SUCCESS", f"   👑 {phone}: Директор найден! ID: {director_entity.id} ({d_name})")
                    else:
                        log_msg("WARN", f"   ⚠️ {phone}: Telegram не нашел номер {final_dir_phone}.")
                
                except Exception as e_dir:
                    log_msg("ERROR", f"   ❌ {phone}: Ошибка добавления Директора: {e_dir}")
            else:
                log_msg("WARN", f"   ⚠️ {phone}: Некорректный номер директора: {raw_dir_phone}")

        # ================================================================

        # Подготовка задач
        tasks = []
        if targets_list:
            tasks = targets_list
        elif manual_names:
            tasks = [{'name': n, 'user': None} for n in manual_names]

        # === ЭТАП 1: СОЗДАНИЕ ГРУПП ===
        for i, task in enumerate(tasks):
            if stop_flag.is_set(): break
            
            group_name = task.get('name', 'Group')
            target_user_obj = task.get('user') 
            
            log_msg("INFO", f"🛠 ({i+1}/{len(tasks)}) {phone}: Создаю '{group_name}'...")

            try:
                # А. Список участников для создания (СРАЗУ ВКЛЮЧАЕМ ДИРЕКТОРА ПО ID)
                users_init = []
                
                if director_entity:
                    # Telethon сам преобразует объект User в InputUser
                    users_init.append(director_entity)
                
                # Создаем группу
                # ВАЖНО: Если директора нет, создаст пустую (только мейкер)
                res = await client(functions.messages.CreateChatRequest(users=users_init, title=group_name))
                
                # Получаем объект чата
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                chat_entity = await client.get_entity(chat.id)
                created_chat_ids.append(chat.id)
                
                # Б. Проверка, добавился ли директор (для лога)
                if director_entity:
                    log_msg("INFO", "   ✅ Директор добавлен при создании.")

                # В. ОБРАБОТКА КЛИЕНТА (ЖЕРТВЫ)
                if target_user_obj:
                    if mode_after == 1:
                        # РЕЖИМ "ПОСЛЕ"
                        pending_contacts.append({'chat': chat_entity, 'user': target_user_obj})
                        log_msg("INFO", f"   ⏳ Клиент отложен (режим 'После').")
                    else:
                        # РЕЖИМ "СРАЗУ"
                        await asyncio.sleep(2)
                        await add_and_clean_strict(client, chat_entity, target_user_obj)
                
                # Г. Пауза
                if i < len(tasks) - 1:
                    await smart_sleep(delays['creation'], delays['random'])

            except PeerFloodError:
                log_msg("ERROR", f"⛔ {phone}: ФЛУД! Стоп.")
                break
            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log_msg("ERROR", f"❌ Ошибка цикла: {e}")

        # === ЭТАП 2: ДОБАВЛЕНИЕ КЛИЕНТОВ (РЕЖИМ "ПОСЛЕ") ===
        if mode_after == 1 and pending_contacts and not stop_flag.is_set():
            log_msg("INFO", f"📥 {phone}: Начинаем добавление отложенных клиентов ({len(pending_contacts)} шт)...")
            
            for item in pending_contacts:
                if stop_flag.is_set(): break
                chat_ent = item['chat']
                user_obj = item['user']
                
                try:
                    await add_and_clean_strict(client, chat_ent, user_obj)
                    await smart_sleep(delays['delay_contact'], delays['random'])
                except Exception as e:
                    log_msg("WARN", f"Ошибка отложенного инвайта: {e}")

        return {'maker_id': my_id, 'chats': created_chat_ids}

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка Maker: {e}")
        return {'maker_id': None, 'chats': []}
    finally:
        if client.is_connected(): await client.disconnect()

# ==== ЛОГИКА ГОСТЯ ======

async def guest_execution_final(session, target_group_ids, greeting_text):
    if not target_group_ids:
        log_msg("WARN", "⚠️ Нет новых групп для приветствия.")
        return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(
        f"session_{phone.replace(' ','')}", 
        api_id, 
        api_hash,
        proxy=get_random_proxy(),
        **DEVICE_CONFIG
    )
    
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

# === ОБНОВЛЕННЫЙ ЗАПУСК ПОТОКОВ ===
def run_thread_adapted(main_sessions, guest_session, tasks_per_session, delays, target_username_manual, greeting_text, need_greet):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 1. ЗАПУСК МЕЙКЕРОВ
    maker_tasks = []
    
    for i, session in enumerate(main_sessions):
        if i < len(tasks_per_session):
            chunk = tasks_per_session[i]
            
            t_list = None
            m_names = None
            
            # Определяем, это список словарей (Smart) или строк (Manual)
            if chunk and isinstance(chunk[0], dict):
                t_list = chunk
            else:
                m_names = chunk

            maker_tasks.append(worker_task(
                session, delays, guest_session, 
                targets_list=t_list, 
                manual_names=m_names,
                target_username_manual=target_username_manual
            ))

    try:
        if maker_tasks:
            log_msg("INFO", "=== ЗАПУСК МЕЙКЕРОВ ===")
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            all_created_groups = []
            for res in results:
                if res and res.get('chats'):
                    all_created_groups.extend(res['chats'])
            
            log_msg("INFO", f"📊 МЕЙКЕРЫ ГОТОВЫ. Групп: {len(all_created_groups)}")

            # 2. ЗАПУСК ГОСТЯ (ПРИВЕТСТВИЕ)
            if guest_session and need_greet and not stop_flag.is_set() and all_created_groups:
                log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ (Приветствие) ===")
                log_msg("WAIT", "⏳ Ждем 3 сек...")
                time.sleep(3)
                loop.run_until_complete(guest_execution_final(guest_session, all_created_groups, greeting_text))
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка: {e}")
    finally:
        loop.close()
        restore_buttons()


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
def save_checked_report(original_file_path, selected_data, group_name):
    try:
        # 1. Читаем исходный файл
        header_text = ""
        with open(original_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            parts = re.split(r'={10,}', content)
            if parts:
                header_text = parts[0].strip()
            else:
                header_text = content.strip()

        # 2. Локальный импорт времени (чтобы не было конфликтов)
        import datetime as dt_safe
        current_time = dt_safe.datetime.now().strftime('%Y-%m-%d %H:%M')

        # 3. Формируем текст
        lines = []
        lines.append(header_text)
        lines.append("\n\n" + "="*30)
        lines.append("="*30)
        lines.append(f"ОТЧЕТ: {group_name}")
        lines.append(f"Дата: {current_time}")
        lines.append("="*30 + "\n")

        for item in selected_data:
            fio = item.get('target_fio', 'Unknown')
            phone = item.get('phone', 'Unknown')
            # === ДОБАВЛЕНО: Достаем дату рождения ===
            dob = item.get('dob', '')
            
            user_obj = item.get('user')
            tg_first = user_obj.first_name if user_obj and user_obj.first_name else ""
            tg_last = user_obj.last_name if user_obj and user_obj.last_name else ""
            tg_name = f"{tg_first} {tg_last}".strip()
            if not tg_name: tg_name = "Без имени"

            lines.append(f"фио: {fio}")
            # === ДОБАВЛЕНО: Пишем дату, если она есть ===
            if dob: lines.append(f"дата рождения: {dob}")
            lines.append(f"номер: {phone}")
            lines.append(f"как подписан в тг: {tg_name}")
            lines.append("-" * 20)

        # 4. Сохраняем
        folder = "прописанные базы"
        if not os.path.exists(folder): os.makedirs(folder)
        
        safe_name = re.sub(r'[\\/*?:"<>|]', "", group_name).strip()
        if not safe_name: safe_name = "Report"
        
        new_filename = f"{safe_name}.txt"
        save_path = os.path.join(folder, new_filename)

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
            
        log_msg("SUCCESS", f"💾 Отчет сохранен: {new_filename}")

    except Exception as e:
        log_msg("ERROR", f"Ошибка сохранения отчета: {e}")

# Найдите функцию start_process и замените её полностью:
def start_process(mode="smart"):
    try:
        # =========================================================================
        # 1. СБОР ДАННЫХ (ИСПРАВЛЕНО: БЕРЕМ ИЗ ПАМЯТИ, А НЕ ИЗ ТАБЛИЦЫ)
        # =========================================================================
        
        # Используем глобальные переменные, куда мы сохраняли выбор галочками
        global current_maker_phone, current_director_phone
        
        sessions_data = load_sessions()
        
        maker_indices = []
        guest_index = -1
        
        # Проходим по всем сессиям и ищем совпадения с выбранными номерами
        for idx, s in enumerate(sessions_data):
            # Чистим телефон из базы для корректного сравнения
            s_phone = s.get('phone', '').replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
            # Если это выбранный Мейкер
            if current_maker_phone and s_phone == current_maker_phone:
                maker_indices.append(idx)
            
            # Если это выбранный Директор
            if current_director_phone and s_phone == current_director_phone:
                guest_index = idx

        # Проверка
        if not maker_indices:
            messagebox.showwarning("!", "Не выбран Мейкер (галочка ☑)!")
            return

        # 2. Файл базы
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not file_path: return 

        # Подготовка интерфейса
        stop_flag.clear()
        log_widget.config(state='normal')
        log_widget.delete("1.0", tk.END)
        log_widget.config(state='disabled')

        # Формируем списки сессий
        main_sessions = [sessions_data[i] for i in maker_indices]
        guest_session = None
        if guest_index != -1:
            guest_session = sessions_data[guest_index]
            # Если Директор случайно попал в мейкеры - убираем его из мейкеров
            if guest_session in main_sessions:
                main_sessions.remove(guest_session)

        # 3. Конфиг и Настройки
        cfg = load_config()
        
        # Получаем текст приветствия
        greeting_text = ""
        if 'txt_greeting' in globals() and txt_greeting:
            greeting_text = txt_greeting.get("1.0", tk.END).strip()
            
        # Считываем галочку отправки
        need_greet = 1
        if 'var_send_greeting' in globals() and var_send_greeting:
            need_greet = var_send_greeting.get()

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "random": int(cfg.get("random_delay", 1)),
            "smart_add_director": 1, 
            "smart_add_clients": 1,
            "contact_mode": int(cfg.get("contact_mode", 0)) 
        }

        if 'smart_btn' in globals(): smart_btn.config(state='disabled')
        
        # 4. Поток выполнения
        def thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Берем первого мейкера как "Лидера" для парсинга базы
            leader_s = main_sessions[0]
            leader_client = TelegramClient(
                f"session_{leader_s['phone'].replace(' ','')}", 
                int(leader_s['api_id']), 
                leader_s['api_hash'], 
                loop=loop,
                proxy=get_random_proxy(),
                **DEVICE_CONFIG
            )
            
            async def run_leader():
                try:
                    # ====================================================
                    # ЗАЩИТА ОТ БЛОКИРОВКИ БАЗЫ (Retry Loop)
                    # ====================================================
                    import sqlite3
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            await leader_client.connect()
                            break # Если успех - выходим из цикла
                        except sqlite3.OperationalError as e:
                            # Если база занята - ждем и пробуем снова
                            if "database is locked" in str(e) and attempt < max_retries - 1:
                                log_msg("WARN", f"⚠️ База занята, жду 2 сек... ({attempt+1}/{max_retries})")
                                await asyncio.sleep(2)
                            else:
                                raise e # Если попытки кончились - ошибка
                    # ====================================================

                    if not await leader_client.is_user_authorized():
                        log_msg("ERROR", f"Лидер {leader_s['phone']} не авторизован!")
                        return None, None, None
                    
                    return await process_smart_target_file(leader_client, None, file_path)
                finally:
                    if leader_client.is_connected(): await leader_client.disconnect()
            
            # Запуск лидера
            tasks_list, group_name, raw_data = loop.run_until_complete(run_leader())
            
            if not tasks_list:
                log_msg("WARN", "Список задач пуст.")
                loop.close()
                restore_buttons()
                return

            if raw_data:
                save_checked_report(file_path, raw_data, group_name)

            # Распределение задач и запуск воркеров
            num_makers = len(main_sessions)
            if num_makers > 0:
                chunk_size = (len(tasks_list) + num_makers - 1) // num_makers
                chunks = [tasks_list[i:i + chunk_size] for i in range(0, len(tasks_list), chunk_size)]
                
                loop.close()
                # Передаем need_greet в функцию запуска
                run_thread_adapted(main_sessions, guest_session, chunks, delays, None, greeting_text, need_greet)
            else:
                log_msg("ERROR", "Нет активных мейкеров!")
                restore_buttons()

        threading.Thread(target=thread_target, daemon=True).start()
            
    except Exception as e:
        messagebox.showerror("Ошибка запуска", str(e))
        restore_buttons()

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

def on_tab_changed(event):
    nb = event.widget
    try:
        total_tabs = nb.index("end")
        if total_tabs == 0: return

        current_tab_index = nb.index("current")
        plus_tab_index = total_tabs - 1
        
        # Если нажали на "ПЛЮС" (последняя вкладка)
        if current_tab_index == plus_tab_index:
            # Уходим с плюса на соседнюю вкладку, чтобы не видеть пустой экран
            if total_tabs > 1: nb.select(0)
            
            def ask_name():
                new_title = simpledialog.askstring("Новая заметка", "Название вкладки:", parent=root)
                if not new_title or not new_title.strip(): return
                
                clean_title = new_title.strip()
                notes = load_notes()
                if clean_title in notes:
                    messagebox.showwarning("Ошибка", "Такое имя уже есть!", parent=root)
                    return

                # Создаем новую вкладку используя нашу красивую функцию
                create_note_tab(nb, clean_title, "")
                
                # Сохраняем пустую запись
                notes[clean_title] = ""
                save_notes_to_file(notes)

                # Перемещаем новую вкладку ПЕРЕД плюсом
                # (create_note_tab добавляет в конец, а плюс у нас тоже в конце)
                # Логика: 
                # 1. Мы добавили вкладку, она стала последней (индекс N).
                # 2. Плюс был на индексе N-1.
                # 3. Нам надо, чтобы Плюс всегда был в конце.
                
                # Проще всего: удалить плюс и добавить снова в конец
                # Но Tkinter позволяет менять порядок через insert, однако add проще.
                
                # Хак для сохранения порядка:
                # В данной реализации create_note_tab добавляет в конец.
                # Поэтому мы должны удалить "Плюс" и добавить его заново.
                
                tabs_count = nb.index("end")
                plus_frame = nb.nametowidget(nb.tabs()[plus_tab_index]) # Старый плюс
                
                # Находим фрейм, который мы только что создали (он последний)
                new_frame_name = nb.tabs()[tabs_count-1]
                new_frame = nb.nametowidget(new_frame_name)
                
                # Перемещаем новую вкладку на место плюса
                nb.insert(plus_tab_index, new_frame, text=clean_title)
                
                # Переключаемся на неё
                nb.select(plus_tab_index)
            
            root.after(100, ask_name)

    except Exception as e:
        print(f"Tab Error: {e}")
        
def stop_process():
    stop_flag.set()
    log_msg("ERROR", "🛑 === НАЖАТ СТОП! ЭКСТРЕННАЯ ОСТАНОВКА === 🛑")
    log_msg("WARN", "⏳ Завершаем текущие сетевые запросы...")
    
    if root: 
        def force_buttons():
            # Проверяем только существующие кнопки
            if 'smart_btn' in globals() and smart_btn and smart_btn.winfo_exists(): 
                smart_btn.config(state='normal')
            if 'start_btn' in globals() and start_btn and start_btn.winfo_exists(): 
                start_btn.config(state='normal')
            
        root.after(1000, force_buttons)

def restore_buttons():
    try:
        if root:
            if 'start_btn' in globals() and start_btn: 
                start_btn.config(state='normal')
            if 'smart_btn' in globals() and smart_btn: 
                smart_btn.config(state='normal')
    except: pass

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
tree_dashboard = None

def setup_dark_theme():
    style = ttk.Style()
    style.theme_use('clam')
    
    bg_main = "#121212"
    bg_sidebar = "#0F0F0F" 
    bg_input = "#1E1E1E"
    fg_text = "#E0E0E0"
    accent = "#9D00FF"
    
    # 1. Основные элементы
    style.configure(".", background=bg_main, foreground=fg_text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg_main)
    style.configure("Sidebar.TFrame", background=bg_sidebar)
    style.configure("TLabel", background=bg_main, foreground=fg_text)
    
    # 2. Таблицы (Treeview)
    style.configure("Treeview", 
                    background=bg_input, 
                    fieldbackground=bg_input, 
                    foreground="white", 
                    borderwidth=0, 
                    rowheight=30,
                    font=("Segoe UI", 10))
    
    style.configure("Treeview.Heading", 
                    background="#252525", 
                    foreground="#9D00FF", 
                    borderwidth=0, 
                    font=("Segoe UI", 9, "bold"))
    
    # === ВОТ ЗДЕСЬ ИСПРАВЛЕНИЕ ===
    # Делаем выделение ЯРКИМ (фиолетовым), чтобы его было видно
    style.map("Treeview", 
              background=[('selected', '#9D00FF')],  # Яркий фиолетовый при выборе
              foreground=[('selected', 'white')])
    # ============================

    # 3. Вкладки заметок
    style.configure("TNotebook", background=bg_main, borderwidth=0)
    style.configure("TNotebook.Tab", 
                    background="#000000",
                    foreground="white",
                    padding=[12, 4],            
                    borderwidth=0,
                    font=("Segoe UI", 9))       
    
    style.map("TNotebook.Tab", 
              background=[('selected', accent),
                          ('active', '#333333')],
              foreground=[('selected', 'white'), 
                          ('active', 'white')])

    # 4. Кнопки
    style.configure("TButton", background=accent, foreground="white", borderwidth=0, padding=6)
    style.map("TButton", background=[('active', "#B540FF"), ('pressed', "#7A00C7")])
    
    style.configure("Green.TButton", background="#00E676", foreground="#121212")
    style.map("Green.TButton", background=[('active', "#69F0AE")])
    
    style.configure("Red.TButton", background="#FF5252", foreground="white")
    style.map("Red.TButton", background=[('active', "#FF8A80")])

    # 5. Поля ввода и Скроллбары
    style.configure("TEntry", fieldbackground=bg_input, foreground="white", insertcolor=accent, borderwidth=0)
    style.configure("Vertical.TScrollbar", troughcolor=bg_main, background="#333", borderwidth=0, arrowcolor="white")

    return bg_main, bg_input

# === ЛОГИКА ВКЛАДКИ НАСТРОЕК (ВСТРОЕННАЯ) ===
def create_settings_tab(parent):
    cfg = load_config()
    fr = ttk.Frame(parent, padding=20)
    fr.pack(fill="both", expand=True)

    # 1. ВЕРХНИЙ ФРЕЙМ ДЛЯ КНОПОК
    top_btn_frame = ttk.Frame(fr)
    top_btn_frame.pack(side="top", fill="x", pady=(0, 20))

    # 2. ФРЕЙМ ДЛЯ КОЛОНОК С НАСТРОЙКАМИ
    cols_frame = ttk.Frame(fr)
    cols_frame.pack(side="top", fill="both", expand=True)

    # --- Левая колонка (Тайминги) ---
    left_col = ttk.LabelFrame(cols_frame, text=" ⏱ Тайминги и Задержки ", padding=15)
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

    var_rand = tk.IntVar(value=int(cfg.get("random_delay", "1")))
    
    def toggle_inputs(*args):
        st = 'disabled' if var_rand.get() else 'normal'
        e1.config(state=st)
        e2.config(state=st)
   
    var_rand.trace_add("write", toggle_inputs)

    chk_rand = ttk.Checkbutton(left_col, text="Включить случайную задержку (5-15 сек)", variable=var_rand)
    chk_rand.pack(anchor="w", pady=(0, 15))

    f_t1 = ttk.Frame(left_col)
    f_t1.pack(fill="x", pady=5)
    ttk.Label(f_t1, text="Пауза после создания группы (сек):").pack(side="left")
    e1 = ttk.Entry(f_t1, width=10, font=("Consolas", 10))
    e1.pack(side="right")
    e1.insert(0, cfg.get("delay_creation", "180"))

    f_t2 = ttk.Frame(left_col)
    f_t2.pack(fill="x", pady=5)
    ttk.Label(f_t2, text="Пауза после инвайта контакта (сек):").pack(side="left")
    e2 = ttk.Entry(f_t2, width=10, font=("Consolas", 10))
    e2.pack(side="right")
    e2.insert(0, cfg.get("delay_contact", "20"))

    toggle_inputs()

    # --- Правая колонка (Технические настройки) ---
    right_col = ttk.LabelFrame(cols_frame, text=" ⚙ Тех. процесс инвайта ", padding=15)
    right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

    ttk.Label(right_col, text="Порядок действий:", foreground="#aaaaaa").pack(anchor="w", pady=(0, 10))
    
    v_mode = tk.IntVar(value=int(cfg.get("contact_mode", "1")))
    
    r1 = ttk.Radiobutton(right_col, text="Создать группу -> СРАЗУ добавить контакт", variable=v_mode, value=0)
    r1.pack(anchor="w", pady=5)
    
    r2 = ttk.Radiobutton(right_col, text="Сначала создать ВСЕ группы -> ПОТОМ добавить контакты", variable=v_mode, value=1)
    r2.pack(anchor="w", pady=5)
    
    ttk.Label(right_col, text="(Второй вариант безопаснее для аккаунтов)", font=("Segoe UI", 8), foreground="#666").pack(anchor="w", padx=20)

    # --- ФУНКЦИЯ СОХРАНЕНИЯ ---
    def save_settings():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get())
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        
        # Принудительно сохраняем эти параметры как включенные "1"
        new_cfg["add_username"] = "1"
        new_cfg["add_contacts"] = "1"
        
        new_cfg["contact_mode"] = str(v_mode.get())
        save_config(new_cfg)
        messagebox.showinfo("Настройки", "✅ Настройки успешно сохранены!")

    # --- СОЗДАНИЕ КНОПОК (ИЗМЕНЕНО) ---
    # Создаем контейнер для кнопок, чтобы они были по центру
    btns_container = ttk.Frame(top_btn_frame)
    btns_container.pack(anchor="center")

    # Кнопка сохранения
    ttk.Button(btns_container, text="💾 СОХРАНИТЬ НАСТРОЙКИ", command=save_settings, style="Green.TButton", width=25)\
        .pack(side="left", padx=5, ipady=5)

    # Кнопка НОВОЕ ОКНО (для мульти-запуска)
    ttk.Button(btns_container, text="❐ ОТКРЫТЬ НОВОЕ ОКНО", command=open_new_window, width=25)\
        .pack(side="left", padx=5, ipady=5)
    

# === ЛОГИКА ВКЛАДКИ АККАУНТОВ (МЕНЕДЖЕР) ===
def create_accounts_tab(parent):
    fr = ttk.Frame(parent, padding=15)
    fr.pack(fill="both", expand=True)

    # Заголовок и Тулбар
    toolbar = ttk.Frame(fr)
    toolbar.pack(fill="x", pady=(0, 10))
    
    ttk.Label(toolbar, text="👥 Менеджер Аккаунтов", font=("Segoe UI", 12, "bold"), foreground="white").pack(side="left")

    # Поиск
    e_acc_search = ttk.Entry(toolbar, width=30)
    e_acc_search.pack(side="right")
    e_acc_search.insert(0, "поиск аккаунта...")
    
    # Кнопка добавления (БОЛЬШАЯ и ЯРКАЯ)
    btn_add = ttk.Button(fr, text="➕ ДОБАВИТЬ АККАУНТ", command=lambda: open_add_account_window(lambda: _refresh_acc_tree()), style="Green.TButton")
    btn_add.pack(fill="x", pady=(0, 10))

    # Таблица
    cols = ("phone", "name", "username", "status")
    global tree_accounts
    tree_accounts = ttk.Treeview(fr, columns=cols, show="headings", selectmode="extended")
    
    tree_accounts.heading("phone", text="Телефон")
    tree_accounts.heading("name", text="Имя")
    tree_accounts.heading("username", text="Username")
    tree_accounts.heading("status", text="Активность")
    
    tree_accounts.column("phone", width=150, anchor="center")
    tree_accounts.column("username", width=150)
    tree_accounts.column("status", width=120, anchor="center")

    sb = ttk.Scrollbar(fr, orient="vertical", command=tree_accounts.yview)
    tree_accounts.configure(yscrollcommand=sb.set)
    tree_accounts.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    # --- КОНТЕКСТНОЕ МЕНЮ (ПКМ) ---
    ctx_menu = tk.Menu(parent, tearoff=0, bg="#252525", fg="white", activebackground="#9D00FF")
    
    def on_right_click(event):
        # Определяем, по какой строке кликнули
        item = tree_accounts.identify_row(event.y)
        
        if item:
            # ЛОГИКА МУЛЬТИ-ВЫБОРА:
            # Если строка, по которой кликнули, НЕ входит в текущее выделение ->
            # -> значит пользователь хочет выделить только её одну.
            if item not in tree_accounts.selection():
                tree_accounts.selection_set(item)
            
            # А если она уже была выделена (вместе с другими), мы ничего не делаем
            # с выделением, просто открываем меню.
            
            ctx_menu.post(event.x_root, event.y_root)

    def _ctx_login():
        sel = tree_accounts.selection()
        if not sel: return
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        threading.Thread(target=lambda: run_login_check(s_data, _refresh_acc_tree), daemon=True).start()

    def _ctx_delete():
        sel = tree_accounts.selection()
        if not sel: return
        if messagebox.askyesno("Удаление", "Удалить выбранный аккаунт из списка?"):
            indices = sorted([int(x) for x in sel], reverse=True)
            ss = load_sessions()
            for i in indices:
                if i < len(ss): del ss[i]
            save_sessions(ss)
            _refresh_acc_tree()
            refresh_dashboard_tree()

    def _ctx_copy_phone():
        sel = tree_accounts.selection()
        if sel:
            val = tree_accounts.item(sel[0])['values'][0]
            root.clipboard_clear()
            root.clipboard_append(val)
            
    # === НОВАЯ ФУНКЦИЯ ВЫЗОВА УДАЛЕНИЯ КОНТАКТОВ ===
    def _ctx_clear_contacts():
        sel = tree_accounts.selection()
        if not sel: return
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        run_delete_contacts_thread(s_data)

    ctx_menu.add_command(label="🔄 Войти / Проверить валид", command=_ctx_login)
    ctx_menu.add_separator()
    ctx_menu.add_command(label="📋 Копировать номер", command=_ctx_copy_phone)
    
    # === ДОБАВЛЕННЫЙ ПУНКТ ===
    ctx_menu.add_separator()
    ctx_menu.add_command(label="🗑 Очистить все контакты", command=_ctx_clear_contacts)
    # =========================
    
    ctx_menu.add_separator()
    ctx_menu.add_command(label="❌ Удалить аккаунт из базы", command=_ctx_delete, foreground="#FF5555")

    tree_accounts.bind("<Button-3>", on_right_click)

    # Функция обновления этой таблицы
    def _refresh_acc_tree(query=""):
        for i in tree_accounts.get_children(): tree_accounts.delete(i)
        
        sessions = load_sessions()
        
        # Подготовка запроса
        raw_q = e_acc_search.get().lower()
        if raw_q == "поиск аккаунта...": raw_q = ""
        clean_q = raw_q.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        for idx, s in enumerate(sessions):
            ph = s.get('phone', '')
            nm = s.get('name', '')
            un = s.get('username', '')
            
            # === УМНЫЙ ФИЛЬТР ===
            if raw_q:
                match_text = (raw_q in nm.lower()) or (raw_q in un.lower())
                match_phone = (clean_q in ph) if clean_q else False
                
                if not (match_text or match_phone):
                    continue
                
            ts = s.get('last_used', 0)
            date_str = "Новый"
            if ts:
                date_str = datetime.fromtimestamp(float(ts)).strftime('%d.%m %H:%M')
            
            # Красивый вывод номера
            disp_ph = ph
            if ph.startswith("+7") and len(ph) == 12:
                disp_ph = f"{ph[:2]} {ph[2:5]} {ph[5:8]} {ph[8:]}"

            tree_accounts.insert("", "end", iid=str(idx), values=(disp_ph, nm, f"@{un}", date_str))

    # Бинды поиска
    e_acc_search.bind("<KeyRelease>", lambda e: _refresh_acc_tree())
    e_acc_search.bind("<FocusIn>", lambda e: e_acc_search.delete(0, 'end') if "поиск" in e_acc_search.get() else None)
    
    _refresh_acc_tree()

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
    client = TelegramClient(
        f"session_{phone}", 
        int(s_data['api_id']), 
        s_data['api_hash'], 
        loop=loop,
        proxy=get_random_proxy(),
        **DEVICE_CONFIG
    )
        
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


# === ГЛАВНАЯ ВКЛАДКА (DASHBOARD) ===
def create_dashboard_tab(parent):
    # Основной контейнер
    main_fr = ttk.Frame(parent, padding=15)
    main_fr.pack(fill="both", expand=True)

    # 1. Верхняя панель
    top_panel = ttk.Frame(main_fr)
    top_panel.pack(fill="x", pady=(0, 10))
    
    ttk.Label(top_panel, text="🎛 Управление ролями (Один Мейкер + Один Дир)", font=("Segoe UI", 12, "bold"), foreground="white").pack(side="left")

    search_fr = ttk.Frame(top_panel)
    search_fr.pack(side="right")
    
    # === 1. ДЕЛАЕМ ПЕРЕМЕННУЮ ПОИСКА ГЛОБАЛЬНОЙ ===
    global e_search 
    e_search = ttk.Entry(search_fr, width=25, font=("Consolas", 10))
    e_search.pack(side="right")
    e_search.insert(0, "поиск...")
    
    def _on_search(e):
        refresh_dashboard_tree() # Теперь аргумент не обязателен, функция сама возьмет текст

    e_search.bind("<KeyRelease>", _on_search)
    e_search.bind("<FocusIn>", lambda e: e_search.delete(0, 'end') if "поиск" in e_search.get() else None)

    # 2. ТАБЛИЦА
    cols = ("maker", "director", "phone", "info")
    global tree_dashboard
    tree_dashboard = ttk.Treeview(main_fr, columns=cols, show="headings", selectmode="browse")

    tree_dashboard.heading("maker", text="🔨 Мейкер")
    tree_dashboard.heading("director", text="👑 Дир")
    tree_dashboard.heading("phone", text="Телефон")
    tree_dashboard.heading("info", text="Имя / Юзернейм")

    tree_dashboard.column("maker", width=70, anchor="center")
    tree_dashboard.column("director", width=60, anchor="center")
    tree_dashboard.column("phone", width=140, anchor="center")
    tree_dashboard.column("info", width=300, anchor="w")

    sb = ttk.Scrollbar(main_fr, orient="vertical", command=tree_dashboard.yview)
    tree_dashboard.configure(yscrollcommand=sb.set)
    tree_dashboard.pack(side="top", fill="both", expand=True)
    sb.pack(side="right", fill="y", in_=main_fr)

    # ЛОГИКА КЛИКОВ
    def on_tree_click(event):
        region = tree_dashboard.identify("region", event.x, event.y)
        if region != "cell": return
        
        col = tree_dashboard.identify_column(event.x)
        item_id = tree_dashboard.identify_row(event.y)
        if not item_id: return
        
        # Получаем данные строки
        vals = tree_dashboard.item(item_id, "values")
        
        # === ВАЖНОЕ ИСПРАВЛЕНИЕ ===
        # Берем номер из таблицы и ОЧИЩАЕМ его от пробелов перед сохранением
        raw_display_phone = vals[2] 
        clicked_phone = raw_display_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # ==========================
        
        global current_maker_phone, current_director_phone

        # Логика для Мейкера (1-я колонка)
        if col == "#1": 
            if current_maker_phone == clicked_phone:
                current_maker_phone = None # Снимаем
            else:
                current_maker_phone = clicked_phone # Ставим
                if current_director_phone == clicked_phone: current_director_phone = None

        # Логика для Директора (2-я колонка)
        elif col == "#2": 
            if current_director_phone == clicked_phone:
                current_director_phone = None # Снимаем
            else:
                current_director_phone = clicked_phone # Ставим
                if current_maker_phone == clicked_phone: current_maker_phone = None

        # Обновляем таблицу
        refresh_dashboard_tree()

    tree_dashboard.bind("<Button-1>", on_tree_click)

    # 3. НИЗ
    bottom_frame = ttk.Frame(parent, padding=15)
    bottom_frame.pack(side="bottom", fill="x")

    lf_greet = ttk.LabelFrame(bottom_frame, text=" 💬 Сообщение директора ", padding=5)
    lf_greet.pack(fill="x", pady=(0, 10))

    # --- ВОТ ТУТ МЫ ВЕРНУЛИ ГАЛОЧКУ ---
    opts_frame = ttk.Frame(lf_greet)
    opts_frame.pack(fill="x", pady=(0, 5))
    
    global var_send_greeting
    var_send_greeting = tk.IntVar(value=1) # По умолчанию ВКЛЮЧЕНО
    chk = ttk.Checkbutton(opts_frame, text="Отправлять приветствие", variable=var_send_greeting)
    chk.pack(side="left", padx=5)

    global txt_greeting
    txt_greeting = scrolledtext.ScrolledText(lf_greet, height=3, font=("Consolas", 10), 
                                         bg="#1E1E1E", fg="#00FF00", borderwidth=0, insertbackground="white")
    txt_greeting.pack(fill="x")
    
    # --- НОВЫЙ ТЕКСТ ПО УМОЛЧАНИЮ ---
    cfg = load_config()
    default_msg = "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?"
    saved_msg = cfg.get("greeting_text", default_msg)
    # Если в конфиге пусто, ставим дефолт
    if not saved_msg: 
        saved_msg = default_msg

    txt_greeting.insert("1.0", saved_msg)

    btn_frame = ttk.Frame(bottom_frame)
    btn_frame.pack(fill="x")
    
    global smart_btn, log_widget
    smart_btn = ttk.Button(btn_frame, text="🚀 ЗАПУСТИТЬ РАБОТУ", command=lambda: start_process("smart"), style="Green.TButton")
    smart_btn.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 5))
    
    ttk.Button(btn_frame, text="🛑 СТОП", command=stop_process, style="Red.TButton").pack(side="left", padx=5, ipadx=10)

    lf_log = ttk.LabelFrame(bottom_frame, text=" Лог событий ", padding=2)
    lf_log.pack(fill="x", pady=(10,0))
    log_widget = scrolledtext.ScrolledText(lf_log, height=6, state='disabled', bg="#050505", fg="#CCC", font=("Consolas", 9))
    log_widget.pack(fill="both")
    
    for t, c in TAG_COLORS.items():
        log_widget.tag_config(t, foreground=c if t != "ERROR" else "#FF5555")

    refresh_dashboard_tree()

# ==========================================
# === ЛОГИКА ВКЛАДКИ БАЗЫ (FILE MANAGER) ===
# ==========================================
def create_databases_tab(parent):
    DB_FOLDER = "прописанные базы"
    # Создаем основную папку, если нет
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    # --- ДОБАВЛЕНО: Создаем подпапку для отмененных баз ---
    CANCEL_DIR = os.path.join(DB_FOLDER, "отмена и схроненные")
    if not os.path.exists(CANCEL_DIR):
        os.makedirs(CANCEL_DIR)

    # Используем PanedWindow для разделения экрана
    paned = ttk.PanedWindow(parent, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=10, pady=10)

    # --- ЛЕВАЯ ЧАСТЬ: СПИСОК ФАЙЛОВ ---
    frame_list = ttk.Frame(paned)
    paned.add(frame_list, weight=1) # Вес 1 (уже)

    # 1. Верхняя панель списка (Заголовок + Кнопка обновления)
    list_header = ttk.Frame(frame_list)
    list_header.pack(fill="x", pady=(0, 5))

    ttk.Label(list_header, text="📂 Файлы отчетов", font=("Segoe UI", 11, "bold"), foreground="#9D00FF").pack(side="left")
    
    # Кнопка обновления теперь вверху справа (компактная)
    btn_refresh = ttk.Button(list_header, text="🔄", width=4, command=lambda: refresh_file_list())
    btn_refresh.pack(side="right")

    # 2. Дерево файлов
    columns = ("filename", "size")
    tree_files = ttk.Treeview(frame_list, columns=columns, show="headings", selectmode="browse")
    tree_files.heading("filename", text="Имя файла")
    tree_files.heading("size", text="Размер")
    
    tree_files.column("filename", width=180)
    tree_files.column("size", width=70, anchor="center")

    sb_files = ttk.Scrollbar(frame_list, orient="vertical", command=tree_files.yview)
    tree_files.configure(yscrollcommand=sb_files.set)

    tree_files.pack(side="left", fill="both", expand=True)
    sb_files.pack(side="right", fill="y")

    # --- ПРАВАЯ ЧАСТЬ: РЕДАКТОР ---
    frame_editor = ttk.Frame(paned)
    paned.add(frame_editor, weight=3) # Вес 3 (шире)

    # Тулбар редактора (Заголовок файла + Кнопки действий)
    toolbar = ttk.Frame(frame_editor)
    toolbar.pack(fill="x", pady=(0, 5))

    lbl_current_file = ttk.Label(toolbar, text="Выберите файл...", font=("Consolas", 10, "bold"), foreground="#888")
    lbl_current_file.pack(side="left", padx=5)

    # Кнопки справа (Сохранить, Удалить)
    btn_del = ttk.Button(toolbar, text="🗑 Удалить", style="Red.TButton", state='disabled')
    btn_del.pack(side="right")
    
    btn_save = ttk.Button(toolbar, text="💾 Сохранить изменения", style="Green.TButton", state='disabled')
    btn_save.pack(side="right", padx=5)

    # Текстовое поле
    txt_content = scrolledtext.ScrolledText(frame_editor, font=("Consolas", 10), 
                                            bg="#0F0F0F", fg="#E0E0E0", 
                                            insertbackground="#9D00FF", borderwidth=0)
    txt_content.pack(fill="both", expand=True)
    txt_content.config(state='disabled') 

    # --- ФУНКЦИОНАЛ ---
    current_file_path = [None] 

    def refresh_file_list():
        # Очистка
        for item in tree_files.get_children():
            tree_files.delete(item)
        
        if not os.path.exists(DB_FOLDER): return

        files = [f for f in os.listdir(DB_FOLDER) if f.endswith(".txt")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(DB_FOLDER, x)), reverse=True)

        for f in files:
            full_path = os.path.join(DB_FOLDER, f)
            size_kb = f"{os.path.getsize(full_path) / 1024:.1f} KB"
            tree_files.insert("", "end", values=(f, size_kb))

    def on_file_select(event):
        sel = tree_files.selection()
        if not sel: return
        
        filename = tree_files.item(sel[0])['values'][0]
        full_path = os.path.join(DB_FOLDER, filename)
        
        if not os.path.exists(full_path):
            messagebox.showerror("Ошибка", "Файл не найден.")
            refresh_file_list()
            return

        current_file_path[0] = full_path
        lbl_current_file.config(text=f"📄 {filename}", foreground="#00E676")
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            txt_content.config(state='normal')
            txt_content.delete("1.0", tk.END)
            txt_content.insert("1.0", content)
            
            btn_save.config(state='normal', command=save_current_file)
            btn_del.config(state='normal', command=delete_current_file)
            
        except Exception as e:
            messagebox.showerror("Ошибка чтения", str(e))

    def save_current_file():
        path = current_file_path[0]
        if not path: return
        try:
            content = txt_content.get("1.0", tk.END)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.strip())
            messagebox.showinfo("Сохранено", "Файл успешно обновлен!")
            refresh_file_list()
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def delete_current_file():
        path = current_file_path[0]
        if not path: return
        if messagebox.askyesno("Удаление", f"Удалить файл?\n{os.path.basename(path)}"):
            try:
                os.remove(path)
                txt_content.delete("1.0", tk.END)
                txt_content.config(state='disabled')
                lbl_current_file.config(text="Файл удален.", foreground="#FF5252")
                current_file_path[0] = None
                btn_save.config(state='disabled')
                btn_del.config(state='disabled')
                refresh_file_list()
            except Exception as e:
                messagebox.showerror("Ошибка удаления", str(e))

    # Бинды и запуск
    # ВАЖНО: Привязываем команду к кнопке обновления здесь, чтобы функция была видна
    btn_refresh.config(command=refresh_file_list)
    
    tree_files.bind("<<TreeviewSelect>>", on_file_select)
    refresh_file_list()

# ==========================================
# === Вклдака ИНСТРУКЦИЯ (CHINESE) ===
# ==========================================
def create_instruction_tab(parent):
    fr = ttk.Frame(parent, padding=15)
    fr.pack(fill="both", expand=True)

    # Заголовок
    lbl_title = ttk.Label(fr, text="📑 使用说明书 (LERA)", font=("Microsoft YaHei", 14, "bold"), foreground="#00E676")
    lbl_title.pack(anchor="w", pady=(0, 10))

    # Текстовое поле с прокруткой
    txt = scrolledtext.ScrolledText(fr, font=("Microsoft YaHei", 10), 
                                    bg="#1E1E1E", fg="#E0E0E0", 
                                    insertbackground="white", borderwidth=0, padx=10, pady=10)
    txt.pack(fill="both", expand=True)

    # --- ТЕКСТ ИНСТРУКЦИИ НА КИТАЙСКОМ ---
    instruction_text = """
GroupMega v24.1 Pro - 操作指南

欢迎使用 GroupMega 自动化系统。本软件用于自动创建 Telegram 群组、邀请用户及管理营销流程。请仔细阅读以下步骤以确保安全高效地运行。

================================================================
一、 基础设置与代理 (Proxy)
================================================================
这是最重要的一步。为了防止账户被封禁，必须正确配置代理。

1. 代理类型 (Proxy Type):
   - 本软件默认使用 HTTP 协议。
   - 请勿在代码中混用 SOCKS5，除非你已更改了源代码。

2. 代理格式 (Proxy Format):
   - IP地址:端口:用户名:密码
   - 例如：45.153.55.203:62652:FjRHSGVc:FvHfAH5g
   - 请确保你使用的是静态住宅代理或高质量的 IPv4 代理。

3. 警告：
   - 不要使用免费代理。
   - 确保你的电脑网络环境稳定。
   - 如果遇到 "Connection Error"，请检查代理是否过期。

================================================================
二、 账户管理 (Account Manager)
================================================================
在 "👥 Accounts" 选项卡中管理你的 Telegram 账户。

1. 添加账户:
   - 点击 "➕ 添加账户 (Add Account)"。
   - 输入手机号码（格式如：+79991234567）。
   - 系统会自动尝试从 my.telegram.org 获取 API ID 和 Hash。
   - 输入 Telegram 发送的验证码。
   - 如果有两步验证 (2FA)，请输入云密码。

2. 检查状态:
   - 在列表中右键点击账户，选择 "🔄 登录/检查 (Login/Check)"。
   - 确保状态显示为活跃，并且能看到用户名。

3. 安全建议:
   - 每个账户每天建议创建群组不超过 5-10 个。
   - 如果账户是新注册的，请先“养号” 3-5 天再使用。

================================================================
三、 角色分配 (Roles: Maker & Director)
================================================================
在 "🏠 主页 (Dashboard)" 选项卡中分配角色。

1. 建群者 (Maker 🔨):
   - 负责创建群组的人。
   - 点击表格第一列的复选框 (☐ -> ☑) 来选择。
   - 必须选择一个 Maker。

2. 领导/主管 (Director 👑):
   - 负责在群组中显得“官方”的人，或者用于被添加到群组中。
   - 点击表格第二列的圆圈 (◌ -> 👑) 来选择。
   - 这是可选的，但建议设置。

================================================================
四、 运行工作流程 (Smart Process)
================================================================
1. 准备数据:
   - 准备好你的客户名单 (.txt 文件)。
   - 格式：公司名称 ------ 客户列表（包含姓名和电话）。

2. 设置参数 (在 ⚙ Settings):
   - 创建群组后暂停：建议 180 秒。
   - 邀请后暂停：建议 20 秒。
   - 开启 "随机延迟 (Random Delay)" 以模拟真人操作。

3. 启动:
   - 回到主页，点击绿色的 "🚀 开始工作 (START WORK)" 按钮。
   - 选择你的 .txt 数据库文件。
   - 系统将自动开始：登录 -> 建群 -> 拉人 -> 清理消息。

================================================================
五、 常见问题与故障排除 (FAQ)
================================================================
Q: 为什么显示 "FloodWait"?
A: Telegram 限制了你的操作频率。请暂停该账户 1-2 小时，并增加延迟时间。

Q: 为什么建群后立即被封号?
A: 你的 IP 地址可能不干净，或者设备指纹被检测到。请更换代理，并确保代码中已启用 "iPhone 15 Pro" 伪装。

Q: 为什么找不到用户?
A: 请确保客户的隐私设置允许被电话号码搜索，且你的账户没有被限制。

----------------------------------------------------------------
祝您使用愉快！如有问题，请联系技术支持。
    """
    
    txt.insert("1.0", instruction_text.strip())
    txt.configure(state='disabled') # Только чтение

# === ЛОГИКА БОКОВОГО МЕНЮ ===
# === ЛОГИКА БОКОВОГО МЕНЮ ===
class SidebarApp:
    def __init__(self, root):
        self.root = root
        self.current_frame = None
        self.frames = {}
        self.buttons = {}
        
        # Настройка сетки
        root.grid_columnconfigure(0, weight=0)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = tk.Frame(root, bg="#0F0F0F", width=200, padx=0, pady=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.configure(width=200)

        lbl_logo = tk.Label(self.sidebar, text="Dark\nGroup", bg="#0F0F0F", fg="#9D00FF", 
                           font=("Segoe UI Black", 16, "bold"), pady=20)
        lbl_logo.pack(fill="x")

        # 2. Content
        self.content_area = tk.Frame(root, bg="#121212")
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # 3. Инициализация экранов
        self.frames["Главная"] = ttk.Frame(self.content_area)
        self.frames["Accounts"] = ttk.Frame(self.content_area)
        self.frames["Settings"] = ttk.Frame(self.content_area)
        self.frames["Databases"] = ttk.Frame(self.content_area)
        self.frames["Instruction"] = ttk.Frame(self.content_area) # <--- [NEW 1] ДОБАВИЛ ЭТУ СТРОКУ
        self.frames["Notes"] = ttk.Frame(self.content_area)

        # Наполняем экраны
        create_dashboard_tab(self.frames["Главная"])
        create_accounts_tab(self.frames["Accounts"])
        create_databases_tab(self.frames["Databases"])
        create_instruction_tab(self.frames["Instruction"])       # <--- [NEW 2] ДОБАВИЛ ЭТУ СТРОКУ
        create_settings_tab(self.frames["Settings"])
        self._init_notes_screen(self.frames["Notes"])

        # 4. Кнопки меню
        self._add_menu_btn("🏠 Главная", "Главная")
        self._add_menu_btn("👥 Accounts", "Accounts")
        
        # --- [NEW 3] ВОТ КНОПКА ДЛЯ ЛЕРЫ ---
        self._add_menu_btn("📖 ИНСТРУКЦИЯ ЛЕРЕ!", "Instruction") 
        # -----------------------------------
        
        self._add_menu_btn("⚙ Settings", "Settings")
        self._add_menu_btn("📂 Пробитые Базы", "Databases")
        self._add_menu_btn("📝 Notes", "Notes")

        # Футер
        tk.Label(self.sidebar, text="v24.1 Pro", bg="#0F0F0F", fg="#555", 
                 font=("Consolas", 8)).pack(side="bottom", pady=10)

        # Показываем первый экран
        self.show_screen("Главная")

    def _add_menu_btn(self, text, screen_name):
        btn = tk.Button(self.sidebar, text=text, font=("Segoe UI", 11), 
                        bg="#0F0F0F", fg="#888", 
                        activebackground="#1E1E1E", activeforeground="white",
                        bd=0, cursor="hand2", anchor="w", padx=20, pady=12,
                        command=lambda: self.show_screen(screen_name))
        
        btn.pack(fill="x", pady=2)
        self.buttons[screen_name] = btn

    def show_screen(self, screen_name):
        if self.current_frame:
            self.current_frame.pack_forget()
        
        for name, btn in self.buttons.items():
            if name == screen_name:
                btn.config(bg="#1E1E1E", fg="#9D00FF", font=("Segoe UI", 11, "bold"))
            else:
                btn.config(bg="#0F0F0F", fg="#888", font=("Segoe UI", 11))

        frame = self.frames[screen_name]
        frame.pack(fill="both", expand=True)
        self.current_frame = frame

    def _init_notes_screen(self, parent):
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
        
def refresh_dashboard_tree(filter_text=None):
    if not tree_dashboard: return
    
    # 1. Подготовка поиска
    q_raw = ""
    q_clean = ""
    
    if filter_text is None:
        if e_search:
            val = e_search.get()
            if val != "поиск...":
                q_raw = val.lower()
                # Удаляем мусор для поиска по телефону
                q_clean = q_raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    else:
        q_raw = filter_text.lower()
        q_clean = q_raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Очистка таблицы
    for item in tree_dashboard.get_children():
        tree_dashboard.delete(item)
        
    sessions = load_sessions()
    global current_maker_phone, current_director_phone
    
    for i, s in enumerate(sessions):
        phone = s.get('phone', 'No Phone') # В базе он чистый: +7994...
        name = s.get('name', 'Без имени')
        uname = f"@{s.get('username', '-')}"
        
        # === УМНЫЙ ПОИСК ===
        if q_raw:
            # 1. Ищем по тексту (имя, юзернейм) как есть
            match_text = (q_raw in name.lower()) or (q_raw in uname.lower())
            
            # 2. Ищем по телефону (сравниваем очищенный запрос с очищенным телефоном)
            match_phone = (q_clean in phone) if q_clean else False
            
            # Если ни то, ни другое не совпало — пропускаем
            if not (match_text or match_phone):
                continue

        # === ВИЗУАЛЬНОЕ ФОРМАТИРОВАНИЕ НОМЕРА (ТОЛЬКО ДЛЯ ГЛАЗ) ===
        # Логика работы не меняется, просто выводим красиво
        display_phone = phone
        if phone.startswith("+7") and len(phone) == 12:
            # Превращаем +79991234567 в +7 999 123 4567
            display_phone = f"{phone[:2]} {phone[2:5]} {phone[5:8]} {phone[8:]}"
            
        # Галочки
        maker_icon = "☑" if phone == current_maker_phone else "☐"
        dir_icon = "👑" if phone == current_director_phone else "◌"
        
        row_tags = ('row',)
        if "Без имени" in name: row_tags = ('gray_row',)
        
        tree_dashboard.insert("", "end", iid=str(i), 
                              values=(maker_icon, dir_icon, display_phone, f"{name} | {uname}"),
                              tags=row_tags)
    
    tree_dashboard.tag_configure('gray_row', foreground='#777')
    
# === ГЛАВНАЯ ФУНКЦИЯ СБОРКИ UI ===
def build_modern_ui():
    global root, guest_account_index
    
    root = tk.Tk()
    root.title("GroupMega v24.1 Pro")
    root.geometry("1100x700")
    
    # Разрешаем растягивание (Сетка: колонка 1 занимает всё место)
    root.minsize(900, 600)
    root.grid_columnconfigure(1, weight=1) 
    root.grid_rowconfigure(0, weight=1)
    
    # Инициализация переменных (оставляем для совместимости)
    guest_account_index = tk.IntVar(value=-1)

    # Применяем тему
    bg, fg = setup_dark_theme()
    root.configure(bg=bg)
    
    # Включаем горячие клавиши (Ctrl+C/V)
    enable_hotkeys(root)

    # Запускаем приложение с боковым меню
    app = SidebarApp(root)

    # ВАЖНО: Вызываем обновление НОВОЙ таблицы
    # (Функцию refresh_dashboard_tree мы добавили шагом ранее)
    refresh_dashboard_tree()

    root.mainloop()

if __name__ == "__main__":
    build_modern_ui()