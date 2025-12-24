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
import tkinter.simpledialog as simpledialog
import os
import json
import random
import time
import subprocess
import sys
import requests  # <--- ДОБАВЛЕНО ВОТ ЭТО
import re
from bs4 import BeautifulSoup
from datetime import datetime
from telethon.errors import UserAlreadyParticipantError
import google.generativeai as genai

# ==== конфиги ====
def load_config(filepath="config.json"):
    defaults = {
        "delay_creation": "180", "delay_contact": "20", "random_delay": "1",
        
        # Smart Mode (По базе)
        "smart_add_director": "1", 
        "smart_add_clients": "1",
        "smart_send_greeting": "1",

        # Manual Mode (По умолчанию)
        "manual_default_dir": "1",
        "manual_default_contact": "0", # <--- НОВАЯ НАСТРОЙКА
        "manual_default_greet": "1",
        
        "greeting_text": "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?"
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
    print(f"[{tag}] {text}") # Дублируем в консоль IDE
    
    if log_widget:
        def _log():
            try:
                if log_widget.winfo_exists():
                    log_widget.config(state='normal')
                    log_widget.insert(tk.END, text + "\n", tag)
                    log_widget.see(tk.END)
                    log_widget.config(state='disabled')
            except: pass
        
        try:
            if root and root.winfo_exists():
                root.after(0, _log)
        except: pass


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

        # Кнопки
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
    Парсер: сохраняет шапку, ищет кандидатов И ДАТУ РОЖДЕНИЯ.
    """
    data = {"company_name": "Unknown_Company", "director_name": None, "candidates": [], "original_header": ""}

    # 1. ГЛАВНОЕ РАЗДЕЛЕНИЕ
    parts = re.split(r'\+?={10,}', file_content)

    if len(parts) > 1:
        header_content = parts[0]
        candidates_content = "\n".join(parts[1:])
    else:
        header_content = file_content
        candidates_content = ""

    data["original_header"] = header_content.strip()

    # --- ЧАСТЬ 1: ПАРСИНГ ДАННЫХ ИЗ ШАПКИ ---
    header_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', header_content)
    if header_match: 
        data["company_name"] = header_match.group(1).strip()
    else:
        fallback_match = re.search(r'["«“]([^"»”]+)["»”]', header_content)
        if fallback_match:
            data["company_name"] = fallback_match.group(1).strip()
    
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
                dob = "" # Переменная для даты рождения
                
                # Ищем ФИО + Дата (Пример: ИВАНОВ ИВАН ИВАНОВИЧ 12.05.1990)
                nm = re.search(r'^([А-ЯЁ\s]+)\s+(\d{2}\.\d{2}\.\d{4})', sec, re.MULTILINE)
                if nm: 
                    name = nm.group(1).strip()
                    dob = nm.group(2).strip() # Запоминаем дату
                else:
                    # Если даты нет, ищем просто ФИО
                    nm2 = re.search(r'^([А-ЯЁ]{2,}\s+[А-ЯЁ]{2,}\s+[А-ЯЁ]{2,})', sec, re.MULTILINE)
                    if nm2: name = nm2.group(1).strip()
                
                # Сохраняем и имя, и дату
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
    
    # === МОМЕНТАЛЬНЫЙ СТОП ===
    # Мы делим ожидание на кусочки по 0.5 сек.
    # Если нажали СТОП — выходим из паузы мгновенно.
    end_time = time.time() + delay
    while time.time() < end_time:
        if stop_flag.is_set():
            return # Прерываем сон
        await asyncio.sleep(0.5)

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
        # Получаем понятное имя для логов
        if hasattr(user, 'first_name'):
            u_name = f"{user.first_name} {user.last_name or ''}".strip()
        else:
            u_name = f"User_ID_{getattr(user, 'user_id', 'Unknown')}"
            
        log_msg("INFO", f"   👤 Инвайт: {u_name}...")

        try:
            # Пытаемся добавить
            await client(functions.messages.AddChatUserRequest(
                chat_id=chat.id, 
                user_id=user, 
                fwd_limit=100
            ))
            log_msg("SUCCESS", f"   ✅ {u_name} добавлен.")
        except UserAlreadyParticipantError:
            log_msg("INFO", f"   ℹ️ {u_name} уже в группе.")
            return True # Это успех, идем дальше
        except UserPrivacyRestrictedError:
            log_msg("WARN", f"   🚫 Приватность: {u_name} запретил инвайт.")
            return False
        except UserChannelsTooMuchError:
            log_msg("WARN", f"   🚫 У {u_name} лимит (слишком много групп).")
            return False
            
        # Пауза перед чисткой сообщения "User joined"
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        try:
            # Чистим сервисные сообщения о вступлении
            msgs = await client.get_messages(chat, limit=3)
            # Ищем сообщения типа "ServiceMessage" (action)
            ids = [m.id for m in msgs if m.action and (m.action_message or isinstance(m.action, types.MessageActionChatAddUser))] 
            if ids: 
                await client.delete_messages(chat, ids, revoke=True)
                log_msg("INFO", "   🧹 Следы вступления зачищены.")
        except Exception as e:
            # Ошибка чистки не критична
            pass
            
        return True

    except PeerFloodError:
        log_msg("ERROR", "   ⛔ FLOOD WAIT! Телеграм запретил инвайт на время.")
        raise # Пробрасываем ошибку наверх, чтобы остановить поток
    except Exception as e:
        log_msg("WARN", f"   ⚠️ Ошибка инвайта: {e}")
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
    

async def process_smart_target_file(maker_client, guest_client, file_path, guest_session_dict=None, pre_approved_data=None, pre_group_name=None):
    try:
        parsed_data = {"candidates": []}
        original_company_name = "Unknown"
        
        # 1. Читаем и парсим файл
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
        log_msg("INFO", f"🔍 Записей в файле: {len(candidates_list)}. Начинаем глубокий пробив...")

        # 2. Подготовка: Разбиваем людей на отдельные номера
        batch_list = []
        tracking_map = {} # client_id -> {данные из файла}

        for cand in candidates_list:
            phones = cand.get('phones', [])
            # Берем ФИО из файла
            fio_file = cand.get('full_name', cand.get('target_fio', cand.get('fio', 'Unknown')))
            
            for raw_phone in phones:
                # Чистим номер
                d = re.sub(r'\D', '', raw_phone)
                if not d: continue
                
                if len(d) == 11 and d.startswith('8'): ph = "+7" + d[1:]
                elif len(d) == 11 and d.startswith('7'): ph = "+" + d
                elif len(d) == 10 and d.startswith('9'): ph = "+7" + d
                else: ph = "+" + d
                
                # Генерируем ID для отслеживания
                my_client_id = random.randint(100000000, 999999999)
                
                tracking_map[my_client_id] = {
                    'fio_file': fio_file,
                    'phone_clean': ph,
                    'phone_orig': raw_phone
                }
                
                # Добавляем в список на импорт с ВРЕМЕННЫМ именем
                batch_list.append(types.InputPhoneContact(
                    client_id=my_client_id,
                    phone=ph,
                    first_name=fio_file[:20], 
                    last_name=""
                ))

        found_matches = []
        
        # 3. Обработка пачками (Импорт -> Удаление -> Получение реального инфо)
        chunk_size = 10 
        for i in range(0, len(batch_list), chunk_size):
            chunk = batch_list[i : i + chunk_size]
            
            try:
                # А. Импорт (Добавляем в контакты)
                res = await maker_client(functions.contacts.ImportContactsRequest(contacts=chunk))
                
                # Б. Сбор данных
                imported_ids_to_delete = []
                users_to_refetch = []
                
                # Карта: Telegram_ID -> Наш_Client_ID
                tg_id_map = {imp.user_id: imp.client_id for imp in res.imported}
                
                for u in res.users:
                    if u.id in tg_id_map:
                        imported_ids_to_delete.append(u.id)
                        # Сохраняем данные для повторного запроса (ID + Hash)
                        users_to_refetch.append(types.InputUser(user_id=u.id, access_hash=u.access_hash))

                # В. !!! УДАЛЕНИЕ ИЗ КОНТАКТОВ !!! 
                # Это ключевой момент. Пока они в контактах, мы видим имя из файла.
                # Как только удалили — мы видим их публичное имя.
                if imported_ids_to_delete:
                    await maker_client(functions.contacts.DeleteContactsRequest(id=imported_ids_to_delete))
                
                # Г. ЗАПРОС ЧИСТЫХ ДАННЫХ
                if users_to_refetch:
                    try:
                        clean_users = await maker_client(functions.users.GetUsersRequest(id=users_to_refetch))
                    except:
                        # Если не вышло (редко), используем то, что есть
                        clean_users = res.users

                    for u in clean_users:
                        # Находим, кто это был по ID
                        c_id = tg_id_map.get(u.id)
                        orig = tracking_map.get(c_id)
                        
                        if orig:
                            found_matches.append({
                                'target_fio': orig['fio_file'], # ФИО из файла
                                'phone': orig['phone_clean'],   # Номер
                                'user': u                       # Объект User с РЕАЛЬНЫМ именем
                            })

                await asyncio.sleep(1.0) 

            except FloodWaitError as e:
                log_msg("WARN", f"⏳ Ждем {e.seconds} сек (FloodWait)...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log_msg("ERROR", f"Ошибка на пачке номеров: {e}")

        if not found_matches:
            log_msg("WARN", "⚠️ Ни один номер не найден в Telegram.")
            return [], None, None

        # 4. Окно выбора
        future_gui = asyncio.get_running_loop().create_future()
        
        def show_gui():
            win = MatchReviewWindow(root, found_matches, original_company_name)
            root.wait_window(win)
            if win.result is not None: future_gui.set_result(win.result)
            else: future_gui.set_result([])
            
        root.after(0, show_gui)
        selected_matches = await future_gui
        
        if not selected_matches: return [], None, None

        # 5. Имя групп
        future_name = asyncio.get_running_loop().create_future()
        def ask_name():
            res = simpledialog.askstring("Название", "Введите имя для групп:", initialvalue=original_company_name, parent=root)
            future_name.set_result(res)
        root.after(0, ask_name)
        
        final_name = await future_name
        if not final_name: final_name = original_company_name

        return [], final_name, selected_matches

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
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, PasswordHashInvalidError, UserNotMutualContactError,
    UserChannelsTooMuchError, PhoneCodeInvalidError, UserAlreadyParticipantError
)

def start_process(mode="smart"):
    try:
        # Всегда просим файл
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not file_path: return 

        stop_flag.clear()
        log_widget.config(state='normal')
        log_widget.delete("1.0", tk.END)
        log_widget.config(state='disabled')

        sessions_data = load_sessions()
        selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
        if not selected_indices: 
            messagebox.showwarning("!", "Выберите мейкеров!")
            return

        guest_idx = guest_account_index.get()
        guest_session = None
        if guest_idx != -1 and guest_idx < len(sessions_data):
            guest_session = sessions_data[guest_idx]
            if guest_idx in selected_indices: selected_indices.remove(guest_idx)

        main_sessions = [sessions_data[i] for i in selected_indices]
        if not main_sessions: 
            messagebox.showwarning("!", "Список мейкеров пуст!")
            return

        cfg = load_config()
        greeting_text = cfg.get("greeting_text", "")
        need_greet = int(cfg.get("smart_send_greeting", "1"))

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "random": int(cfg.get("random_delay", 1)),
            "smart_add_director": int(cfg.get("smart_add_director", 1)),
            "smart_add_clients": int(cfg.get("smart_add_clients", 1))
        }

        dummy_names = []; manual_username = ""     

        if 'smart_btn' in globals(): smart_btn.config(state='disabled')
        
        # ЗАПУСК НАПРЯМУЮ (БЕЗ SAFETY CHECK)
        threading.Thread(
            target=run_thread,
            args=(main_sessions, guest_session, dummy_names, delays, manual_username, greeting_text, need_greet, file_path),
            daemon=True
        ).start()
            
    except Exception as e:
        messagebox.showerror("Критическая ошибка запуска", str(e))
        if 'smart_btn' in globals() and smart_btn: smart_btn.config(state='normal')

async def worker_task(session, delays, guest_session=None, smart_file_path=None, pre_approved_chunk=None, pre_group_name=None, manual_names=None, manual_target_user=None, greeting_text="", lock=None):
    # Явный импорт
    from telethon import TelegramClient, functions, types
    from telethon.errors import FloodWaitError, UserAlreadyParticipantError

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    raw_phone = session['phone']
    phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    
    # 1. Клиент Мейкера
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    # 2. Клиент Директора (Гостя)
    client_guest = None
    need_director = int(delays.get("smart_add_director", 1)) if not manual_names else int(delays.get("manual_add_director", 1))
    
    if guest_session and need_director:
        g_phone = guest_session['phone'].replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        client_guest = TelegramClient(f"session_{g_phone}", int(guest_session['api_id']), guest_session['api_hash'])

    created_links = [] 
    my_id = None

    try:
        await client.connect()
        if client_guest: await client_guest.connect()

        if not await client.is_user_authorized():
            log_msg("WARN", f"🔐 {phone}: Требуется вход! (Пропуск)")
            return {'maker_id': None, 'links': []}
        
        if client_guest and not await client_guest.is_user_authorized():
            log_msg("WARN", f"🔐 Директор не авторизован! Вход отменен.")
            client_guest = None 

        me = await client.get_me()
        my_id = me.id
        try: await hide_maker_phone(client)
        except: pass
        
        # ОПРЕДЕЛЕНИЕ РЕЖИМА
        names = []
        smart_users = []
        is_smart_mode = False
         
        if manual_names:
            names = manual_names
            smart_users = [None] * len(names)
        elif pre_approved_chunk:
            is_smart_mode = True
            names = [pre_group_name or "Group" for _ in range(len(pre_approved_chunk))]
            smart_users = pre_approved_chunk

        if not names: return {'maker_id': my_id, 'links': []}

        # Настройка инвайта
        need_invite_to_chat = delays.get("manual_add_contacts", 0) if manual_names else delays.get("smart_add_clients", 1)

        # === ЦИКЛ РАБОТЫ ПО ГРУППАМ ===
        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            
            curr_contact = smart_users[i] if i < len(smart_users) else None
            log_msg("INFO", f"🛠 {phone}: Группа {i+1}/{len(names)}...")

            try:
                # --- [ЭТАП 1] СОХРАНЕНИЕ В КНИГУ ---
                saved_contact_user = None
                if is_smart_mode and curr_contact:
                    try:
                        # 1. Подготовка номера
                        raw_c_phone = curr_contact.get('phone', '')
                        d = re.sub(r'\D', '', raw_c_phone)
                        if len(d) == 11 and d.startswith('8'): c_phone_clean = "+7" + d[1:]
                        elif len(d) == 11 and d.startswith('7'): c_phone_clean = "+" + d
                        elif len(d) == 10 and d.startswith('9'): c_phone_clean = "+7" + d
                        else: c_phone_clean = "+" + d
                        
                        # 2. ОПРЕДЕЛЕНИЕ ИМЕНИ ДЛЯ СОХРАНЕНИЯ (ИЗМЕНЕНО)
                        # По умолчанию используем номер телефона как имя (чтобы не палить имя из файла)
                        save_first_name = c_phone_clean
                        save_last_name = ""
                        
                        # Если у нас есть реальный объект User (после проверки базы), берем имя из него
                        if curr_contact.get('user'):
                            u_obj = curr_contact['user']
                            if hasattr(u_obj, 'first_name') and u_obj.first_name:
                                save_first_name = u_obj.first_name
                            if hasattr(u_obj, 'last_name') and u_obj.last_name:
                                save_last_name = u_obj.last_name

                        # 3. Импорт с правильным именем
                        import_res = await client(functions.contacts.ImportContactsRequest(contacts=[
                            types.InputPhoneContact(
                                client_id=random.randint(1000000, 99999999), 
                                phone=c_phone_clean,
                                first_name=save_first_name[:40], # Реальное имя из ТГ
                                last_name=save_last_name
                            )
                        ]))
                        
                        if import_res.users:
                            saved_contact_user = import_res.users[0]
                            real_name_log = f"{saved_contact_user.first_name} {saved_contact_user.last_name or ''}".strip()
                            log_msg("INFO", f"   📒 Сохранен как в ТГ: {real_name_log}")
                        else:
                            # Повторная попытка (без плюса), если не вышло
                            if c_phone_clean.startswith("+"):
                                c_phone_retry = c_phone_clean[1:]
                                retry_res = await client(functions.contacts.ImportContactsRequest(contacts=[
                                    types.InputPhoneContact(
                                        client_id=random.randint(1000000, 99999999), 
                                        phone=c_phone_retry, 
                                        first_name=save_first_name[:40], 
                                        last_name=save_last_name
                                    )
                                ]))
                                if retry_res.users:
                                    saved_contact_user = retry_res.users[0]
                                    log_msg("INFO", f"   📒 Сохранен (поп.2)")

                    except Exception as e:
                        log_msg("WARN", f"   ⚠️ Ошибка импорта контакта: {e}")

                # --- [ЭТАП 2] СОЗДАНИЕ ГРУППЫ ---
                res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                
                # --- [ЭТАП 3] ССЫЛКА ---
                invite_link = None
                try:
                    invite = await client(functions.messages.ExportChatInviteRequest(peer=chat))
                    invite_link = invite.link
                    created_links.append(invite_link)
                except Exception as e:
                    log_msg("ERROR", f"   ❌ Ошибка ссылки: {e}")

                # === [ЭТАП 3.5] ДИРЕКТОР ЗАХОДИТ (С ОЧЕРЕДЬЮ И ЗАЩИТОЙ) ===
                if client_guest and invite_link:
                    context_manager = lock if lock else asyncio.NullContext()
                    async with context_manager:
                        try:
                            wait_guest = random.uniform(07.0, 15.0) 
                            log_msg("WAIT", f"   ⏳ Директор ждет очереди {wait_guest:.1f} сек...")
                            await asyncio.sleep(wait_guest)

                            hash_arg = invite_link.replace("https://t.me/+", "").replace("https://t.me/joinchat/", "").strip()
                            updates = await client_guest(functions.messages.ImportChatInviteRequest(hash=hash_arg))
                            
                            if greeting_text:
                                new_chat = updates.chats[0] if updates.chats else None
                                if new_chat:
                                    await asyncio.sleep(2)
                                    await client_guest.send_message(new_chat, greeting_text)
                                    log_msg("GUEST", f"   😎 Директор зашел и написал.")
                                else:
                                    log_msg("GUEST", f"   😎 Директор зашел.")
                        except UserAlreadyParticipantError:
                            log_msg("GUEST", "   ℹ️ Директор уже там.")
                        except FloodWaitError as fe:
                             log_msg("ERROR", f"   ⛔ FLOOD WAIT у Директора! Спим {fe.seconds} сек.")
                             await asyncio.sleep(fe.seconds)
                        except Exception as e:
                            log_msg("WARN", f"   ⚠️ Директор не смог зайти: {e}")

                # --- [ЭТАП 4] ИНВАЙТ КЛИЕНТА ---
                if need_invite_to_chat:
                    if saved_contact_user:
                        await asyncio.sleep(1)
                        await add_and_clean(client, chat, saved_contact_user, delays)
                    else:
                        if is_smart_mode: log_msg("WARN", "   ℹ️ Инвайт невозможен: контакт не сохранился.")
                else:
                    if is_smart_mode: log_msg("INFO", "   🚫 Инвайт выключен (Клиент остался в книге).")

                # --- ПАУЗА ---
                if i < len(names) - 1:
                    wait_t = delays.get('creation', 180)
                    log_msg("WAIT", f"⏳ Пауза {wait_t} сек...")
                    await smart_sleep(wait_t, False) 

            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Флуд {e.seconds} сек.")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка в цикле группы: {e}")

        return {'maker_id': my_id, 'links': created_links}

    except Exception as e: 
        log_msg("ERROR", f"❌ Критическая ошибка Worker: {e}")
        return {'maker_id': None, 'links': []}
    finally:
        if client.is_connected(): await client.disconnect()
        if client_guest and client_guest.is_connected(): await client_guest.disconnect()

async def guest_execution_final(session, target_group_ids, greeting_text):
    if not target_group_ids:
        log_msg("WARN", "⚠️ Нет новых групп для приветствия.")
        return

    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    phone = session['phone']
    
    client = TelegramClient(f"session_{phone.replace(' ','')}", api_id, api_hash)
    
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

                # Отправка сообщения
                title = getattr(target_entity, 'title', str(gid))
                log_msg("DEBUG", f"   ✍️ Пишем в '{title}'...")
                
                await client.send_message(target_entity, greeting_text)
                log_msg("SUCCESS", f"   📨 Сообщение отправлено!")
                count_sent += 1
                
                # Пауза
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except Exception as e:
                log_msg("WARN", f"   ⚠️ Ошибка отправки в {gid}: {e}")
                if "FloodWait" in str(e):
                    await asyncio.sleep(10)

        log_msg("GUEST", f"🏁 ГОСТЬ: Рассылка завершена ({count_sent} из {len(target_group_ids)}).")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Гостя: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

# === ОБНОВЛЕННЫЙ ЗАПУСК ПОТОКОВ ===
def run_thread(main_sessions, guest_session, names, delays, target_username_manual, greeting_text, need_greet, smart_file_path=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # !!! СОЗДАЕМ ЗАМОК ДЛЯ ДИРЕКТОРА !!!
    director_lock = asyncio.Lock()

    try:
        if not main_sessions: return

        chunks_data = [] 
        is_manual = False
        group_name_smart = None

        # --- ЛОГИКА ЛИДЕРА (Проверка базы) ---
        if smart_file_path:
            leader_session = main_sessions[0]
            log_msg("INFO", f"👑 Лидер ({leader_session['phone']}) проверяет базу...")
            
            leader_client = TelegramClient(f"session_{leader_session['phone']}", int(leader_session['api_id']), leader_session['api_hash'], loop=loop)
            guest_client = None
            if guest_session:
                 guest_client = TelegramClient(f"session_{guest_session['phone']}", int(guest_session['api_id']), guest_session['api_hash'], loop=loop)

            async def run_leader_check():
                try:
                    await leader_client.connect()
                    if not await leader_client.is_user_authorized():
                        log_msg("ERROR", "❌ Лидер не авторизован!")
                        return None, None, None
                    if guest_client: await guest_client.connect()
                    
                    return await process_smart_target_file(
                        leader_client, guest_client, smart_file_path, guest_session
                    )
                except Exception as e:
                    log_msg("ERROR", f"Ошибка Лидера: {e}")
                    return None, None, None
                finally:
                    if leader_client.is_connected(): await leader_client.disconnect()
                    if guest_client and guest_client.is_connected(): await guest_client.disconnect()

            _, group_name_smart, selected_raw_data = loop.run_until_complete(run_leader_check())
            
            if not selected_raw_data:
                log_msg("WARN", "⛔ Отмена пользователем или пусто.")
                return
            
            chunks_data = selected_raw_data
            
        elif names:
            is_manual = True
            chunks_data = names
            log_msg("INFO", f"🛠 Запуск РУЧНОГО режима: {len(names)} групп.")

        # --- РАСПРЕДЕЛЕНИЕ ЗАДАЧ ---
        total_items = len(chunks_data)
        num_makers = len(main_sessions)
        if num_makers == 0: return
        
        chunk_size = (total_items + num_makers - 1) // num_makers
        chunks = [chunks_data[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
        
        log_msg("INFO", f"📦 Распределение: {total_items} задач на {num_makers} акк.")

        # --- ЗАПУСК WORKERS ---
        maker_tasks = []
        final_greet_text = greeting_text if need_greet else ""

        for i, session in enumerate(main_sessions):
            if i < len(chunks) and chunks[i]:
                # Передаем lock в каждый worker
                if is_manual:
                    task = worker_task(
                        session=session, 
                        delays=delays, 
                        guest_session=guest_session, 
                        manual_names=chunks[i],
                        manual_target_user=target_username_manual,
                        greeting_text=final_greet_text,
                        lock=director_lock # <--- ВАЖНО
                    )
                else:
                    task = worker_task(
                        session=session, 
                        delays=delays, 
                        guest_session=guest_session, 
                        pre_approved_chunk=chunks[i], 
                        pre_group_name=group_name_smart,
                        greeting_text=final_greet_text,
                        lock=director_lock # <--- ВАЖНО
                    )
                maker_tasks.append(task)

        if maker_tasks:
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            total_links = 0
            for res in results:
                if res and isinstance(res, dict) and res.get('links'): 
                    total_links += len(res['links'])
            
            log_msg("INFO", f"🏁 Работа завершена. Всего групп: {total_links}")
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка Run Thread: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try: loop.close()
        except: pass
        
def restore_buttons():
    try:
        if root:
            if 'start_btn' in globals() and start_btn: 
                start_btn.config(state='normal')
            if 'smart_btn' in globals() and smart_btn: 
                smart_btn.config(state='normal')
    except: pass


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

# ==========================================
# === НОВЫЙ БЛОК: ФУНКЦИИ ДЛЯ ЖЕЛТОЙ КНОПКИ ===
# ==========================================

def parse_custom_file(content):
    """
    Парсер с защитой от ИНН и ОГРН.
    Ищет номера, начинающиеся строго на 7, 8 или 9.
    """
    candidates = []
    # Разбиваем по длинным разделителям (-----------------------)
    sections = re.split(r'-{5,}', content)
    
    for sec in sections:
        if not sec.strip(): continue
        
        # 1. Ищем телефоны (СТРОГИЙ ФИЛЬТР)
        # Ищем 10-11 цифр, но они ОБЯЗАНЫ начинаться на 7, 8 или 9.
        # Это отсекает ИНН типа 1157... или 50..., но оставляет мобильные.
        raw_nums = re.findall(r'\b(?:7|8|9)\d{9,10}\b', sec)
        
        phones = []
        for p in raw_nums:
            # Доп. защита от годов рождения (19xx, 20xx)
            if not ((p.startswith('19') or p.startswith('20')) and len(p)==4):
                phones.append(p)
        
        if phones:
            name = "Unknown"
            dob = ""
            
            # 2. Ищем ФИО и Дату
            match = re.search(r'([А-ЯЁ][А-ЯЁ\s-]{4,})\s+(\d{2}\.\d{2}\.\d{4})', sec)
            
            if match:
                name = match.group(1).strip()
                dob = match.group(2).strip()
            else:
                # Если даты нет, берем просто ФИО
                match_name = re.search(r'([А-ЯЁ][А-ЯЁ\s-]{4,})', sec)
                if match_name:
                    name = match_name.group(1).strip()
            
            # Очистка имени от лишних слов (Руководитель и т.д., если попали)
            if "РУКОВОДИТЕЛЬ" in name.upper(): name = "Руководитель"
            
            candidates.append({"fio": name, "dob": dob, "phones": phones})

    return candidates

async def process_check_and_save(file_path):
    sessions = load_sessions()
    if not sessions:
        messagebox.showerror("Ошибка", "Нет активных сессий!")
        return

    # Берем первый аккаунт
    session = sessions[0] 
    api_id = int(session['api_id'])
    api_hash = session['api_hash']
    
    raw_phone = session['phone']
    phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    
    try:
        log_msg("INFO", f"🔌 Подключение: {phone}...")
        await client.connect()
        
        if not await client.is_user_authorized():
            messagebox.showerror("Ошибка", f"Аккаунт {phone} не авторизован!")
            return

        # === ЧТЕНИЕ ФАЙЛА С АВТО-ОПРЕДЕЛЕНИЕМ КОДИРОВКИ ===
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='cp1251') as f: content = f.read()
                log_msg("INFO", "⚠️ Файл был в кодировке Windows (cp1251). Прочитан успешно.")
            except:
                messagebox.showerror("Ошибка", "Не удалось прочитать файл (непонятная кодировка).")
                return

        # Ищем имя компании для названия файла
        comp_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', content)
        company_name = comp_match.group(1).strip() if comp_match else "Base"
        
        # Парсим
        candidates = parse_custom_file(content)
        
        # === ОТЛАДКА ДЛЯ ВАС ===
        total_phones = sum(len(c['phones']) for c in candidates)
        log_msg("DEBUG", f"📊 Найдено кандидатов: {len(candidates)}")
        log_msg("DEBUG", f"📞 Всего телефонов (после фильтра): {total_phones}")
        
        if not candidates:
            messagebox.showwarning("Пусто", "Не удалось найти контакты. Проверьте формат файла.")
            return

        log_msg("INFO", f"🚀 Начинаем пробив {len(candidates)} чел...")

        batch_list = []
        tracking_map = {} 

        # Подготовка данных
        for cand in candidates:
            for raw in cand['phones']:
                d = re.sub(r'\D', '', raw)
                # Коррекция номеров для РФ
                if len(d) == 11 and d.startswith('8'): import_phone = "+7" + d[1:]
                elif len(d) == 11 and d.startswith('7'): import_phone = "+" + d
                elif len(d) == 10 and d.startswith('9'): import_phone = "+7" + d
                else: import_phone = "+" + d # Остальные как есть
                
                my_client_id = random.randint(10000000, 999999999)
                tracking_map[my_client_id] = {
                    'fio': cand['fio'], 'dob': cand['dob'], 'orig_phone': raw.strip()
                }
                
                batch_list.append(types.InputPhoneContact(
                    client_id=my_client_id, 
                    phone=import_phone, 
                    first_name=cand['fio'][:20], 
                    last_name=""
                ))

        found_matches = []
        all_imported_ids = []

        # Импорт (УМЕНЬШИЛ ПАЧКУ ДО 5 ЧТОБЫ ТЕЛЕГРАМ НЕ РУГАЛСЯ)
        chunk_size = 5 
        
        for i in range(0, len(batch_list), chunk_size):
            chunk = batch_list[i : i + chunk_size]
            log_msg("INFO", f"   🔎 Проверка {i+1}-{min(i+len(chunk), len(batch_list))}...")
            
            try:
                res = await client(functions.contacts.ImportContactsRequest(contacts=chunk))
                
                # Собираем ID, кого ТГ нашел
                for u in res.users: all_imported_ids.append(u.id)
                
                # Маппинг
                tg_id_to_client = {imp.user_id: imp.client_id for imp in res.imported}
                
                users_refetch = [types.InputUser(user_id=u.id, access_hash=u.access_hash) for u in res.users if u.id in tg_id_to_client]
                
                if users_refetch:
                    clean_users = await client(functions.users.GetUsersRequest(id=users_refetch))
                    for u in clean_users:
                        c_id = tg_id_to_client.get(u.id)
                        orig = tracking_map.get(c_id)
                        if orig:
                            found_matches.append({
                                'target_fio': orig['fio'], 'target_dob': orig['dob'],
                                'user': u, 'phone': orig['orig_phone']
                            })
                            log_msg("SUCCESS", f"      ✅ Есть: {orig['fio']}")
                else:
                    # Если ТГ вернул пустой список, но ошибок нет
                    if res.imported or res.retry_contacts:
                         log_msg("DEBUG", f"      ⚠️ Telegram принял номера, но не вернул юзеров (возможно, у них скрыты номера).")
                    else:
                         log_msg("WARN", f"      ⚠️ Telegram ничего не вернул. Возможно, лимит на аккаунте.")

                # Пауза побольше, чтобы не словить бан
                await asyncio.sleep(random.uniform(2.0, 4.0))

            except FloodWaitError as e:
                log_msg("WARN", f"⏳ Ждем {e.seconds} сек (FloodWait)...")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"Err: {e}")

        if not found_matches:
            messagebox.showinfo("Результат", "Никого не нашли.\nЛибо на номерах нет Telegram, либо аккаунт временно ограничен на добавление контактов.");
            return

        # Окно выбора
        future_gui = asyncio.get_running_loop().create_future()
        def show_gui():
            win = MatchReviewWindow(root, found_matches, company_name)
            root.wait_window(win)
            if win.result is not None: future_gui.set_result(win.result)
            else: future_gui.set_result([])
        root.after(0, show_gui)
        
        selected_matches = await future_gui

        # Если отмена
        if not selected_matches:
            log_msg("WARN", "⛔ Отмена. Чистка...")
            try:
                for k in range(0, len(all_imported_ids), 50):
                    await client(functions.contacts.DeleteContactsRequest(id=all_imported_ids[k:k+50]))
            except: pass
            return

        # === СОХРАНЕНИЕ ===
        log_msg("INFO", "💾 Сохранение...")
        
        # Удаляем лишних из книги
        selected_tg_ids = [m['user'].id for m in selected_matches]
        ids_to_del = [uid for uid in all_imported_ids if uid not in selected_tg_ids]
        
        if ids_to_del:
            try:
                for k in range(0, len(ids_to_del), 50):
                    await client(functions.contacts.DeleteContactsRequest(id=ids_to_del[k:k+50]))
            except: pass

        # Запись файла
        save_dir = "прописанные базы"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        safe_name = re.sub(r'[\\/*?:"<>|]', "", company_name).strip() or "Base"
        filename = f"{safe_name}_CHECKED_{ts}.txt"
        
        with open(os.path.join(save_dir, filename), "w", encoding="utf-8") as f:
            # Оригинальная шапка (берем из content, так надежнее)
            head_split = re.split(r'-{5,}', content)
            if head_split: f.write(head_split[0].strip() + "\n")
            
            f.write("\n" + "="*40 + "\n")
            f.write(f"Группа: {company_name}\n")
            f.write("ОТЧЕТ ПРОБИВА\n\n")

            for m in selected_matches:
                line_fio = m['target_fio']
                if m.get('target_dob'): line_fio += f" {m['target_dob']}"
                
                u = m['user']
                tg_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                if u.username: tg_name += f" (@{u.username})"
                
                f.write(f"{line_fio} /\n")
                f.write(f" {m['phone']} /\n")
                f.write(f" {tg_name}\n")
                f.write("-" * 36 + "\n\n")
        
        log_msg("SUCCESS", f"✅ Готово! Файл: {filename}")
        messagebox.showinfo("Готово", f"Сохранено: {len(selected_matches)} чел.")

    except Exception as e:
        log_msg("ERROR", f"Critical: {e}"); messagebox.showerror("Err", str(e))
    finally:
        if client.is_connected(): await client.disconnect()

def run_check_save_thread():
    """Запускает процесс желтой кнопки в потоке."""
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")], title="Выберите базу для пробива")
    if not file_path: return

    # Очистка лога перед стартом
    log_widget.config(state='normal')
    log_widget.delete("1.0", tk.END)
    log_widget.config(state='disabled')

    threading.Thread(target=lambda: asyncio.run(process_check_and_save(file_path)), daemon=True).start()

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

def load_config(filepath="config.json"):
    defaults = {
        "delay_creation": "180", "delay_contact": "20", "random_delay": "1",
        
        # Smart Mode (По базе)
        "smart_add_director": "1", 
        "smart_add_clients": "1",
        "smart_send_greeting": "1",

        # Manual Mode (По умолчанию)
        "manual_default_dir": "1",
        "manual_default_contact": "0", # <--- НОВАЯ НАСТРОЙКА
        "manual_default_greet": "1",
        
        "greeting_text": "Приветствую! Пишу по делу, есть пара вопросов. Удобно переговорить?"
    }
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: defaults.update(json.load(f))
        except: pass
    return defaults

# === ЛОГИКА ВКЛАДКИ НАСТРОЕК (CONTROL CENTER) ===
def create_settings_tab(parent):
    cfg = load_config()
    
    canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0)
    sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)
    
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    setup_scroll_canvas(canvas, scroll_frame) 

    pad = 20

    # 1. ПАНЕЛЬ ЗАПУСКА
    lbl_title = tk.Label(scroll_frame, text="ПУЛЬТ УПРАВЛЕНИЯ", font=("Segoe UI Black", 14), bg="#121212", fg="#9D00FF")
    lbl_title.pack(anchor="w", padx=pad, pady=(20, 10))

    f_btns = ttk.Frame(scroll_frame)
    f_btns.pack(fill="x", padx=pad, pady=(0, 20))
    
    # Кнопка ручного режима (Мануал)
    btn_manual = ttk.Button(f_btns, text="🛠 РУЧНОЙ РЕЖИМ (Мануал)", command=open_manual_mode_window)
    btn_manual.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=10)
    
    # Кнопка нового окна
    btn_new = ttk.Button(f_btns, text="❐ НОВОЕ ОКНО (Мультизапуск)", command=open_new_window)
    btn_new.pack(side="left", fill="x", expand=True, ipady=10)

    # 2. ГЛОБАЛЬНЫЕ ТАЙМИНГИ
    lbl_sets = tk.Label(scroll_frame, text="ГЛОБАЛЬНЫЕ НАСТРОЙКИ", font=("Segoe UI Black", 14), bg="#121212", fg="#00E676")
    lbl_sets.pack(anchor="w", padx=pad, pady=(0, 10))

    time_frame = ttk.LabelFrame(scroll_frame, text=" ⏱ Тайминги (сек) ", padding=15)
    time_frame.pack(fill="x", padx=pad, pady=(0, 10))

    f_t1 = ttk.Frame(time_frame); f_t1.pack(fill="x", pady=5)
    ttk.Label(f_t1, text="После создания группы:").pack(side="left")
    e1 = ttk.Entry(f_t1, width=8, font=("Consolas", 10), justify="center")
    e1.pack(side="right"); e1.insert(0, cfg.get("delay_creation", "180"))

    f_t2 = ttk.Frame(time_frame); f_t2.pack(fill="x", pady=5)
    ttk.Label(f_t2, text="После инвайта контакта:").pack(side="left")
    e2 = ttk.Entry(f_t2, width=8, font=("Consolas", 10), justify="center")
    e2.pack(side="right"); e2.insert(0, cfg.get("delay_contact", "20"))
    
    var_rand = tk.IntVar(value=int(cfg.get("random_delay", "1")))
    ttk.Checkbutton(time_frame, text="Случайная задержка (+5..15с)", variable=var_rand).pack(anchor="w", pady=(10, 0))

    # 3. НАСТРОЙКИ ПО РЕЖИМАМ
    modes_frame = ttk.Frame(scroll_frame)
    modes_frame.pack(fill="x", padx=pad, pady=(0, 10))

    # Smart Mode (Зеленая кнопка на главной)
    smart_frame = ttk.LabelFrame(modes_frame, text=" 🧠 Smart Mode (По базе) ", padding=15)
    smart_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

    v_smart_dir = tk.IntVar(value=int(cfg.get("smart_add_director", "1")))
    ttk.Checkbutton(smart_frame, text="Добавлять Директора (по ссылке)", variable=v_smart_dir).pack(anchor="w", pady=2)
    
    v_smart_client = tk.IntVar(value=int(cfg.get("smart_add_clients", "1")))
    chk_s_c = ttk.Checkbutton(smart_frame, text="Инвайтить Клиентов в группу", variable=v_smart_client) 
    chk_s_c.pack(anchor="w", pady=2)
    
    lbl_hint = tk.Label(smart_frame, text="(Если НЕТ: просто сохранит в книгу)", font=("Segoe UI", 7), fg="#777", bg="#121212")
    lbl_hint.pack(anchor="w", padx=20)
    
    v_smart_greet = tk.IntVar(value=int(cfg.get("smart_send_greeting", "1")))
    ttk.Checkbutton(smart_frame, text="Слать приветствие", variable=v_smart_greet).pack(anchor="w", pady=2)

    # Manual Mode (Кнопка в настройках)
    manual_frame = ttk.LabelFrame(modes_frame, text=" 🛠 Manual Mode (Пустышки) ", padding=15)
    manual_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

    v_man_dir = tk.IntVar(value=int(cfg.get("manual_default_dir", "1")))
    ttk.Checkbutton(manual_frame, text="Добавлять Директора", variable=v_man_dir).pack(anchor="w", pady=2)
    
    v_man_cont = tk.IntVar(value=int(cfg.get("manual_default_contact", "0")))
    ttk.Checkbutton(manual_frame, text="Инвайтить Контакты (Из книги)", variable=v_man_cont).pack(anchor="w", pady=2)
    
    v_man_greet = tk.IntVar(value=int(cfg.get("manual_default_greet", "1")))
    ttk.Checkbutton(manual_frame, text="Слать приветствие", variable=v_man_greet).pack(anchor="w", pady=2)

    # 4. ТЕКСТ ПРИВЕТСТВИЯ
    greet_frame = ttk.LabelFrame(scroll_frame, text=" 💬 Текст приветствия ", padding=15)
    greet_frame.pack(fill="x", padx=pad, pady=(0, 20))

    txt_greet_set = scrolledtext.ScrolledText(greet_frame, height=4, font=("Consolas", 10), bg="#0F0F0F", fg="#00FF00", insertbackground="#9D00FF", borderwidth=0)
    txt_greet_set.pack(fill="x")
    txt_greet_set.insert("1.0", cfg.get("greeting_text", ""))

    def save_settings():
        new_cfg = cfg.copy()
        new_cfg["random_delay"] = str(var_rand.get())
        new_cfg["delay_creation"] = e1.get()
        new_cfg["delay_contact"] = e2.get()
        
        # Smart
        new_cfg["smart_add_director"] = str(v_smart_dir.get())
        new_cfg["smart_add_clients"] = str(v_smart_client.get())
        new_cfg["smart_send_greeting"] = str(v_smart_greet.get())
        
        # Manual
        new_cfg["manual_default_dir"] = str(v_man_dir.get())
        new_cfg["manual_default_contact"] = str(v_man_cont.get())
        new_cfg["manual_default_greet"] = str(v_man_greet.get())
        
        new_cfg["greeting_text"] = txt_greet_set.get("1.0", tk.END).strip()
        
        save_config(new_cfg)
        messagebox.showinfo("Настройки", "✅ Конфигурация сохранена!", parent=parent)

    save_btn = ttk.Button(scroll_frame, text="💾 ПРИМЕНИТЬ НАСТРОЙКИ", command=save_settings, style="Green.TButton")
    save_btn.pack(fill="x", padx=pad, pady=(0, 30), ipady=8)
    

# === ЛОГИКА ВКЛАДКИ АККАУНТОВ (МЕНЕДЖЕР) ===
def create_accounts_tab(parent):
    global tree_accounts
    
    fr = ttk.Frame(parent)
    fr.pack(fill="both", expand=True)

    toolbar = ttk.Frame(fr, padding=10)
    toolbar.pack(fill="x")

    # ПОИСК
    search_frame = ttk.Frame(fr, padding=(10, 0, 10, 10))
    search_frame.pack(fill="x")
    ent_search = ttk.Entry(search_frame, width=30, font=("Consolas", 10))
    ent_search.pack(side="left")
    
    # ФУНКЦИЯ ОБНОВЛЕНИЯ
    def _refresh_tree(event=None):
        if tree_accounts is None: return
        raw_val = ent_search.get().lower().strip()
        search_query = ""
        clean_query_phone = "" 

        if raw_val and raw_val != "поиск":
            search_query = raw_val
            clean_query_phone = raw_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        for i in tree_accounts.get_children():
            try: tree_accounts.delete(i)
            except: pass
            
        sessions = load_sessions()
        
        for idx, s in enumerate(sessions):
            raw_phone = s.get('phone', '')
            name = s.get('name', 'Без имени')
            uname = s.get('username', '')
            
            if search_query:
                db_phone_clean = raw_phone.lower().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                in_phone = clean_query_phone in db_phone_clean
                in_name = search_query in name.lower()
                in_uname = search_query in uname.lower()
                if not (in_phone or in_name or in_uname): continue

            last_ts = s.get('last_used', 0)
            dt_str = datetime.fromtimestamp(float(last_ts)).strftime('%d.%m %H:%M') if last_ts else "Новый"
            row_tags = ('gold_user',) if uname else ()
            display_uname = f"@{uname}" if uname else "-"
            tree_accounts.insert("", "end", iid=str(idx), values=(raw_phone, name, display_uname, dt_str), tags=row_tags)

    ent_search.bind("<KeyRelease>", _refresh_tree)
    
    # !!! ВОТ ЗДЕСЬ ОПРЕДЕЛЯЕМ ФУНКЦИИ ДО КНОПОК !!!
    def _delete_logic():
        if not tree_accounts: return
        sel = tree_accounts.selection()
        if not sel: return
        if not messagebox.askyesno("Удаление", f"Удалить {len(sel)} аккаунтов?"): return
        indices = sorted([int(x) for x in sel], reverse=True)
        ss = load_sessions()
        for i in indices: 
            if i < len(ss): del ss[i]
        save_sessions(ss)
        _refresh_tree(); refresh_main_checks()

    def _clear_contacts():
        if not tree_accounts: return
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

    # КНОПКИ
    f_left = ttk.Frame(toolbar); f_left.pack(side="left")
    ttk.Button(f_left, text="➕ Добавить", command=lambda: open_add_account_window(lambda: (_refresh_tree(), refresh_main_checks()))).pack(side="left", padx=(0, 5))
    ttk.Button(f_left, text="🔄 Войти/Обновить", command=lambda: threading.Thread(target=lambda: run_login_check(load_sessions()[int(tree_accounts.selection()[0])], _refresh_tree), daemon=True).start() if tree_accounts.selection() else None).pack(side="left", padx=5)
    
    f_mid = ttk.Frame(toolbar); f_mid.pack(side="left", padx=20)
    ttk.Button(f_mid, text="🧹 Удалить контакты", command=_clear_contacts).pack(side="left")
    ttk.Button(f_mid, text="⚡ Чекнуть ВСЕХ", command=lambda: (start_update_all(), parent.after(2000, _refresh_tree))).pack(side="left", padx=5)

    ttk.Button(toolbar, text="❌ Удалить", command=_delete_logic, style="Red.TButton").pack(side="right")

    # ТАБЛИЦА
    columns = ("phone", "name", "username", "last_active")
    tree_accounts = ttk.Treeview(fr, columns=columns, show="headings", selectmode="extended")
    tree_accounts.heading("phone", text="Телефон"); tree_accounts.column("phone", width=140, anchor="center")
    tree_accounts.heading("name", text="Имя"); tree_accounts.column("name", width=180, anchor="w")
    tree_accounts.heading("username", text="Username"); tree_accounts.column("username", width=140, anchor="w")
    tree_accounts.heading("last_active", text="Обновлен"); tree_accounts.column("last_active", width=130, anchor="center")
    
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


# === ГЛАВНАЯ ВКЛАДКА (DASHBOARD) ===
def create_dashboard_tab(parent):
    # 1. ЦЕНТР
    center_frame = ttk.Frame(parent, padding=(15, 15, 15, 0))
    center_frame.pack(fill="both", expand=True)
    
    # Мейкеры
    lf_makers = ttk.LabelFrame(center_frame, text=" 🤖 1. Расходка (Мейкеры) ", padding=10)
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

    # Гость
    lf_guest = ttk.LabelFrame(center_frame, text=" 👤 2. Дир (Гость) ", padding=10)
    lf_guest.pack(side="right", fill="both", expand=True, padx=(5, 0))
    
    f_search_g = ttk.Frame(lf_guest)
    f_search_g.pack(fill="x", pady=(0, 5))
    
    global ent_guest_search
    ent_guest_search = ttk.Entry(f_search_g, font=("Consolas", 10))
    ent_guest_search.pack(fill="x")
    ent_guest_search.bind("<KeyRelease>", lambda e: refresh_main_checks())

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

    # НИЗ
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

    # КНОПКИ (Без желтой кнопки)
    btn_area = ttk.Frame(bottom_frame)
    btn_area.pack(fill="x", pady=5)
     
    global smart_btn
    smart_btn = ttk.Button(btn_area, text="📂 СТАРТ ПО БАЗЕ (Smart)", command=lambda: start_process("smart"), style="Green.TButton")
    smart_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
    
    ttk.Button(btn_area, text="🛑 СТОП", command=stop_process, style="Red.TButton").pack(side="left", padx=(5, 0), fill="x", ipadx=20, ipady=8)
    
    lf_log = ttk.LabelFrame(bottom_frame, text=" Лог событий ", padding=5)
    lf_log.pack(fill="x", pady=(10, 0))
    
    global log_widget
    log_widget = scrolledtext.ScrolledText(lf_log, height=8, state='disabled', font=("Consolas", 10), bg="#050505", fg="#CCCCCC", insertbackground="#9D00FF", borderwidth=0)
    log_widget.pack(fill="both", expand=True, padx=2, pady=2)
    for t, c in TAG_COLORS.items():
        log_widget.tag_config(t, foreground=c)

# ==========================================
# === ЛОГИКА ВКЛАДКИ БАЗЫ (FILE MANAGER) ===
# ==========================================
def create_databases_tab(parent, custom_path=None):
    # Если путь передан, используем его. Если нет — берем дефолтный.
    if custom_path:
        DB_FOLDER = custom_path
    else:
        DB_FOLDER = "прописанные базы"
    
    # Создаем папку, если нет
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

    folder_name = os.path.basename(DB_FOLDER)
    ttk.Label(list_header, text=f"📂 {folder_name}", font=("Segoe UI", 11, "bold"), foreground="#9D00FF").pack(side="left")
    
    btn_refresh = ttk.Button(list_header, text="🔄", width=4) # Команду привяжем ниже
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
    paned.add(frame_editor, weight=3)

    # Тулбар редактора
    toolbar = ttk.Frame(frame_editor)
    toolbar.pack(fill="x", pady=(0, 5))

    lbl_current_file = ttk.Label(toolbar, text="Выберите файл...", font=("Consolas", 10, "bold"), foreground="#888")
    lbl_current_file.pack(side="left", padx=5)

    btn_del = ttk.Button(toolbar, text="🗑 Удалить", style="Red.TButton", state='disabled')
    btn_del.pack(side="right")
    
    btn_save = ttk.Button(toolbar, text="💾 Сохранить", style="Green.TButton", state='disabled')
    btn_save.pack(side="right", padx=5)

    txt_content = scrolledtext.ScrolledText(frame_editor, font=("Consolas", 10), 
                                            bg="#0F0F0F", fg="#E0E0E0", 
                                            insertbackground="#9D00FF", borderwidth=0)
    txt_content.pack(fill="both", expand=True)
    txt_content.config(state='disabled') 

    # --- ФУНКЦИОНАЛ ---
    current_file_path = [None] 

    def refresh_file_list():
        for item in tree_files.get_children():
            tree_files.delete(item)
        
        if not os.path.exists(DB_FOLDER): return

        files = [f for f in os.listdir(DB_FOLDER) if f.endswith(".txt")]
        # Сортировка по времени изменения (свежие сверху)
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

    btn_refresh.config(command=refresh_file_list)
    tree_files.bind("<<TreeviewSelect>>", on_file_select)
    refresh_file_list()

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
        self.frames["Настройки запуска"] = ttk.Frame(self.content_area)
        
        # --- ВКЛАДКА 1: ПРОБИТЫЕ БАЗЫ ---
        self.frames["Databases"] = ttk.Frame(self.content_area)
        
        # --- ВКЛАДКА 2: АРХИВ (ОТМЕНЕННЫЕ) ---
        self.frames["SavedBases"] = ttk.Frame(self.content_area) # <-- Новая вкладка
        
        
        self.frames["Заметки"] = ttk.Frame(self.content_area)

        # Наполняем экраны
        create_dashboard_tab(self.frames["Главная"])
        create_accounts_tab(self.frames["Accounts"])
        
        # Вызываем нашу функцию дважды с разными путями:
        # 1. Основные
        create_databases_tab(self.frames["Databases"], custom_path="прописанные базы")
        
        # 2. Отмененные (путь внутри прописанных баз)
        saved_path = os.path.join("прописанные базы", "отмена и схроненные")
        create_databases_tab(self.frames["SavedBases"], custom_path=saved_path)

        create_settings_tab(self.frames["Настройки запуска"])
        self._init_notes_screen(self.frames["Заметки"])

        # 4. Кнопки меню (Порядок кнопок тут)
        self._add_menu_btn("🏠 Главная", "Главная")
        self._add_menu_btn("👥 Accounts", "Accounts")
        self._add_menu_btn("⚙ Настройки запуска", "Настройки запуска")
        self._add_menu_btn("📂 Пробитые Базы", "Databases")
        self._add_menu_btn("💾 Сохраненные / Отмена", "SavedBases") # <-- Новая кнопка
        
        
        self._add_menu_btn("📝 Заметки", "Заметки")

        # Футер
        tk.Label(self.sidebar, text="v24.2 Pro", bg="#0F0F0F", fg="#555", 
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

class ManualModeWindow(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ручной режим (Manual Mode)")
        self.geometry("600x650")
        try:
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            self.geometry(f"+{(sw-600)//2}+{(sh-650)//2}")
        except: pass
        self.configure(bg="#121212")
        self.transient(parent)
        self.old_log_widget = globals().get('log_widget')
        
        cfg = load_config()

        # --- 1. ПАРАМЕТРЫ ГРУПП ---
        top_frame = ttk.Frame(self, padding=20)
        top_frame.pack(fill="x")
        tf_grid = ttk.LabelFrame(top_frame, text=" 📝 Параметры групп ", padding=15)
        tf_grid.pack(fill="x")

        ttk.Label(tf_grid, text="Название:").grid(row=0, column=0, sticky="w", padx=(0,10))
        self.ent_name = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10))
        self.ent_name.grid(row=0, column=1, sticky="w")
        
        ttk.Label(tf_grid, text="Кол-во:").grid(row=0, column=2, sticky="w", padx=(10,10))
        self.ent_count = ttk.Entry(tf_grid, width=8, font=("Segoe UI", 10))
        self.ent_count.insert(0, "5")
        self.ent_count.grid(row=0, column=3, sticky="w")

        # --- НОВОЕ ПОЛЕ: ЮЗЕРНЕЙМ ---
        ttk.Label(tf_grid, text="Username Дира:").grid(row=1, column=0, sticky="w", padx=(0,10), pady=(15,0))
        self.ent_user = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10))
        self.ent_user.grid(row=1, column=1, sticky="w", pady=(15,0))
        
        ttk.Label(tf_grid, text="(@username или ссылка)", font=("Segoe UI", 8), foreground="#777").grid(row=1, column=2, columnspan=2, sticky="w", padx=10, pady=(15,0))

        # --- 2. ИНФО О НАСТРОЙКАХ ---
        info_frame = ttk.Frame(self, padding=(20, 0))
        info_frame.pack(fill="x")
        
        s_dir = "ДА" if cfg.get("manual_default_dir") == "1" else "НЕТ"
        s_cont = "ДА" if cfg.get("manual_default_contact") == "1" else "НЕТ"
        s_greet = "ДА" if cfg.get("manual_default_greet") == "1" else "НЕТ"
        
        lbl_info = tk.Label(info_frame, text=f"ℹ Настройки (из Settings):\n"
                                             f"• Добавлять Директора: {s_dir}\n"
                                             f"• Инвайтить Контакты: {s_cont}\n"
                                             f"• Слать Приветствие: {s_greet}", 
                            bg="#1E1E1E", fg="#9D00FF", font=("Consolas", 9), justify="left", padx=10, pady=10)
        lbl_info.pack(fill="x")

        # --- 3. КНОПКА ЗАПУСКА ---
        btn_frame = ttk.Frame(self, padding=20)
        btn_frame.pack(fill="x")
        self.btn_start = ttk.Button(btn_frame, text="🚀 ЗАПУСТИТЬ", command=self.start_manual, style="Green.TButton")
        self.btn_start.pack(fill="x", ipady=8)
        
        # --- 4. ЛОГ ---
        log_frame = ttk.LabelFrame(self, text=" Лог событий ", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.manual_log = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9), bg="#050505", fg="#CCCCCC", insertbackground="#9D00FF", borderwidth=0)
        self.manual_log.pack(fill="both", expand=True)
        for t, c in TAG_COLORS.items():
            if t == "ERROR": c = "#FF5555"
            if t == "SUCCESS": c = "#50FA7B"
            if t == "WARN": c = "#FFB86C"
            if t == "WAIT": c = "#8BE9FD"
            if t == "INFO": c = "#F8F8F2"
            if t == "GUEST": c = "#BD93F9"
            if t == "DEBUG": c = "#6272A4"
            self.manual_log.tag_config(t, foreground=c)
        globals()['log_widget'] = self.manual_log
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        globals()['log_widget'] = self.old_log_widget
        self.destroy()

    def start_manual(self):
        try:
            base_name = self.ent_name.get().strip()
            try: count_per_maker = int(self.ent_count.get())
            except: messagebox.showerror("Error", "Количество - число!"); return

            cfg = load_config()
            need_add_dir = int(cfg.get("manual_default_dir", "1"))
            need_add_cont = int(cfg.get("manual_default_contact", "0"))
            need_greet = int(cfg.get("manual_default_greet", "1"))
            greeting_text = cfg.get("greeting_text", "")
            
            manual_username_input = self.ent_user.get().strip()

            sessions_data = load_sessions()
            selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
            if not selected_indices: messagebox.showwarning("!", "Выберите мейкеров в ГЛАВНОМ окне!"); return

            # Логика выбора директора
            guest_idx = guest_account_index.get()
            guest_session = None
            
            if need_add_dir:
                if guest_idx != -1 and guest_idx < len(sessions_data):
                    guest_session = sessions_data[guest_idx]
                    if guest_idx in selected_indices: selected_indices.remove(guest_idx)
                elif manual_username_input:
                    pass 
                else:
                    messagebox.showwarning("!", "Включено 'Добавлять Директора', но он не выбран!")
                    return
            
            main_sessions = [sessions_data[i] for i in selected_indices]
            if not main_sessions: messagebox.showwarning("!", "Список мейкеров пуст!"); return

            delays = {
                "creation": float(cfg.get("delay_creation", 180)),
                "contact": float(cfg.get("delay_contact", 20)),
                "cleanup": 10, "random": 1,
                "manual_add_director": need_add_dir, 
                "manual_add_contacts": need_add_cont 
            }

            use_words = int(cfg.get("use_random_words", "1"))
            if not base_name and not use_words: base_name = "Group"
            
            # Расчет имен (исправлен)
            total_groups = count_per_maker * len(main_sessions)
            names = generate_group_names(base_name, total_groups)

            self.btn_start.config(state='disabled', text="⏳ ЗАПУЩЕНО")
            
            # ЗАПУСК НАПРЯМУЮ
            threading.Thread(
                target=run_thread,
                args=(main_sessions, guest_session, names, delays, manual_username_input, greeting_text, need_greet, None),
                daemon=True
            ).start()

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.btn_start.config(state='normal', text="🚀 ЗАПУСТИТЬ")

# Хелпер для открытия
def open_manual_mode_window():
    if not check_vars:
        messagebox.showwarning("Внимание", "Сначала загрузите аккаунты на главной вкладке!")
        return
    win = ManualModeWindow(root)

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