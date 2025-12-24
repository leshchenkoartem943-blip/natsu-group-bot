import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, Toplevel, filedialog
import tkinter.simpledialog as simpledialog
import os
import sys
import pygame

import random
import requests
from telethon import functions, types
import json
from telethon.tl.functions.messages import EditChatAdminRequest
from telethon import utils
import threading
import glob
from collections import deque
import math
import time
import re
import asyncio
import subprocess
from datetime import datetime
from PIL import Image, ImageTk, ImageSequence
import multiprocessing
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputFolderPeer, InputPeerNotifySettings
import customtkinter as ctk
from telethon.tl.types import InputUserSelf
import webbrowser
import openpyxl
from telethon.tl.functions.messages import MigrateChatRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.types import ChatAdminRights, InputUserSelf
import python_socks
from bs4 import BeautifulSoup
import google.generativeai as genai
from telethon.tl.types import ChatAdminRights, InputPhoneContact, MessageActionChatDeleteUser
from telethon import TelegramClient, functions, types, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError, UserAlreadyParticipantError
)

# === Новые импорты для смены профиля, приватности и фото ===
from telethon.tl.functions.account import (
    UpdateProfileRequest, 
    SetPrivacyRequest, 
    UpdateUsernameRequest  # <--- ДОБАВЛЕНО
)
from telethon.tl.functions.photos import DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.functions.contacts import DeleteContactsRequest
from telethon.tl.types import (
    InputPrivacyKeyAddedByPhone, 
    InputPrivacyValueAllowAll, 
    InputPhoto  # <--- БЫЛО InputInputPhoto, СТАЛО InputPhoto
)
from telethon.tl.types import ChatAdminRights
import hashlib
import uuid
from tkinter import simpledialog

# ==========================================
# === СИСТЕМА СЛЕЖЕНИЯ И КОНТРОЛЯ ===
# ==========================================
ADMIN_ID = "8351214331"  # Например: "123456789"
BOT_TOKEN = "8529020816:AAEFZ07T3JlkM2vQbQxSyjTARtACEVb4eQU" # Например: "777777:AAH..."
IS_SPY_MODE = False  # Если True - шлет ВСЕ логи админу
REMOTE_PAUSE = False 
IS_LOCKED_PAUSE = False
last_shown_message = None 
last_opened_url = None
update_notified = False
last_opened_update_url = None
last_global_msg = None
USER_FILE = "license_name.json"
FIREBASE_DB_URL = "https://base-natsu-default-rtdb.firebaseio.com"
CURRENT_VERSION = "25.0"

def firebase_patch(path, data):
    """
    Отправляет данные на сервер (обновляет конкретные поля).
    path: путь внутри базы (например, "/config/users/HWID")
    data: словарь с данными
    """
    try:
        url = f"{FIREBASE_DB_URL}{path}.json"
        requests.patch(url, json=data, timeout=10)
    except Exception as e:
        print(f"Firebase Patch Error: {e}")

def firebase_get(path):
    """
    Скачивает данные с сервера.
    path: путь внутри базы
    """
    try:
        url = f"{FIREBASE_DB_URL}{path}.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Firebase Get Error: {e}")
        return None

def start_listening():
    """
    Фоновая функция: слушает команды от админа МГНОВЕННО (каждые 1.5 сек).
    Обрабатывает: Бан (Kill), Паузу (Заморозку экрана), ЛС, Глобальные смс, Ссылки, Слежку.
    """
    def _loop():
        # Переменные памяти (чтобы не спамить одним и тем же окном)
        last_glob_msg = ""
        last_personal_msg = ""
        opened_urls_history = set()

        while True:
            try:
                # 1. Скачиваем конфиг
                config = firebase_get("/config")
                
                if config:
                    # --- А) ГЛОБАЛЬНЫЕ КОМАНДЫ ---
                    if config.get("global_stop") == True:
                        print("⛔ GLOBAL STOP")
                        os._exit(1)
                    
                    # Глобальное сообщение
                    g_msg = config.get("global_message", "")
                    if g_msg and g_msg != last_glob_msg:
                        last_glob_msg = g_msg
                        if root: root.after(0, lambda m=g_msg: messagebox.showinfo("Сообщение всем", m))

                    # --- Б) ЛИЧНЫЕ КОМАНДЫ ДЛЯ ЮЗЕРА ---
                    my_hwid = get_hwid()
                    users = config.get("users", {})
                    
                    if my_hwid in users:
                        user_data = users[my_hwid]
                        
                        # 3. Статус (Active / Pause / Kill)
                        status = user_data.get("status", "active")
                        
                        # Нам нужна переменная REMOTE_PAUSE, чтобы понимать текущее состояние
                        # (она меняется внутри set_freeze_mode, но читаем мы её здесь)
                        global REMOTE_PAUSE 
                        
                        # === ЛОГИКА УПРАВЛЕНИЯ ===
                        if status == "kill":
                            print("💀 ПОЛУЧЕНА КОМАНДА KILL. ЗАВЕРШЕНИЕ РАБОТЫ.")
                            os._exit(0) # Жесткий выход
                            
                        elif status == "pause":
                            # Если админ поставил паузу, а у нас её еще нет -> МОРОЗИМ
                            if not REMOTE_PAUSE:
                                print("❄️ КОМАНДА: ЗАМОРОЗКА")
                                # Вызываем GUI-функцию через главный поток
                                if root: root.after(0, lambda: set_freeze_mode(True))
                                
                        elif status == "active":
                            # Если админ снял паузу, а мы заморожены -> РАЗМОРАЖИВАЕМ
                            if REMOTE_PAUSE:
                                print("🔥 КОМАНДА: РАЗМОРОЗКА")
                                if root: root.after(0, lambda: set_freeze_mode(False))
                        # =========================

                        # 4. Режим Слежки (Spy Mode)
                        global IS_SPY_MODE
                        IS_SPY_MODE = user_data.get("spy_mode", False)

                        # 5. Личное сообщение (ЛС)
                        p_msg = user_data.get("message", "")
                        if p_msg and p_msg != last_personal_msg:
                            last_personal_msg = p_msg
                            if root: root.after(0, lambda m=p_msg: messagebox.showinfo("Личное сообщение", m))

                        # 6. Открытие ссылок
                        raw_urls = user_data.get("open_urls", [])
                        current_urls = raw_urls if isinstance(raw_urls, list) else [raw_urls] if raw_urls else []
                        
                        for url in current_urls:
                            url = str(url).strip()
                            if url and url not in opened_urls_history:
                                webbrowser.open(url)
                                opened_urls_history.add(url)
                                
            except Exception as e:
                print(f"Listen Error: {e}")
            
            time.sleep(1.5) 

    # Запускаем в вечном фоновом потоке
    threading.Thread(target=_loop, daemon=True).start()

# ==========================================
# === ДОБАВИТЬ ЭТИ ФУНКЦИИ В НАЧАЛО ФАЙЛА (В БЛОК FIREBASE) ===
# ==========================================

def update_daily_stats_firebase():
    """
    Отправляет статистику запуска (+1 к счетчику за сегодня).
    """
    try:
        my_hwid = get_hwid()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Получаем текущий счетчик
        path = f"/config/users/{my_hwid}/stats"
        current_data = firebase_get(path)
        
        new_count = 1
        if current_data and current_data.get("date") == today:
            new_count = current_data.get("count", 0) + 1
            
        # Записываем
        firebase_patch(path, {"date": today, "count": new_count})
        
    except Exception as e:
        print(f"Stats Error: {e}")

def push_log_firebase(text):
    """
    Отправляет короткий лог действия в админку (поле last_log).
    """
    try:
        my_hwid = get_hwid()
        timestamp = datetime.now().strftime("[%H:%M] ")
        # Просто обновляем поле last_log
        path = f"/config/users/{my_hwid}"
        firebase_patch(path, {"last_log": timestamp + text})
    except: pass

def auto_register_in_firebase():
    """
    Автоматически регистрирует пользователя на сервере при запуске.
    """
    try:
        hwid = get_hwid()
        name = get_registered_user()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Проверяем, есть ли юзер в базе
        path = f"/config/users/{hwid}"
        current_data = firebase_get(path)
        
        if current_data:
            # ЮЗЕР УЖЕ ЕСТЬ -> Обновляем только дату входа и имя
            payload = {
                "rename_to": name,
                "last_seen": now,
                "version": CURRENT_VERSION
            }
            # Если вдруг нет статуса, ставим active
            if "status" not in current_data:
                payload["status"] = "active"
                
            firebase_patch(path, payload)
            print(f"Firebase: Юзер {name} обновлен.")
            
        else:
            # ЮЗЕР НОВЫЙ -> Создаем запись
            payload = {
                "rename_to": name,
                "status": "active",
                "spy_mode": False,
                "message": "",
                "last_seen": now,
                "registered_at": now,
                "version": CURRENT_VERSION,
                "open_urls": [],
                "last_log": "Регистрация..."
            }
            firebase_patch(path, payload)
            print(f"Firebase: Новый юзер {name} зарегистрирован!")
            
    except Exception as e:
        print(f"Auto-Register Error: {e}")

def check_for_updates():
    """
    Сверяет текущую версию с той, что в базе.
    Если устарела — предлагает (или заставляет) обновиться.
    """
    try:
        # 1. Качаем инфо о версиях из Глобальной вкладки
        config = firebase_get("/config/version_info")
        if not config: return

        latest_ver = config.get("latest_version", CURRENT_VERSION)
        min_ver = config.get("min_working_version", "0.0")
        download_url = config.get("download_url", "")

        # Если версии совпадают — все ок
        if latest_ver == CURRENT_VERSION:
            return

        # 2. Если версия пользователя МЕНЬШЕ минимальной — БЛОКИРУЕМ
        # (Например, старая версия 24.0, а минимальная 25.0)
        if float(CURRENT_VERSION) < float(min_ver):
            messagebox.showerror("КРИТИЧЕСКОЕ ОБНОВЛЕНИЕ", 
                                 f"Ваша версия ({CURRENT_VERSION}) устарела!\n"
                                 f"Минимальная версия: {min_ver}\n\n"
                                 "Программа будет закрыта. Пожалуйста, обновитесь.")
            if download_url: webbrowser.open(download_url)
            os._exit(0)

        # 3. Если просто вышла новая версия (Например, 26.0), но старая еще работает
        if float(latest_ver) > float(CURRENT_VERSION):
            if messagebox.askyesno("Обновление", 
                                   f"Вышла новая версия: {latest_ver}\n"
                                   f"У вас: {CURRENT_VERSION}\n\n"
                                   "Хотите скачать обновление сейчас?"):
                if download_url:
                    webbrowser.open(download_url)
                    os._exit(0) # Закрываем, чтобы обновил

    except Exception as e:
        print(f"Update Check Error: {e}")

def resource_path(relative_path):
    """ Получает абсолютный путь к ресурсу, работает и для dev, и для PyInstaller """
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_hwid():
    """Генерирует уникальный ID компьютера (железа)."""
    try:
        mac = uuid.getnode()
        hwid = hashlib.md5(str(mac).encode()).hexdigest()
        return hwid
    except:
        return "unknown_hwid"

# ==========================================
# === РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===
# ==========================================


def get_registered_user():
    """
    Проверяет, представился ли пользователь.
    Если нет - просит ввести имя и сохраняет его навсегда.
    """
    # 1. Если файл есть - читаем имя
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("name", "Unknown")
        except: pass

    # 2. Если файла нет - требуем ввод
    # Создаем временное скрытое окно для диалога
    temp_root = tk.Tk()
    temp_root.withdraw()
    
    user_name = ""
    while not user_name:
        user_name = simpledialog.askstring(
            "Активация", 
            "Введите ваше ИМЯ для активации лицензии:\n(Например: Иван)", 
            parent=temp_root
        )
        
        # Если нажал Отмена или крестик - закрываем программу жестко
        if user_name is None:
            sys.exit()
            
        user_name = user_name.strip()
        if not user_name:
            messagebox.showwarning("Ошибка", "Имя не может быть пустым!")

    temp_root.destroy()

    # 3. Сохраняем имя и отправляем админу уведомление о новом юзере
    try:
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump({"name": user_name}, f, ensure_ascii=False)
            
        # Сразу стучим тебе, что появился новенький
        send_admin_log("🆕 НОВАЯ РЕГИСТРАЦИЯ", f"Пользователь представился как: {user_name}")
    except: pass
    
    return user_name

def send_admin_log(action_name, details=""):
    """
    Отправляет уведомление разработчику о действиях пользователя.
    """
    try:
        import platform
        # 1. Собираем инфо о компьютере
        pc_name = platform.node()
        system_info = platform.platform()
        try: user_pc = os.getlogin()
        except: user_pc = "Unknown"
        
        # HWID
        hwid = get_hwid()

        # ИМЯ ИЗ ЛИЦЕНЗИИ
        registered_name = "Неизвестный"
        if os.path.exists("license_name.json"):
            try:
                with open("license_name.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    registered_name = data.get("name", "Неизвестный")
            except: pass

        # IP
        try: ip = requests.get('https://api.ipify.org', timeout=2).text
        except: ip = "Не определен"

        # Формируем сообщение
        msg = (
            f"🔔 <b>ACTIVATION ALERT</b>\n\n"
            f"🆔 <b>HWID:</b> <code>{hwid}</code>\n"  # <--- ВОТ ТУТ НОВЫЙ ID
            f"👤 <b>NAME:</b> {registered_name}\n"
            f"👤 <b>PC User:</b> {user_pc}\n"
            f"💻 <b>PC Name:</b> {pc_name}\n"
            f"🌐 <b>IP:</b> {ip}\n"
            f"⚙️ <b>OS:</b> {system_info}\n\n"
            f"🚀 <b>Action:</b> {action_name}\n"
            f"📝 <b>Details:</b> {details}"
        )
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"}, timeout=3)
        short_log = f"{action_name}: {details[:50]}" # Обрезаем, чтобы не было слишком длинно
    
    # Запускаем в отдельном потоке, чтобы программа не висла
        threading.Thread(target=lambda: push_log_firebase(short_log), daemon=True).start()
    except Exception: pass

# ==========================================
# === УДАЛЕННОЕ ОТКЛЮЧЕНИЕ (KILL SWITCH) ===
# ==========================================

# Твой список прокси (формат IP:PORT:USER:PASS)
MY_PROXIES = [
    "45.148.242.11:63626:FjRHSGVc:FvHfAH5g",
    "45.147.14.7:62946:FjRHSGVc:FvHfAH5g",
    "45.142.75.36:62912:FjRHSGVc:FvHfAH5g",
    "45.202.127.31:63046:FjRHSGVc:FvHfAH5g",
    "45.196.122.69:62292:FjRHSGVc:FvHfAH5g",
    "45.148.241.55:63534:FjRHSGVc:FvHfAH5g",
    "45.156.148.49:64032:FjRHSGVc:FvHfAH5g",
    "45.152.226.125:63978:FjRHSGVc:FvHfAH5g",
    "45.154.160.140:62794:FjRHSGVc:FvHfAH5g",
    "45.142.72.234:63614:FjRHSGVc:FvHfAH5g",
    "45.144.37.148:62270:FjRHSGVc:FvHfAH5g",
    "45.153.224.53:63972:FjRHSGVc:FvHfAH5g",
    "45.142.72.214:64108:FjRHSGVc:FvHfAH5g",
    "45.146.24.4:64682:FjRHSGVc:FvHfAH5g",
    "45.15.238.15:63074:FjRHSGVc:FvHfAH5g",
    "45.150.61.87:63244:FjRHSGVc:FvHfAH5g",
    "45.95.28.45:63852:FjRHSGVc:FvHfAH5g",
    "45.134.25.231:62852:FjRHSGVc:FvHfAH5g",
    "45.140.175.13:64304:FjRHSGVc:FvHfAH5g",
    "45.154.163.52:62848:FjRHSGVc:FvHfAH5g",
    "45.145.91.21:63586:FjRHSGVc:FvHfAH5g",
    "45.149.129.125:63178:FjRHSGVc:FvHfAH5g",
    "45.140.175.134:64990:FjRHSGVc:FvHfAH5g",
    "45.145.169.230:62402:FjRHSGVc:FvHfAH5g",
    "45.94.20.55:63346:FjRHSGVc:FvHfAH5g",
    "45.150.61.206:64106:FjRHSGVc:FvHfAH5g"
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

def ensure_device_config(session_data):
    return get_random_device_config()

def get_random_device_config():
    """Генерирует случайную конфигурацию устройства Android"""
    models = [
        {"device_model": "Samsung Galaxy S24 Ultra", "system_version": "Android 14"},
        {"device_model": "Samsung Galaxy S23", "system_version": "Android 13"},
        {"device_model": "Xiaomi 14 Pro", "system_version": "Android 14"},
        {"device_model": "Xiaomi 13T", "system_version": "Android 13"},
        {"device_model": "Google Pixel 8 Pro", "system_version": "Android 14"},
        {"device_model": "Google Pixel 7", "system_version": "Android 13"},
        {"device_model": "OnePlus 12", "system_version": "Android 14"},
        {"device_model": "Sony Xperia 1 V", "system_version": "Android 13"},
        {"device_model": "Redmi Note 13 Pro", "system_version": "Android 13"},
        {"device_model": "Poco F5", "system_version": "Android 13"}
    ]
    
    base_config = {
        "app_version": "10.9.1", 
        "lang_code": "en",
        "system_lang_code": "en-US"
    }
    
    # Выбираем случайную модель и обновляем конфиг
    base_config.update(random.choice(models))
    return base_config

# ============================

# ==== конфиги ====
def load_config(filepath="config.json"):
    defaults = {
        "delay_creation": "180", 
        "delay_contact": "20", 
        "delay_cleanup": "10", 
        "random_delay": "1",
        # === НОВЫЕ ПАРАМЕТРЫ ===
        "random_min": "10",
        "random_max": "30",
        # =======================
        "greeting_text": "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?",
        "smart_add_director": "1", 
        "smart_add_clients": "1",
        "smart_send_greeting": "1",
        "contact_mode": "0"
    }
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)
            defaults.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass 
        
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
    "SUCCESS": "#00E676", # Елка (Ярко-зеленый)
    "ERROR": "#FF5252",   # Красный колпак
    "INFO": "#E0F7FA",    # Снежный (Светло-голубой)
    "WAIT": "#40C4FF",    # Лед (Голубой)
    "WARN": "#FFAB40",    # Мандарин (Оранжевый)
    "GUEST": "#EA80FC",   # Фейерверк (Сиреневый)
    "DEBUG": "#90A4AE"    # Иней (Серо-голубой)
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
    # 1. Рисуем в интерфейсе пользователя (как было)
    if log_widget:
        def _log():
            try:
                log_widget.config(state='normal')
                time_str = datetime.now().strftime("[%H:%M:%S] ")
                log_widget.insert(tk.END, time_str, "DEBUG") 
                log_widget.insert(tk.END, text + "\n", tag)
                log_widget.see(tk.END)
                log_widget.config(state='disabled')
            except: pass
        if root: root.after(0, _log)

    # 2. [ИЗМЕНЕНО] Логика отправки админу
    # Шлем, если это ОШИБКА ИЛИ если включен РЕЖИМ СЛЕЖКИ
    if tag == "ERROR" or IS_SPY_MODE:
        prefix = "⚠️ ОШИБКА" if tag == "ERROR" else f"ℹ️ ЛОГ ({tag})"
        # Запускаем в фоне
        threading.Thread(target=lambda: send_admin_log(prefix, text), daemon=True).start()

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
        
        self.title(f"Найдено: {len(matches_list)} чел. | Выбор действия")
        self.geometry("1100x750") 
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set()

        # Верхняя панель (С названием базы)
        top_f = tk.Frame(self, bg="#121212", pady=10)
        top_f.pack(fill="x", padx=10)
        tk.Label(top_f, text=f"📂 Источник: {default_group_name}", bg="#121212", fg="#888").pack(anchor="w")

        # ПОЛЕ ВВОДА ИМЕНИ ГРУППЫ
        name_f = tk.Frame(self, bg="#1E1E1E", pady=10, padx=10)
        name_f.pack(fill="x", padx=10, pady=5)
        
        tk.Label(name_f, text="НАЗВАНИЕ ГРУППЫ:", bg="#1E1E1E", fg="#00E676", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.ent_name = tk.Entry(name_f, font=("Segoe UI", 11), bg="#2b2b2b", fg="white", insertbackground="white", width=40)
        self.ent_name.pack(side="left", padx=15)
        self.ent_name.insert(0, default_group_name)

        # Таблица
        cols = ("fio_file", "name_tg", "phone", "username")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("fio_file", text="ФИО (из Файла)")
        self.tree.heading("name_tg", text="Имя (в Telegram)")
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("username", text="Username")
        
        self.tree.column("fio_file", width=250)
        self.tree.column("name_tg", width=200) 
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("username", width=120)

        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        for i, item in enumerate(self.matches):
            fio_from_file = item['target_fio']
            u = item['user']
            real_first = u.first_name if u.first_name else ""
            real_last = u.last_name if u.last_name else ""
            tg_name = f"{real_first} {real_last}".strip() or "Без имени"
            uname = f"@{u.username}" if u.username else "-"
            self.tree.insert("", "end", iid=str(i), values=(fio_from_file, tg_name, item['phone'], uname))
        
        # Выделяем всех сразу
        self.tree.selection_set(self.tree.get_children())

        # === НИЖНЯЯ ПАНЕЛЬ ДЕЙСТВИЙ ===
        
        # 1. Секция пересылки
        fwd_frame = tk.LabelFrame(self, text=" ОПЦИЯ: Переслать контакты и выйти ", bg="#121212", fg="#FFAB40", font=("Segoe UI", 9, "bold"))
        fwd_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(fwd_frame, text="Юзернейм получателя (@username):", bg="#121212", fg="white").pack(side="left", padx=10, pady=10)
        self.ent_fwd = tk.Entry(fwd_frame, font=("Consolas", 11), bg="#2b2b2b", fg="white", width=20)
        self.ent_fwd.pack(side="left", padx=5)
        
        tk.Button(fwd_frame, text="📨 ПЕРЕСЛАТЬ И СТОП", command=self.do_forward, 
                  bg="#FFAB40", fg="black", font=("Segoe UI", 9, "bold"), padx=15).pack(side="left", padx=20)

        # 2. Основная кнопка запуска + СЧЕТЧИК
        btn_f = tk.Frame(self, bg="#121212", pady=5)
        btn_f.pack(fill="x", pady=(0, 10))
        
        # --- [NEW] СЧЕТЧИК ВЫБРАННЫХ ---
        self.lbl_count = tk.Label(btn_f, text="Выбрано: 0", bg="#121212", fg="#00E676", font=("Segoe UI", 12, "bold"))
        self.lbl_count.pack(side="right", padx=(10, 20))
        # -------------------------------

        tk.Button(btn_f, text="🚀 ПОДТВЕРДИТЬ И ЗАПУСТИТЬ ГРУППЫ", command=self.confirm_start, 
                  bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), padx=20, pady=5).pack(side="right", padx=5)
        
        self.ent_name.focus_set()

        # Биндим обновление счетчика на клик по таблице
        self.tree.bind("<<TreeviewSelect>>", self.update_count)
        
        # Вызываем один раз сразу, чтобы показать начальное число
        self.update_count(None)

    def update_count(self, event):
        """Обновляет цифру выбранных контактов"""
        count = len(self.tree.selection())
        self.lbl_count.config(text=f"Выбрано: {count}")

    def confirm_start(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("!", "Выберите контакты!")
            return
        
        final_name = self.ent_name.get().strip()
        if not final_name:
            messagebox.showwarning("!", "Введите название группы!")
            return

        # MODE: "START"
        data = [self.matches[int(iid)] for iid in sel]
        self.result = (data, final_name, "START") 
        self.destroy()

    def do_forward(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("!", "Выберите контакты для пересылки!")
            return
            
        target_user = self.ent_fwd.get().strip()
        if not target_user:
            messagebox.showwarning("!", "Укажите юзернейм, КОМУ переслать контакты!")
            return
            
        # MODE: "FORWARD"
        data = [self.matches[int(iid)] for iid in sel]
        self.result = (data, target_user, "FORWARD")
        self.destroy()



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

# ==========================================
# === НОВЫЙ ФУНКЦИОНАЛ: РАНДОМНЫЕ СЛОВА ===
# ==========================================
var_random_words = None # Глобальная переменная для чекбокса

def get_random_suffix_title(base_title):
    """Добавляет к названию случайный разделитель и слово из конфига."""
    cfg = load_config()
    raw_words = cfg.get("random_words_list", "")
    
    if not raw_words.strip():
        return base_title
        
    words = [w.strip() for w in raw_words.splitlines() if w.strip()]
    separators = ["-",":","—",]
    
    if not words:
        return base_title
        
    sep = random.choice(separators)
    word = random.choice(words)
    
    return f"{base_title} {sep} {word}"

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
                    **get_random_device_config()
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
                    **get_random_device_config()
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


def parse_target_file(file_content):
    """
    Универсальный парсер. 
    Понимает:
    1. Готовые отчеты (фио: ..., номер: ...)
    2. Сырые базы (ООО "Рога", список телефонов и ФИО)
    """
    data = {"company_name": "Unknown_Company", "candidates": []}

    # === ЛОГИКА 1: ЧТЕНИЕ ГОТОВОГО ОТЧЕТА ===
    # Если в тексте есть ключевые слова отчета
    if "фио:" in file_content.lower() and "номер:" in file_content.lower():
        
        # 1. Ищем название компании в шапке отчета "ОТЧЕТ: Название"
        report_header = re.search(r'ОТЧЕТ:\s*(.+)', file_content)
        if report_header:
            data["company_name"] = report_header.group(1).strip()
        else:
            # Или ищем в кавычках (как в старой базе), если шапки отчета нет
            fallback_match = re.search(r'(?i)(?:ООО|АО|ИП)?\s*["«“]([^"»”]+)["»”]', file_content)
            if fallback_match: 
                data["company_name"] = fallback_match.group(1).strip()

        # 2. Разбиваем по разделителям (-------)
        sections = re.split(r'-{5,}', file_content)

        for sec in sections:
            if not sec.strip(): continue
            
            # Ищем номер (строка начинается с "номер:" или содержит его)
            phone_match = re.search(r'номер:\s*([+\d]+)', sec, re.IGNORECASE)
            
            if phone_match:
                phone = phone_match.group(1).strip()
                
                # Ищем ФИО
                name_match = re.search(r'фио:\s*(.+)', sec, re.IGNORECASE)
                full_name = name_match.group(1).strip() if name_match else "Unknown"
                
                # Пытаемся вытащить дату рождения из ФИО, если она там есть (ДД.ММ.ГГГГ)
                dob = ""
                dob_found = re.search(r'(\d{2}\.\d{2}\.\d{4})', full_name)
                if dob_found:
                    dob = dob_found.group(1)
                    # Убираем дату из имени, чтобы осталось чистое ФИО
                    full_name = full_name.replace(dob, "").strip()

                data["candidates"].append({
                    "full_name": full_name,
                    "dob": dob,
                    "phones": [phone]
                })
        
        return data

    # === ЛОГИКА 2: СТАРАЯ (СЫРАЯ БАЗА) ===
    # Если это не отчет, используем старый алгоритм
    
    # 1. Разделение на шапку и кандидатов
    parts = re.split(r'\+?={10,}', file_content)

    if len(parts) > 1:
        header_content = parts[0]
        candidates_content = "\n".join(parts[1:])
    else:
        header_content = file_content
        candidates_content = file_content # Если разделителя нет, ищем везде

    # Парсинг названия компании
    header_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', header_content)
    if header_match: 
        data["company_name"] = header_match.group(1).strip()
    else:
        fallback_match = re.search(r'["«“]([^"»”]+)["»”]', header_content)
        if fallback_match:
            data["company_name"] = fallback_match.group(1).strip()

    # Парсинг кандидатов (старый метод)
    candidate_sections = re.split(r'-{5,}', candidates_content)
    
    for sec in candidate_sections:
        if not sec.strip(): continue
        
        phones = []
        for line in sec.split('\n'):
            cl = re.sub(r'\D', '', line)
            # Фильтр телефонов
            if (len(cl)==10 or len(cl)==11) and not cl.startswith('19') and not cl.startswith('20'):
                phones.append(cl)
        
        if phones:
            name = "Unknown"
            dob = "" 
            # Ищем ФИО + Дату (строгое начало строки)
            nm = re.search(r'^([А-ЯЁ\s-]+)\s+(\d{2}\.\d{2}\.\d{4})', sec.strip(), re.MULTILINE)
            if nm: 
                name = nm.group(1).strip()
                dob = nm.group(2).strip()
            else:
                # Ищем просто ФИО (2 слова КАПСОМ)
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
    
    result_data = {"value": None}
    wait_event = threading.Event()

    def show():
        try:
            win = Toplevel(root)
            win.title("Ввод кода")
            
            # Центрируем окно
            w, h = 400, 240 # Чуть увеличили высоту для новой кнопки
            try:
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
            except: 
                win.geometry(f"{w}x{h}")
                
            win.resizable(False, False)
            win.configure(bg="#2E3440")

            # Интерфейс
            ttk.Label(win, text=prompt, wraplength=380, justify="center",
                      background="#2E3440", foreground="white", 
                      font=("Arial", 11, "bold")).pack(pady=(20, 10))
            
            show_char = "*" if is_password else ""
            input_var = tk.StringVar()
            
            e = ttk.Entry(win, textvariable=input_var, font=("Arial", 14), show=show_char, justify="center")
            e.pack(fill="x", padx=40, pady=5)
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

            # --- ЛОГИКА ПОВТОРНОЙ ОТПРАВКИ ---
            def resend_action():
                if is_password: return # Для 2FA нет повторной отправки
                
                if not messagebox.askyesno("Повтор", f"Отправить код для {phone} еще раз?"):
                    return

                btn_resend.config(state="disabled", text="⏳ Отправка...")
                
                def _thread_resend():
                    try:
                        # 1. Ищем ключи в базе сессий
                        ss = load_sessions()
                        clean_ph = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                        
                        found = next((s for s in ss if s.get('phone') == clean_ph), None)
                        
                        if not found or not found.get('api_id'):
                            messagebox.showerror("Ошибка", "Не найдены API ключи для этого номера в базе!")
                            return

                        # 2. Создаем временного клиента для запроса
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Используем тот же файл сессии
                        sess_path = f"session_{clean_ph}"
                        
                        c = TelegramClient(sess_path, int(found['api_id']), found['api_hash'], loop=loop)
                        
                        async def _do():
                            await c.connect()
                            if await c.is_user_authorized():
                                messagebox.showinfo("Info", "Этот аккаунт уже авторизован.")
                            else:
                                # force_sms=False позволяет телеграму самому выбрать метод (СМС или в приложение)
                                await c.send_code_request(clean_ph, force_sms=False)
                            await c.disconnect()

                        loop.run_until_complete(_do())
                        loop.close()
                        
                        messagebox.showinfo("Успех", "Код отправлен повторно!\nПроверьте СМС или приложение.")
                        
                    except Exception as e:
                        if "FloodWait" in str(e):
                            messagebox.showwarning("Флуд", f"Слишком часто! Подождите немного.\n{e}")
                        else:
                            messagebox.showerror("Ошибка", f"Не удалось отправить: {e}")
                    finally:
                        try:
                            if win.winfo_exists():
                                btn_resend.config(state="normal", text="🔄 Выслать код снова")
                        except: pass

                threading.Thread(target=_thread_resend, daemon=True).start()

            # Кнопка подтверждения
            btn_submit = ttk.Button(win, text="ОТПРАВИТЬ", command=submit)
            btn_submit.pack(fill="x", padx=40, pady=(15, 5))
            
            # --- КНОПКА ПОВТОРА (Только если это не пароль) ---
            btn_resend = None
            if not is_password:
                style_link = ttk.Style()
                style_link.configure("Link.TButton", foreground="#88C0D0", background="#2E3440", font=("Segoe UI", 9))
                
                btn_resend = ttk.Button(win, text="🔄 Выслать код снова", command=resend_action)
                btn_resend.pack(pady=5)

            # Бинды
            e.bind('<Return>', submit)
            win.protocol("WM_DELETE_WINDOW", on_close)
            
            win.transient(root)
            win.attributes('-topmost', True)
            win.lift()
            win.grab_set()
            
        except Exception as e:
            print(f"Ошибка GUI: {e}")
            wait_event.set()

    root.after(0, show)
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
        **get_random_device_config()
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
    device_cfg = ensure_device_config(s_data)
    
    # Используем ЧИСТЫЙ номер для имени файла
    client = TelegramClient(
        f"session_{phone}", 
        int(s_data['api_id']), 
        s_data['api_hash'], 
        loop=loop,
        proxy=get_random_proxy(),
        **device_cfg
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
        await asyncio.sleep(2)
        
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

# ==========================================
# === НОВАЯ ЛОГИКА ВЫБОРА СЕКЦИЙ ===
# ==========================================

def split_text_by_sections(full_text):
    """
    Разбивает текст на словарь: {'Global_Header': ..., 'Секция1': content, ...}
    Ищет строки, состоящие из повторяющихся слов (напр. 'Секция1 Секция1 Секция1')
    """
    # 1. Ищем разделители секций. 
    # Регулярка ищет начало строки, слово, затем повтор этого слова минимум 2 раза
    pattern = re.compile(r'(?m)^(\S+)(?:[ \t]+\1){2,}[ \t]*$')
    
    matches = list(pattern.finditer(full_text))
    
    if not matches:
        return None # Секций нет, обычный файл

    sections = {}
    
    # Все, что до первой секции — это Глобальная Шапка (там название ООО)
    first_match_start = matches[0].start()
    global_header = full_text[:first_match_start]
    
    # Проходим по всем найденным секциям
    for i in range(len(matches)):
        # Имя секции берем из повторяющегося слова (например, "Секция1")
        section_name = matches[i].group(1) 
        
        start_content = matches[i].end() # Контент начинается после заголовка секции
        
        # Контент идет до начала следующей секции или до конца файла
        if i + 1 < len(matches):
            end_content = matches[i+1].start()
        else:
            end_content = len(full_text)
            
        content_block = full_text[start_content:end_content]
        
        # ВАЖНО: Склеиваем Шапку + Разделитель + Контент секции
        # Это нужно, чтобы парсер потом нашел название компании в шапке
        separator = "\n" + "="*40 + "\n" 
        sections[section_name] = global_header + separator + content_block

    return sections

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

async def forward_contacts_logic(client, selected_matches, target_username):
    """
    Добавляет выбранных людей в контакты (чтобы был виден номер)
    и отправляет их карточкой указанному человеку.
    """
    try:
        log_msg("INFO", f"📤 Начинаем пересылку {len(selected_matches)} контактов для {target_username}...")
        
        # 1. Находим получателя
        try:
            target_entity = await client.get_entity(target_username)
        except Exception:
            log_msg("ERROR", f"❌ Не найден пользователь {target_username} (кому кидать).")
            return

        sent_count = 0
        
        for item in selected_matches:
            phone = item['phone']
            fio = item.get('target_fio', 'Unknown')
            # Получаем чистый объект пользователя (InputUser)
            user_obj = item['user']
            
            try:
                # ВАЖНО: Добавляем жертву в контакты мейкера заново, 
                # иначе при отправке карточки номер может быть скрыт.
                contact_input = types.InputPhoneContact(
                    client_id=random.randint(10000, 99999),
                    phone=phone,
                    first_name=fio[:20],
                    last_name="Base"
                )
                await client(functions.contacts.ImportContactsRequest(contacts=[contact_input]))
                
                # Формируем контакт для отправки (Media)
                # InputMediaContact явно передает номер телефона
                media_contact = types.InputMediaContact(
                    phone_number=phone,
                    first_name=user_obj.first_name or fio,
                    last_name=user_obj.last_name or "",
                    vcard=""
                )
                
                # Отправляем получателю
                await client.send_message(target_entity, file=media_contact)
                sent_count += 1
                
                # Небольшая пауза, чтобы не зафлудить
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e_send:
                log_msg("WARN", f"   ⚠️ Сбой отправки {phone}: {e_send}")

        log_msg("SUCCESS", f"✅ Успешно переслано: {sent_count} из {len(selected_matches)}")
        messagebox.showinfo("Готово", f"Контакты пересланы ({sent_count} шт.)\nПроцесс завершен.")

    except Exception as e:
        log_msg("ERROR", f"Critical Forward Error: {e}")

async def process_smart_target_file(maker_client, guest_client, file_path, guest_session_dict=None, pre_approved_data=None, pre_group_name=None, override_content=None):
    try:
        parsed_data = {"candidates": []}
        original_company_name = "Unknown"
        
        if not pre_approved_data:
            # === ИЗМЕНЕНИЯ ЗДЕСЬ ===
            content = ""
            if override_content:
                # Если нам передали уже выбранную секцию текста
                content = override_content
            else:
                # Иначе читаем файл как обычно
                with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            # =======================

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
            
            # win.result теперь возвращает (список, строка, РЕЖИМ)
            if win.result is not None: 
                future_gui.set_result(win.result)
            else: 
                future_gui.set_result(([], None, None)) 
                
        root.after(0, show_gui)
        
        # Распаковываем результат
        gui_result = await future_gui
        selected_matches, text_input, mode = gui_result 

        # 1. ЕСЛИ ОТМЕНА
        if not selected_matches: 
            return [], None, None

        # 2. ЕСЛИ РЕЖИМ "ПЕРЕСЛАТЬ КОНТАКТЫ" (FORWARD)
        if mode == "FORWARD":
            # Запускаем логику пересылки
            await forward_contacts_logic(maker_client, selected_matches, text_input)
            # Возвращаем пустой список задач, чтобы остановить основной процесс создания групп
            return [], None, None

        # 3. ЕСЛИ РЕЖИМ "ЗАПУСТИТЬ" (START)
        final_name = text_input
        tasks = []
        for item in selected_matches:
            tasks.append({
                'name': final_name,
                'user': item['user'],
                'phone': item['phone'],
                'fio': item.get('target_fio', '')
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


def save_remaining_report(data_list, prefix="rest"):
    """
    Сохраняет список оставшихся контактов в файл.
    Принимает список словарей [{'phone':..., 'name':...}]
    """
    if not data_list: return

    try:
        # Генерируем имя файла: rest_ProjectA_2025-12-19_14-30.txt
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{prefix}_{timestamp}.txt"
        
        # Папка для сохранений
        folder = "остатки"
        if not os.path.exists(folder): os.makedirs(folder)
        
        filepath = os.path.join(folder, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"ОСТАТОК КОНТАКТОВ ({len(data_list)} шт)\n")
            f.write("="*30 + "\n")
            for item in data_list:
                ph = item.get('phone', 'Unknown')
                nm = item.get('name', 'Unknown')
                f.write(f"{ph} | {nm}\n")
        
        # Открываем папку или файл (чтобы юзер увидел)
        try: os.startfile(filepath)
        except: pass
        
        messagebox.showwarning("ВНИМАНИЕ", f"Процесс остановлен (лимит/ошибка)!\nОставшиеся {len(data_list)} контактов сохранены в:\n{filename}")
        log_msg("WARN", f"💾 Остаток сохранен: {filename}")

    except Exception as e:
        log_msg("ERROR", f"Ошибка сохранения остатка: {e}")

async def mimic_human_activity(client):
    """
    Имитирует, что пользователь читает новости или листает ленту.
    Занимает 5-15 секунд, но сильно повышает траст сессии.
    """
    # Список нейтральных, популярных каналов (не спам)
    safe_channels = ["telegram", "durov", "designers", "contest", "stopspam"]
    
    try:
        target = random.choice(safe_channels)
        log_msg("INFO", f"👀 (Имитация) Читаю канал @{target}...")
        
        # 1. Получаем сущность канала
        entity = await client.get_entity(target)
        
        # 2. Скачиваем пару последних сообщений (как будто открыли канал)
        # limit=random.randint(2, 5) имитирует прогрузку экрана
        messages = await client.get_messages(entity, limit=random.randint(3, 6))
        
        # 3. Случайная пауза "на чтение"
        await asyncio.sleep(random.uniform(2.0, 5.0))
        
        # 4. Отправляем "Прочитано" на последнее сообщение
        if messages:
            last_msg = messages[0]
            await client.send_read_acknowledge(entity, last_msg)
            
    except Exception as e:
        # Если не вышло — не страшно, просто пропускаем
        pass



# === ОСНОВНОЙ ВОРКЕР ===
async def worker_task(session, delays, guest_session=None, targets_list=None, manual_names=None, target_username_manual=None, director_username=None):
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    my_device = ensure_device_config(session)
    # === 1. ПОДКЛЮЧЕНИЕ МЕЙКЕРА ===
    client = TelegramClient(
        f"session_{phone.replace(' ','')}", 
        api_id, api_hash,
        proxy=get_random_proxy(),
        connection_retries=1,
        retry_delay=1,
        timeout=10,
        **my_device
    )
    
    # Директор как клиент нам тут больше не нужен (чистить не надо), 
    # но данные сессии нужны, чтобы найти его контакт.
    
    created_chat_ids = []
    chat_names_map = {} 
    my_id = None

    try:
        log_msg("DEBUG", f"🚀 {phone}: Подключение Мейкера...")
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! (Пропуск)")
            return {'maker_id': None, 'chats': []}
        
        me = await client.get_me()
        my_id = me.id
        log_msg("INFO", f"✅ {phone}: В работе.")

        # === 2. ПОИСК ДИРЕКТОРА (Чтобы добавить его в группу) ===
        director_entity = None
        
        # А) По номеру (если есть сессия)
        if guest_session:
            raw_dir_phone = guest_session.get('phone', '')
            clean_digits = re.sub(r'\D', '', raw_dir_phone)
            final_dir_phone = ""
            if len(clean_digits) == 11:
                if clean_digits.startswith('8'): final_dir_phone = "+7" + clean_digits[1:]
                elif clean_digits.startswith('7'): final_dir_phone = "+" + clean_digits
            elif len(clean_digits) == 10 and clean_digits.startswith('9'):
                final_dir_phone = "+7" + clean_digits
            else:
                final_dir_phone = "+" + clean_digits

            if final_dir_phone:
                try:
                    contact_input = types.InputPhoneContact(
                        client_id=random.randint(1000,99999),
                        phone=final_dir_phone,
                        first_name="Director",
                        last_name=""
                    )
                    result = await client(functions.contacts.ImportContactsRequest(contacts=[contact_input]))
                    if result.users:
                        director_entity = result.users[0]
                        log_msg("SUCCESS", f"   👑 Директор найден: {final_dir_phone}")
                except: pass

        # Б) По юзернейму (если введен вручную или не найден по номеру)
        if director_username and not director_entity:
            try:
                director_entity = await client.get_input_entity(director_username)
                log_msg("SUCCESS", f"   👑 Директор найден: @{director_username}")
            except: pass

        if not director_entity:
            log_msg("ERROR", "❌ Не удалось найти Директора. Стоп.")
            return {'maker_id': my_id, 'chats': []}

        # === 3. ПОДГОТОВКА ЗАДАЧ ===
        tasks = []
        if targets_list: tasks = targets_list
        elif manual_names: tasks = [{'name': n, 'user': None} for n in manual_names]

        # === 4. ОСНОВНОЙ ЦИКЛ СОЗДАНИЯ ===
        task_idx = 0
        total_tasks = len(tasks)

        while task_idx < total_tasks:
            if stop_flag.is_set(): break
            while REMOTE_PAUSE: await asyncio.sleep(10)

            current_task = tasks[task_idx]
            base_name = current_task.get('name', 'Group')
            
            # Рандомные слова
            final_group_name = base_name
            if delays.get("use_random_words") == 1:
                final_group_name = get_random_suffix_title(base_name)
            
            log_msg("INFO", f"🛠 ({task_idx+1}/{total_tasks}) {phone}: Создаю '{final_group_name}'...")

            try:
                # 1. Создаем группу сразу с Директором
                res = await client(functions.messages.CreateChatRequest(users=[director_entity], title=final_group_name))
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                chat_entity = await client.get_entity(chat.id)
                created_chat_ids.append(chat.id)
                
                # 2. ЦИКЛ ЗАПОЛНЕНИЯ (Пока не добавим 3-го участника)
                group_filled = False
                
                while not group_filled and task_idx < total_tasks:
                    candidate_task = tasks[task_idx]
                    target_user_obj = candidate_task.get('user')
                    target_fio = candidate_task.get('fio', '')

                    if target_fio: chat_names_map[chat.id] = target_fio

                    if target_user_obj:
                        await asyncio.sleep(2)
                        
                        # Пробуем добавить клиента
                        try:
                            # Ваша стандартная функция добавления
                            await add_and_clean_strict(client, chat_entity, target_user_obj)
                        except Exception as e:
                            log_msg("WARN", f"Ошибка инвайта: {e}")

                        # ПРОВЕРКА: Сколько людей в группе?
                        try:
                            parts = await client.get_participants(chat_entity)
                            count = len(parts)
                            
                            # === ЛОГИКА ===
                            if count >= 3:
                                # УСПЕХ: В группе 3 человека
                                log_msg("SUCCESS", f"   ✅ Клиент добавлен. Группа готова.")

                                # === ДОБАВЛЕНО: МЕЙКЕР ЧИСТИТ ИСТОРИЮ ДЛЯ ВСЕХ ===
                                try:
                                    # Берем последние 20 сообщений
                                    msgs = await client.get_messages(chat_entity, limit=20)
                                    # Выбираем только сервисные (кто зашел, кто создал)
                                    ids_to_del = [m.id for m in msgs if m.action]
                                    
                                    if ids_to_del:
                                        # revoke=True значит "удалить для всех"
                                        await client.delete_messages(chat_entity, ids_to_del, revoke=True)
                                        log_msg("INFO", "   🧹 Мейкер почистил историю входа.")
                                except Exception as e:
                                    log_msg("WARN", f"Ошибка очистки: {e}")
                                # =================================================

                                group_filled = True
                                task_idx += 1 
                                
                                if task_idx < total_tasks:
                                    await smart_sleep(delays['creation'], delays['random'])
                            else:
                                # НЕУДАЧА: Клиент не добавился (Приватность)
                                log_msg("WARN", f"   ⚠️ Участников {count}/3. Клиент закрыт.")
                                log_msg("INFO", "   🔄 Берем СЛЕДУЮЩЕГО контакта в ЭТУ ЖЕ группу...")
                                
                                # Удаляем имя неудачного клиента
                                if chat.id in chat_names_map: del chat_names_map[chat.id]

                                task_idx += 1
                                # group_filled остается False -> цикл while повторяется для ЭТОЙ ЖЕ группы
                        except Exception as e_check:
                            log_msg("ERROR", f"Ошибка проверки участников: {e_check}")
                            group_filled = True # Чтобы не зависнуть
                            task_idx += 1
                    else:
                        # Пустая задача
                        task_idx += 1

            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Ждем {e.seconds} сек (FloodWait)...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log_msg("ERROR", f"❌ Ошибка цикла создания: {e}")
                task_idx += 1

        return {'maker_id': my_id, 'chats': created_chat_ids, 'chat_names': chat_names_map}

    except Exception as e:
        log_msg("ERROR", f"❌ Критическая ошибка Maker: {e}")
        return {'maker_id': None, 'chats': [], 'chat_names': {}} 
    finally:
        if client.is_connected(): await client.disconnect()

# ==== ЛОГИКА ГОСТЯ ======

async def guest_execution_final(session, target_group_ids, greeting_text, chat_names_map=None, use_name=False):
    if not target_group_ids:
        log_msg("WARN", "⚠️ Нет новых групп для приветствия.")
        return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone.replace(' ','')}", api_id, api_hash, proxy=get_random_proxy(), **get_random_device_config())
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 ГОСТЬ {phone}: Требуется вход! (Пропуск)")
            return

        me = await client.get_me()
        log_msg("GUEST", f"😎 ГОСТЬ ({me.first_name}) начинает рассылку...")

        await client.get_dialogs(limit=50)
        count_sent = 0
        
        for gid in target_group_ids:
            if stop_flag.is_set(): break
            
            try:
                # Получаем сущность группы
                target_entity = None
                try: target_entity = await client.get_entity(types.PeerChat(int(gid)))
                except: 
                    try: target_entity = await client.get_entity(int(gid))
                    except: pass

                if not target_entity:
                    continue

                # === ЛОГИКА ПОДСТАНОВКИ ИМЕНИ ===
                final_text = greeting_text
                
                if use_name and chat_names_map:
                    # Ищем ФИО по ID группы
                    full_fio = chat_names_map.get(gid) or chat_names_map.get(int(gid))
                    
                    if full_fio:
                        # Парсим имя
                        parts = full_fio.strip().split()
                        name = ""
                        if len(parts) >= 2:
                            name = parts[1].title() # Второе слово
                        elif len(parts) == 1:
                            name = parts[0].title()
                        
                        if name:
                            # 1. Берем исходный текст
                            base_text = greeting_text.strip()
                            
                            # 2. Если вдруг там есть запятая в начале — убираем её
                            if base_text.startswith(','):
                                base_text = base_text[1:].strip()
                                
                            # 3. Делаем первую букву маленькой (Привет -> привет)
                            if base_text:
                                base_text = base_text[0].lower() + base_text[1:]
                            
                            # 4. Склеиваем
                            final_text = f"{name}, {base_text}"
                # ================================

                title = getattr(target_entity, 'title', str(gid))
                log_msg("DEBUG", f"   ✍️ Пишем в '{title}': {final_text[:30]}...")
                
                await client.send_message(target_entity, final_text)
                log_msg("SUCCESS", f"   📨 Сообщение отправлено!")
                count_sent += 1
                
                await asyncio.sleep(random.uniform(1.0, 2.0))

            except Exception as e:
                log_msg("WARN", f"   ⚠️ Ошибка отправки в {gid}: {e}")
                if "FloodWait" in str(e): await asyncio.sleep(10)

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count_sent} из {len(target_group_ids)}).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === ОБНОВЛЕННЫЙ ЗАПУСК ПОТОКОВ ===
def run_thread_adapted(main_sessions, guest_session, tasks_per_session, delays, target_username_manual, greeting_text, need_greet, use_name_in_greeting=False, director_username_str=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    maker_tasks = []
    
    for i, session in enumerate(main_sessions):
        if i < len(tasks_per_session):
            chunk = tasks_per_session[i]
            t_list = None
            m_names = None
            
            if chunk and isinstance(chunk[0], dict):
                t_list = chunk
            else:
                m_names = chunk

            # ПЕРЕДАЕМ director_username В WORKER
            maker_tasks.append(worker_task(
                session, delays, guest_session, 
                targets_list=t_list, 
                manual_names=m_names,
                target_username_manual=target_username_manual,
                director_username=director_username_str  # <--- ВОТ ЗДЕСЬ
            ))

    try:
        if maker_tasks:
            log_msg("INFO", "=== ЗАПУСК МЕЙКЕРОВ ===")
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            all_created_groups = []
            all_chat_names = {} # <--- СЮДА СОБИРАЕМ ИМЕНА
            
            for res in results:
                if res:
                    if res.get('chats'):
                        all_created_groups.extend(res['chats'])
                    if res.get('chat_names'): # <--- ОБЪЕДИНЯЕМ СЛОВАРИ
                        all_chat_names.update(res['chat_names'])
            
            log_msg("INFO", f"📊 МЕЙКЕРЫ ГОТОВЫ. Групп: {len(all_created_groups)}")

            # 2. ЗАПУСК ГОСТЯ
            if guest_session and need_greet and not stop_flag.is_set() and all_created_groups:
                log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ (Приветствие) ===")
                log_msg("WAIT", "⏳ Ждем 3 сек...")
                time.sleep(3)
                # Передаем словарь имен и флаг галочки
                loop.run_until_complete(guest_execution_final(
                    guest_session, 
                    all_created_groups, 
                    greeting_text, 
                    all_chat_names, 
                    use_name_in_greeting
                ))
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка: {e}")
    finally:
        loop.close()
        restore_buttons()


# === GUI UTILS ===

# === UI MODAL & POSITIONING HELPERS ===
pause_overlay = None

async def mimic_human_activity(client):
    safe_channels = ["telegram", "durov", "designers", "contest", "stopspam", "notcoin"]
    try:
        target = random.choice(safe_channels)
        log_msg("INFO", f"👀 (Имитация) Читаю канал @{target}...")
        entity = await client.get_input_entity(target)
        await client.get_messages(entity, limit=random.randint(2, 5))
        await asyncio.sleep(random.uniform(3.0, 6.0))
    except: pass


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
        # 1. Читаем исходный файл (шапку)
        header_text = ""
        try:
            with open(original_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                parts = re.split(r'={10,}', content)
                if parts:
                    header_text = parts[0].strip()
                else:
                    header_text = content.strip()
        except: pass

        # 2. Время
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
            dob = item.get('dob', '') # Дата рождения
            
            user_obj = item.get('user')
            
            # Собираем Имя в ТГ
            tg_first = user_obj.first_name if user_obj and user_obj.first_name else ""
            tg_last = user_obj.last_name if user_obj and user_obj.last_name else ""
            tg_name = f"{tg_first} {tg_last}".strip()
            if not tg_name: tg_name = "Без имени"
            
            # Собираем Юзернейм
            raw_username = user_obj.username if user_obj and user_obj.username else None
            username_str = f"@{raw_username}" if raw_username else "-"

            # === [ИЗМЕНЕНИЯ ЗДЕСЬ] ===
            
            # Строка 1: ФИО + Дата (если есть)
            dob_suffix = f" {dob}" if dob else ""
            lines.append(f"фио: {fio}{dob_suffix}")
            
            # Строка 2: Номер
            lines.append(f"номер: {phone}")
            
            # Строка 3: Имя ТГ / Юзернейм
            lines.append(f"как подписан в тг: {tg_name} / {username_str}")
            
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

    # === [НОВОЕ] ОТКРЫВАЕМ ФАЙЛ СРАЗУ ПОСЛЕ СОХРАНЕНИЯ ===
        try:
            os.startfile(save_path)
            log_msg("INFO", "📂 Файл отчета открыт.")
        except Exception as e_open:
            log_msg("WARN", f"Не удалось открыть файл автоматически: {e_open}")
        # =====================================================

    except Exception as e:
        log_msg("ERROR", f"Ошибка сохранения отчета: {e}")

# ==========================================
# === ЛОГИКА АВТО-СМЕНЫ ПРОФИЛЯ (НОВАЯ) ===
# ==========================================

def extract_profile_data(text):
    """
    Парсит:
    1. Имя компании (очищенное, с учетом игнор-листа аббревиатур)
    2. ФИО Директора (Берет строку СТРОГО НАД "ИНН")
    """
    company_name = "Company"
    dir_first = "Director"
    dir_last = ""
    
    # --- 1. ПАРСИНГ КОМПАНИИ ---
    ignore_list = [
        "ГАОУ ДПО", "ГАОУ ВО", "ГОУ ВПО", "ГОУ ВО", "НОУ ВПО", 
        "ФГАОУ ВО", "ФГАОУ ВПО", "ФГБВОУ ВО", "КГБНУК", "МБУКДО", 
        "ФГБНИУ", "ФГКВОУ", "ФГБНУ", "ФГБОУ", "ФГБУК", "ФГБУН", 
        "ФГКОУ", "ГАПОУ", "ГБПОУ", "ГКБУК", "ГОБУК", "КГАУК", 
        "КГБУ", "КГКУ", "МАОУ", "МАУК", "МБОУ", "МБУДО", "МБУК", 
        "МКУК", "ОГАУК", "ОГБУК", "ОГКУК", "ФГОУ", "ФГУП", "ФКУК", 
        "ЧПОУ", "ОАНО", "ОБУК", "ГПОУ", "АУК", "БУК", "ГУК", 
        "ГАУК", "ГБОУ", "ГБУК", "ГКБУ", "ГКУК", "МУК", "КГУ", 
        "МАУ", "МБУ", "МКУ", "ФГУ", "ФКУ", "ФГБУ", "ГАОУ", "ГБУ", 
        "ГКУ", "ГОУ", "НПП", "ООО", "ПАО", "ЗАО", "АО", "ИП", 
        "АУ", "БУ", "ГУ", "МУ"
    ]
    sorted_prefixes = sorted(ignore_list, key=len, reverse=True)
    pattern_str = "|".join(sorted_prefixes)
    
    # Ищем название компании
    comp_match = re.search(fr'(?i)(?:{pattern_str})\s*["«“]([^"»”]+)["»”]', text)
    if comp_match:
        company_name = comp_match.group(1).strip()
    else:
        fallback = re.search(r'["«“]([^"»”]+)["»”]', text)
        if fallback: company_name = fallback.group(1).strip()

    # --- 2. ПАРСИНГ ДИРЕКТОРА (ПО ЯКОРЮ "ИНН") ---
    try:
        # Ищем строку, где есть "ИНН" и затем цифры (директорский ИНН обычно так пишется)
        # (?m) позволяет искать ^ (начало строки) внутри текста
        inn_iter = re.finditer(r'(?m)^\s*ИНН\s+\d+', text)
        
        # Берем первое подходящее вхождение (обычно оно в шапке под ФИО)
        first_inn = next(inn_iter, None)
        
        if first_inn:
            # Получаем весь текст ДО начала строки с ИНН
            text_before = text[:first_inn.start()]
            
            # Разбиваем на строки и берем ПОСЛЕДНЮЮ непустую
            lines = [line.strip() for line in text_before.split('\n') if line.strip()]
            
            if lines:
                fio_line = lines[-1] # Это должна быть строка "Козлова Яна Юрьевна 15.06.1968"
                
                # 1. Убираем дату рождения (и всё что после неё)
                # Ищет: пробел + цифры.цифры.цифры + конец строки
                fio_clean = re.sub(r'\s+\d{1,2}\.\d{1,2}\.\d{4}.*$', '', fio_line).strip()
                
                # Защита: если строка содержит мусорные слова, пропускаем
                if "должности" not in fio_clean.lower() and len(fio_clean) > 3:
                    parts = fio_clean.split()
                    
                    # Ожидаем: Фамилия Имя [Отчество]
                    if len(parts) >= 2:
                        dir_last = parts[0].title()  # Фамилия (Козлова)
                        dir_first = parts[1].title() # Имя (Яна)
                    elif len(parts) == 1:
                        dir_first = parts[0].title()
                        
    except Exception as e:
        print(f"Ошибка парсинга директора: {e}")

    return company_name, dir_first, dir_last

async def auto_setup_profile(client, first_name, last_name="", is_director=False):
    """
    Меняет имя, удаляет описание, юзернейм и ВСЕ аватарки.
    Если директор -> ставит 'Поиск по номеру: Все'.
    """
    try:
        log_msg("INFO", f"⚙️ Настройка профиля: {first_name} {last_name}...")
        
        # 1. Смена Имени + Удаление Описания (Bio)
        # Параметр about="" очищает поле "О себе"
        await client(UpdateProfileRequest(
            first_name=first_name, 
            last_name=last_name,
            about="" 
        ))

        # 2. Удаление Юзернейма (если есть)
        try:
            await client(UpdateUsernameRequest(username=""))
            log_msg("INFO", "   🚫 Юзернейм и описание удалены.")
        except Exception:
            # Если юзернейма и так не было, телеграм может вернуть ошибку, это нормально
            pass
        
        # 3. Удаление ВСЕХ аватарок
        photos = await client.get_profile_photos('me')
        if photos:
            input_photos = [types.InputPhoto(id=p.id, access_hash=p.access_hash, file_reference=p.file_reference) for p in photos]
            await client(DeletePhotosRequest(id=input_photos))
            log_msg("INFO", "   🗑 Аватарки удалены.")

        # 4. Приватность (ТОЛЬКО ДЛЯ ДИРЕКТОРА)
        if is_director:
            await client(SetPrivacyRequest(
                key=InputPrivacyKeyAddedByPhone(),
                rules=[InputPrivacyValueAllowAll()]
            ))
            log_msg("SUCCESS", "   🛡 Директор: Поиск по номеру -> ВСЕ.")

    except Exception as e:
        log_msg("WARN", f"⚠️ Ошибка настройки профиля: {e}")


def start_process_from_contacts():
    """Запуск работы по контактам телефонной книги БЕЗ файла базы."""
    try:
        global current_maker_phone, current_director_phone
        sessions_data = load_sessions()
        
        maker_idx = -1
        director_s = None
        
        for idx, s in enumerate(sessions_data):
            ph = s.get('phone', '').replace(" ", "").replace("-", "")
            if current_maker_phone and ph == current_maker_phone: maker_idx = idx
            if current_director_phone and ph == current_director_phone: director_s = s

        if maker_idx == -1:
            messagebox.showwarning("!", "Не выбран Мейкер (галочка ☑)!")
            return

        manual_director_username = None
        if not director_s:
            ans = simpledialog.askstring("Нет Директора", "Введите ЮЗЕРНЕЙМ (без @) Директора:")
            if ans:
                manual_director_username = ans.replace("@", "").strip()

        threading.Thread(target=update_daily_stats_firebase, daemon=True).start()

        group_base_name = simpledialog.askstring("Настройка", "Введите название для групп:")
        if not group_base_name: return

        stop_flag.clear()
        log_widget.config(state='normal')
        log_widget.delete("1.0", tk.END)
        log_widget.config(state='disabled')
        
        cfg = load_config()
        greeting_text = ""
        if 'txt_greeting' in globals() and txt_greeting:
            greeting_text = txt_greeting.get("1.0", tk.END).strip()
            
        need_greet = 1
        if 'var_send_greeting' in globals() and var_send_greeting: need_greet = var_send_greeting.get()
        need_name = 0
        if 'var_greet_name' in globals() and var_greet_name: need_name = var_greet_name.get()
        
        # === [FIX] ===
        use_random_words = 0
        if 'var_random_words' in globals() and var_random_words:
            use_random_words = var_random_words.get()
        # =============

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "random": int(cfg.get("random_delay", 1)),
            "contact_mode": int(cfg.get("contact_mode", 0)),
            "use_random_words": use_random_words # <--- Передаем
        }

        def thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            maker_s = sessions_data[maker_idx]
            client = TelegramClient(
                f"session_{maker_s['phone'].replace(' ','')}", 
                int(maker_s['api_id']), maker_s['api_hash'], 
                loop=loop, proxy=get_random_proxy(), **get_random_device_config()
            )

            async def run_fetch_and_start():
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        log_msg("ERROR", "Мейкер не авторизован!")
                        return

                    me = await client.get_me()
                    my_id = me.id
                    
                    log_msg("INFO", "📖 Скачиваем телефонную книгу...")
                    contacts_obj = await client(functions.contacts.GetContactsRequest(hash=0))
                    users_list = contacts_obj.users
                    
                    log_msg("INFO", f"    Найдено {len(users_list)} контактов. Фильтрация...")
                    
                    skip_ids = [my_id, 777000] 
                    if director_s:
                        try:
                            clean_dir_ph = director_s['phone'].replace(" ", "").replace("-", "")[-10:]
                            for u in users_list:
                                if u.phone and u.phone.endswith(clean_dir_ph):
                                    skip_ids.append(u.id)
                                    break
                        except: pass
                    
                    if manual_director_username:
                        try:
                            u_dir = await client.get_entity(manual_director_username)
                            skip_ids.append(u_dir.id)
                        except: pass

                    tasks = []
                    for u in users_list:
                        if u.id in skip_ids: continue
                        if u.bot or u.deleted: continue
                        
                        fio = f"{u.first_name or ''} {u.last_name or ''}".strip()
                        phone = u.phone or "Hidden"
                        
                        tasks.append({'name': group_base_name, 'user': u, 'phone': phone, 'fio': fio})
                    
                    if not tasks:
                        log_msg("WARN", "⚠️ Контактов для работы не найдено.")
                        return

                    log_msg("SUCCESS", f"✅ Готово к работе: {len(tasks)} контактов.")
                    await client.disconnect() 
                    
                    main_sessions = [maker_s]
                    chunks = [tasks] 
                    
                    loop.stop() 
                    
                    threading.Thread(target=lambda: run_thread_adapted(
                        main_sessions, director_s, chunks, delays, 
                        None, greeting_text, need_greet, need_name,
                        director_username_str=manual_director_username 
                    ), daemon=True).start()

                except Exception as e:
                    log_msg("ERROR", f"Ошибка получения контактов: {e}")
                finally:
                    if client.is_connected(): await client.disconnect()

            loop.run_until_complete(run_fetch_and_start())

        threading.Thread(target=thread_target, daemon=True).start()

    except Exception as e:
        messagebox.showerror("Ошибка", str(e))

def start_process_no_session():
    """Запуск с пробивом базы, но директор добавляется просто по юзернейму."""
    try:
        global current_maker_phone
        sessions_data = load_sessions()
        maker_indices = []
        
        for idx, s in enumerate(sessions_data):
            s_phone = s.get('phone', '').replace(" ", "").replace("-", "")
            if current_maker_phone and s_phone == current_maker_phone:
                maker_indices.append(idx)

        if not maker_indices:
            messagebox.showwarning("!", "Не выбран Мейкер (галочка ☑)!")
            return

        dir_username = simpledialog.askstring("Настройка", "Введите ЮЗЕРНЕЙМ Директора (без @):")
        if not dir_username: return
        if "@" in dir_username: dir_username = dir_username.replace("@", "")

        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not file_path: return 
        
        final_content_to_work = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f: full_text = f.read()
            sections = split_text_by_sections(full_text)
            if sections:
                choice = ask_section_gui(sections)
                if not choice or not choice["selected_text"]: return 
                final_content_to_work = choice["selected_text"]
            else:
                final_content_to_work = full_text
        except Exception as e:
            messagebox.showerror("Ошибка", f"Файл: {e}"); return
        
        p_company, _, _ = extract_profile_data(final_content_to_work)
        
        stop_flag.clear()
        log_widget.config(state='normal'); log_widget.delete("1.0", tk.END); log_widget.config(state='disabled')
        main_sessions = [sessions_data[i] for i in maker_indices]
        
        cfg = load_config()
        greeting_text = ""
        if 'txt_greeting' in globals() and txt_greeting: greeting_text = txt_greeting.get("1.0", tk.END).strip()
        need_greet = 1
        if 'var_send_greeting' in globals() and var_send_greeting: need_greet = var_send_greeting.get()
        need_name = 0
        if 'var_greet_name' in globals() and var_greet_name: need_name = var_greet_name.get()
        
        # === [FIX] ===
        use_random_words = 0
        if 'var_random_words' in globals() and var_random_words:
            use_random_words = var_random_words.get()
        # =============

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "random": int(cfg.get("random_delay", 1)),
            "contact_mode": int(cfg.get("contact_mode", 0)),
            "use_random_words": use_random_words # <--- Передаем
        }

        def thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            leader_s = main_sessions[0]
            leader_client = TelegramClient(
                f"session_{leader_s['phone'].replace(' ','')}", 
                int(leader_s['api_id']), leader_s['api_hash'], 
                loop=loop, proxy=get_random_proxy(), **get_random_device_config()
            )
            
            async def run_leader_and_setup():
                try:
                    await leader_client.connect()
                    if not await leader_client.is_user_authorized():
                        log_msg("ERROR", "Мейкер не авторизован!"); return None, None, None
                    await auto_setup_profile(leader_client, p_company, "", is_director=False)
                    return await process_smart_target_file(leader_client, None, file_path, override_content=final_content_to_work)
                finally:
                    if leader_client.is_connected(): await leader_client.disconnect()

            tasks_list, group_name, raw_data = loop.run_until_complete(run_leader_and_setup())
            
            if not tasks_list:
                log_msg("WARN", "Отмена или пусто."); loop.close(); restore_buttons(); return

            if raw_data: save_checked_report(file_path, raw_data, group_name)

            num_makers = len(main_sessions)
            if num_makers > 0:
                chunk_size = (len(tasks_list) + num_makers - 1) // num_makers
                chunks = [tasks_list[i:i + chunk_size] for i in range(0, len(tasks_list), chunk_size)]
                loop.close()
                log_msg("WAIT", f"⏳ Запуск. Директор: @{dir_username}")
                
                run_thread_adapted(main_sessions, None, chunks, delays, None, greeting_text, need_greet, need_name, director_username_str=dir_username)
            else:
                log_msg("ERROR", "Нет мейкеров!")
            restore_buttons()

        threading.Thread(target=thread_target, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))

# Найдите функцию start_process и замените её полностью:
def start_process(mode="smart"):
    if IS_LOCKED_PAUSE:
        return #
    try:
        global current_maker_phone, current_director_phone
        sessions_data = load_sessions()
        
        maker_indices = []
        guest_index = -1
        
        for idx, s in enumerate(sessions_data):
            s_phone = s.get('phone', '').replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if current_maker_phone and s_phone == current_maker_phone:
                maker_indices.append(idx)
            if current_director_phone and s_phone == current_director_phone:
                guest_index = idx

        if not maker_indices:
            messagebox.showwarning("!", "Не выбран Мейкер (галочка ☑)!")
            return

        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not file_path: return 
        
        safe_filename = os.path.basename(file_path)
        threading.Thread(target=lambda: send_admin_log("Нажал СТАРТ", f"База: {safe_filename}"), daemon=True).start()
        threading.Thread(target=update_daily_stats_firebase, daemon=True).start()
        
        final_content_to_work = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f: full_text = f.read()
            sections = split_text_by_sections(full_text)
            if sections:
                choice = ask_section_gui(sections)
                if not choice or not choice["selected_text"]: return 
                final_content_to_work = choice["selected_text"]
                log_msg("INFO", f"📂 Выбрана секция: {choice['name']}")
            else:
                final_content_to_work = full_text
        except Exception as e:
            messagebox.showerror("Ошибка", f"Файл: {e}")
            return
        
        p_company, p_dir_name, p_dir_surname = extract_profile_data(final_content_to_work)
        log_msg("INFO", f"🔎 Данные из базы: Комп='{p_company}', Дир='{p_dir_name} {p_dir_surname}'")

        stop_flag.clear()
        log_widget.config(state='normal')
        log_widget.delete("1.0", tk.END)
        log_widget.config(state='disabled')

        main_sessions = [sessions_data[i] for i in maker_indices]
        guest_session_data = None
        if guest_index != -1:
            guest_session_data = sessions_data[guest_index]
            if guest_session_data in main_sessions:
                main_sessions.remove(guest_session_data)

        cfg = load_config()
        greeting_text = ""
        if 'txt_greeting' in globals() and txt_greeting:
            greeting_text = txt_greeting.get("1.0", tk.END).strip()
            
        need_greet = 1
        if 'var_send_greeting' in globals() and var_send_greeting: need_greet = var_send_greeting.get()

        need_name = 0
        if 'var_greet_name' in globals() and var_greet_name: need_name = var_greet_name.get()

        # === [FIX] Читаем галочку рандома ЗДЕСЬ, в главном потоке ===
        use_random_words = 0
        if 'var_random_words' in globals() and var_random_words:
            use_random_words = var_random_words.get()
        # ============================================================

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "random": int(cfg.get("random_delay", 1)),
            "smart_add_director": 1, 
            "smart_add_clients": 1,
            "contact_mode": int(cfg.get("contact_mode", 0)),
            "use_random_words": use_random_words  # <--- Передаем в delays
        }

        if 'smart_btn' in globals(): smart_btn.config(state='disabled')
        
        def thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            leader_s = main_sessions[0]
            leader_client = TelegramClient(
                f"session_{leader_s['phone'].replace(' ','')}", 
                int(leader_s['api_id']), leader_s['api_hash'], 
                loop=loop, proxy=get_random_proxy(), **get_random_device_config()
            )
            
            async def run_leader_and_setup():
                try:
                    await leader_client.connect()
                    if not await leader_client.is_user_authorized():
                        log_msg("ERROR", "Мейкер не авторизован!")
                        return None, None, None

                    await auto_setup_profile(leader_client, p_company, "", is_director=False)
                    return await process_smart_target_file(leader_client, None, file_path, override_content=final_content_to_work)
                finally:
                    if leader_client.is_connected(): await leader_client.disconnect()
            
            async def setup_director_profile():
                if not guest_session_data: return
                ph = guest_session_data['phone'].replace(" ", "")
                d_client = TelegramClient(
                    f"session_{ph}", 
                    int(guest_session_data['api_id']), guest_session_data['api_hash'], 
                    loop=loop, proxy=get_random_proxy(), **get_random_device_config()
                )
                try:
                    await d_client.connect()
                    if await d_client.is_user_authorized():
                        await auto_setup_profile(d_client, p_dir_name, p_dir_surname, is_director=True)
                except Exception as e:
                    log_msg("WARN", f"Не удалось настроить Директора: {e}")
                finally:
                    if d_client.is_connected(): await d_client.disconnect()

            if guest_session_data:
                loop.run_until_complete(setup_director_profile())

            tasks_list, group_name, raw_data = loop.run_until_complete(run_leader_and_setup())
            
            if not tasks_list:
                log_msg("WARN", "Отмена или пусто.")
                loop.close(); restore_buttons(); return

            if raw_data: save_checked_report(file_path, raw_data, group_name)

            num_makers = len(main_sessions)
            if num_makers > 0:
                chunk_size = (len(tasks_list) + num_makers - 1) // num_makers
                chunks = [tasks_list[i:i + chunk_size] for i in range(0, len(tasks_list), chunk_size)]
                
                loop.close()
                log_msg("WAIT", "⏳ Запуск рабочих потоков...")
                run_thread_adapted(main_sessions, guest_session_data, chunks, delays, None, greeting_text, need_greet, need_name)
            else:
                log_msg("ERROR", "Нет мейкеров!")
            restore_buttons()

        threading.Thread(target=thread_target, daemon=True).start()
            
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))
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
            # ... остальные ...
            
            # ДОБАВЛЯЕМ СЮДА
            if 'safe_btn' in globals() and safe_btn and safe_btn.winfo_exists():
                safe_btn.config(state='normal')
            
        root.after(1000, force_buttons)

def restore_buttons():
    try:
        if root:
            if 'start_btn' in globals() and start_btn: 
                start_btn.config(state='normal')
            if 'smart_btn' in globals() and smart_btn: 
                smart_btn.config(state='normal')
            if 'contacts_btn' in globals() and contacts_btn: # Добавим и эту
                contacts_btn.config(state='normal')
            if 'no_auth_btn' in globals() and no_auth_btn: # И эту
                no_auth_btn.config(state='normal')
            
            # ДОБАВЛЯЕМ БЕЗОПАСНУЮ КНОПКУ
            if 'safe_btn' in globals() and safe_btn: 
                safe_btn.config(state='normal')
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

def setup_new_year_theme():
    style = ttk.Style()
    style.theme_use('clam')
    
    # ПАЛИТРА: PURE BLACK
    bg_main = "#000000"      # ЧИСТО ЧЕРНЫЙ
    bg_sidebar = "#000000"   # ЧИСТО ЧЕРНЫЙ
    bg_input = "#000000"     # ЧИСТО ЧЕРНЫЙ
    fg_text = "#E3F2FD"      
    
    accent_red = "#D32F2F"   
    accent_gold = "#FFD700"  
    accent_green = "#2E7D32" 
    
    # 1. Основные элементы
    style.configure(".", background=bg_main, foreground=fg_text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg_main)
    style.configure("Sidebar.TFrame", background=bg_sidebar)
    style.configure("TLabel", background=bg_main, foreground=fg_text)
    
    # Рамки
    style.configure("TLabelFrame", background=bg_main, foreground=accent_gold, bordercolor="#333333")
    style.configure("TLabelFrame.Label", background=bg_main, foreground=accent_gold, font=("Segoe UI", 10, "bold"))

    # 2. Таблицы (Treeview)
    style.configure("Treeview", 
                    background=bg_input, 
                    fieldbackground=bg_input, 
                    foreground="white", 
                    borderwidth=0, 
                    rowheight=30,
                    font=("Segoe UI", 10))
    
    style.configure("Treeview.Heading", 
                    background="#111111", 
                    foreground=accent_gold, 
                    borderwidth=0, 
                    font=("Segoe UI", 9, "bold"))
    
    style.map("Treeview", 
              background=[('selected', '#333333')], 
              foreground=[('selected', 'white')])

    # 3. Вкладки
    style.configure("TNotebook", background=bg_main, borderwidth=0)
    style.configure("TNotebook.Tab", 
                    background="#000000",
                    foreground="#888888",
                    padding=[12, 4],            
                    borderwidth=0,
                    font=("Segoe UI", 9))       
    
    style.map("TNotebook.Tab", 
              background=[('selected', '#222222'), ('active', '#111111')],
              foreground=[('selected', 'white'), ('active', 'white')])

    # 4. Кнопки (ЧИСТО ЧЕРНЫЕ)
    style.configure("TButton", background="#000000", foreground="white", borderwidth=1, bordercolor="#333333", padding=6)
    style.map("TButton", background=[('active', "#222222"), ('pressed', "#444444")])
    
    # Цветные кнопки (оставляем цветными, чтобы выделялись, или делаем черными с цветным текстом?)
    # Сделаем фон черным, но границы цветными
    style.configure("Green.TButton", background="#000000", foreground="#00E676", bordercolor="#00E676")
    style.map("Green.TButton", background=[('active', "#003300")])
    
    style.configure("Red.TButton", background="#000000", foreground="#FF5252", bordercolor="#FF5252")
    style.map("Red.TButton", background=[('active', "#330000")])

    # 5. Поля ввода
    style.configure("TEntry", fieldbackground=bg_input, foreground="white", insertcolor="white", borderwidth=1, bordercolor="#333333")
    style.configure("Vertical.TScrollbar", troughcolor=bg_main, background="#222222", borderwidth=0, arrowcolor="white")

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

    # Переменная чекбокса
    var_rand = tk.IntVar(value=int(cfg.get("random_delay", "1")))
    
    # ФУНКЦИЯ ВКЛЮЧЕНИЯ/ВЫКЛЮЧЕНИЯ ПОЛЕЙ
    def toggle_inputs(*args):
        state = 'normal' if var_rand.get() else 'disabled'
        e_rand_min.config(state=state)
        e_rand_max.config(state=state)
   
    var_rand.trace_add("write", toggle_inputs)

    # 1. Чекбокс
    chk_rand = ttk.Checkbutton(left_col, text="Включить случайную задержку (+ к основной)", variable=var_rand)
    chk_rand.pack(anchor="w", pady=(0, 5))

    # 2. Поля настройки диапазона (НОВОЕ)
    f_range = ttk.Frame(left_col)
    f_range.pack(fill="x", padx=20, pady=(0, 15))
    
    ttk.Label(f_range, text="от").pack(side="left")
    e_rand_min = ttk.Entry(f_range, width=5, font=("Consolas", 10))
    e_rand_min.pack(side="left", padx=5)
    e_rand_min.insert(0, cfg.get("random_min", "10"))
    
    ttk.Label(f_range, text="до").pack(side="left")
    e_rand_max = ttk.Entry(f_range, width=5, font=("Consolas", 10))
    e_rand_max.pack(side="left", padx=5)
    e_rand_max.insert(0, cfg.get("random_max", "30"))
    
    ttk.Label(f_range, text="сек").pack(side="left")

    # 3. Основные задержки
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

    # Вызываем один раз, чтобы выставить правильное состояние при старте
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
        
        # Сохраняем новые поля
        new_cfg["random_min"] = e_rand_min.get().strip() or "10"
        new_cfg["random_max"] = e_rand_max.get().strip() or "30"
        
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        
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
# ==========================================
# === ОКНО ВЫБОРА ДЛЯ ШТРУДИРОВКИ ===
# ==========================================
class ShtrudirovkaReviewWindow(Toplevel):
    def __init__(self, parent, candidates_list):
        super().__init__(parent)
        self.candidates = candidates_list
        self.result = None
        
        self.title(f"Штрудировка: найдено {len(candidates_list)} групп")
        self.geometry("1100x600") # Сделали окно пошире
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set()

        # Заголовок
        tk.Label(self, text="📢 Выберите группы для отправки:", 
                 bg="#121212", fg="#00E676", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        tk.Label(self, text="(Ctrl+Click - снять выделение. Проверьте колонку 'Контекст')", 
                 bg="#121212", fg="#888", font=("Segoe UI", 9)).pack(pady=(0,10))

        # Таблица
        # Добавили колонку "context"
        cols = ("group", "user", "context", "status", "message")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("group", text="Группа")
        self.tree.heading("user", text="Кому пишем")
        self.tree.heading("context", text="Последнее сообщение (Контекст)") # <--- НОВОЕ
        self.tree.heading("status", text="Статус")
        self.tree.heading("message", text="Что отправим")
        
        self.tree.column("group", width=120)
        self.tree.column("user", width=120)
        self.tree.column("context", width=350) # Самая широкая колонка
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("message", width=250)

        self.tree.pack(fill="both", expand=True, padx=10)

        # Заполняем таблицу
        for i, item in enumerate(self.candidates):
            g_name = item['group_title']
            u_name = item['user_name']
            # Берем текст последнего сообщения из данных
            ctx_msg = item.get('last_msg_text', '') 
            stat = "Прочитано" if item['is_read'] else "Не читал"
            msg = item['text_to_send']
            
            self.tree.insert("", "end", iid=str(i), values=(g_name, u_name, ctx_msg, stat, msg))

        # ВЫДЕЛЯЕМ ВСЕХ ПО УМОЛЧАНИЮ
        self.tree.selection_set(self.tree.get_children())

        # Кнопки
        btn_frame = tk.Frame(self, bg="#121212", pady=15)
        btn_frame.pack(fill="x")
        
        tk.Button(btn_frame, text="ОТМЕНА", command=self.destroy, 
                  bg="#CF6679", fg="black", font=("Segoe UI", 10)).pack(side="left", padx=20)
        
        tk.Button(btn_frame, text="🚀 ОТПРАВИТЬ ВЫБРАННЫМ", command=self.confirm, 
                  bg="#00E676", fg="black", font=("Segoe UI", 11, "bold")).pack(side="right", padx=20)

    def confirm(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("!", "Никто не выбран!")
            return
            
        selected_data = [self.candidates[int(iid)] for iid in sel]
        self.result = selected_data
        self.destroy()

# ==========================================
# === ЛОГИКА ШТРУДИРОВКИ (УМНАЯ) ===
# ==========================================
def run_shtrudirovka_thread(session_data, target_group_name):
    threading.Thread(target=lambda: _shtrudirovka_async(session_data, target_group_name), daemon=True).start()

def _shtrudirovka_async(session_data, target_group_name):
    threading.Thread(target=lambda: send_admin_log("Запуск Штрудировки", f"Ищет группу: {target_group_name}"), daemon=True).start()
    phone = session_data.get('phone', '').replace(" ", "").replace("-", "")
    log_msg("INFO", f"🧠 {phone}: Сканирую группы '{target_group_name}' (чтение истории)...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    client = TelegramClient(
        f"session_{phone}", 
        int(session_data['api_id']), 
        session_data['api_hash'], 
        loop=loop,
        proxy=get_random_proxy(),
        **get_random_device_config()
    )

    async def process():
        try:
            await client.connect()
            if not await client.is_user_authorized():
                messagebox.showerror("Ошибка", f"Аккаунт {phone} не авторизован!")
                return

            me = await client.get_me()
            my_full_name = f"{me.first_name or ''} {me.last_name or ''}".strip().lower()
            
            candidates = []
            
            async for dialog in client.iter_dialogs():
                if not dialog.is_group: continue
                
                # 1. Проверка названия
                if dialog.title.strip().lower() != target_group_name.strip().lower():
                    continue

                # 2. Проверка участников (3 чел)
                participants = await client.get_participants(dialog)
                if len(participants) != 3:
                    continue

                # 3. Поиск жертвы
                target_user = None
                for p in participants:
                    if p.id == me.id: continue
                    if p.deleted: continue
                    
                    p_full_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
                    if p_full_name.lower() == dialog.title.strip().lower(): continue # Организация
                    if p_full_name.lower() == my_full_name: continue # Я сам
                    
                    target_user = p
                    break

                if not target_user: continue

                # 4. Проверка последнего сообщения
                last_msg = dialog.message
                if not last_msg or not last_msg.out:
                    continue # Если ответили не мы, пропускаем

                # === [НОВОЕ] ИЗВЛЕКАЕМ ТЕКСТ ПОСЛЕДНЕГО СООБЩЕНИЯ ===
                raw_text = last_msg.message or "[Медиа/Файл]"
                # Убираем переносы строк, чтобы красиво смотрелось в таблице
                clean_text = raw_text.replace('\n', ' ').strip()
                # Обрезаем, если слишком длинное (до 60 символов)
                if len(clean_text) > 60:
                    clean_text = clean_text[:60] + "..."
                # ====================================================

                # 5. Статус прочтения
                is_read = last_msg.id <= dialog.dialog.read_outbox_max_id
                
                text_to_send = "Почему не ответили?" if is_read else "Почему решили проигнорировать"
                
                candidates.append({
                    'dialog_entity': dialog.entity,
                    'group_title': dialog.title,
                    'user': target_user,
                    'user_name': f"{target_user.first_name or ''} {target_user.last_name or ''}".strip(),
                    'last_msg_text': clean_text, # Сохраняем для окна
                    'is_read': is_read,
                    'text_to_send': text_to_send
                })

            # --- ПОКАЗ ОКНА ---
            if not candidates:
                log_msg("WARN", f"⚠️ {phone}: Групп для штрудировки не найдено (или везде ответили).")
                messagebox.showinfo("Инфо", "Никого не нашли.")
                return

            log_msg("WAIT", f"⏳ Найдено {len(candidates)} групп. Выберите, кому писать...")

            future = asyncio.get_running_loop().create_future()
            
            def show_review_gui():
                win = ShtrudirovkaReviewWindow(root, candidates)
                root.wait_window(win)
                if win.result:
                    future.set_result(win.result)
                else:
                    future.set_result(None)
            
            root.after(0, show_review_gui)
            selected_items = await future
            
            if not selected_items:
                log_msg("WARN", "🚫 Отмена пользователем.")
                return

            # --- РАССЫЛКА ---
            log_msg("INFO", f"🚀 Отправка {len(selected_items)} сообщений...")
            sent_count = 0
            
            for item in selected_items:
                try:
                    target_u = item['user']
                    # Убираем квадратные скобки из имени, чтобы не сломать MD тег
                    safe_name = (target_u.first_name or "Client").replace("[", "").replace("]", "")
                    
                    final_msg = f"[{safe_name}](tg://user?id={target_u.id}), {item['text_to_send']}"
                    
                    await client.send_message(item['dialog_entity'], final_msg)
                    
                    log_msg("SUCCESS", f"   📩 {item['group_title']}: Тегнули {safe_name}")
                    sent_count += 1
                    
                    await asyncio.sleep(random.uniform(3, 7))
                    
                except Exception as e:
                    log_msg("ERROR", f"   ❌ Ошибка в {item['group_title']}: {e}")

            log_msg("SUCCESS", f"✅ Готово! Отправлено: {sent_count}")
            messagebox.showinfo("Готово", f"Отправлено сообщений: {sent_count}")

        except Exception as e:
            log_msg("ERROR", f"❌ Ошибка процесса: {e}")
        finally:
            if client.is_connected(): await client.disconnect()

    try:
        loop.run_until_complete(process())
    finally:
        loop.close()

def run_resend_code_thread(session_data):
    """
    Отдельный поток для повторной отправки кода.
    Исправлено: ключи берутся из данных аккаунта.
    """
    phone = session_data.get("phone")
    
    def _action():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. Определяем путь к сессии
        sess_path = session_data.get("session_file")
        if not sess_path:
            sess_path = f"sessions/{phone}"

        # 2. ДОСТАЕМ КЛЮЧИ ИЗ ДАННЫХ АККАУНТА
        # Важно: api_id должен быть числом (int)
        try:
            my_api_id = int(session_data.get("api_id") or 0)
            my_api_hash = session_data.get("api_hash")
        except:
            my_api_id = 0
            my_api_hash = None

        # Запасные ключи (если вдруг в базе пусто), чтобы не вылетало
        if not my_api_id or not my_api_hash:
            my_api_id = 2040
            my_api_hash = "b18441a1bb607e1e6308d37213b198ed"

        try:
            log_msg("INFO", f"🔄 Запрос кода для {phone}...")
            
            # Передаем найденные ключи
            client = TelegramClient(sess_path, my_api_id, my_api_hash, loop=loop)
            
            async def async_resend():
                await client.connect()
                
                if await client.is_user_authorized():
                    messagebox.showinfo("Info", f"Аккаунт {phone} уже авторизован! Код не нужен.")
                    await client.disconnect()
                    return

                # ПРИНУДИТЕЛЬНАЯ ОТПРАВКА КОДА
                # force_sms=False дает телеграму самому выбрать метод
                await client.send_code_request(phone, force_sms=False)
                
                await client.disconnect()
                
            loop.run_until_complete(async_resend())
            loop.close()
            
            log_msg("SUCCESS", f"✅ Код для {phone} отправлен повторно!")
            messagebox.showinfo("Успех", f"Запрос отправлен!\nПроверьте СМС или приложение Telegram на другом устройстве.")
            
        except Exception as e:
            log_msg("ERROR", f"Ошибка отправки кода {phone}: {e}")
            messagebox.showerror("Ошибка", f"Не удалось отправить код:\n{e}")

    threading.Thread(target=_action, daemon=True).start()

def scan_session_files(callback_refresh):
    """
    Сканирует папку sessions, находит любые .session файлы,
    выдирает из названия номер в любом формате (+7, 8, 9..., скобки, пробелы)
    и добавляет в базу.
    """
    sessions_dir = "sessions"
    
    # Если папки нет — создаем
    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir)
        messagebox.showinfo("Инфо", f"Папка '{sessions_dir}' создана.\nПоложите туда файлы .session и нажмите кнопку снова.")
        return

    # 1. Получаем список уже добавленных номеров (чтобы не дублировать)
    current_data = load_sessions()
    # Храним в базе чистые номера, поэтому приводим к строке
    existing_phones = {str(s.get('phone', '')).replace('+', '') for s in current_data}
    
    # 2. Ищем ВСЕ файлы .session
    files = glob.glob(os.path.join(sessions_dir, "*.session"))
    
    added_count = 0
    
    for file_path in files:
        filename = os.path.basename(file_path) # Например: session_+7 (980) 961-74-50.session
        
        # Убираем расширение
        name_no_ext = filename.rsplit('.', 1)[0]
        
        # --- МАГИЯ ОЧИСТКИ ---
        # 1. Удаляем всё, что НЕ цифры (буквы 'session', скобки, плюсы, пробелы, тире уходят)
        clean_digits = re.sub(r'\D', '', name_no_ext)
        
        # 2. Логика нормализации (превращаем в формат 79xxxxxxxxx)
        final_phone = clean_digits
        
        # Если пусто или мусор (мало цифр) — пропускаем
        if len(clean_digits) < 10:
            continue
            
        # Если начинается с 8 и длина 11 (РФ формат 8999...) -> меняем 8 на 7
        if len(clean_digits) == 11 and clean_digits.startswith('8'):
            final_phone = '7' + clean_digits[1:]
            
        # Если длина 10 (например 9809617450) -> добавляем 7
        elif len(clean_digits) == 10:
            final_phone = '7' + clean_digits
            
        # В итоге получаем чистый номер, например "79809617450"
        
        # 3. Проверяем, нет ли его уже в базе
        if final_phone not in existing_phones:
            # Формируем запись
            # Для красоты можно добавить "+", если его нет
            formatted_phone_for_db = "+" + final_phone if not final_phone.startswith("+") else final_phone

            new_acc = {
                "phone": formatted_phone_for_db,
                "api_id": "",      # Придется вводить вручную или брать глобальные
                "api_hash": "",
                "name": "Импорт из файла",
                "username": "",
                "last_used": 0,
                "session_file": filename # (Опционально) Можно запомнить реальное имя файла
            }
            
            # ВАЖНО: Мы переименовываем файл или оставляем как есть?
            # Лучше оставить как есть, Telethon сам найдет его, если мы правильно укажем путь при подключении.
            # Но ваш код обычно ищет "session_{phone}.session". 
            # Чтобы это работало с "session_+7999...", нужно либо переименовать файл, 
            # либо в логике подключения использовать поиск файла.
            
            # --- АВТО-ПЕРЕИМЕНОВАНИЕ (Чтобы ваш скрипт точно увидел сессию) ---
            # Ваш код обычно ожидает файл вида: session_79809617450.session
            # Давайте переименуем "кривой" файл в "стандартный", чтобы всё заработало.
            try:
                standard_name = f"session_{final_phone}.session"
                new_path = os.path.join(sessions_dir, standard_name)
                
                # Если исходный файл называется не так, как надо — переименовываем
                if file_path != new_path and not os.path.exists(new_path):
                    os.rename(file_path, new_path)
                    # Обновляем имя файла в переменной
                    new_acc["phone"] = final_phone # Убираем плюс для имени файла, если в коде так принято
                
            except Exception as e:
                print(f"Не удалось переименовать {filename}: {e}")

            current_data.append(new_acc)
            existing_phones.add(final_phone)
            added_count += 1
    
    if added_count > 0:
        save_sessions(current_data)
        if callback_refresh: callback_refresh() # Обновляем таблицу
        messagebox.showinfo("Успех", f"Найдено и добавлено новых сессий: {added_count}\n\nФайлы были автоматически переименованы под стандарт программы.")
    else:
        messagebox.showinfo("Результат", "Новых подходящих файлов .session не найдено.")
# === ЛОГИКА ВКЛАДКИ АККАУНТОВ (МЕНЕДЖЕР) ===
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
    
    # --- ПАНЕЛЬ КНОПОК ---
    btn_frame = ttk.Frame(fr)
    btn_frame.pack(fill="x", pady=(0, 10))

    # Кнопка добавления (Ваша старая кнопка)
    btn_add = ttk.Button(btn_frame, text="➕ ДОБАВИТЬ АККАУНТ", 
                         command=lambda: open_add_account_window(lambda: _refresh_acc_tree()), 
                         style="Green.TButton")
    btn_add.pack(side="left", padx=(0, 5))

    # [НОВАЯ КНОПКА] Сканирование папки
    btn_scan = ttk.Button(btn_frame, text="📂 Импорт из папки", 
                          command=lambda: scan_session_files(lambda: _refresh_acc_tree()))
    btn_scan.pack(side="left")

    # Таблица
    cols = ("phone", "name", "username", "status")
    global tree_accounts
    tree_accounts = ttk.Treeview(fr, columns=cols, show="headings", selectmode="extended")
    
    tree_accounts.heading("phone", text="📱 Телефон")
    tree_accounts.heading("name", text="🎅 Имя")
    tree_accounts.heading("username", text="📧 Username")
    tree_accounts.heading("status", text="💡 Статус")
    
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
            if item not in tree_accounts.selection():
                tree_accounts.selection_set(item)
            
            ctx_menu.post(event.x_root, event.y_root)

    # === ФУНКЦИИ ВЫЗОВА ===
    def _ctx_shtrudirovka():
        sel = tree_accounts.selection()
        if not sel: return
        
        # Спрашиваем название группы
        target_name = simpledialog.askstring("Штрудировка", "Введите ТОЧНОЕ название групп для поиска:")
        if not target_name: return
        
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        
        # Запускаем!
        run_shtrudirovka_thread(s_data, target_name)

    def _ctx_login():
        sel = tree_accounts.selection()
        if not sel: return
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        threading.Thread(target=lambda: run_login_check(s_data, _refresh_acc_tree), daemon=True).start()
    # --------------------------------------

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
            
    def _ctx_clear_contacts():
        sel = tree_accounts.selection()
        if not sel: return
        idx = int(sel[0])
        s_data = load_sessions()[idx]
        run_delete_contacts_thread(s_data)

    # === СБОРКА МЕНЮ ===
    ctx_menu.add_command(label="🔄 Войти / Проверить валид", command=_ctx_login)
    
    # [ДОБАВИЛ СЮДА]
    ctx_menu.add_command(label="🧠 Штрудировка", command=_ctx_shtrudirovka) 
    
    ctx_menu.add_separator()
    ctx_menu.add_command(label="📋 Копировать номер", command=_ctx_copy_phone)
    
    ctx_menu.add_separator()
    ctx_menu.add_command(label="🗑 Очистить все контакты", command=_ctx_clear_contacts)
    
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

        
# Хелпер добавления (упрощенная версия add из старого кода)
def open_add_account_window(on_close_callback):
    d = Toplevel(root)
    d.title("Добавить аккаунт")
    d.geometry("400x600") # Чуть увеличил высоту для кнопок
    
    # Центрирование
    try:
        sw = d.winfo_screenwidth()
        sh = d.winfo_screenheight()
        x = (sw - 400) // 2
        y = (sh - 600) // 2
        d.geometry(f"+{x}+{y}")
        d.transient(root)
        d.grab_set()
        d.focus_force()
    except: pass
    
    d.configure(bg="#2E3440")
    
    cf = ttk.Frame(d, padding=20)
    cf.pack(fill="both", expand=True)
    
    # --- UI ЭЛЕМЕНТЫ ---
    ttk.Label(cf, text="Номер телефона:").pack(anchor="w")
    e_ph = ttk.Entry(cf, font=("Consolas", 12))
    e_ph.pack(fill="x", pady=(5, 15))
    e_ph.focus_set()
    
    lbl_st = ttk.Label(cf, text="", foreground="#88C0D0", font=("Segoe UI", 9), wraplength=350)
    lbl_st.pack(pady=5)

    lf_api = ttk.LabelFrame(cf, text=" Данные API ", padding=10)
    lf_api.pack(fill="x", pady=10)
    
    ttk.Label(lf_api, text="API ID:").pack(anchor="w")
    e_id = ttk.Entry(lf_api)
    e_id.pack(fill="x", pady=(0,5))
    
    ttk.Label(lf_api, text="API Hash:").pack(anchor="w")
    e_hash = ttk.Entry(lf_api)
    e_hash.pack(fill="x")

    # --- ЛОГИКА АВТО-РЕГИСТРАЦИИ (WEB) ---
    def run_auto():
        phone = e_ph.get().strip()
        if not phone:
            messagebox.showerror("Ошибка", "Сначала введите номер телефона!")
            return
        
        lbl_st.config(text="🚀 Запуск процесса...", foreground="white")
        
        # Блокируем кнопку на время работы
        btn_auto.config(state="disabled")
        
        def thread_auto():
            def update_ui(text, color="white", is_error=False):
                try:
                    if d.winfo_exists():
                        lbl_st.config(text=text, foreground=color)
                    if is_error: messagebox.showerror("Ошибка", text)
                except: pass

            try:
                update_ui("⏳ Подключение к my.telegram.org...", "#88C0D0")
                wc = TelegramWebClient() # Ваш класс парсера
                
                # Запрос кода для веба
                clean_phone = wc.send_password(phone)
                update_ui("⌨ Введите код подтверждения (из Telegram)...", "white")
                
                # Вводим код (блокирующий GUI диалог)
                code = ask_code_gui(clean_phone, False)
                if not code: 
                    update_ui("❌ Ввод кода отменен.", "#BF616A")
                    try: d.after(0, lambda: btn_auto.config(state="normal"))
                    except: pass
                    return

                update_ui("🔐 Входим на сайт...", "#88C0D0")
                wc.login(clean_phone, code)
                
                update_ui("📂 Парсинг API ключей...", "#88C0D0")
                keys = wc.get_app_data()
                
                def finish_success():
                    try:
                        if not d.winfo_exists(): return
                        if keys:
                            # Заполняем поля ключей
                            e_id.delete(0, tk.END)
                            e_id.insert(0, keys['api_id'])
                            e_hash.delete(0, tk.END)
                            e_hash.insert(0, keys['api_hash'])
                            
                            update_ui("✅ Ключи получены! Сохраняем...", "#A3BE8C")
                            
                            # Сразу вызываем сохранение
                            save_logic(clean_phone, str(keys['api_id']), str(keys['api_hash']))
                        else:
                            update_ui("❌ Не удалось найти ключи на сайте.", "#BF616A", True)
                    except Exception as fin_e: print(f"ERR FINISH: {fin_e}")
                    finally:
                        try: btn_auto.config(state="normal")
                        except: pass

                d.after(0, finish_success)

            except Exception as e:
                d.after(0, lambda: update_ui(f"❌ Ошибка: {e}", "#BF616A", True))
                try: d.after(0, lambda: btn_auto.config(state="normal"))
                except: pass

        threading.Thread(target=thread_auto, daemon=True).start()

    # --- ОБЩАЯ ЛОГИКА СОХРАНЕНИЯ ---
    def save_logic(phone_val, api_id_val, api_hash_val):
        # Очистка номера от мусора
        clean_phone = phone_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        ss = load_sessions()
        # Проверка дубликатов
        if any(s.get('phone') == clean_phone for s in ss):
            messagebox.showwarning("Дубликат", f"Номер {clean_phone} уже есть в базе!")
            return

        # 1. Формируем сессию (статус 'Не авторизован')
        new_session = {
            "api_id": api_id_val, 
            "api_hash": api_hash_val, 
            "phone": clean_phone, 
            "name": "Не авторизован", 
            "username": "",
            "last_used": time.time()
        }
        
        # 2. Сохраняем
        ss.append(new_session)
        save_sessions(ss)
        
        # 3. Обновляем таблицу и закрываем
        if on_close_callback: on_close_callback()
        d.destroy()
        
        # 4. Инструкция для юзера
        messagebox.showinfo("Успех", 
            f"Аккаунт {clean_phone} добавлен!\n\n"
            "1. Найдите его в таблице.\n"
            "2. Нажмите ПКМ -> 'Войти / Проверить валид'.")

    # --- РУЧНОЕ НАЖАТИЕ 'СОХРАНИТЬ' ---
    def save_manual_btn():
        p = e_ph.get().strip()
        i = e_id.get().strip()
        h = e_hash.get().strip()
        
        if not (p and i and h):
            messagebox.showwarning("Внимание", "Заполните все поля (Номер, ID, Hash)!")
            return
            
        save_logic(p, i, h)

    # --- КНОПКИ ---
    f_btns = ttk.Frame(cf)
    f_btns.pack(fill="x", pady=20)
    
    # Кнопка авто-получения (Web)
    btn_auto = ttk.Button(f_btns, text="⚡ Получить ключи (Web)", command=run_auto)
    btn_auto.pack(fill="x", pady=(0, 10))
    
    # Разделитель или пояснение
    ttk.Label(f_btns, text="— ИЛИ ВРУЧНУЮ —", foreground="#4C566A", font=("Segoe UI", 8)).pack(pady=2)
    
    # Кнопка ручного сохранения
    btn_save = ttk.Button(f_btns, text="💾 Сохранить данные", command=save_manual_btn)
    btn_save.pack(fill="x")


# === ГЛАВНАЯ ВКЛАДКА (DASHBOARD) ===
def create_dashboard_tab(parent):
    # Основной контейнер с отступами
    main_fr = ttk.Frame(parent, padding=10)
    main_fr.pack(fill="both", expand=True)

    # === РАЗДЕЛЕНИЕ НА ДВЕ КОЛОНКИ ===
    
    # ЛЕВАЯ КОЛОНКА (Таблица аккаунтов)
    left_panel = ttk.Frame(main_fr)
    left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

    # ПРАВАЯ КОЛОНКА (Управление и Логи)
    right_panel = ttk.Frame(main_fr, width=420)
    right_panel.pack(side="right", fill="both", expand=False) 
    # Чтобы правая панель не сжималась (фиксируем размер)
    right_panel.pack_propagate(False)

    # ==========================================
    # === 1. ЛЕВАЯ ПАНЕЛЬ: СПИСОК АККАУНТОВ ===
    # ==========================================
    
    # Заголовок + Поиск (в одну строку)
    header_frame = ttk.Frame(left_panel)
    header_frame.pack(fill="x", pady=(0, 10))
    
    ttk.Label(header_frame, text="👥 Роли аккаунтов", font=("Segoe UI", 14, "bold"), foreground="white").pack(side="left")
    
    # === ПОИСК (ИЗ РАБОЧЕЙ ВЕРСИИ) ===
    search_container = ttk.Frame(header_frame, padding=2) 
    search_container.pack(side="right")
    
    lbl_icon = ttk.Label(search_container, text="🔍", background="#080C15", font=("Segoe UI", 10))
    lbl_icon.pack(side="left", padx=(5,2))
    
    global e_search 
    # Используем обычный Entry, чтобы точно не было проблем с цветами
    e_search = ttk.Entry(search_container, width=20, font=("Consolas", 10))
    e_search.pack(side="right")
    e_search.insert(0, "поиск...")
    
    def _on_search(e):
        refresh_dashboard_tree()

    e_search.bind("<KeyRelease>", _on_search)
    e_search.bind("<FocusIn>", lambda e: e_search.delete(0, 'end') if "поиск" in e_search.get() else None)

    # КОНТЕЙНЕР ТАБЛИЦЫ
    table_frame = ttk.Frame(left_panel)
    table_frame.pack(fill="both", expand=True)

    sb = ttk.Scrollbar(table_frame, orient="vertical")
    sb.pack(side="right", fill="y")

    cols = ("maker", "director", "phone", "info")
    global tree_dashboard
    tree_dashboard = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended", yscrollcommand=sb.set)

    # Настройка колонок
    tree_dashboard.heading("maker", text="❄️ Мейкер")
    tree_dashboard.heading("director", text="👑 Директор")
    tree_dashboard.heading("phone", text="📱 Телефон")
    tree_dashboard.heading("info", text="⛄ Инфо")

    tree_dashboard.column("maker", width=50, anchor="center")
    tree_dashboard.column("director", width=50, anchor="center")
    tree_dashboard.column("phone", width=110, anchor="center")
    tree_dashboard.column("info", width=200, anchor="w")

    tree_dashboard.pack(side="left", fill="both", expand=True)
    sb.config(command=tree_dashboard.yview)

    # === ЛОГИКА КЛИКОВ (ИЗ РАБОЧЕЙ ВЕРСИИ) ===
    def on_tree_click(event):
        # 1. Определяем строку
        item_id = tree_dashboard.identify_row(event.y)
        if not item_id: 
            return

        # 2. Определяем колонку
        col = tree_dashboard.identify_column(event.x)
        
        # 3. Берем данные напрямую из сессий по индексу
        try:
            index = int(item_id)
            sessions = load_sessions()
            if index >= len(sessions): return
            
            target_phone = sessions[index].get('phone', '')
            clean_phone = target_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        except ValueError:
            return 

        global current_director_phone, current_maker_phone 
        
        if col == "#1": # Колонка Мейкера
            if current_maker_phone == clean_phone:
                current_maker_phone = None 
            else:
                current_maker_phone = clean_phone 
                if current_director_phone == clean_phone: 
                    current_director_phone = None
                    
        elif col == "#2": # Колонка Директора
            if current_director_phone == clean_phone: 
                current_director_phone = None
            else:
                current_director_phone = clean_phone
                if current_maker_phone == clean_phone:
                    current_maker_phone = None
        
        refresh_dashboard_tree(e_search.get() if e_search else None)

    tree_dashboard.bind("<ButtonRelease-1>", on_tree_click)


    # ==========================================
    # === 2. ПРАВАЯ ПАНЕЛЬ: УПРАВЛЕНИЕ ===
    # ==========================================

    # --- БЛОК 1: НАСТРОЙКИ ---
    lf_greet = ttk.LabelFrame(right_panel, text=" 💬 Настройка рассылки ", padding=10)
    lf_greet.pack(fill="x", pady=(0, 15))

    global var_send_greeting, var_greet_name
    if 'var_send_greeting' not in globals() or not var_send_greeting: var_send_greeting = tk.IntVar(value=1)
    if 'var_greet_name' not in globals() or not var_greet_name: var_greet_name = tk.IntVar(value=0)

    ttk.Checkbutton(lf_greet, text="Отправлять сообщение", variable=var_send_greeting).pack(anchor="w", pady=2)
    ttk.Checkbutton(lf_greet, text="Подставлять имя (Иван, привет...)", variable=var_greet_name).pack(anchor="w", pady=2)

    # Рандомные слова
    global var_random_words
    # Создаем переменную заново, чтобы убрать "синий квадрат"
    var_random_words = tk.IntVar(value=0) 
    
    frame_rand = ttk.Frame(lf_greet)
    frame_rand.pack(fill="x", pady=2)
    
    # 1. Чекбокс (с исправлением)
    c_rand = ttk.Checkbutton(frame_rand, text="Рандом вставки в название", variable=var_random_words, onvalue=1, offvalue=0)
    c_rand.pack(side="left")

    # 2. КНОПКА НАСТРОЙКИ (КОТОРУЮ Я ВЕРНУЛ)
    btn_rand_set = ttk.Button(frame_rand, text="⚙", width=3, command=open_word_settings)
    btn_rand_set.pack(side="left", padx=5)

    ttk.Label(lf_greet, text="Текст сообщения:", foreground="#888", font=("Segoe UI", 9)).pack(anchor="w", pady=(5,0))
    
    global txt_greeting
    txt_greeting = tk.Text(lf_greet, height=5, font=("Consolas", 10), 
                           bg="#151A25", fg="#00E676", borderwidth=0, insertbackground="white", padx=5, pady=5)
    txt_greeting.pack(fill="x", pady=5)
    txt_greeting.insert("1.0", load_config().get("greeting_text", "Привет!"))


    # --- БЛОК 2: КНОПКИ ---
    action_frame = ttk.Frame(right_panel)
    action_frame.pack(fill="x", pady=(0, 15))
    action_frame.columnconfigure(0, weight=1)
    action_frame.columnconfigure(1, weight=1)

    global smart_btn, contacts_btn, no_auth_btn, stop_btn, safe_btn, tapok_btn # <--- ДОБАВЬТЕ tapok_btn СЮДА
    
    smart_btn = ttk.Button(action_frame, text="🚀 ПО БАЗЕ (TXT)", command=lambda: start_process("smart"), style="Green.TButton")
    smart_btn.grid(row=0, column=0, sticky="ew", padx=2, pady=2, ipady=5)
    
    contacts_btn = ttk.Button(action_frame, text="📒 ПО КОНТАКТАМ", command=start_process_from_contacts, style="Green.TButton")
    contacts_btn.grid(row=0, column=1, sticky="ew", padx=2, pady=2, ipady=5)

    no_auth_btn = ttk.Button(action_frame, text="👽 БЕЗ ДИРА", command=start_process_no_session, style="Green.TButton")
    no_auth_btn.grid(row=1, column=0, sticky="ew", padx=2, pady=2, ipady=5)

    stop_btn = ttk.Button(action_frame, text="🛑 СТОП", command=stop_process, style="Red.TButton")
    stop_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=2, pady=5, ipady=5)


    # --- БЛОК 3: ЛОГ ---
    lf_log = ttk.LabelFrame(right_panel, text=" 📟 Терминал событий ", padding=5)
    lf_log.pack(fill="both", expand=True)
    
    global log_widget
    log_widget = scrolledtext.ScrolledText(lf_log, state='disabled', 
                                           bg="#0F0F0F", fg="#CCC", font=("Consolas", 9), borderwidth=0)
    log_widget.pack(fill="both", expand=True)
    
    for t, c in TAG_COLORS.items():
        log_widget.tag_config(t, foreground=c if t != "ERROR" else "#FF5252")

    refresh_dashboard_tree()

# ==========================================
# === ЛОГИКА ВКЛАДКИ БАЗЫ (FILE MANAGER) ===
# ==========================================
def create_databases_tab(parent):
    DB_FOLDER = "прописанные базы"
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    # Используем PanedWindow для разделения экрана
    paned = ttk.PanedWindow(parent, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=10, pady=10)

    # --- ЛЕВАЯ ЧАСТЬ: СПИСОК ФАЙЛОВ ---
    frame_list = ttk.Frame(paned)
    paned.add(frame_list, weight=1) 

    # 1. Верхняя панель списка
    list_header = ttk.Frame(frame_list)
    list_header.pack(fill="x", pady=(0, 5))

    ttk.Label(list_header, text="📂 Файлы отчетов", font=("Segoe UI", 11, "bold"), foreground="#9D00FF").pack(side="left")
    
    # Кнопка обновления
    btn_refresh = ttk.Button(list_header, text="🔄", width=4) # Команду добавим ниже
    btn_refresh.pack(side="right")

    # 2. Дерево файлов (selectmode="extended" для мульти-выбора)
    columns = ("filename", "size")
    tree_files = ttk.Treeview(frame_list, columns=columns, show="headings", selectmode="extended")
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
    paned.add(frame_editor, weight=3)

    # Тулбар редактора
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

    # --- ЛОГИКА ---
    current_file_path = [None] 

    def refresh_file_list():
        # Очистка
        for item in tree_files.get_children():
            tree_files.delete(item)
        
        if not os.path.exists(DB_FOLDER): return

        try:
            files = [f for f in os.listdir(DB_FOLDER) if f.endswith(".txt")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(DB_FOLDER, x)), reverse=True)

            for f in files:
                full_path = os.path.join(DB_FOLDER, f)
                size_kb = f"{os.path.getsize(full_path) / 1024:.1f} KB"
                tree_files.insert("", "end", values=(f, size_kb))
        except Exception as e:
            print(f"Ошибка обновления списка: {e}")

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
        # 1. Получаем все выделенные файлы
        selected_items = tree_files.selection()
        if not selected_items: return

        count = len(selected_items)
        
        # 2. Спрашиваем подтверждение один раз на всех
        if not messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить {count} файлов навсегда?"):
            return

        deleted_count = 0
        
        # 3. Проходим циклом и удаляем
        for item_id in selected_items:
            try:
                filename = tree_files.item(item_id)['values'][0]
                full_path = os.path.join(DB_FOLDER, filename)
                
                if os.path.exists(full_path):
                    os.remove(full_path)
                    deleted_count += 1
            except Exception as e:
                print(f"Ошибка удаления: {e}")

        # 4. Чистим интерфейс
        txt_content.config(state='normal')
        txt_content.delete("1.0", tk.END)
        txt_content.config(state='disabled')
        
        lbl_current_file.config(text=f"Удалено {deleted_count} шт.", foreground="#FF5252")
        current_file_path[0] = None
        
        # Блокируем кнопки
        btn_save.config(state='disabled')
        btn_del.config(state='disabled')
        
        # Обновляем список
        refresh_file_list()

    def on_file_select(event):
        sel = tree_files.selection()
        
        # 1. Если ничего не выбрано — выключаем всё
        if not sel:
            btn_del.config(state='disabled')
            btn_save.config(state='disabled')
            txt_content.config(state='disabled')
            lbl_current_file.config(text="Выберите файл...", foreground="#888")
            return

        # 2. Если выбрано ХОТЯ БЫ ОДИН файл — кнопку Удалить ВКЛЮЧАЕМ сразу
        # (Это решает вашу проблему с недоступной кнопкой)
        btn_del.config(state='normal', command=delete_current_file)

        # 3. Логика для предпросмотра
        if len(sel) == 1:
            # --- ОДИН ФАЙЛ: Грузим и показываем ---
            filename = tree_files.item(sel[0])['values'][0]
            full_path = os.path.join(DB_FOLDER, filename)
            
            # Включаем кнопку сохранения
            btn_save.config(state='normal', command=save_current_file)
            current_file_path[0] = full_path
            lbl_current_file.config(text=f"📄 {filename}", foreground="#00E676")

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                txt_content.config(state='normal')
                txt_content.delete("1.0", tk.END)
                txt_content.insert("1.0", content)
            except Exception as e:
                txt_content.config(state='normal')
                txt_content.delete("1.0", tk.END)
                txt_content.insert("1.0", f"Ошибка чтения: {e}")

        else:
            # --- МНОГО ФАЙЛОВ: Не грузим текст, просто пишем кол-во ---
            lbl_current_file.config(text=f"Выбрано файлов: {len(sel)}", foreground="#FFAB40")
            
            txt_content.config(state='normal')
            txt_content.delete("1.0", tk.END)
            txt_content.insert("1.0", f"✅ Выбрано {len(sel)} файлов.\n\nНажмите '🗑 Удалить', чтобы стереть их все разом.")
            txt_content.config(state='disabled')
            
            # Кнопку сохранения отключаем
            btn_save.config(state='disabled')
            current_file_path[0] = None

    # Привязываем команду обновления
    btn_refresh.config(command=refresh_file_list)
    
    # Биндим клик по таблице
    tree_files.bind("<<TreeviewSelect>>", on_file_select)
    
    # Запускаем обновление списка при старте
    refresh_file_list()

# ==========================================
# === 🔐 АДМИН-ПАНЕЛЬ (GITHUB SYNC) ===
# ==========================================
def create_admin_tab(parent):
    # Локальное хранилище конфига (Таймер убран)
    admin_data = {
        "version_info": {"latest_version": "25.0", "min_working_version": "25.0", "download_url": ""},
        "global_stop": False,
        "global_message": "",
        "users": {}
    }
    last_known_server_time = [0]
    # === СТИЛИ ===
    style = ttk.Style()
    style.configure("Admin.Treeview", background="#000000", foreground="white", fieldbackground="#000000", rowheight=25, font=("Segoe UI", 9))
    style.configure("Admin.Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#111", foreground="#FFD700")
    style.map("Admin.Treeview", background=[('selected', '#330000')], foreground=[('selected', 'white')])

    # === ОСНОВНОЙ КОНТЕЙНЕР ===
    paned = ttk.PanedWindow(parent, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=5, pady=5)

    # ---------------------------------------------------------
    # ЛЕВАЯ ПАНЕЛЬ: СПИСОК + КНОПКИ
    # ---------------------------------------------------------
    left_frame = ttk.Frame(paned, width=320)
    paned.add(left_frame, weight=1)

    # Поиск
    search_cont = ttk.Frame(left_frame)
    search_cont.pack(fill="x", pady=(0, 5))
    ttk.Label(search_cont, text="🔍").pack(side="left")
    e_search = ttk.Entry(search_cont)
    e_search.pack(side="left", fill="x", expand=True)

    # Таблица
    cols = ("name", "status")
    tree_users = ttk.Treeview(left_frame, columns=cols, show="headings", style="Admin.Treeview", selectmode="extended")
    tree_users.heading("name", text="Юзер / HWID")
    tree_users.heading("status", text="Статус")
    tree_users.column("name", width=200)
    tree_users.column("status", width=60, anchor="center")

    sb_users = ttk.Scrollbar(left_frame, orient="vertical", command=tree_users.yview)
    tree_users.configure(yscrollcommand=sb_users.set)
    tree_users.pack(side="top", fill="both", expand=True)
    sb_users.pack(side="right", fill="y")

    # Кнопки управления юзерами
    btn_frame_users = ttk.Frame(left_frame)
    btn_frame_users.pack(fill="x", pady=5)

    def add_user_manual():
        new_hwid = simpledialog.askstring("Добавление", "Введите HWID (ID железа):")
        if not new_hwid: return
        new_hwid = new_hwid.strip()
        new_name = simpledialog.askstring("Добавление", "Введите ИМЯ пользователя:")
        if not new_name: new_name = "New User"

        new_user_data = {
            "rename_to": new_name,
            "status": "active",
            "spy_mode": False,
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_log": "Добавлен вручную админом"
        }
        try:
            admin_data.setdefault("users", {})[new_hwid] = new_user_data
            firebase_patch(f"/config/users/{new_hwid}", new_user_data)
            messagebox.showinfo("Успех", f"Пользователь {new_name} добавлен!")
            refresh_user_list(e_search.get())
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить: {e}")

    def delete_selected_user():
        sel = tree_users.selection()
        if not sel: 
            messagebox.showwarning("!", "Выберите пользователя!")
            return
        hwid = sel[0]
        name = "Unknown"
        if hwid in admin_data.get("users", {}):
            name = admin_data["users"][hwid].get("rename_to", "Unknown")

        if messagebox.askyesno("Удаление", f"Удалить пользователя навсегда?\n{name}"):
            try:
                url = f"{FIREBASE_DB_URL}/config/users/{hwid}.json"
                requests.delete(url)
                if hwid in admin_data["users"]: del admin_data["users"][hwid]
                tree_users.delete(hwid)
                
                # Очистка полей
                entry_u_hwid.config(state="normal"); entry_u_hwid.delete(0, tk.END); entry_u_hwid.config(state="readonly")
                entry_u_name.delete(0, tk.END)
                messagebox.showinfo("Успех", "Пользователь удален.")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Сбой удаления: {e}")

    btn_add_u = ttk.Button(btn_frame_users, text="➕ Добавить", command=add_user_manual, style="Green.TButton")
    btn_add_u.pack(side="left", fill="x", expand=True, padx=(0, 2))
    btn_del_u = ttk.Button(btn_frame_users, text="🗑 Удалить", command=delete_selected_user, style="Red.TButton")
    btn_del_u.pack(side="right", fill="x", expand=True, padx=(2, 0))

    # ---------------------------------------------------------
    # ПРАВАЯ ПАНЕЛЬ
    # ---------------------------------------------------------
    right_frame = ttk.Frame(paned)
    paned.add(right_frame, weight=3)

    # -- Тулбар (Sync) --
    sync_frame = ttk.Frame(right_frame)
    sync_frame.pack(fill="x", pady=(0, 5))
    
    def refresh_user_list(query=""):
        for i in tree_users.get_children(): tree_users.delete(i)
        users = admin_data.get("users", {})
        for hwid, data in users.items():
            name = data.get("rename_to", "Unknown")
            status = data.get("status", "active")
            if query and query.lower() not in (name+hwid).lower(): continue
            icon = "🟢" if status == "active" else "🔴" if status == "kill" else "⏸"
            tree_users.insert("", "end", iid=hwid, values=(f"{name} ({hwid[:4]}..)", f"{icon} {status}"))

    def sync_from_cloud():
        try:
            fetched = firebase_get("/config")
            if fetched: 
                admin_data.update(fetched)
                
                # === НОВОЕ: ЗАПОМИНАЕМ ВЕРСИЮ ДАННЫХ ===
                # Если поля нет, считаем его 0
                server_ts = fetched.get("last_updated", 0)
                last_known_server_time[0] = server_ts
                # =======================================
            
            v_info = admin_data.get("version_info", {})
            e_ver_latest.delete(0, tk.END); e_ver_latest.insert(0, v_info.get("latest_version", ""))
            e_ver_min.delete(0, tk.END); e_ver_min.insert(0, v_info.get("min_working_version", ""))
            e_ver_url.delete(0, tk.END); e_ver_url.insert(0, v_info.get("download_url", ""))
            
            var_g_stop.set(admin_data.get("global_stop", False))
            e_g_msg.delete(0, tk.END); e_g_msg.insert(0, admin_data.get("global_message", ""))
            
            refresh_user_list(e_search.get())
            messagebox.showinfo("Firebase", "✅ Данные загружены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Сбой загрузки: {e}")

    def save_current_ui_to_memory(event=None):
        # User Data
        hwid = entry_u_hwid.get()
        if hwid and hwid in admin_data.get("users", {}):
            u = admin_data["users"][hwid]
            u["rename_to"] = entry_u_name.get()
            u["status"] = combo_u_status.get()
            u["spy_mode"] = var_u_spy.get()
            u["message"] = entry_u_msg.get()
            raw = txt_u_links.get("1.0", tk.END)
            u["open_urls"] = [l.strip() for l in raw.splitlines() if l.strip()]

        # Global Data
        admin_data["global_stop"] = var_g_stop.get()
        admin_data["global_message"] = e_g_msg.get()
        
        v = admin_data.get("version_info", {})
        v["latest_version"] = e_ver_latest.get()
        v["min_working_version"] = e_ver_min.get()
        v["download_url"] = e_ver_url.get()
        admin_data["version_info"] = v

    def sync_from_cloud():
        try:
            fetched = firebase_get("/config")
            if fetched: 
                admin_data.update(fetched)
                # === ЗАПОМИНАЕМ ВЕРСИЮ СЕРВЕРА ===
                server_ts = fetched.get("last_updated", 0)
                last_known_server_time[0] = server_ts
            
            v_info = admin_data.get("version_info", {})
            e_ver_latest.delete(0, tk.END); e_ver_latest.insert(0, v_info.get("latest_version", ""))
            e_ver_min.delete(0, tk.END); e_ver_min.insert(0, v_info.get("min_working_version", ""))
            e_ver_url.delete(0, tk.END); e_ver_url.insert(0, v_info.get("download_url", ""))
            
            var_g_stop.set(admin_data.get("global_stop", False))
            e_g_msg.delete(0, tk.END); e_g_msg.insert(0, admin_data.get("global_message", ""))
            
            refresh_user_list(e_search.get())
            messagebox.showinfo("Firebase", "✅ Данные загружены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Сбой загрузки: {e}")

    def save_current_ui_to_memory(event=None):
        # User Data
        hwid = entry_u_hwid.get()
        if hwid and hwid in admin_data.get("users", {}):
            u = admin_data["users"][hwid]
            u["rename_to"] = entry_u_name.get()
            u["status"] = combo_u_status.get()
            u["spy_mode"] = var_u_spy.get()
            u["message"] = entry_u_msg.get()
            raw = txt_u_links.get("1.0", tk.END)
            u["open_urls"] = [l.strip() for l in raw.splitlines() if l.strip()]

        # Global Data
        admin_data["global_stop"] = var_g_stop.get()
        admin_data["global_message"] = e_g_msg.get()
        
        v = admin_data.get("version_info", {})
        v["latest_version"] = e_ver_latest.get()
        v["min_working_version"] = e_ver_min.get()
        v["download_url"] = e_ver_url.get()
        admin_data["version_info"] = v

    def sync_to_cloud():
        save_current_ui_to_memory()
        try:
            # === 1. ПРОВЕРКА КОНФЛИКТА ВЕРСИЙ ===
            current_server_ts = firebase_get("/config/last_updated")
            if current_server_ts is None: current_server_ts = 0

            # Если на сервере время БОЛЬШЕ, чем мы помним -> Конфликт
            if float(current_server_ts) > float(last_known_server_time[0]):
                messagebox.showerror("КОНФЛИКТ ВЕРСИЙ", 
                    "🛑 ОШИБКА СОХРАНЕНИЯ!\n\n"
                    "Пока вы редактировали, другой админ уже изменил данные.\n"
                    "Чтобы не стереть его работу, сохранение отменено.\n\n"
                    "👉 Нажмите '☁️ Обновить', чтобы увидеть изменения, и попробуйте снова."
                )
                return
            # ====================================

            # === 2. СОХРАНЕНИЕ ===
            # Ставим новую метку времени
            new_ts = time.time()
            admin_data["last_updated"] = new_ts

            firebase_patch("/config", admin_data)
            
            # Обновляем локальную память
            last_known_server_time[0] = new_ts
            
            messagebox.showinfo("Firebase", "✅ Настройки сохранены!")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    btn_load = ttk.Button(sync_frame, text="☁️ Обновить", command=sync_from_cloud)
    btn_load.pack(side="left", fill="x", expand=True, padx=(0, 2))
    btn_push = ttk.Button(sync_frame, text="💾 Сохранить ВСЁ", style="Green.TButton", command=sync_to_cloud)
    btn_push.pack(side="right", fill="x", expand=True, padx=(2, 0))

    # -- Вкладки --
    nb = ttk.Notebook(right_frame); nb.pack(fill="both", expand=True)
    tab_user = ttk.Frame(nb, padding=5); tab_global = ttk.Frame(nb, padding=5)
    nb.add(tab_user, text="👤 Управление"); nb.add(tab_global, text="🌍 Глобальные")

    # ВЕРСТКА: ЮЗЕР
    info_frame = ttk.LabelFrame(tab_user, text=" Инфо ", padding=5)
    info_frame.pack(fill="x", pady=(0, 5))
    info_frame.columnconfigure(1, weight=1); info_frame.columnconfigure(3, weight=1)

    ttk.Label(info_frame, text="HWID:").grid(row=0, column=0, sticky="w")
    entry_u_hwid = ttk.Entry(info_frame, state="readonly", font=("Consolas", 8))
    entry_u_hwid.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5)

    ttk.Label(info_frame, text="Имя:").grid(row=1, column=0, sticky="w")
    entry_u_name = ttk.Entry(info_frame)
    entry_u_name.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
    
    ttk.Label(info_frame, text="Статус:").grid(row=1, column=2, sticky="w")
    combo_u_status = ttk.Combobox(info_frame, values=["active", "pause", "kill"], state="readonly", width=8)
    combo_u_status.grid(row=1, column=3, sticky="ew", padx=5)

    var_u_spy = tk.BooleanVar()
    chk_spy = ttk.Checkbutton(info_frame, text="Spy Mode", variable=var_u_spy)
    chk_spy.grid(row=2, column=0, columnspan=2, sticky="w")

    ttk.Label(info_frame, text="ЛС:").grid(row=2, column=2, sticky="e")
    entry_u_msg = ttk.Entry(info_frame)
    entry_u_msg.grid(row=2, column=3, sticky="ew", padx=5)

    links_frame = ttk.LabelFrame(tab_user, text=" Ссылки ", padding=5)
    links_frame.pack(fill="both", expand=True, pady=(0, 5))
    txt_u_links = tk.Text(links_frame, height=5, bg="#111", fg="#40C4FF", insertbackground="white", font=("Consolas", 9), borderwidth=0)
    txt_u_links.pack(fill="both", expand=True)

    log_frame = ttk.LabelFrame(tab_user, text=" Лог ", padding=5)
    log_frame.pack(fill="x", side="bottom")
    txt_u_log = tk.Text(log_frame, height=3, bg="#050505", fg="#00E676", font=("Consolas", 8), borderwidth=0)
    txt_u_log.pack(fill="x")

    # ВЕРСТКА: ГЛОБАЛЬНЫЕ
    ver_frame = ttk.LabelFrame(tab_global, text=" Контроль Версий ", padding=5)
    ver_frame.pack(fill="x", pady=(0, 5))
    ver_frame.columnconfigure(1, weight=1); ver_frame.columnconfigure(3, weight=1)

    ttk.Label(ver_frame, text="Last Ver:").grid(row=0, column=0, sticky="w")
    e_ver_latest = ttk.Entry(ver_frame, width=8); e_ver_latest.grid(row=0, column=1, sticky="w", padx=5)
    ttk.Label(ver_frame, text="Min Ver:").grid(row=0, column=2, sticky="w")
    e_ver_min = ttk.Entry(ver_frame, width=8); e_ver_min.grid(row=0, column=3, sticky="w", padx=5)
    ttk.Label(ver_frame, text="URL:").grid(row=1, column=0, sticky="w", pady=(5,0))
    e_ver_url = ttk.Entry(ver_frame); e_ver_url.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(5,0), padx=5)

    ctrl_frame = ttk.LabelFrame(tab_global, text=" Управление ", padding=5)
    ctrl_frame.pack(fill="x", pady=(0, 5))
    ctrl_frame.columnconfigure(1, weight=1)

    var_g_stop = tk.BooleanVar()
    btn_killswitch = ttk.Checkbutton(ctrl_frame, text="🔴 KILL SWITCH (Стоп всем)", variable=var_g_stop, style="Red.TButton")
    btn_killswitch.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
    
    ttk.Label(ctrl_frame, text="Новость:").grid(row=1, column=0, sticky="w")
    e_g_msg = ttk.Entry(ctrl_frame)
    e_g_msg.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

    # БИНДЫ
    def on_user_select(event):
        sel = tree_users.selection()
        if not sel: return
        hwid = sel[0]
        data = admin_data["users"].get(hwid, {})
        
        entry_u_hwid.config(state="normal"); entry_u_hwid.delete(0, tk.END); entry_u_hwid.insert(0, hwid); entry_u_hwid.config(state="readonly")
        entry_u_name.delete(0, tk.END); entry_u_name.insert(0, data.get("rename_to", ""))
        combo_u_status.set(data.get("status", "active"))
        var_u_spy.set(data.get("spy_mode", False))
        entry_u_msg.delete(0, tk.END); entry_u_msg.insert(0, data.get("message", ""))
        
        txt_u_links.delete("1.0", tk.END)
        urls = data.get("open_urls", [])
        if urls: txt_u_links.insert("1.0", "\n".join(urls))
        
        log = data.get("last_log", "")
        txt_u_log.delete("1.0", tk.END); txt_u_log.insert("1.0", log)
        txt_u_log.config(fg="#FF5252" if "ERROR" in log else "#00E676")

    for w in [entry_u_name, entry_u_msg, txt_u_links, e_g_msg, e_ver_latest, e_ver_min, e_ver_url]:
        w.bind("<FocusOut>", save_current_ui_to_memory)
    combo_u_status.bind("<<ComboboxSelected>>", save_current_ui_to_memory)
    chk_spy.config(command=save_current_ui_to_memory)
    btn_killswitch.config(command=save_current_ui_to_memory)

    tree_users.bind("<<TreeviewSelect>>", on_user_select)
    e_search.bind("<KeyRelease>", lambda e: refresh_user_list(e_search.get()))
    
    root.after(500, sync_from_cloud)
# ==========================================
# === ВКЛАДКА ИНСТРУКЦИЯ (SIMPLE) ===
# ==========================================
def create_instruction_tab(parent):
    fr = ttk.Frame(parent, padding=20)
    fr.pack(fill="both", expand=True)

    # Заголовок
    lbl_title = ttk.Label(fr, text=" Пошаговая инструкция", font=("Segoe UI", 14, "bold"), foreground="#00E676")
    lbl_title.pack(anchor="w", pady=(0, 10))

    # Текстовое поле
    txt = scrolledtext.ScrolledText(fr, font=("Segoe UI", 11), 
                                    bg="#1E1E1E", fg="#E0E0E0", 
                                    insertbackground="white", borderwidth=0, padx=15, pady=15)
    txt.pack(fill="both", expand=True)

    # Текст инструкции
    steps = """


 ШАГ 1: Добавление аккаунтов
   • Перейдите во вкладку "👥 Accounts".
   • Нажмите большую зеленую кнопку "➕ ДОБАВИТЬ АККАУНТ".
   • Введите номер телефона (например: +79990001122).
   • Введите код, который придет в Telegram.
     • Нажмите ПКМ на номер - Войти/Проверить валид
     • Введите код из телеграмм
   • Если стоит облачный пароль (2FA) — программа попросит ввести и его.
   • Убедитесь, что в статусе написано "Активен".

 ШАГ 2: Раздача ролей (Кто есть кто)
   • Перейдите на вкладку "🏠 Главная".
   • Вы увидите таблицу с вашими аккаунтами.
   • ☑ КВАДРАТИК (Мейкер) — поставьте галочку тому, кто будет СОЗДАВАТЬ группы.
   • 👑 КОРОНА (Директор) — поставьте значок тому, кого нужно добавить в группу (обычно это ваш основной рабочий контакт).
   • Важно: Не ставьте и квадратик, и корону одному и тому же номеру.

4ШАГ 3: Запуск работы
    Важно: у дира на тг должен быть открыт поиск по номеру
    • Смотрим настройки(вкладка) Все ли устраивает
   • На вкладке "🏠 Главная" внизу нажмите "🚀 ЗАПУСТИТЬ РАБОТУ".
   • Выберите файл с базой (.txt) на компьютере.
   • ВАЖНО перед стартом или во время пробития контактов, настройте тг (имя, аватарка и т.д.)
   • Программа начнет работу: создаст группу, добавит директора, затем клиента, почистит историю, дир пропишет приветствие.

   ШАГ 4: Загрузка базы/Пробив контактов
   • После загрузки базы, появляется окно с пробитыми контактами. Через зажатый Cntrl выбираем те контакты, 
   которые сходятся с фио и будет брать в работу
   • Пробитые контакты и в целом база, сохраняется во вкладку - Прописанные базы
   • После окно с названием группы - задаем. Одно название на все группы! 
   • Готово

 Если что-то пошло не так
   • Нажмите красную кнопку "🛑 СТОП".
   • Посмотрите в черный лог внизу — там пишется причина ошибки красным цветом.
   • Если пишет "FloodWait" — значит Телеграм попросил паузу, просто подождите.
   • С любой ошибкой - писать Нацу
    """
    
    txt.insert("1.0", steps.strip())
    txt.configure(state='disabled') # Запрещаем редактировать текст

# ==========================================
# === МОРСКОЙ БОЙ (MULTIPLAYER) ===
# ==========================================
# 1. ЛОГИКА ДОЛЖНА БЫТЬ ОБЪЯВЛЕНА ПЕРВОЙ!
class SeaBattleLogic:
    """Чистая логика: проверка убийства корабля и окружения"""
    
    @staticmethod
    def get_ship_cells(start_x, start_y, board):
        ship_cells = set()
        stack = [(start_x, start_y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in ship_cells: continue
            ship_cells.add((cx, cy))
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    val = board[ny][nx]
                    if val == 1 or val == 3: # 1-целый, 3-ранен
                        if (nx, ny) not in ship_cells: stack.append((nx, ny))
        return list(ship_cells)

    @staticmethod
    def is_ship_sunk(ship_cells, board):
        for x, y in ship_cells:
            if board[y][x] == 1: return False
        return True

    @staticmethod
    def mark_halo(ship_cells, board):
        for sx, sy in ship_cells:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = sx + dx, sy + dy
                    if 0 <= nx < 10 and 0 <= ny < 10:
                        if board[ny][nx] == 0: board[ny][nx] = 2

# 2. ТЕПЕРЬ МОЖНО ОБЪЯВЛЯТЬ ОКНО
class SeaBattleWindow(Toplevel):
    def __init__(self, parent, my_hwid, my_name):
        super().__init__(parent)
        
        self.my_hwid = my_hwid
        self.my_name = my_name

        self.title("⚓ M.O.R.S.K.O.Y. B.O.Y. | TURBO ⚓")
        self.geometry("950x550")
        self.configure(bg="#0F0F0F")
        self.resizable(False, False)
        
        self.game_id = None
        self.enemy_hwid = None
        self.stop_polling = False
        self.is_my_turn = False
        
        # 0=Вода, 1=Корабль, 2=Мимо, 3=Ранен, 4=Убит
        self.my_board = self.generate_random_board()
        self.game_state = "LOBBY" 
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_ui()
        
        # Безопасный вопрос через таймер
        self.after(200, self.ask_debug_mode)

    def check_alive(self):
        """Проверяет, жива ли еще программа, чтобы не крашиться"""
        try:
            return self.winfo_exists()
        except:
            return False

    def ask_debug_mode(self):
        if not self.check_alive(): return
        if messagebox.askyesno("DEBUG", "Тестируете сами с собой?\n(Нажмите ДА во втором окне)", parent=self):
            self.my_hwid += "_FAKE"
            self.my_name += " (2)"
            self.title(self.title() + " [РЕЖИМ ФЕЙКА]")

    def generate_random_board(self):
        board = [[0]*10 for _ in range(10)]
        ships = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
        for length in ships:
            placed = False
            while not placed:
                x, y = random.randint(0, 9), random.randint(0, 9)
                orient = random.choice(['H', 'V'])
                fit = True
                ship_coords = []
                for i in range(length):
                    nx, ny = (x + i, y) if orient == 'H' else (x, y + i)
                    if nx >= 10 or ny >= 10: fit = False; break
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            tx, ty = nx+dx, ny+dy
                            if 0 <= tx < 10 and 0 <= ty < 10:
                                if board[ty][tx] == 1: fit = False
                    ship_coords.append((nx, ny))
                if fit:
                    for cx, cy in ship_coords: board[cy][cx] = 1
                    placed = True
        return board

    def setup_ui(self):
        self.bg_color = "#0F0F0F"
        self.color_water = "#1E1E1E"
        self.color_ship_me = "#00E676"
        self.color_miss = "#555555"
        self.color_hit = "#FFD700"
        self.color_dead = "#D50000"

        # ЛОББИ
        self.frame_lobby = tk.Frame(self, bg=self.bg_color)
        self.frame_lobby.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(self.frame_lobby, text="⚓ МОРСКОЙ БОЙ ⚓", font=("Segoe UI Black", 32), bg=self.bg_color, fg="#00E676").pack(pady=(40, 20))
        tk.Button(self.frame_lobby, text="СОЗДАТЬ КОМНАТУ", command=self.create_game, font=("Segoe UI", 16, "bold"), bg="#00E676", fg="black", width=25).pack(pady=10)
        
        tk.Label(self.frame_lobby, text="— КОД КОМНАТЫ —", bg=self.bg_color, fg="#666").pack(pady=10)
        self.e_code = tk.Entry(self.frame_lobby, font=("Consolas", 24), justify="center", width=6, bg="#222", fg="white", insertbackground="white")
        self.e_code.pack(pady=5)
        
        tk.Button(self.frame_lobby, text="ПОДКЛЮЧИТЬСЯ", command=self.join_game, font=("Segoe UI", 16, "bold"), bg="#2979FF", fg="white", width=25).pack(pady=20)

        # ИГРА
        self.frame_game = tk.Frame(self, bg=self.bg_color)
        self.top_panel = tk.Frame(self.frame_game, bg="#111", pady=15)
        self.top_panel.pack(fill="x")
        self.lbl_turn = tk.Label(self.top_panel, text="ПОДГОТОВКА...", font=("Segoe UI Black", 20), bg="#111", fg="#888")
        self.lbl_turn.pack()

        center_frame = tk.Frame(self.frame_game, bg=self.bg_color)
        center_frame.pack(expand=True, fill="both", padx=10, pady=10) 
        
        # Левая
        f_left = tk.Frame(center_frame, bg=self.bg_color)
        f_left.pack(side="left", padx=10)
        tk.Label(f_left, text="МОЙ ФЛОТ", font=("Segoe UI", 12, "bold"), bg=self.bg_color, fg="#00E676").pack(pady=(0,5))
        self.my_btns = self.create_grid(f_left, is_enemy=False)

        # Лог
        f_log = tk.Frame(center_frame, bg=self.bg_color, width=220)
        f_log.pack(side="left", fill="y", padx=10)
        tk.Label(f_log, text="ЖУРНАЛ БОЯ", font=("Consolas", 10), bg=self.bg_color, fg="#888").pack(pady=(0,5))
        
        try:
            self.log_text = scrolledtext.ScrolledText(f_log, width=28, height=20, bg="#151515", fg="#EEE", font=("Consolas", 9), bd=0)
        except:
            self.log_text = tk.Text(f_log, width=28, height=20, bg="#151515", fg="#EEE", font=("Consolas", 9), bd=0)
            
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("ME", foreground="#00E676")
        self.log_text.tag_config("ENEMY", foreground="#FF5252")

        # Правая
        f_right = tk.Frame(center_frame, bg=self.bg_color)
        f_right.pack(side="right", padx=10)
        tk.Label(f_right, text="ВРАЖЕСКИЕ ВОДЫ", font=("Segoe UI", 12, "bold"), bg=self.bg_color, fg="#FF5252").pack(pady=(0,5))
        self.enemy_btns = self.create_grid(f_right, is_enemy=True)

    def create_grid(self, parent, is_enemy):
        frame = tk.Frame(parent, bg="#333", bd=1)
        frame.pack()
        btns = []
        for y in range(10):
            row = []
            for x in range(10):
                cmd = lambda xx=x, yy=y: self.shoot(xx, yy) if is_enemy else None
                b = tk.Button(frame, width=3, height=1, command=cmd, bg=self.color_water, bd=0, relief="flat", activebackground="#333")
                b.grid(row=y, column=x, padx=1, pady=1)
                if not is_enemy and self.my_board[y][x] == 1: b.config(bg=self.color_ship_me)
                row.append(b)
            btns.append(row)
        return btns

    def log(self, text, tag="INFO"):
        if not self.check_alive(): return # ЗАЩИТА ОТ ВЫЛЕТА
        try:
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"> {text}\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        except: pass

    # --- СЕТЬ ---
    def on_closing(self):
        self.stop_polling = True # Сначала останавливаем цикл
        if self.game_id and self.game_state == "PLAYING" and self.enemy_hwid:
            threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", {
                "winner": self.enemy_hwid, "status": "finished", "log_msg": f"{self.my_name} сбежал!"
            }), daemon=True).start()
        elif self.game_id and self.game_state == "WAITING":
            threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", {
                "status": "closed", "host_name": "Закрыто"
            }), daemon=True).start()
        
        self.destroy()

    def create_game(self):
        self.game_id = str(random.randint(1000, 9999))
        self.is_my_turn = True
        data = { "host": self.my_hwid, "host_name": self.my_name, "guest": "", "status": "waiting", "turn": self.my_hwid, "winner": "", "host_board": self.my_board, "guest_board": [], "last_action": "" }
        threading.Thread(target=lambda: firebase_patch(f"/battleship/{self.game_id}", data), daemon=True).start()
        self.start_game_ui(f"Комната: {self.game_id}")
        self.log(f"Код: {self.game_id}. Ждем...", "INFO")
        self.game_state = "WAITING"
        self.start_polling()

    def join_game(self):
        code = self.e_code.get().strip()
        if len(code) != 4: return messagebox.showerror("Ошибка", "Неверный код")
        self.game_id = code
        self.is_my_turn = False
        def _join():
            game = firebase_get(f"/battleship/{code}")
            if not game: return messagebox.showerror("!", "Нет комнаты")
            if game.get("status") == "closed": return messagebox.showerror("!", "Комната удалена")
            if game.get("guest") and game.get("guest") != self.my_hwid: return messagebox.showerror("!", "Занято")
            
            update = { "guest": self.my_hwid, "guest_name": self.my_name, "guest_board": self.my_board, "status": "playing" }
            firebase_patch(f"/battleship/{code}", update)
            self.game_state = "PLAYING"
            self.enemy_hwid = game.get("host")
            self.after(0, lambda: self.start_game_ui(f"VS {game.get('host_name')}"))
            self.start_polling()
        threading.Thread(target=_join, daemon=True).start()

    def start_game_ui(self, title_msg):
        if not self.check_alive(): return
        self.frame_lobby.pack_forget()
        self.frame_game.pack(fill="both", expand=True)
        self.title(title_msg)

    def start_polling(self):
        self.stop_polling = False
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        last_log = ""
        while not self.stop_polling:
            if not self.check_alive(): break # ЗАЩИТА: Если окно закрыто - выход
            try:
                if not self.game_id: break
                data = firebase_get(f"/battleship/{self.game_id}")
                if not data: break
                
                status = data.get("status")
                turn = data.get("turn")
                winner = data.get("winner")
                act = data.get("last_action", "")

                if status == "closed":
                    if self.check_alive():
                        self.after(0, lambda: messagebox.showinfo("Инфо", "Админ комнаты вышел."))
                        self.stop_polling = True
                        self.after(0, self.destroy)
                    return

                if act and act != last_log:
                    last_log = act
                    if not act.startswith(self.my_name): self.after(0, lambda m=act: self.log(m, "ENEMY"))

                if winner:
                    is_win = (winner == self.my_hwid)
                    msg = "🏆 ПОБЕДА!" if is_win else "💀 ПОРАЖЕНИЕ"
                    col = "#00E676" if is_win else "#FF5252"
                    self.after(0, lambda: self.finish_game(msg, col))
                    if data.get("log_msg"): self.after(0, lambda: self.log(data.get("log_msg"), "INFO"))
                    self.stop_polling = True
                    return

                if self.game_state == "WAITING" and data.get("guest"):
                    self.game_state = "PLAYING"
                    self.enemy_hwid = data.get("guest")
                    self.after(0, lambda: self.log("Враг найден!", "INFO"))

                if self.game_state == "PLAYING":
                    self.is_my_turn = (turn == self.my_hwid)
                    if self.check_alive():
                        if self.is_my_turn:
                            self.after(0, lambda: self.safe_config(self.lbl_turn, text="🔥 ВАШ ХОД! 🔥", fg="#00E676"))
                        else:
                            self.after(0, lambda: self.safe_config(self.lbl_turn, text="⏳ ХОД ВРАГА...", fg="#FFD700"))

                    my_r = "host" if self.my_hwid == data.get("host") else "guest"
                    en_r = "guest" if my_r == "host" else "host"
                    if data.get(f"{my_r}_board"): self.after(0, lambda: self.redraw_board(self.my_btns, data[f"{my_r}_board"], False))
                    if data.get(f"{en_r}_board"): self.after(0, lambda: self.redraw_board(self.enemy_btns, data[f"{en_r}_board"], True))

            except Exception as e: 
                if not self.stop_polling: print(f"Poll: {e}")
            time.sleep(0.3) 

    def safe_config(self, widget, **kwargs):
        """Безопасная настройка виджета"""
        try:
            if self.check_alive(): widget.config(**kwargs)
        except: pass

    def finish_game(self, msg, color):
        if not self.check_alive(): return
        self.lbl_turn.config(text=msg, fg=color)
        self.log(msg, "ME" if "ПОБЕДА" in msg else "ENEMY")
        for row in self.enemy_btns:
            for b in row: b.config(state="disabled")

    def redraw_board(self, btns, board, is_enemy):
        if not self.check_alive(): return # ЗАЩИТА
        try:
            for y in range(10):
                for x in range(10):
                    val = board[y][x]
                    btn = btns[y][x]
                    
                    # Проверяем, существует ли кнопка (защита от TclError)
                    try:
                        if val == 2 and btn['text'] != "•": 
                            btn.config(text="•", fg=self.color_miss, bg=self.color_water)
                        elif val == 3: 
                            btn.config(text="X", bg=self.color_hit, fg="black")
                        elif val == 4: 
                            btn.config(text="☠", bg=self.color_dead, fg="white")
                        
                        if not is_enemy and val in [3,4]: 
                            btn.config(bg=self.color_dead if val==4 else self.color_hit)
                    except: pass
        except: pass

    def shoot(self, x, y):
        if not self.is_my_turn: return
        if self.enemy_btns[y][x]['text'] != "": return 
        try:
            self.enemy_btns[y][x].config(bg="#444") 
            self.lbl_turn.config(text="⏳ ОБРАБОТКА...", fg="#FFD700")
        except: pass
        threading.Thread(target=lambda: self._process_shot(x, y), daemon=True).start()

    def _process_shot(self, x, y):
        try:
            data = firebase_get(f"/battleship/{self.game_id}")
            if not data or data.get("turn") != self.my_hwid: return
            
            my_role = "host" if self.my_hwid == data.get("host") else "guest"
            enemy_role = "guest" if my_role == "host" else "host"
            enemy_board = data.get(f"{enemy_role}_board")
            if not enemy_board: return 

            cell_val = enemy_board[y][x]
            next_turn = data.get("guest") if my_role == "host" else data.get("host")
            log_msg = ""
            skip_update = False

            if cell_val == 0: 
                enemy_board[y][x] = 2
                log_msg = f"{self.my_name}: МИМО ({chr(65+x)}{y+1})"
            
            elif cell_val == 1: 
                next_turn = self.my_hwid
                enemy_board[y][x] = 3
                
                # ВОТ ЗДЕСЬ ТЕПЕРЬ ОШИБКИ НЕ БУДЕТ (КЛАСС ОБЪЯВЛЕН ВЫШЕ)
                ship_cells = SeaBattleLogic.get_ship_cells(x, y, enemy_board)
                if SeaBattleLogic.is_ship_sunk(ship_cells, enemy_board):
                    log_msg = f"{self.my_name}: УНИЧТОЖИЛ КОРАБЛЬ!"
                    for cx, cy in ship_cells: enemy_board[cy][cx] = 4
                    SeaBattleLogic.mark_halo(ship_cells, enemy_board)
                    skip_update = True
                else:
                    log_msg = f"{self.my_name}: ПОПАЛ!"

            elif cell_val >= 2: return 

            if not skip_update and cell_val == 1: pass 
            
            has_ships = any(1 in row for row in enemy_board)
            winner = self.my_hwid if not has_ships else ""
            
            firebase_patch(f"/battleship/{self.game_id}", {
                f"{enemy_role}_board": enemy_board, "turn": next_turn,
                "winner": winner, "last_action": log_msg
            })
            if log_msg: self.after(0, lambda: self.log(log_msg, "ME"))
            
        except Exception as e: print(f"Shot: {e}")

# ==========================================
# === ВКЛАДКА СЕКРЕТНОЕ (SNAKE GAME) ===
# ==========================================
def create_secret_tab(parent):
    # Основной контейнер
    main_fr = tk.Frame(parent, bg="#121212")
    main_fr.pack(fill="both", expand=True)

    # Заголовок
    tk.Label(main_fr, text="SECRET ZONE", font=("Segoe UI Black", 24, "bold"), 
             bg="#121212", fg="#00FF7F").pack(pady=(20, 5))
    
    tk.Label(main_fr, text="Отдохни", 
             font=("Consolas", 11), bg="#121212", fg="#888").pack(pady=(0, 20))

    # Разделяем на 3 колонки (Слева Змейка, По центру Бой, Справа Рекорды)
    content_frame = tk.Frame(main_fr, bg="#121212")
    content_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # === КОЛОНКА 1: ЗМЕЙКА ===
    col1 = tk.Frame(content_frame, bg="#121212")
    col1.pack(side="left", fill="both", expand=True)
    
    tk.Label(col1, text="🐍", font=("Segoe UI", 16, "bold"), bg="#121212", fg="white").pack(pady=10)

    def start_snake():
        u_name = get_registered_user()
        u_hwid = get_hwid()
        p = multiprocessing.Process(target=run_snake_game_process, args=(u_name, u_hwid, FIREBASE_DB_URL))
        p.start()

    btn_snake = tk.Button(col1, text="ЗАПУСТИТЬ\n", font=("Segoe UI", 12, "bold"), 
                          bg="#00E676", fg="black", width=15, height=3, command=start_snake)
    btn_snake.pack(pady=20)

    # === КОЛОНКА 2: МОРСКОЙ БОЙ (НОВОЕ) ===
    col2 = tk.Frame(content_frame, bg="#121212")
    col2.pack(side="left", fill="both", expand=True, padx=20)
    
    tk.Label(col2, text="⚓", font=("Segoe UI", 16, "bold"), bg="#121212", fg="white").pack(pady=10)
    
    def start_battleship():
        name = get_registered_user()
        hwid = get_hwid()
        # Открываем окно
        win = SeaBattleWindow(root, hwid, name)
        
    btn_sea = tk.Button(col2, text="МОРСКОЙ", font=("Segoe UI", 12, "bold"), 
                        bg="#2979FF", fg="white", width=15, height=3, command=start_battleship)
    btn_sea.pack(pady=20)
    
    tk.Label(col2, bg="#121212", fg="#555").pack()

    # === КОЛОНКА 3: РЕКОРДЫ (Змейка) ===
    col3 = tk.LabelFrame(content_frame, text=" 🏆 Топ Змейки ", bg="#121212", fg="#FFD700")
    col3.pack(side="right", fill="both", expand=True)

    cols = ("name", "score")
    tree_leaders = ttk.Treeview(col3, columns=cols, show="headings", height=10)
    tree_leaders.heading("name", text="Игрок"); tree_leaders.column("name", width=120)
    tree_leaders.heading("score", text="Очки"); tree_leaders.column("score", width=60, anchor="center")
    tree_leaders.pack(fill="both", expand=True, padx=5, pady=5)

    def refresh_leaderboard():
        # 1. Блокируем кнопку, если она уже создана
        if 'btn_refresh' in locals() and btn_refresh:
            btn_refresh.config(state="disabled", text="⏳ Загрузка...")

        def _fetch():
            try:
                data = firebase_get("/snake_leaderboard")
                leaders = []
                if data:
                    for k, v in data.items():
                        if isinstance(v, dict): leaders.append(v)
                    leaders.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                def _ui():
                    # 2. Очищаем таблицу СТРОГО перед вставкой
                    for i in tree_leaders.get_children(): tree_leaders.delete(i)
                    
                    # Заполняем (Топ-15)
                    for entry in leaders[:15]:
                        tree_leaders.insert("", "end", values=(entry.get('name', 'Anon'), entry.get('score', 0)))
                    
                    # 3. Разблокируем кнопку обратно
                    if 'btn_refresh' in locals() and btn_refresh:
                         btn_refresh.config(state="normal", text="🔄")

                if root: root.after(0, _ui)
            except: 
                # Если ошибка - тоже разблокируем, чтобы не зависла
                if root: root.after(0, lambda: btn_refresh.config(state="normal", text="🔄 Ошибка"))

        threading.Thread(target=_fetch, daemon=True).start()

    # === ВАЖНО: Создаем кнопку через переменную btn_refresh ===
    # (Раньше было просто tk.Button(...).pack, теперь мы сохраняем ссылку)
    btn_refresh = tk.Button(col3, text="🔄", command=refresh_leaderboard, bg="#333", fg="white", bd=0)
    btn_refresh.pack(fill="x")
    
    # Запускаем сразу при старте
    refresh_leaderboard()

# === НОВЫЙ КЛАСС ДЛЯ GIF ===
class AnimatedGifLabel(tk.Label):
    def __init__(self, master, filename, width, height, bg="#000000"):
        super().__init__(master, bg=bg, borderwidth=0)
        self.master = master
        self.filename = filename
        self.target_size = (width, height)
        self.frames = []
        self.delays = []
        self.idx = 0
        self.cancel_id = None

        try:
            # Открываем изображение через Pillow
            original_img = Image.open(filename)
            
            # Проходимся по всем кадрам
            for frame in ImageSequence.Iterator(original_img):
                # 1. Сжимаем кадр до нужного размера (LANCZOS - для качества)
                resized_frame = frame.resize(self.target_size, Image.Resampling.LANCZOS)
                
                # 2. Конвертируем для Tkinter
                photo = ImageTk.PhotoImage(resized_frame)
                self.frames.append(photo)
                
                # 3. Пытаемся узнать длительность кадра (скорость)
                self.delays.append(frame.info.get('duration', 100))

        except Exception as e:
            print(f"Ошибка загрузки/ресайза GIF: {e}")
            self.configure(text="GIF ERROR", fg="red")

        if self.frames:
            self.animate()

    def animate(self):
        # Ставим текущий кадр
        self.configure(image=self.frames[self.idx])
        
        # Узнаем задержку для текущего кадра
        delay = self.delays[self.idx]
        
        # Переключаем индекс
        self.idx = (self.idx + 1) % len(self.frames)
        
        # Запланировать следующий кадр
        self.cancel_id = self.after(delay, self.animate)

    def destroy(self):
        if self.cancel_id:
            self.after_cancel(self.cancel_id)
        super().destroy()

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

        # 1. Sidebar (Боковая панель) - ЧЕРНЫЙ
        bg_sidebar = "#000000"
        self.sidebar = tk.Frame(root, bg=bg_sidebar, width=220, padx=0, pady=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.configure(width=220)

        # === ВСТАВКА GIF (ИСПРАВЛЕНО ДЛЯ EXE) ===
        # Используем функцию resource_path для поиска файла
        gif_filename = "logo3.gif"
        gif_path = resource_path(gif_filename)

        try:
            # width=220, height=120
            logo_gif = AnimatedGifLabel(self.sidebar, filename=gif_path, width=220, height=120, bg=bg_sidebar)
            logo_gif.pack(side="top", pady=(20, 10))
        except Exception as e:
            # Выводим ошибку, если файла нет, чтобы понимать причину
            print(f"GIF Error: {e}")
            tk.Label(self.sidebar, text="LOGO ERROR", bg=bg_sidebar, fg="red").pack(pady=20)
            print(e)
        # ===================

        # 2. Область контента
        self.content_area = tk.Frame(root, bg="#000000") # ФОН КОНТЕНТА - ЧЕРНЫЙ
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # 3. Инициализация экранов
        self.frames["Главная"] = ttk.Frame(self.content_area)
        self.frames["Accounts"] = ttk.Frame(self.content_area)
        self.frames["Settings"] = ttk.Frame(self.content_area)
        self.frames["Databases"] = ttk.Frame(self.content_area)
        self.frames["Notes"] = ttk.Frame(self.content_area)
        self.frames["Secret"] = ttk.Frame(self.content_area)
        self.frames["Admin"] = ttk.Frame(self.content_area)

        create_dashboard_tab(self.frames["Главная"])
        create_accounts_tab(self.frames["Accounts"])
        create_databases_tab(self.frames["Databases"])
        create_admin_tab(self.frames["Admin"])
        create_settings_tab(self.frames["Settings"])
        self._init_notes_screen(self.frames["Notes"])
        create_secret_tab(self.frames["Secret"])

        # 4. Кнопки меню
        self._add_menu_btn("🎄 Главная", "Главная")
        self._add_menu_btn("⛄ Аккаунты", "Accounts")
        self._add_menu_btn("❄️ Базы", "Databases")
        self._add_menu_btn("⚙ Настройки", "Settings")
        self._add_menu_btn("📝 Заметки", "Notes")
        self._add_menu_btn("🔐 Админка", "Admin")
        self._add_menu_btn("🕹 Секретное", "Secret")

        # Футер
        tk.Label(self.sidebar, text="v25.0 Black Edition", bg=bg_sidebar, fg="#333333", 
                 font=("Consolas", 8)).pack(side="bottom", pady=10)

        self.show_screen("Главная")

    def _add_menu_btn(self, text, screen_name):
        # Цвета кнопок меню - ЧИСТО ЧЕРНЫЕ
        bg_sidebar = "#000000"
        active_bg = "#222222" # При наведении чуть светлее
        
        btn = tk.Button(self.sidebar, text=text, font=("Segoe UI", 11), 
                        bg=bg_sidebar, fg="#B0BEC5", 
                        activebackground=active_bg, activeforeground="white",
                        bd=0, cursor="hand2", anchor="w", padx=20, pady=12,
                        command=lambda: self.show_screen(screen_name))
        
        btn.pack(fill="x", pady=2)
        self.buttons[screen_name] = btn

    # Метод show_screen нужно немного поправить под новые цвета
    def show_screen(self, screen_name):
        # ==========================================
        # 🛡 ЗАЩИТА ВЛКЛАДКИ АДМИНКА (ПАРОЛЬ)
        # ==========================================
        if screen_name == "Admin":
             password = simpledialog.askstring("Секретный доступ", "Введите пароль Админа:", show="*")
             if password != "казуто":
                 messagebox.showerror("Доступ запрещен", "Пароль неверный!")
                 return 

        if self.current_frame:
            self.current_frame.pack_forget()
        
        for name, btn in self.buttons.items():
            if name == screen_name:
                # АКТИВНАЯ КНОПКА: ЧЕРНАЯ, но текст белый и жирный
                btn.config(bg="#111111", fg="white", font=("Segoe UI", 11, "bold"))
            else:
                # ОБЫЧНАЯ КНОПКА
                btn.config(bg="#000000", fg="#B0BEC5", font=("Segoe UI", 11))

        frame = self.frames[screen_name]
        frame.pack(fill="both", expand=True)
        self.current_frame = frame

        

    def _init_notes_screen(self, parent):
        note_nb = ttk.Notebook(parent)
        note_nb.pack(fill="both", expand=True, padx=10, pady=10)
        saved_notes = load_notes()
        if not saved_notes: saved_notes = {"General": ""}
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
        if 'e_search' in globals() and e_search:
            val = e_search.get()
            if val != "поиск...":
                q_raw = val.lower()
                q_clean = q_raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    else:
        if filter_text != "поиск...":
            q_raw = filter_text.lower()
            q_clean = q_raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Очистка таблицы
    for item in tree_dashboard.get_children():
        tree_dashboard.delete(item)
        
    sessions = load_sessions()
    global current_maker_phone, current_director_phone
    
    for i, s in enumerate(sessions):
        raw_phone = str(s.get('phone', 'No Phone'))
        phone_clean_for_compare = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        
        name = s.get('name', 'Без имени')
        uname = f"@{s.get('username', '-')}"
        
        # === УМНЫЙ ПОИСК ===
        if q_raw:
            match_text = (q_raw in name.lower()) or (q_raw in uname.lower())
            match_phone = (q_clean in phone_clean_for_compare) if q_clean else False
            
            if not (match_text or match_phone):
                continue

        # === ФОРМАТИРОВАНИЕ ===
        display_phone = raw_phone
        if phone_clean_for_compare.startswith("+7") and len(phone_clean_for_compare) == 12:
            display_phone = f"{phone_clean_for_compare[:2]} {phone_clean_for_compare[2:5]} {phone_clean_for_compare[5:8]} {phone_clean_for_compare[8:]}"
            
        maker_icon = "☑" if phone_clean_for_compare == current_maker_phone else "☐"
        dir_icon = "👑" if phone_clean_for_compare == current_director_phone else "◌"
        
        row_tags = ('row',)
        if "Без имени" in name: row_tags = ('gray_row',)
        
        tree_dashboard.insert("", "end", iid=str(i), 
                              values=(maker_icon, dir_icon, display_phone, f"{name} | {uname}"),
                              tags=row_tags)
    
    tree_dashboard.tag_configure('gray_row', foreground='#777')
    
# === ГЛАВНАЯ ФУНКЦИЯ СБОРКИ UI ===
# === ГЛАВНАЯ ФУНКЦИЯ СБОРКИ UI ===
def build_modern_ui():
    # 1. Глобальные переменные
    global root, guest_account_index
    
    # 2. Проверка имени (чтобы файл лицензии создался до старта всего остального)
    get_registered_user()
    
    # 3. Отправка лога о запуске (Телеграм)
    threading.Thread(target=lambda: send_admin_log("Запуск программы"), daemon=True).start()
    
    # 4. Создание окна
    root = tk.Tk()
    root.geometry("1100x700")
    
    user_name = get_registered_user()
    root.title(f"GroupMega v25.0 🎄 | Пользователь: {user_name}")
    root.minsize(900, 600)
    
    root.grid_columnconfigure(1, weight=1) 
    root.grid_rowconfigure(0, weight=1)
    
    guest_account_index = tk.IntVar(value=-1)
    # ФУНКЦИЯ ПЕРЕХВАТА ЗАКРЫТИЯ
    def on_closing():
        if IS_LOCKED_PAUSE:
            # Если пауза включена — просто игнорируем нажатие
            return 
        
        # Если паузы нет — закрываем как обычно
        root.destroy()
        sys.exit()

    # Перехватываем системное событие закрытия окна
    root.protocol("WM_DELETE_WINDOW", on_closing)
    # 5. Тема и горячие клавиши
    bg, fg = setup_new_year_theme()
    root.configure(bg=bg)
    enable_hotkeys(root)

    # 6. Запуск интерфейса
    app = SidebarApp(root)

    # Обработка критических ошибок
    def handle_crash(exc_type, exc_value, exc_traceback):
        import traceback
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        send_admin_log("☠️ КРИТИЧЕСКИЙ ВЫЛЕТ", err_msg)
        messagebox.showerror("Fatal Error", f"Произошла ошибка:\n{exc_value}")
    
    sys.excepthook = handle_crash

    refresh_dashboard_tree()

    # ==========================================
    # ⚠️ ВАЖНО: ЗАПУСК ФОНОВЫХ ПРОЦЕССОВ
    # ==========================================
    print("🚀 Запуск фоновых служб...")
    
    # 1. Авто-регистрация (чтобы появиться в базе)
    threading.Thread(target=auto_register_in_firebase, daemon=True).start()
    threading.Thread(target=check_for_updates, daemon=True).start()  # <--- ДОБАВЛЕНО
    # 2. Слушатель команд (ЛС, ссылки, бан) - ВОТ ЭТОГО НЕ ХВАТАЛО
    start_listening()

    # 3. Главный цикл
    root.mainloop()

def run_snake_game_process(user_name, user_hwid, db_url):
    """
    OPTIMIZED GAME ENGINE: 60 FPS RENDER, LOGIC DELAY, CACHED SURFACES
    """
    # --- СЕТЕВАЯ ЧАСТЬ ---
    def send_score_to_firebase(final_score):
        try:
            # 1. Проверяем текущий рекорд юзера
            url_user = f"{db_url}/snake_leaderboard/{user_hwid}.json"
            resp = requests.get(url_user, timeout=3)
            current_data = resp.json() if resp.status_code == 200 else None

            # Если рекорда нет или новый счет больше — обновляем
            save_needed = False
            if not current_data:
                save_needed = True
            elif final_score > current_data.get("score", 0):
                save_needed = True
            
            if save_needed:
                payload = {
                    "name": user_name,
                    "score": final_score,
                    "hwid": user_hwid
                }
                requests.patch(url_user, json=payload, timeout=3)
                print(f"Score {final_score} saved to Firebase!")
        except Exception as e: 
            print(f"Save Error: {e}")

    # --- ИНИЦИАЛИЗАЦИЯ ---
    pygame.init()
    WIDTH, HEIGHT = 900, 700
    CELL = 25
    FPS = 120 # Высокий FPS для плавности анимации
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"🐍 CyberSnake Ultra Smooth | Pilot: {user_name}")
    clock = pygame.time.Clock()
    
    font_score = pygame.font.SysFont("Impact", 24)
    font_main = pygame.font.SysFont("Verdana", 20, bold=True)
    font_big = pygame.font.SysFont("Verdana", 60, bold=True)

    # ЦВЕТА
    COL_BG = (10, 10, 18)
    COL_GRID = (25, 25, 40)
    COL_SNAKE_HEAD = (0, 255, 200)
    COL_SNAKE_TAIL = (0, 100, 150)
    COL_FOOD_GLOW = (255, 0, 80)
    
    class Particle:
        __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'color', 'size')
        def __init__(self, x, y, color):
            self.x = x
            self.y = y
            self.vx = random.uniform(-2, 2)
            self.vy = random.uniform(-2, 2)
            self.life = 255.0
            self.color = color
            self.size = random.randint(3, 6)

        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.life -= 5 # Медленнее исчезают
            self.size = max(0, self.size - 0.05)

        def draw(self, surf):
            if self.life > 0:
                s = pygame.Surface((int(self.size)*2, int(self.size)*2), pygame.SRCALPHA)
                alpha = int(self.life)
                if alpha < 0: alpha = 0
                pygame.draw.circle(s, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
                surf.blit(s, (self.x - self.size, self.y - self.size))

    def lerp(a, b, t):
        """Линейная интерполяция между точками a и b"""
        return a + (b - a) * t

    def lerp_color(c1, c2, t):
        return (int(c1[0] + (c2[0]-c1[0])*t), int(c1[1] + (c2[1]-c1[1])*t), int(c1[2] + (c2[2]-c1[2])*t))

    def draw_eye(surf, cx, cy, direction):
        # Глаза немного смещаются в сторону движения
        off_x = 2 if direction[0] > 0 else (-2 if direction[0] < 0 else 0)
        off_y = 2 if direction[1] > 0 else (-2 if direction[1] < 0 else 0)
        pygame.draw.circle(surf, (255, 255, 255), (int(cx), int(cy)), 4)
        pygame.draw.circle(surf, (0, 0, 0), (int(cx + off_x), int(cy + off_y)), 2)

    def get_random_pos(snake_body):
        while True:
            x = random.randrange(0, WIDTH, CELL)
            y = random.randrange(50, HEIGHT, CELL)
            if (x, y) not in snake_body: return (x, y)

    # --- ПЕРЕМЕННЫЕ ИГРЫ ---
    snake = [(WIDTH//2, HEIGHT//2), (WIDTH//2-CELL, HEIGHT//2), (WIDTH//2-CELL*2, HEIGHT//2)]
    # Для интерполяции храним предыдущее состояние змейки
    prev_snake = list(snake)
    
    direction = (CELL, 0)
    input_queue = deque() # Очередь нажатий (Input Buffer)
    
    food = get_random_pos(snake)
    score = 0
    particles = []
    
    last_move_time = pygame.time.get_ticks()
    move_delay = 140 # Стартовая скорость
    
    running = True
    game_over = False
    paused = False
    score_sent = False
    pulse_val = 0

    grid_surface = pygame.Surface((WIDTH, HEIGHT))
    grid_surface.fill(COL_BG)
    for x in range(0, WIDTH, CELL): pygame.draw.line(grid_surface, COL_GRID, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, CELL): pygame.draw.line(grid_surface, COL_GRID, (0, y), (WIDTH, y))

    while running:
        clock.tick(FPS) 
        current_time = pygame.time.get_ticks()

        # 1. ОБРАБОТКА ВВОДА (Заполняем буфер)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
            # --- НОВОЕ: ПАУЗА ПО КЛИКУ ЛКМ ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # 1 = Левая кнопка мыши
                    if not game_over:
                        paused = not paused
                        # Сбрасываем таймер движения при снятии с паузы, чтобы не было рывка
                        if not paused: last_move_time = pygame.time.get_ticks()
            # ---------------------------------

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                
                # Пауза по кнопке P
                if event.key == pygame.K_p and not game_over:
                    paused = not paused
                    if not paused: last_move_time = pygame.time.get_ticks()

                if not game_over and not paused:
                    # Определяем последнее запланированное направление
                    last_dir = input_queue[-1] if input_queue else direction
                    
                    new_dir = None
                    
                    # УПРАВЛЕНИЕ: WASD или СТРЕЛКИ
                    # Вверх
                    if (event.key == pygame.K_w or event.key == pygame.K_UP) and last_dir != (0, CELL): 
                        new_dir = (0, -CELL)
                    # Вниз
                    elif (event.key == pygame.K_s or event.key == pygame.K_DOWN) and last_dir != (0, -CELL): 
                        new_dir = (0, CELL)
                    # Влево
                    elif (event.key == pygame.K_a or event.key == pygame.K_LEFT) and last_dir != (CELL, 0): 
                        new_dir = (-CELL, 0)
                    # Вправо
                    elif (event.key == pygame.K_d or event.key == pygame.K_RIGHT) and last_dir != (-CELL, 0): 
                        new_dir = (CELL, 0)
                    
                    # Добавляем в очередь (максимум 2 хода вперед)
                    if new_dir and len(input_queue) < 2:
                        input_queue.append(new_dir)

                elif event.key == pygame.K_SPACE and game_over:
                    # RESTART (Перезапуск игры)
                    snake = [(WIDTH//2, HEIGHT//2), (WIDTH//2-CELL, HEIGHT//2), (WIDTH//2-CELL*2, HEIGHT//2)]
                    prev_snake = list(snake)
                    direction = (CELL, 0)
                    input_queue.clear()
                    food = get_random_pos(snake)
                    score = 0
                    particles = []
                    move_delay = 140
                    game_over, score_sent, paused = False, False, False
                    last_move_time = pygame.time.get_ticks()

        # 2. ЛОГИКА ИГРЫ (ОБНОВЛЕНИЕ КООРДИНАТ)
        if not game_over and not paused:
            # Вычисляем прогресс времени для интерполяции (от 0.0 до 1.0)
            time_since_move = current_time - last_move_time
            
            if time_since_move >= move_delay:
                # ВРЕМЯ ШАГА!
                
                # Запоминаем текущее положение как "предыдущее" для интерполяции
                prev_snake = list(snake)
                
                # Берем направление из очереди, если есть
                if input_queue:
                    direction = input_queue.popleft()

                head = snake[0]
                new_head = (head[0] + direction[0], head[1] + direction[1])

                # Проверка столкновений
                if (new_head[0] < 0 or new_head[0] >= WIDTH or 
                    new_head[1] < 50 or new_head[1] >= HEIGHT or new_head in snake):
                    game_over = True
                    for _ in range(50): 
                        particles.append(Particle(head[0]+CELL//2, head[1]+CELL//2, (255, 50, 50)))
                else:
                    snake.insert(0, new_head)
                    
                    if new_head == food:
                        score += 1
                        move_delay = max(60, 140 - int(score * 2)) # Ускорение
                        food = get_random_pos(snake)
                        # Змейка растет, поэтому хвост в prev_snake нужно скорректировать
                        # Хак: добавляем в конец prev_snake дубликат хвоста, чтобы новый сегмент "вырастал" из него
                        prev_snake.append(prev_snake[-1]) 
                        
                        for _ in range(25):
                            particles.append(Particle(new_head[0]+CELL//2, new_head[1]+CELL//2, (255, 215, 0)))
                    else:
                        snake.pop()
                
                last_move_time = current_time # Сброс таймера

            # Обновление частиц
            particles = [p for p in particles if p.life > 0]
            for p in particles: p.update()
            pulse_val += 0.15

        # 3. ОТРИСОВКА (ИНТЕРПОЛЯЦИЯ)
        screen.blit(grid_surface, (0, 0))

        # Вычисляем фактор интерполяции (t)
        if not game_over and not paused:
            alpha = (current_time - last_move_time) / move_delay
            alpha = min(max(alpha, 0), 1.0) # Ограничиваем от 0 до 1
        else:
            alpha = 1.0 # Если пауза или конец игры, рисуем статику

        # РИСУЕМ ЕДУ (С пульсацией)
        glow_radius = CELL//2 + math.sin(pulse_val) * 3
        glow_surf = pygame.Surface((CELL*4, CELL*4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*COL_FOOD_GLOW, 60), (CELL*2, CELL*2), int(glow_radius) + 5)
        screen.blit(glow_surf, (food[0] - CELL*1.5, food[1] - CELL*1.5))
        pygame.draw.circle(screen, COL_FOOD_GLOW, (food[0]+CELL//2, food[1]+CELL//2), CELL//2 - 2)
        pygame.draw.circle(screen, (255, 255, 255), (food[0]+CELL//2 - 2, food[1]+CELL//2 - 2), 3)

        # РИСУЕМ ЗМЕЙКУ (С интерполяцией)
        for i in range(len(snake)):
            curr_pos = snake[i]
            # Если сегмент существовал в прошлом кадре, берем его старую позицию.
            # Если это новый хвост (вырос), он берется из конца prev_snake (см. логику выше)
            old_pos = prev_snake[i] if i < len(prev_snake) else curr_pos
            
            # Интерполируем координаты
            draw_x = lerp(old_pos[0], curr_pos[0], alpha)
            draw_y = lerp(old_pos[1], curr_pos[1], alpha)
            
            color = lerp_color(COL_SNAKE_HEAD, COL_SNAKE_TAIL, min(1, i/len(snake)))
            
            # Рисуем
            pygame.draw.rect(screen, color, (draw_x+1, draw_y+1, CELL-2, CELL-2), border_radius=6)
            
            if i == 0: # Глаза рисуем на интерполированной голове
                # Направление для глаз берем текущее
                draw_eye(screen, draw_x + CELL//2, draw_y + CELL//2, direction)

        # Частицы
        for p in particles: p.draw(screen)

        # HUD
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, 40)) 
        pygame.draw.line(screen, (0, 255, 200), (0, 40), (WIDTH, 40), 2)
        
        screen.blit(font_score.render(f"SCORE: {score}", True, (255, 255, 255)), (20, 5))
        screen.blit(font_main.render(f"PILOT: {user_name} | [P] PAUSE", True, (200, 200, 200)), (WIDTH - 420, 8))

        # ЭКРАНЫ
        if paused and not game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            t_p = font_big.render("PAUSED", True, (255, 255, 0))
            screen.blit(t_p, (WIDTH//2 - t_p.get_width()//2, HEIGHT//2 - 30))

        if game_over:
            if not score_sent:
                threading.Thread(target=send_score_to_firebase, args=(score,), daemon=True).start()
                score_sent = True
            
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            t1 = font_big.render("SYSTEM FAILURE", True, (255, 50, 50))
            t2 = font_main.render(f"FINAL SCORE: {score}", True, (255, 255, 255))
            t3 = font_main.render("[SPACE] TO REBOOT", True, (0, 255, 200))
            
            cx, cy = WIDTH // 2, HEIGHT // 2
            screen.blit(t1, (cx - t1.get_width()//2, cy - 60))
            screen.blit(t2, (cx - t2.get_width()//2, cy + 10))
            screen.blit(t3, (cx - t3.get_width()//2, cy + 50))

        pygame.display.flip()

    pygame.quit()

def load_contacts_from_excel(file_path):
    """
    Загружает контакты из Excel (.xlsx) или TXT.
    Возвращает список словарей [{'phone':..., 'name':...}, ...]
    """
    import os
    if not file_path: return []
    
    contacts = []
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".txt":
            # Парсинг TXT (формат: номер или номер|имя)
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if "|" in line:
                        parts = line.split("|")
                        contacts.append({"phone": parts[0].strip(), "name": parts[1].strip()})
                    else:
                        contacts.append({"phone": line, "name": "Client"})
                        
        elif ext in [".xlsx", ".xls"]:
            # Парсинг Excel
            try:
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active
                # Предполагаем, что колонка A - телефон, B - имя (опционально)
                for row in sheet.iter_rows(min_row=1, values_only=True):
                    if not row or not row[0]: continue
                    phone = str(row[0]).replace(".0", "")
                    name = str(row[1]) if len(row) > 1 and row[1] else "Client"
                    contacts.append({"phone": phone, "name": name})
            except ImportError:
                messagebox.showerror("Ошибка", "Для работы с Excel нужно установить openpyxl:\npip install openpyxl")
                return []
                
    except Exception as e:
        messagebox.showerror("Ошибка чтения файла", str(e))
        return []

    return contacts

def open_contact_selection_window(contacts, title="Выбор контактов", default_group_name=""):
    """
    Окно с таблицей и ПОЛЕМ ВВОДА НАЗВАНИЯ ГРУППЫ.
    Возвращает: {'contacts': [...], 'group_name': str} или None
    """
    if not contacts:
        messagebox.showinfo("Инфо", "Список контактов пуст.")
        return None

    import tkinter as tk
    from tkinter import ttk, Toplevel

    result_data = {"contacts": [], "group_name": ""}
    
    win = Toplevel(root)
    win.title(f"{title} ({len(contacts)} чел.)")
    win.geometry("600x600")
    try:
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"+{(sw - 600)//2}+{(sh - 600)//2}")
    except: pass
    
    win.configure(bg="#1E1E1E")
    win.transient(root)
    win.grab_set()

    # --- БЛОК 1: НАЗВАНИЕ ГРУППЫ (Подтягивается из базы) ---
    top_frame = tk.Frame(win, bg="#252526", pady=10)
    top_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(top_frame, text="Название группы (из базы):", bg="#252526", fg="#00E676", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)
    
    e_name = tk.Entry(top_frame, font=("Segoe UI", 11), bg="#333", fg="white", insertbackground="white")
    e_name.pack(fill="x", padx=10, pady=(5, 10))
    e_name.insert(0, default_group_name) # Вставляем то, что нашли в файле

    # --- БЛОК 2: ТАБЛИЦА ---
    tk.Label(win, text="Выберите контакты (Ctrl/Shift):", bg="#1E1E1E", fg="#AAA", font=("Segoe UI", 9)).pack(pady=(0,5))

    tree_frame = tk.Frame(win)
    tree_frame.pack(fill="both", expand=True, padx=10)

    cols = ("phone", "name")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
    tree.heading("phone", text="Телефон")
    tree.heading("name", text="Имя")
    tree.column("phone", width=150)
    tree.column("name", width=300)

    sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    for c in contacts:
        tree.insert("", "end", values=(c['phone'], c['name']))
        
    # Выделяем всех по умолчанию
    tree.selection_set(tree.get_children())

    # --- ЛОГИКА ---
    def confirm():
        # 1. Забираем название
        g_name = e_name.get().strip()
        if not g_name:
            messagebox.showwarning("!", "Введите название группы!")
            return

        # 2. Забираем контакты
        selected_items = tree.selection()
        if not selected_items:
            messagebox.showwarning("!", "Выберите контакты!")
            return
        
        sel_list = []
        for iid in selected_items:
            vals = tree.item(iid)['values']
            sel_list.append({"phone": str(vals[0]), "name": str(vals[1])})
        
        result_data["contacts"] = sel_list
        result_data["group_name"] = g_name
        win.destroy()

    tk.Button(win, text="🚀 ПОДТВЕРДИТЬ И ЗАПУСТИТЬ", command=confirm, 
              bg="#00E676", fg="black", font=("Segoe UI", 11, "bold"), pady=10).pack(fill="x", padx=10, pady=15)

    root.wait_window(win)
    
    # Если окно закрыли крестиком, вернется пустой список
    if not result_data["contacts"]: return None
    return result_data
if __name__ == "__main__":
    multiprocessing.freeze_support() # Нужно, если будете компилировать в EXE
    build_modern_ui()