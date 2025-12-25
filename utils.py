import os
import sys
import json
import uuid
import hashlib
import random
import requests
import re
import threading
import time
from datetime import datetime

# Импортируем конфиг для доступа к путям и константам
import config

# ==========================================
# СИСТЕМНЫЕ ФУНКЦИИ (HWID, ПУТИ)
# ==========================================

def get_hwid():
    """Получает уникальный ID железа (для лицензии/идентификации)"""
    try:
        mac = uuid.getnode()
        return hashlib.md5(str(mac).encode()).hexdigest()
    except:
        return "unknown_hwid"

def resource_path(relative_path):
    """Получает путь к ресурсам (работает и в IDE, и в EXE)"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==========================================
# FIREBASE (БАЗА ДАННЫХ)
# ==========================================

def firebase_patch(path, data):
    """Отправляет PATCH запрос в Firebase"""
    try:
        requests.patch(f"{config.FIREBASE_DB_URL}{path}.json", json=data, timeout=10)
    except: 
        pass

def firebase_get(path):
    """Получает данные из Firebase"""
    try:
        resp = requests.get(f"{config.FIREBASE_DB_URL}{path}.json", timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except: 
        return None

# ==========================================
# КОНФИГУРАЦИЯ И ФАЙЛЫ
# ==========================================

def load_config(filepath="config.json"):
    """Загружает настройки бота"""
    defaults = {
        "delay_creation": "180", 
        "delay_contact": "20", 
        "random_delay": "1",
        "sessions_dir": "sessions",
        "api_id": "",          
        "api_hash": "",
        "proxy_list": []       
    }
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"Ошибка чтения конфига: {e}")

    # ОБНОВЛЯЕМ ГЛОБАЛЬНУЮ ПЕРЕМЕННУЮ ПУТИ К СЕССИЯМ
    config.SESSIONS_DIR = defaults.get("sessions_dir", "sessions")
    
    return defaults

def save_config(cfg, filepath="config.json"):
    """Сохраняет настройки в файл"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        # Сразу обновляем глобалку при сохранении
        config.SESSIONS_DIR = cfg.get("sessions_dir", "sessions")
    except Exception as e:
        print(f"Config Save Error: {e}")

# ==========================================
# РАБОТА С СЕССИЯМИ
# ==========================================

def load_sessions(filepath="sessions.json"):
    """Загружает список сессий из JSON"""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: 
                return json.load(f)
        except: 
            pass
    return []

def save_sessions(sessions, filepath="sessions.json"):
    """Сохраняет список сессий в JSON"""
    try:
        with open(filepath, "w", encoding="utf-8") as f: 
            json.dump(sessions, f, indent=4)
    except Exception as e: 
        # ВАЖНО: Используем print вместо messagebox, чтобы избежать 
        # циклического импорта GUI -> Utils -> GUI
        print(f"Ошибка сохранения сессий: {e}")

def update_session_info(phone, full_name, username):
    """Обновляет информацию о сессии (имя, юзернейм) в файле"""
    sessions = load_sessions()
    updated = False
    for s in sessions:
        if s.get('phone') == phone:
            s['name'] = full_name
            s['username'] = username
            s['last_used'] = time.time()
            updated = True
            break
    
    if updated:
        save_sessions(sessions)

# ==========================================
# ЭМУЛЯЦИЯ УСТРОЙСТВ (ANDROID)
# ==========================================

def get_random_device_config():
    """Генерирует параметры реального Android-устройства для Telegram"""
    models = [
        {"device_model": "Samsung Galaxy S24 Ultra", "system_version": "Android 14"},
        {"device_model": "Xiaomi 14 Pro", "system_version": "Android 14"},
        {"device_model": "Google Pixel 8 Pro", "system_version": "Android 14"},
        {"device_model": "OnePlus 12", "system_version": "Android 14"},
        {"device_model": "Samsung Galaxy S23 Ultra", "system_version": "Android 13"},
        {"device_model": "Samsung Galaxy Z Fold 5", "system_version": "Android 13"},
        {"device_model": "Xiaomi 13T Pro", "system_version": "Android 13"},
        {"device_model": "Poco F5 Pro", "system_version": "Android 13"}
    ]
    
    # Базовые параметры
    base_config = {
        "app_version": "10.9.1",  # Версия Telegram
        "lang_code": "en",
        "system_lang_code": "en-US"
    }
    
    # Добавляем случайную модель
    base_config.update(random.choice(models))
    return base_config

def ensure_device_config(session_data=None):
    """Возвращает конфиг устройства, если он не передан"""
    if session_data and isinstance(session_data, dict) and "device_model" in session_data:
        return session_data
    return get_random_device_config()