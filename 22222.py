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
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

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
        "manual_default_contact": "0", 
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

# === ГОРЯЧИЕ КЛАВИШИ И СКРОЛЛ ===
def enable_hotkeys(window):
    def check_key(event):
        if event.keysym.lower() in ['c', 'v', 'x', 'a']: return
        try:
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
    def _on_wheel(event):
        if event.num == 5 or event.delta < 0: canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: canvas.yview_scroll(-1, "units")

    def _bind_to_mouse(event):
        canvas.bind_all("<MouseWheel>", _on_wheel)
        canvas.bind_all("<Button-4>", _on_wheel)
        canvas.bind_all("<Button-5>", _on_wheel)

    def _unbind_from_mouse(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    for widget in [canvas, inner_frame]:
        widget.bind('<Enter>', _bind_to_mouse)
        widget.bind('<Leave>', _unbind_from_mouse)
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
        except Exception as e: raise Exception(f"Ошибка сети: {e}")
            
        try:
            data = resp.json()
            if "random_hash" not in data: raise Exception(data.get("error", resp.text))
            self.random_hash = data["random_hash"]
            return clean_phone
        except:
            if "Too many tries" in resp.text: raise Exception("БАН IP (Too many tries). Включите VPN.")
            raise Exception("Сайт вернул ошибку (не JSON).")

    def login(self, phone, code):
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        time.sleep(0.5)
        data = {"phone": clean_phone, "random_hash": self.random_hash, "password": code}
        try: resp = self.session.post(f"{self.BASE_URL}/auth/login", data=data, timeout=10)
        except Exception as e: raise Exception(f"Ошибка сети при входе: {e}")
        
        if resp.text.strip() == "true": return True
        if "invalid code" in resp.text.lower(): raise Exception("Неверный код!")
        raise Exception(f"Ошибка входа: {resp.text[:50]}")

    def get_app_data(self):
        time.sleep(1)
        try: resp = self.session.get(f"{self.BASE_URL}/apps", timeout=10)
        except Exception as e: raise Exception(f"Ошибка получения Apps: {e}")
            
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
        raise Exception("Не удалось прочитать ключи после создания.")

# 📝 ЛОГИРОВАНИЕ
def log_msg(tag, text):
    print(f"[{tag}] {text}")
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
            if root and root.winfo_exists(): root.after(0, _log)
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
            s['last_used'] = time.time()
            updated = True
            break
    if updated:
        save_sessions(sessions)
        if root: root.after(0, lambda: refresh_main_checks())

# 1. КЛАСС ОКНА С ЧЕКБОКСАМИ (Review)
class MatchReviewWindow(Toplevel):
    def __init__(self, parent, matches_list, original_company_name="Unknown"):
        super().__init__(parent)
        self.matches = matches_list
        self.company_name = original_company_name
        self.result = None
        self.group_name_result = None # Новая переменная для имени
        
        self.title(f"Проверка совпадений ({len(matches_list)} чел.)")
        self.geometry("1100x600")
        self.minsize(900, 500)
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set()

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Review.Treeview", background="#101010", foreground="white", fieldbackground="#101010", rowheight=30, borderwidth=0)
        style.map("Review.Treeview", background=[('selected', '#9D00FF')], foreground=[('selected', 'white')])
        style.configure("Review.Treeview.Heading", background="#2E2E2E", foreground="#9D00FF", font=("Segoe UI", 10, "bold"))

        # ВЕРХНЯЯ ЧАСТЬ
        top_frame = tk.Frame(self, bg="#121212", pady=10)
        top_frame.pack(fill="x")
        tk.Label(top_frame, text="Выберите контакты. Невыбранные будут удалены из книги.", font=("Segoe UI", 11), fg="#00E676", bg="#121212").pack()

        # ТАБЛИЦА
        table_frame = tk.Frame(self, bg="#121212")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        cols = ("fio_file", "name_tg", "phone", "username")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended", style="Review.Treeview")
        
        self.tree.heading("fio_file", text="ФИО из Файла")
        self.tree.heading("name_tg", text="Имя в Telegram")
        self.tree.heading("phone", text="Телефон")
        self.tree.heading("username", text="Username")
        
        self.tree.column("fio_file", width=250, anchor="w")
        self.tree.column("name_tg", width=250, anchor="w")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("username", width=120, anchor="w")
        
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for i, item in enumerate(self.matches):
            tg_u = item['user']
            tg_name = f"{tg_u.first_name or ''} {tg_u.last_name or ''}".strip()
            uname = f"@{tg_u.username}" if tg_u.username else "-"
            self.tree.insert("", "end", iid=str(i), values=(item['target_fio'], tg_name, item['phone'], uname))

        all_ids = self.tree.get_children()
        self.tree.selection_set(all_ids)

        # НИЖНЯЯ ЧАСТЬ (КНОПКИ И ВВОД ИМЕНИ)
        btn_frame = tk.Frame(self, bg="#121212", pady=15)
        btn_frame.pack(fill="x")
        
        f_left = tk.Frame(btn_frame, bg="#121212")
        f_left.pack(side="left", padx=20)
        tk.Button(f_left, text="Выделить все", command=self.select_all, bg="#333", fg="white", bd=0, padx=15, pady=5).pack(side="left", padx=5)
        tk.Button(f_left, text="Снять выделение", command=self.deselect_all, bg="#333", fg="white", bd=0, padx=15, pady=5).pack(side="left", padx=5)

        f_right = tk.Frame(btn_frame, bg="#121212")
        f_right.pack(side="right", padx=20)

        # Поле ввода имени группы
        tk.Label(f_right, text="Имя групп:", bg="#121212", fg="#00E676", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0,5))
        self.ent_group_name = ttk.Entry(f_right, width=25, font=("Segoe UI", 10))
        self.ent_group_name.insert(0, original_company_name)
        self.ent_group_name.pack(side="left", padx=(0, 15))

        tk.Button(f_right, text="💾 СОХРАНИТЬ И ОТМЕНА", command=self.save_and_cancel, bg="#FFD700", fg="black", font=("Segoe UI", 9, "bold"), bd=0, padx=15, pady=8).pack(side="left", padx=10)
        tk.Button(f_right, text="✅ ЗАПУСТИТЬ", command=self.confirm, bg="#00E676", fg="black", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=8).pack(side="left")

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def deselect_all(self):
        self.tree.selection_remove(self.tree.selection())

    def save_and_cancel(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showwarning("Пусто", "Выделите контакты!", parent=self)
            return
        base_dir = "прописанные базы"
        save_dir = os.path.join(base_dir, "отмена и схроненные")
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_name = re.sub(r'[\\/*?:"<>|]', "", self.company_name).strip() or "SavedBase"
        filename = f"{safe_name}_CHECKED_{timestamp}.txt"
        filepath = os.path.join(save_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f'ООО "{self.company_name}"\nRun: SAVED\n' + "="*30 + "\n\n")
                for iid in selected_iids:
                    item = self.matches[int(iid)]
                    line_fio = item['target_fio']
                    if item.get('target_dob'): line_fio += f" {item['target_dob']}"
                    f.write(f"{line_fio}\n{item['phone']}\n" + "-" * 20 + "\n")
            messagebox.showinfo("Сохранено", f"Путь: {filepath}", parent=self)
            self.result = None
            self.destroy()
        except Exception as e: messagebox.showerror("Ошибка", str(e), parent=self)

    def confirm(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showwarning("Внимание", "Вы никого не выбрали!", parent=self)
            return
        # Сохраняем введенное имя группы
        self.group_name_result = self.ent_group_name.get().strip()
        if not self.group_name_result: self.group_name_result = "Group"
        
        self.result = [self.matches[int(iid)] for iid in selected_iids]
        self.destroy()

# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
async def set_guest_phone_privacy(client):
    try:
        rules = [types.InputPrivacyValueAllowContacts()] 
        await client(functions.account.SetPrivacyRequest(key=types.InputPrivacyKeyPhoneNumber(), rules=rules))
    except Exception as e: print(f"Ошибка установки приватности Гостя: {e}")

async def hide_maker_phone(client):
    try:
        await client(functions.account.SetPrivacyRequest(key=types.InputPrivacyKeyPhoneNumber(), rules=[types.InputPrivacyValueDisallowAll()]))
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

def parse_target_file(file_content):
    data = {"company_name": "Unknown_Company", "director_name": None, "candidates": [], "original_header": ""}
    parts = re.split(r'\+?={10,}', file_content)
    if len(parts) > 1:
        header_content = parts[0]
        candidates_content = "\n".join(parts[1:])
    else:
        header_content = file_content
        candidates_content = ""

    data["original_header"] = header_content.strip()
    
    header_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', header_content)
    if header_match: data["company_name"] = header_match.group(1).strip()
    else:
        fallback_match = re.search(r'["«“]([^"»”]+)["»”]', header_content)
        if fallback_match: data["company_name"] = fallback_match.group(1).strip()
    
    try:
        director_match = re.search(r'(?:Руководитель|ГЕНЕРАЛЬНЫЙ ДИРЕКТОР)[\s\S]*?([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)', header_content)
        if director_match:
            parts = director_match.group(1).split()
            if len(parts) >= 2: data["director_name"] = f"{parts[0]} {parts[1]}"
    except: pass

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
                name = "Unknown"; dob = ""
                nm = re.search(r'^([А-ЯЁ\s]+)\s+(\d{2}\.\d{2}\.\d{4})', sec, re.MULTILINE)
                if nm: 
                    name = nm.group(1).strip()
                    dob = nm.group(2).strip()
                else:
                    nm2 = re.search(r'^([А-ЯЁ]{2,}\s+[А-ЯЁ]{2,}\s+[А-ЯЁ]{2,})', sec, re.MULTILINE)
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
        for _ in range(count): raw_names.append(f"{base} {random.choice(seps)} {random.choice(words)}")
    return raw_names

async def smart_sleep(base_delay, is_random):
    if is_random:
        delay = random.uniform(5.0, 15.0)
        log_msg("WAIT", f"⏳ Случайная пауза {delay:.1f} сек...")
    else:
        delay = float(base_delay)
        log_msg("WAIT", f"⏳ Пауза {delay:.1f} сек...")
    end_time = time.time() + delay
    while time.time() < end_time:
        if stop_flag.is_set(): return 
        await asyncio.sleep(0.5)

# 🔐 AUTH GUI
def ask_code_gui(phone, is_password=False):
    prompt = f"Введите ОБЛАЧНЫЙ ПАРОЛЬ (2FA) для {phone}:" if is_password else f"Дайте буквы из смс:) для {phone}:"
    result_data = {"value": None}
    wait_event = threading.Event()

    def show():
        try:
            win = Toplevel(root)
            win.title("Ввод кода")
            w, h = 350, 180
            sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
            win.resizable(False, False)
            win.configure(bg="#2E3440")
            ttk.Label(win, text=prompt, wraplength=330, background="#2E3440", foreground="white", font=("Arial", 10, "bold")).pack(pady=(15, 10))
            show_char = "*" if is_password else ""
            input_var = tk.StringVar()
            e = ttk.Entry(win, textvariable=input_var, font=("Arial", 12), show=show_char)
            e.pack(fill="x", padx=20, pady=5)
            e.focus_force()

            def submit(*args):
                val = input_var.get().strip()
                if val: result_data["value"] = val
                wait_event.set(); win.destroy()

            def on_close():
                wait_event.set(); win.destroy()

            ttk.Button(win, text="ОТПРАВИТЬ", command=submit).pack(pady=15)
            e.bind('<Return>', submit)
            win.protocol("WM_DELETE_WINDOW", on_close)
            win.transient(root)
            win.attributes('-topmost', True)
            win.lift()
            win.grab_set() 
        except Exception as e:
            print(f"Ошибка GUI: {e}"); wait_event.set()

    root.after(0, show)
    wait_event.wait()
    return result_data["value"]

async def add_and_clean(client, chat, user, delays):
    try:
        if hasattr(user, 'first_name'): u_name = user.first_name
        else: u_id = getattr(user, 'user_id', 'Unknown'); u_name = f"User_ID_{u_id}"
            
        log_msg("INFO", f"   👤 Инвайт контакта: {u_name}...")
        await client(functions.messages.AddChatUserRequest(chat_id=chat.id, user_id=user, fwd_limit=100))
        log_msg("SUCCESS", f"   ✅ Контакт добавлен.")
        await asyncio.sleep(1)
        
        msgs = await client.get_messages(chat, limit=5)
        ids = [m.id for m in msgs if m.action] 
        if ids: await client.delete_messages(chat, ids, revoke=True)
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

async def process_smart_target_file(maker_client, guest_client, file_path, guest_session_dict=None, pre_approved_data=None, pre_group_name=None):
    try:
        parsed_data = {"candidates": []}
        original_company_name = "Unknown"
    
        if not pre_approved_data:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            parsed_data = parse_target_file(content)
            original_company_name = parsed_data.get('company_name', 'Unknown_Company')

            if guest_client and parsed_data['director_name']:
                try:
                    if await guest_client.is_user_authorized():
                        d_name = parsed_data['director_name']
                        parts = d_name.split()
                        if len(parts) >= 2: new_first = parts[1]; new_last = parts[0]
                        else: new_first = d_name; new_last = ""
                        await guest_client(functions.account.UpdateProfileRequest(first_name=new_first, last_name=new_last))
                        if guest_session_dict:
                            guest_session_dict['name'] = f"{new_first} {new_last}"
                            update_session_info(guest_session_dict['phone'], guest_session_dict['name'], guest_session_dict.get('username', ''))
                        log_msg("GUEST", f"👤 Гость переименован: {new_first} {new_last}")
                except: pass

            if maker_client and original_company_name:
                try: await maker_client(functions.account.UpdateProfileRequest(first_name=original_company_name, last_name=""))
                except: pass
        else:
            parsed_data['candidates'] = pre_approved_data
            original_company_name = pre_group_name if pre_group_name else "Group"
            log_msg("INFO", f"⚙️ Работа по утвержденному списку ({len(pre_approved_data)} чел.)")

        batch_list = []; tracking_map = {} 
        for candidate in parsed_data['candidates']:
            phones = candidate.get('phones', [])
            if not phones and 'phone' in candidate: phones = [candidate['phone']] 
            fio = candidate.get('full_name', candidate.get('target_fio', 'Unknown'))
            dob = candidate.get('dob', candidate.get('target_dob', ''))
            for raw in phones:
                d = re.sub(r'\D', '', raw)
                if len(d) == 11 and d.startswith('8'): import_phone = "+7" + d[1:]
                elif len(d) == 11 and d.startswith('7'): import_phone = "+" + d
                elif len(d) == 10 and d.startswith('9'): import_phone = "+7" + d
                else: import_phone = "+" + d
                my_client_id = random.randint(10000000, 999999999)
                tracking_map[my_client_id] = {'fio': fio, 'dob': dob, 'orig_phone': raw.strip()}
                batch_list.append(types.InputPhoneContact(client_id=my_client_id, phone=import_phone, first_name=fio[:20], last_name=""))

        found_matches = []; all_imported_ids = []
        for i in range(0, len(batch_list), 15):
            chunk = batch_list[i : i + 15]
            if not pre_approved_data: log_msg("INFO", f"   📤 Проверка пачки {i+1}-{i+len(chunk)}...")
            try:
                res = await maker_client(functions.contacts.ImportContactsRequest(contacts=chunk))
                for u in res.users: all_imported_ids.append(u.id) # Запоминаем всех найденных
                
                tg_map = {imp.user_id: imp.client_id for imp in res.imported}
                users_to_refetch = [types.InputUser(u.id, u.access_hash) for u in res.users if u.id in tg_map]

                if users_to_refetch:
                    clean_users = await maker_client(functions.users.GetUsersRequest(id=users_to_refetch))
                    for u in clean_users:
                        cid = tg_map.get(u.id)
                        orig = tracking_map.get(cid)
                        if orig:
                            found_matches.append({'target_fio': orig['fio'], 'target_dob': orig.get('dob', ''), 'user': u, 'phone': orig['orig_phone']})
                            if not pre_approved_data: log_msg("SUCCESS", f"      ✅ {orig['fio']}")
                await asyncio.sleep(1) 
            except FloodWaitError as e:
                log_msg("ERROR", f"⛔ FLOOD WAIT: Ждем {e.seconds} сек."); await asyncio.sleep(e.seconds)
            except Exception as e: log_msg("ERROR", f"❌ Ошибка: {e}")

        if pre_approved_data:
            return [await maker_client.get_input_entity(m['user']) for m in found_matches], original_company_name, None

        if not found_matches: log_msg("WARN", "⚠️ Никого не нашли."); return [], None, None

        # --- GUI ВЫБОРА (Ждем решения пользователя) ---
        future_gui = asyncio.get_running_loop().create_future()
        def show_gui():
            win = MatchReviewWindow(root, found_matches, original_company_name)
            root.wait_window(win)
            # Возвращаем результат И введенное имя
            if win.result is not None: future_gui.set_result((win.result, win.group_name_result))
            else: future_gui.set_result(([], None))
        root.after(0, show_gui)
        
        selected_matches, manual_group_name = await future_gui
        final_group_name = manual_group_name if manual_group_name else original_company_name

        # --- ЧИСТКА КОНТАКТОВ (Удаляем тех, кого НЕ выбрали) ---
        if all_imported_ids:
            kept_ids = [m['user'].id for m in selected_matches] if selected_matches else []
            to_del = [uid for uid in all_imported_ids if uid not in kept_ids]
            if to_del:
                log_msg("INFO", f"🧹 Удаление {len(to_del)} невыбранных контактов...")
                try:
                    for k in range(0, len(to_del), 50):
                        await maker_client(functions.contacts.DeleteContactsRequest(id=to_del[k:k+50]))
                except: pass

        if not selected_matches: return [], None, None

        # Сохранение отчета
        try:
            folder_name = "прописанные базы"
            if not os.path.exists(folder_name): os.makedirs(folder_name)
            safe = re.sub(r'[\\/*?:"<>|]', "", original_company_name).strip() or "Report"
            full_path = os.path.join(folder_name, f"{safe}.txt")
            with open(full_path, "w", encoding="utf-8") as f:
                if parsed_data.get('original_header'): f.write(parsed_data['original_header'] + "\n" + "="*50 + "\n\n")
                f.write(f"ОТЧЕТ: {original_company_name}\nИСПОЛЬЗУЕМОЕ ИМЯ: {final_group_name}\n" + "="*50 + "\n\n")
                for m in selected_matches:
                    u = m['user']
                    f.write(f"👤 {m['target_fio']}\n📱 {m['phone']}\n✅ @{u.username or '-'}\n" + "-" * 40 + "\n")
            log_msg("SUCCESS", f"📄 Отчет: {full_path}")
        except: pass

        # Возвращаем данные для запуска Воркера
        return [], final_group_name, selected_matches

    except Exception as e:
        log_msg("ERROR", f"Smart error: {e}"); return [], None, None

# === ВОРКЕР ===
async def worker_task(session, delays, guest_session=None, smart_file_path=None, pre_approved_chunk=None, pre_group_name=None, manual_names=None, manual_target_user=None):
    # ВАЖНО: В начале стоит async def
    api_id = int(session['api_id']); api_hash = session['api_hash']
    phone = session['phone'].replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    links = []; my_id = None

    try:
        await client.connect()
        if not await client.is_user_authorized(): 
            log_msg("WARN", f"🔐 {phone}: Требуется вход! (Пропуск)")
            return {'links': []}

        me = await client.get_me()
        my_id = me.id
        try: await hide_maker_phone(client)
        except: pass
        
        # Определяем имена и цели
        names = manual_names if manual_names else [pre_group_name] * len(pre_approved_chunk)
        targets = [None] * len(names) if manual_names else pre_approved_chunk
        
        # Настройки инвайта
        need_invite = delays.get("manual_add_contacts", 0) if manual_names else delays.get("smart_add_clients", 1)

        for i, name in enumerate(names):
            if stop_flag.is_set(): break
            log_msg("INFO", f"🛠 {phone}: Группа {i+1}/{len(names)} ({name})")

            try:
                # --- ЭТАП 1: ПОЛУЧЕНИЕ КОНТАКТА ---
                contact_user = None
                
                # Если это Smart Mode, у нас уже есть объект InputUser или User
                if not manual_names and targets[i]:
                    raw_user = targets[i].get('user')
                    # Если это объект User (полный), используем его. 
                    # Если InputUser - тоже ок.
                    contact_user = raw_user

                # --- ЭТАП 2: СОЗДАНИЕ ГРУППЫ ---
                try:
                    res = await client(functions.messages.CreateChatRequest(users=[], title=name))
                    chat = res.chats[0] if hasattr(res, 'chats') and res.chats else res.updates.chats[0]
                except Exception as e:
                    log_msg("ERROR", f"   ❌ Не создал группу: {e}")
                    continue
                
                # --- ЭТАП 3: ССЫЛКА ---
                try:
                    invite = await client(functions.messages.ExportChatInviteRequest(peer=chat))
                    links.append(invite.link)
                except Exception as e: 
                    log_msg("ERROR", f"   ❌ Ошибка ссылки: {e}")

                # --- ЭТАП 4: ИНВАЙТ КЛИЕНТА ---
                if need_invite and contact_user:
                    # Пауза, чтобы Телеграм "увидел" чат
                    await asyncio.sleep(1)
                    await add_and_clean(client, chat, contact_user, delays)
                elif need_invite and not contact_user:
                    log_msg("WARN", "   ⚠️ Некого инвайтить (нет контакта).")
                
                # Пауза между группами
                if i < len(names) - 1:
                    wait_t = delays.get('creation', 180)
                    await smart_sleep(wait_t, False) 

            except FloodWaitError as e:
                log_msg("WAIT", f"⏳ {phone}: Флуд {e.seconds} сек.")
                await asyncio.sleep(e.seconds)
            except Exception as e: 
                log_msg("ERROR", f"❌ Ошибка в цикле группы: {e}")

        return {'links': links}

    except Exception as e: 
        log_msg("ERROR", f"❌ Критическая ошибка Worker: {e}")
        return {'links': []}
    finally:
        if client.is_connected(): await client.disconnect()

async def guest_execution_final(session, links, text):
    if not links: return
    api_id = int(session['api_id']); api_hash = session['api_hash']
    phone = session['phone'].replace(" ", "")
    
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized(): return
        
        me = await client.get_me()
        log_msg("GUEST", f"😎 Директор ({me.first_name}) заходит в {len(links)} групп...")

        for link in links:
            if stop_flag.is_set(): break
            try:
                hash_arg = link.replace("https://t.me/+", "").replace("https://t.me/joinchat/", "").strip()
                updates = await client(functions.messages.ImportChatInviteRequest(hash=hash_arg))
                new_chat = updates.chats[0] if updates.chats else None
                
                if new_chat:
                    await asyncio.sleep(2) 
                    await client.send_message(new_chat, text)
                    log_msg("SUCCESS", f"   ✅ Зашел и написал: {new_chat.title}")
            except Exception as e:
                log_msg("WARN", f"   ⚠️ Сбой входа: {e}")
            
            await asyncio.sleep(random.uniform(3.0, 5.0))
            
        log_msg("GUEST", "🏁 Работа Директора завершена.")

    except Exception as e:
        log_msg("ERROR", f"❌ Ошибка Директора: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

def run_thread(main_sessions, guest_session, names, delays, manual_uname, greet_txt, need_greet, smart_path=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        chunks_data = [] 
        is_manual = False
        group_name_smart = None

        # --- ЛОГИКА ЛИДЕРА (Проверка базы) ---
        if smart_path:
            ls = main_sessions[0]
            # Создаем клиенты с привязкой к loop
            lc = TelegramClient(f"session_{ls['phone'].replace(' ','')}", int(ls['api_id']), ls['api_hash'], loop=loop)
            gc = None
            if guest_session:
                 gc = TelegramClient(f"session_{guest_session['phone'].replace(' ','')}", int(guest_session['api_id']), guest_session['api_hash'], loop=loop)

            async def run_leader_check():
                await lc.connect()
                if not await lc.is_user_authorized():
                    log_msg("ERROR", "❌ Лидер не авторизован!")
                    return None, None
                if gc: await gc.connect()
                
                # Запускаем проверку
                return await process_smart_target_file(lc, gc, smart_path, guest_session)

            group_name_smart, selected_raw_data = loop.run_until_complete(run_leader_check())
            
            if lc.is_connected(): loop.run_until_complete(lc.disconnect())
            if gc and gc.is_connected(): loop.run_until_complete(gc.disconnect())

            if not selected_raw_data:
                log_msg("WARN", "⛔ Отмена или пусто.")
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
        for i, session in enumerate(main_sessions):
            if i < len(chunks) and chunks[i]:
                # Создаем задачи (coroutine objects)
                if is_manual:
                    task = worker_task(session, delays, guest_session, manual_names=chunks[i], manual_target_user=manual_uname)
                else:
                    task = worker_task(session, delays, guest_session, pre_approved_chunk=chunks[i], pre_group_name=group_name_smart)
                maker_tasks.append(task)

        all_created_links = []
        if maker_tasks:
            # ВОТ ЗДЕСЬ ПАДАЛО. Теперь maker_tasks точно содержит корутины.
            results = loop.run_until_complete(asyncio.gather(*maker_tasks))
            
            for res in results:
                if res and isinstance(res, dict) and res.get('links'): 
                    all_created_links.extend(res['links'])
            
            log_msg("INFO", f"📊 ИТОГ: Сгенерировано {len(all_created_links)} ссылок.")

            # --- ЗАПУСК ГОСТЯ ---
            nd = delays.get("manual_add_director", 1) if is_manual else delays.get("smart_add_director", 1)

            if guest_session and not stop_flag.is_set() and all_created_links and nd:
                log_msg("INFO", "\n=== ЗАПУСК ГОСТЯ ===")
                log_msg("WAIT", "⏳ Ждем 3 сек...")
                time.sleep(3)
                
                final_text = greet_txt if need_greet else ""
                loop.run_until_complete(guest_execution_final(guest_session, all_created_links, final_text))
            
    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка Run Thread: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try: loop.close()
        except: pass
        
        def restore_buttons():
            try:
                # ВОССТАНАВЛИВАЕМ ТОЛЬКО СУЩЕСТВУЮЩИЕ КНОПКИ
                if 'smart_btn' in globals() and smart_btn and smart_btn.winfo_exists(): smart_btn.config(state='normal')
                if 'load_btn' in globals() and load_btn and load_btn.winfo_exists(): load_btn.config(state='normal')
            except: pass
        if root and root.winfo_exists(): root.after(0, restore_buttons)

def get_cursor_screen_pos():
    try: return root.winfo_pointerxy()
    except: return 200, 200

def position_near_cursor(win, width=None, height=None, offset=(12, 12)):
    try:
        screen_w = win.winfo_screenwidth(); screen_h = win.winfo_screenheight()
        cx, cy = get_cursor_screen_pos()
        win.update_idletasks()
        w = width or win.winfo_width() or 350; h = height or win.winfo_height() or 200
        x = max(0, min(screen_w - w, cx + offset[0]))
        y = max(0, min(screen_h - h, cy + offset[1]))
        win.geometry(f"{w}x{h}+{x}+{y}")
    except: pass

def make_modal(win, parent=None, near_cursor=True, width=None, height=None):
    try:
        if parent: win.transient(parent)
        win.attributes('-topmost', True); win.lift(); win.focus_force(); win.grab_set()
        if near_cursor: position_near_cursor(win, width=width, height=height)
    except: pass

def open_new_window():
    try: subprocess.Popen([sys.executable, __file__])
    except Exception as e: messagebox.showerror("Ошибка", f"Не удалось открыть новое окно: {e}")

def run_login_check(s_data, callback_refresh):
    raw_phone = s_data.get('phone', '')
    phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
    async def process():
        try:
            await client.connect()
            if not await client.is_user_authorized():
                try:
                    await client.send_code_request(phone)
                    code = await loop.run_in_executor(None, ask_code_gui, raw_phone, False)
                    if not code: return
                    try: await client.sign_in(phone, code)
                    except SessionPasswordNeededError:
                        pwd = await loop.run_in_executor(None, ask_code_gui, raw_phone, True)
                        await client.sign_in(password=pwd)
                except Exception as ex: messagebox.showerror("Ошибка входа", f"Не удалось войти:\n{ex}"); return
            me = await client.get_me()
            update_session_info(raw_phone, f"{me.first_name} {me.last_name or ''}", me.username or "")
            messagebox.showinfo("Успех", f"Аккаунт {phone} активен!\nUser: @{me.username}")
            if root: root.after(0, callback_refresh)
        except Exception as e: messagebox.showerror("Ошибка", f"Критический сбой:\n{e}")
        finally:
            if client.is_connected(): await client.disconnect()
    try: loop.run_until_complete(process())
    finally: loop.close()

def open_add_account_window(on_close_callback):
    d = Toplevel(root); d.title("Добавить аккаунт"); d.geometry("400x550")
    make_modal(d, root, False)
    d.configure(bg="#2E3440")
    cf = ttk.Frame(d, padding=20); cf.pack(fill="both", expand=True)
    ttk.Label(cf, text="Номер телефона:").pack(anchor="w")
    e_ph = ttk.Entry(cf, font=("Consolas", 12)); e_ph.pack(fill="x", pady=(5, 15)); e_ph.focus_set()
    lbl_st = ttk.Label(cf, text="", foreground="#88C0D0", font=("Segoe UI", 9)); lbl_st.pack(pady=5)
    lf_api = ttk.LabelFrame(cf, text=" Данные API ", padding=10); lf_api.pack(fill="x", pady=10)
    ttk.Label(lf_api, text="API ID:").pack(anchor="w"); e_id = ttk.Entry(lf_api); e_id.pack(fill="x", pady=(0,5))
    ttk.Label(lf_api, text="API Hash:").pack(anchor="w"); e_hash = ttk.Entry(lf_api); e_hash.pack(fill="x")
    
    def run_auto():
        phone = e_ph.get().strip()
        if not phone: messagebox.showerror("Ошибка", "Сначала введите номер телефона!"); return
        lbl_st.config(text="🚀 Запуск процесса...", foreground="white")
        def thread_auto():
            def update_ui(text, color="white"):
                try:
                    if d.winfo_exists(): lbl_st.config(text=text, foreground=color)
                except: pass
            try:
                update_ui("⏳ Подключение к my.telegram.org...", "#88C0D0")
                wc = TelegramWebClient()
                clean_phone = wc.send_password(phone)
                update_ui("⌨ Дайте цифры из Telegram...", "white")
                code = ask_code_gui(clean_phone, False)
                if not code: update_ui("❌ Ввод кода отменен.", "#BF616A"); return
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
                            if any(s.get('phone') == clean_phone for s in ss): messagebox.showwarning("Дубликат", "Этот номер уже есть!"); return
                            ss.append({"api_id": str(keys['api_id']), "api_hash": str(keys['api_hash']), "phone": clean_phone, "name": "Auto (Нужен вход)", "username": "", "last_used": time.time()})
                            save_sessions(ss)
                            if on_close_callback: on_close_callback()
                            messagebox.showinfo("Успех", f"Аккаунт {clean_phone} добавлен!"); d.destroy()
                        else: update_ui("❌ Не удалось найти ключи.", "#BF616A")
                    except: pass
                d.after(0, finish_success)
            except Exception as e: d.after(0, lambda: update_ui(f"❌ Ошибка: {e}", "#BF616A"))
        threading.Thread(target=thread_auto, daemon=True).start()

    def save_manual():
        phone = e_ph.get().strip(); aid = e_id.get().strip(); ahash = e_hash.get().strip()
        if not (phone and aid and ahash): messagebox.showwarning("!", "Заполните все поля"); return
        ss = load_sessions()
        if any(s.get('phone') == phone for s in ss): messagebox.showwarning("!", "Дубликат"); return
        ss.append({"api_id": aid, "api_hash": ahash, "phone": phone, "name": "Manual New", "username": "", "last_used": time.time()})
        save_sessions(ss)
        if on_close_callback: on_close_callback()
        d.destroy()

    ttk.Button(cf, text="⚡ Авто-получение (Web)", command=run_auto).pack(fill="x", pady=5)
    ttk.Button(cf, text="💾 Сохранить", command=save_manual, style="Green.TButton").pack(fill="x", pady=(10,0))

def parse_custom_file(content):
    candidates = []
    sections = re.split(r'-{5,}', content)
    for sec in sections:
        if not sec.strip(): continue
        raw_nums = re.findall(r'\b(?:7|8|9)\d{9,10}\b', sec)
        phones = []
        for p in raw_nums:
            if not ((p.startswith('19') or p.startswith('20')) and len(p)==4): phones.append(p)
        if phones:
            name = "Unknown"; dob = ""
            match = re.search(r'([А-ЯЁ][А-ЯЁ\s-]{4,})\s+(\d{2}\.\d{2}\.\d{4})', sec)
            if match: name = match.group(1).strip(); dob = match.group(2).strip()
            else:
                match_name = re.search(r'([А-ЯЁ][А-ЯЁ\s-]{4,})', sec)
                if match_name: name = match_name.group(1).strip()
            if "РУКОВОДИТЕЛЬ" in name.upper(): name = "Руководитель"
            candidates.append({"fio": name, "dob": dob, "phones": phones})
    return candidates

async def process_check_and_save(file_path):
    sessions = load_sessions()
    if not sessions: messagebox.showerror("Ошибка", "Нет активных сессий!"); return
    session = sessions[0]; api_id = int(session['api_id']); api_hash = session['api_hash']
    phone = session['phone'].replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
    client = TelegramClient(f"session_{phone}", api_id, api_hash)
    try:
        log_msg("INFO", f"🔌 Подключение: {phone}...")
        await client.connect()
        if not await client.is_user_authorized(): messagebox.showerror("Ошибка", f"Аккаунт {phone} не авторизован!"); return
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
        except:
            with open(file_path, 'r', encoding='cp1251') as f: content = f.read()
        
        comp_match = re.search(r'(?i)(?:ООО|АО|НПП|ПАО|ЗАО|ИП)\s*["«“]([^"»”]+)["»”]', content)
        company_name = comp_match.group(1).strip() if comp_match else "Base"
        candidates = parse_custom_file(content)
        if not candidates: messagebox.showwarning("Пусто", "Не удалось найти контакты."); return

        log_msg("INFO", f"🚀 Начинаем пробив {len(candidates)} чел...")
        batch_list = []; tracking_map = {} 
        for cand in candidates:
            for raw in cand['phones']:
                d = re.sub(r'\D', '', raw)
                if len(d) == 11 and d.startswith('8'): import_phone = "+7" + d[1:]
                elif len(d) == 11 and d.startswith('7'): import_phone = "+" + d
                elif len(d) == 10 and d.startswith('9'): import_phone = "+7" + d
                else: import_phone = "+" + d
                my_client_id = random.randint(10000000, 999999999)
                tracking_map[my_client_id] = {'fio': cand['fio'], 'dob': cand['dob'], 'orig_phone': raw.strip()}
                batch_list.append(types.InputPhoneContact(client_id=my_client_id, phone=import_phone, first_name=cand['fio'][:20], last_name=""))

        found_matches = []; all_imported_ids = []; chunk_size = 5 
        for i in range(0, len(batch_list), chunk_size):
            chunk = batch_list[i : i + chunk_size]
            log_msg("INFO", f"   🔎 Проверка {i+1}-{min(i+len(chunk), len(batch_list))}...")
            try:
                res = await client(functions.contacts.ImportContactsRequest(contacts=chunk))
                # Запоминаем ID всех найденных
                for u in res.users: all_imported_ids.append(u.id)
                
                tg_id_to_client = {imp.user_id: imp.client_id for imp in res.imported}
                users_refetch = [types.InputUser(user_id=u.id, access_hash=u.access_hash) for u in res.users if u.id in tg_id_to_client]
                
                # НЕ УДАЛЯЕМ ЗДЕСЬ!
                
                if users_refetch:
                    clean_users = await client(functions.users.GetUsersRequest(id=users_refetch))
                    for u in clean_users:
                        c_id = tg_id_to_client.get(u.id)
                        orig = tracking_map.get(c_id)
                        if orig:
                            found_matches.append({'target_fio': orig['fio'], 'target_dob': orig['dob'], 'user': u, 'phone': orig['orig_phone']})
                            log_msg("SUCCESS", f"      ✅ Есть: {orig['fio']}")
                else:
                    if res.imported or res.retry_contacts: log_msg("DEBUG", f"      ⚠️ Telegram принял номера, но не вернул юзеров.")
                    else: log_msg("WARN", f"      ⚠️ Telegram ничего не вернул.")
                await asyncio.sleep(random.uniform(2.0, 4.0))
            except Exception as e: log_msg("ERROR", f"Err: {e}")

        if not found_matches: messagebox.showinfo("Результат", "Никого не нашли."); return

        future_gui = asyncio.get_running_loop().create_future()
        def show_gui():
            win = MatchReviewWindow(root, found_matches, company_name)
            root.wait_window(win)
            if win.result is not None: future_gui.set_result(win.result)
            else: future_gui.set_result([])
        root.after(0, show_gui)
        selected_matches = await future_gui

        # === ЛОГИКА ОЧИСТКИ (Желтая кнопка) ===
        # Удаляем только тех, кого НЕ выбрали
        if all_imported_ids:
            kept_ids = [m['user'].id for m in selected_matches] if selected_matches else []
            ids_to_del = [uid for uid in all_imported_ids if uid not in kept_ids]
            
            if ids_to_del:
                log_msg("INFO", f"🧹 Очистка: удаляем {len(ids_to_del)} лишних...")
                try:
                    for k in range(0, len(ids_to_del), 50): await client(functions.contacts.DeleteContactsRequest(id=ids_to_del[k:k+50]))
                except: pass
            else:
                log_msg("INFO", "✅ Контакты сохранены.")

        if not selected_matches:
            log_msg("WARN", "⛔ Отмена.")
            return

        log_msg("INFO", "💾 Сохранение файла...")
        save_dir = "прописанные базы"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        safe_name = re.sub(r'[\\/*?:"<>|]', "", company_name).strip() or "Base"
        filename = f"{safe_name}_CHECKED_{ts}.txt"
        
        with open(os.path.join(save_dir, filename), "w", encoding="utf-8") as f:
            head_split = re.split(r'-{5,}', content)
            if head_split: f.write(head_split[0].strip() + "\n")
            f.write("\n" + "="*40 + "\nГруппа: {company_name}\nОТЧЕТ ПРОБИВА\n\n")
            for m in selected_matches:
                line_fio = m['target_fio']
                if m.get('target_dob'): line_fio += f" {m['target_dob']}"
                u = m['user']
                tg_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                if u.username: tg_name += f" (@{u.username})"
                f.write(f"{line_fio} /\n {m['phone']} /\n {tg_name}\n" + "-" * 36 + "\n\n")
        log_msg("SUCCESS", f"✅ Готово! Файл: {filename}")
        messagebox.showinfo("Готово", f"Сохранено: {len(selected_matches)} чел.")

    except Exception as e: log_msg("ERROR", f"Critical: {e}"); messagebox.showerror("Err", str(e))
    finally:
        if client.is_connected(): await client.disconnect()

def start_process(mode="smart"):
    try:
        initial_dir = os.getcwd() 
        if mode == "saved": initial_dir = os.path.join("прописанные базы", "отмена и схроненные")
        if not os.path.exists(initial_dir): os.makedirs(initial_dir)
        
        smart_path = filedialog.askopenfilename(initialdir=initial_dir, title="Выберите файл", filetypes=[("Text Files", "*.txt")])
        if not smart_path: return 

        stop_flag.clear()
        if log_widget:
            log_widget.config(state='normal'); log_widget.delete("1.0", tk.END); log_widget.config(state='disabled')

        sessions_data = load_sessions()
        selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
        if not selected_indices: messagebox.showwarning("!", "Выберите мейкеров!"); return

        guest_idx = guest_account_index.get()
        guest_session = None
        if guest_idx != -1 and guest_idx < len(sessions_data):
            guest_session = sessions_data[guest_idx]
            if guest_idx in selected_indices: selected_indices.remove(guest_idx)

        main_sessions = [sessions_data[i] for i in selected_indices]
        if not main_sessions: messagebox.showwarning("!", "Нет мейкеров (все заняты или не выбраны)!"); return

        cfg = load_config()
        greeting_text = cfg.get("greeting_text", "")
        smart_greet = int(cfg.get("smart_send_greeting", "1"))

        if guest_session and smart_greet and not greeting_text:
            messagebox.showwarning("Внимание", "Текст приветствия пустой!"); return

        delays = {
            "creation": float(cfg.get("delay_creation", 180)),
            "delay_contact": float(cfg.get("delay_contact", 20)),
            "cleanup": 10, "random": int(cfg.get("random_delay", 1)),
            "smart_add_director": int(cfg.get("smart_add_director", "1")),
            "smart_add_clients": int(cfg.get("smart_add_clients", "1")),
            "smart_send_greeting": smart_greet 
        }

        # Блокируем кнопки
        if 'smart_btn' in globals() and smart_btn: smart_btn.config(state='disabled')
        if 'load_btn' in globals() and load_btn: load_btn.config(state='disabled')
        
        # ЗАПУСК БЕЗ ВОПРОСОВ
        threading.Thread(target=run_thread, args=(main_sessions, guest_session, [], delays, "", greeting_text, smart_greet, smart_path), daemon=True).start()
        
    except Exception as e:
        messagebox.showerror("Ошибка", str(e))
        if 'smart_btn' in globals() and smart_btn: smart_btn.config(state='normal')
        if 'load_btn' in globals() and load_btn: load_btn.config(state='normal')

def run_safety_check(main_sessions, callback_success):
    log_msg("INFO", "🛡 ЗАПУСК ПРЕДОХРАНИТЕЛЯ... Проверка статуса.")
    def _check():
        try: current_ip = requests.get("https://api64.ipify.org?format=json", timeout=5).json().get("ip", "ERR")
        except: current_ip = "Ошибка сети"
        leader_status = "Skipped"; is_bad = False
        if main_sessions:
            s = main_sessions[0]
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{s['phone']}", int(s['api_id']), s['api_hash'], loop=loop)
            async def safe_check():
                st, bad = "OK", False
                try:
                    await client.connect()
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        if me.restricted: st, bad = f"RESTRICTED: {me.restriction_reason}", True
                        else: st = "ACTIVE (Clean)"
                    else: st = "NEED AUTH"
                except FloodWaitError as e: st, bad = f"FLOOD WAIT {e.seconds}s", True
                except Exception as e: st = f"ERR: {e}"
                finally:
                    if client.is_connected(): await client.disconnect()
                return st, bad
            try: leader_status, is_bad = loop.run_until_complete(safe_check())
            finally: loop.close()

        def show():
            icon = "warning" if is_bad else "info"
            msg = f"🔎 IP: {current_ip}\n👤 Аккаунт: {leader_status}\n\nПродолжить?"
            parent = root
            for w in root.winfo_children():
                if isinstance(w, Toplevel) and w.winfo_viewable(): parent = w; break
            if messagebox.askyesno("Предохранитель", msg, icon=icon, parent=parent):
                log_msg("SUCCESS", "⚡ Запуск процессов...")
                callback_success()
            else:
                log_msg("WARN", "⛔ Отмена.")
                if 'smart_btn' in globals() and smart_btn: smart_btn.config(state='normal')
                if 'load_btn' in globals() and load_btn: load_btn.config(state='normal')
        root.after(0, show)
    threading.Thread(target=_check, daemon=True).start()

NOTES_FILE = "notes_data.json"
def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}
def save_notes_to_file(data):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def create_note_tab(notebook, title, content=""):
    frame = ttk.Frame(notebook); notebook.add(frame, text=title)
    txt = scrolledtext.ScrolledText(frame, font=("Consolas", 11), bg="#0F0F0F", fg="#E0E0E0", insertbackground="#9D00FF")
    txt.pack(fill="both", expand=True, padx=5, pady=5); txt.insert("1.0", content)
    btn_frame = ttk.Frame(frame); btn_frame.pack(fill="x", padx=5, pady=5)
    def _save():
        d = load_notes(); d[title] = txt.get("1.0", tk.END); save_notes_to_file(d)
        messagebox.showinfo("Сохранено", f"Заметка '{title}' сохранена!")
    def _delete():
        if messagebox.askyesno("Удаление", f"Удалить вкладку '{title}'?"):
            d = load_notes(); 
            if title in d: del d[title]
            save_notes_to_file(d); notebook.forget(frame)
    ttk.Button(btn_frame, text="💾 Сохранить", command=_save).pack(side="left")
    ttk.Button(btn_frame, text="🗑 Удалить вкладку", command=_delete).pack(side="right")

def on_tab_changed(event):
    nb = event.widget
    try:
        if nb.index("current") == nb.index("end") - 1:
            if nb.index("end") > 1: nb.select(0)
            def ask_name():
                new_title = simpledialog.askstring("Новая заметка", "Название вкладки:", parent=root)
                if not new_title or not new_title.strip(): return
                create_note_tab(nb, new_title.strip()); save_notes_to_file(load_notes())
                nb.select(nb.index("end") - 2)
            root.after(100, ask_name)
    except: pass

def stop_process():
    stop_flag.set()
    log_msg("ERROR", "🛑 === НАЖАТ СТОП! ЭКСТРЕННАЯ ОСТАНОВКА === 🛑")
    
    # ИСПРАВЛЕНО: Убрал start_btn из списка, оставил только smart_btn и load_btn
    if root: 
        root.after(1000, lambda: [b.config(state='normal') for b in [smart_btn, load_btn] if b and b.winfo_exists()])

# === UI MODAL ===
def setup_dark_theme():
    style = ttk.Style(); style.theme_use('clam')
    bg_main = "#121212"; bg_input = "#1E1E1E"; fg_text = "#E0E0E0"; accent = "#9D00FF"
    style.configure(".", background=bg_main, foreground=fg_text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg_main); style.configure("Sidebar.TFrame", background="#0F0F0F")
    style.configure("TLabel", background=bg_main, foreground=fg_text)
    style.configure("TEntry", fieldbackground=bg_input, foreground="white", insertcolor=accent, borderwidth=0)
    style.map("TEntry", fieldbackground=[('focus', bg_input)], bordercolor=[('focus', accent)])
    style.configure("TLabelframe", background=bg_main, bordercolor="#333333", borderwidth=1)
    style.configure("TLabelframe.Label", background=bg_main, foreground=accent, font=("Segoe UI", 9, "bold"))
    style.configure("TButton", background=accent, foreground="white", borderwidth=0, padding=6)
    style.map("TButton", background=[('active', "#B540FF"), ('pressed', "#7A00C7")])
    style.configure("Green.TButton", background="#00E676", foreground="#121212")
    style.map("Green.TButton", background=[('active', "#69F0AE")])
    style.configure("Red.TButton", background="#FF5252", foreground="white")
    style.map("Red.TButton", background=[('active', "#FF8A80")])
    style.configure("Vertical.TScrollbar", troughcolor=bg_main, background="#333", borderwidth=0, arrowcolor="white")
    style.configure("TNotebook", background=bg_main, borderwidth=0)
    style.configure("TNotebook.Tab", background="#1E1E1E", foreground="#888", padding=[10, 5])
    style.map("TNotebook.Tab", background=[('selected', accent)], foreground=[('selected', 'white')])
    style.configure("Treeview", background=bg_input, fieldbackground=bg_input, foreground="white", borderwidth=0, rowheight=28)
    style.configure("Treeview.Heading", background="#252525", foreground=accent, borderwidth=0, font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[('selected', accent)], foreground=[('selected', 'white')])
    return bg_main, bg_input

def create_settings_tab(parent):
    cfg = load_config()
    canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0)
    sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
    setup_scroll_canvas(canvas, scroll_frame) 

    pad = 20
    tk.Label(scroll_frame, text="ПУЛЬТ УПРАВЛЕНИЯ", font=("Segoe UI Black", 14), bg="#121212", fg="#9D00FF").pack(anchor="w", padx=pad, pady=(20, 10))
    f_btns = ttk.Frame(scroll_frame); f_btns.pack(fill="x", padx=pad, pady=(0, 20))
    ttk.Button(f_btns, text="🛠 РУЧНОЙ РЕЖИМ (Мануал)", command=open_manual_mode_window).pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=10)
    ttk.Button(f_btns, text="❐ НОВОЕ ОКНО (Мультизапуск)", command=open_new_window).pack(side="left", fill="x", expand=True, ipady=10)

    time_frame = ttk.LabelFrame(scroll_frame, text=" ⏱ Тайминги (сек) ", padding=15); time_frame.pack(fill="x", padx=pad, pady=(0, 10))
    f_t1 = ttk.Frame(time_frame); f_t1.pack(fill="x", pady=5)
    ttk.Label(f_t1, text="После создания группы:").pack(side="left")
    e1 = ttk.Entry(f_t1, width=8, font=("Consolas", 10), justify="center"); e1.pack(side="right"); e1.insert(0, cfg.get("delay_creation", "180"))
    f_t2 = ttk.Frame(time_frame); f_t2.pack(fill="x", pady=5)
    ttk.Label(f_t2, text="После инвайта контакта:").pack(side="left")
    e2 = ttk.Entry(f_t2, width=8, font=("Consolas", 10), justify="center"); e2.pack(side="right"); e2.insert(0, cfg.get("delay_contact", "20"))
    var_rand = tk.IntVar(value=int(cfg.get("random_delay", "1")))
    ttk.Checkbutton(time_frame, text="Случайная задержка (+5..15с)", variable=var_rand).pack(anchor="w", pady=(10, 0))

    modes_frame = ttk.Frame(scroll_frame); modes_frame.pack(fill="x", padx=pad, pady=(0, 10))
    smart_frame = ttk.LabelFrame(modes_frame, text=" 🧠 Smart Mode (По базе) ", padding=15)
    smart_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    v_smart_dir = tk.IntVar(value=int(cfg.get("smart_add_director", "1")))
    ttk.Checkbutton(smart_frame, text="Добавлять Директора (по ссылке)", variable=v_smart_dir).pack(anchor="w", pady=2)
    v_smart_client = tk.IntVar(value=int(cfg.get("smart_add_clients", "1")))
    ttk.Checkbutton(smart_frame, text="Инвайтить Клиентов в группу", variable=v_smart_client).pack(anchor="w", pady=2)
    tk.Label(smart_frame, text="(Если НЕТ: просто сохранит в книгу)", font=("Segoe UI", 7), fg="#777", bg="#121212").pack(anchor="w", padx=20)
    v_smart_greet = tk.IntVar(value=int(cfg.get("smart_send_greeting", "1")))
    ttk.Checkbutton(smart_frame, text="Слать приветствие", variable=v_smart_greet).pack(anchor="w", pady=2)

    manual_frame = ttk.LabelFrame(modes_frame, text=" 🛠 Manual Mode (Пустышки) ", padding=15)
    manual_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
    v_man_dir = tk.IntVar(value=int(cfg.get("manual_default_dir", "1")))
    ttk.Checkbutton(manual_frame, text="Добавлять Директора", variable=v_man_dir).pack(anchor="w", pady=2)
    v_man_cont = tk.IntVar(value=int(cfg.get("manual_default_contact", "0")))
    ttk.Checkbutton(manual_frame, text="Инвайтить Контакты (Из книги)", variable=v_man_cont).pack(anchor="w", pady=2)
    v_man_greet = tk.IntVar(value=int(cfg.get("manual_default_greet", "1")))
    ttk.Checkbutton(manual_frame, text="Слать приветствие", variable=v_man_greet).pack(anchor="w", pady=2)

    greet_frame = ttk.LabelFrame(scroll_frame, text=" 💬 Текст приветствия ", padding=15); greet_frame.pack(fill="x", padx=pad, pady=(0, 20))
    txt_greet_set = scrolledtext.ScrolledText(greet_frame, height=4, font=("Consolas", 10), bg="#0F0F0F", fg="#00FF00", insertbackground="#9D00FF", borderwidth=0)
    txt_greet_set.pack(fill="x"); txt_greet_set.insert("1.0", cfg.get("greeting_text", ""))

    def save_settings():
        new_cfg = cfg.copy()
        new_cfg.update({
            "random_delay": str(var_rand.get()), "delay_creation": e1.get(), "delay_contact": e2.get(),
            "smart_add_director": str(v_smart_dir.get()), "smart_add_clients": str(v_smart_client.get()), "smart_send_greeting": str(v_smart_greet.get()),
            "manual_default_dir": str(v_man_dir.get()), "manual_default_contact": str(v_man_cont.get()), "manual_default_greet": str(v_man_greet.get()),
            "greeting_text": txt_greet_set.get("1.0", tk.END).strip()
        })
        save_config(new_cfg)
        messagebox.showinfo("Настройки", "✅ Конфигурация сохранена!", parent=parent)

    ttk.Button(scroll_frame, text="💾 ПРИМЕНИТЬ НАСТРОЙКИ", command=save_settings, style="Green.TButton").pack(fill="x", padx=pad, pady=(0, 30), ipady=8)

global tree_accounts
tree_accounts = None

def create_accounts_tab(parent):
    global tree_accounts
    fr = ttk.Frame(parent); fr.pack(fill="both", expand=True)
    toolbar = ttk.Frame(fr, padding=10); toolbar.pack(fill="x")
    search_frame = ttk.Frame(fr, padding=(10, 0, 10, 10)); search_frame.pack(fill="x")
    ent_search = ttk.Entry(search_frame, width=30, font=("Consolas", 10)); ent_search.pack(side="left")
    
    def _refresh_tree(event=None):
        if tree_accounts is None: return
        raw_val = ent_search.get().lower().strip()
        search_query = raw_val if raw_val and raw_val != "поиск" else ""
        clean_query_phone = raw_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        for i in tree_accounts.get_children(): tree_accounts.delete(i)
        sessions = load_sessions()
        for idx, s in enumerate(sessions):
            raw_phone = s.get('phone', ''); name = s.get('name', 'Без имени'); uname = s.get('username', '')
            if search_query:
                db_phone_clean = raw_phone.lower().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                if not (clean_query_phone in db_phone_clean or search_query in name.lower() or search_query in uname.lower()): continue
            last_ts = s.get('last_used', 0)
            dt_str = datetime.fromtimestamp(float(last_ts)).strftime('%d.%m %H:%M') if last_ts else "Новый"
            tree_accounts.insert("", "end", iid=str(idx), values=(raw_phone, name, f"@{uname}" if uname else "-", dt_str))

    ent_search.bind("<KeyRelease>", _refresh_tree)

    def _delete_logic():
        if not tree_accounts: return
        sel = tree_accounts.selection()
        if not sel: return
        if not messagebox.askyesno("Удаление", f"Удалить {len(sel)} аккаунтов?"): return
        indices = sorted([int(x) for x in sel], reverse=True)
        ss = load_sessions()
        for i in indices: 
            if i < len(ss): del ss[i]
        save_sessions(ss); _refresh_tree(); refresh_main_checks()

    def _clear_contacts():
        sel = tree_accounts.selection()
        if not sel: messagebox.showwarning("!", "Выберите аккаунт!"); return
        idx = int(sel[0]); s_data = load_sessions()[idx]; phone = s_data['phone']
        if not messagebox.askyesno("Внимание", f"УДАЛИТЬ ВСЕ КОНТАКТЫ на {phone}?"): return
        def runner():
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            client = TelegramClient(f"session_{phone}", int(s_data['api_id']), s_data['api_hash'], loop=loop)
            try:
                loop.run_until_complete(client.connect())
                if loop.run_until_complete(client.is_user_authorized()):
                    cts = loop.run_until_complete(client(functions.contacts.GetContactsRequest(hash=0)))
                    u_ids = [u.id for u in cts.users if not u.self]
                    if u_ids: 
                        for i in range(0, len(u_ids), 50): loop.run_until_complete(client(functions.contacts.DeleteContactsRequest(id=u_ids[i:i+50])))
            except: pass
            finally: 
                if client.is_connected(): loop.run_until_complete(client.disconnect())
            loop.close()
        threading.Thread(target=runner, daemon=True).start()

    f_left = ttk.Frame(toolbar); f_left.pack(side="left")
    ttk.Button(f_left, text="➕ Добавить", command=lambda: open_add_account_window(lambda: (_refresh_tree(), refresh_main_checks()))).pack(side="left", padx=(0, 5))
    ttk.Button(f_left, text="🔄 Войти/Обновить", command=lambda: threading.Thread(target=lambda: run_login_check(load_sessions()[int(tree_accounts.selection()[0])], _refresh_tree), daemon=True).start() if tree_accounts.selection() else None).pack(side="left", padx=5)
    f_mid = ttk.Frame(toolbar); f_mid.pack(side="left", padx=20)
    ttk.Button(f_mid, text="🧹 Удалить контакты", command=_clear_contacts).pack(side="left")
    ttk.Button(f_mid, text="⚡ Чекнуть ВСЕХ", command=lambda: (start_update_all(), parent.after(2000, _refresh_tree))).pack(side="left", padx=5)
    ttk.Button(toolbar, text="❌ Удалить", command=_delete_logic, style="Red.TButton").pack(side="right")

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

def create_dashboard_tab(parent):
    center_frame = ttk.Frame(parent, padding=(15, 15, 15, 0)); center_frame.pack(fill="both", expand=True)
    lf_makers = ttk.LabelFrame(center_frame, text=" 🤖 1. Расходка (Мейкеры) ", padding=10); lf_makers.pack(side="left", fill="both", expand=True, padx=(0, 5))
    c_makers = tk.Canvas(lf_makers, bg="#121212", highlightthickness=0)
    sb_makers = ttk.Scrollbar(lf_makers, command=c_makers.yview)
    c_makers.configure(yscrollcommand=sb_makers.set)
    c_makers.pack(side="left", fill="both", expand=True); sb_makers.pack(side="right", fill="y")
    global sc_fr
    sc_fr = ttk.Frame(c_makers); c_makers.create_window((0,0), window=sc_fr, anchor="nw")
    sc_fr.bind("<Configure>", lambda e: c_makers.configure(scrollregion=c_makers.bbox("all")))
    setup_scroll_canvas(c_makers, sc_fr)

    lf_guest = ttk.LabelFrame(center_frame, text=" 👤 2. Дир (Гость) ", padding=10); lf_guest.pack(side="right", fill="both", expand=True, padx=(5, 0))
    f_search_g = ttk.Frame(lf_guest); f_search_g.pack(fill="x", pady=(0, 5))
    global ent_guest_search
    ent_guest_search = ttk.Entry(f_search_g, font=("Consolas", 10)); ent_guest_search.pack(fill="x")
    ent_guest_search.insert(0, "поиск"); ent_guest_search.configure(foreground="#888")
    ent_guest_search.bind("<FocusIn>", lambda e: (ent_guest_search.delete(0, "end"), ent_guest_search.configure(foreground="white")) if ent_guest_search.get()=="поиск" else None)
    ent_guest_search.bind("<FocusOut>", lambda e: (ent_guest_search.insert(0, "поиск"), ent_guest_search.configure(foreground="#888")) if not ent_guest_search.get() else None)
    ent_guest_search.bind("<KeyRelease>", lambda e: refresh_main_checks())

    c_guest = tk.Canvas(lf_guest, bg="#121212", highlightthickness=0)
    sb_guest = ttk.Scrollbar(lf_guest, command=c_guest.yview)
    c_guest.configure(yscrollcommand=sb_guest.set)
    c_guest.pack(side="left", fill="both", expand=True); sb_guest.pack(side="right", fill="y")
    global guest_group
    guest_group = ttk.Frame(c_guest); c_guest.create_window((0,0), window=guest_group, anchor="nw")
    guest_group.bind("<Configure>", lambda e: c_guest.configure(scrollregion=c_guest.bbox("all")))
    setup_scroll_canvas(c_guest, guest_group)

    bottom_frame = ttk.Frame(parent, padding=15); bottom_frame.pack(fill="both")
    btn_area = ttk.Frame(bottom_frame); btn_area.pack(fill="x", pady=5)
     
    global smart_btn, load_btn
    smart_btn = ttk.Button(btn_area, text="📂 СТАРТ ПО БАЗЕ (Smart)", command=lambda: start_process("smart"), style="Green.TButton")
    smart_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
    load_btn = tk.Button(btn_area, text="📂 ВЫГРУЗИТЬ ПРОБИТУЮ БАЗУ", command=lambda: start_process("saved"), bg="#FFD700", fg="black", bd=0, font=("Segoe UI", 9, "bold"), cursor="hand2")
    load_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=8)
    ttk.Button(btn_area, text="🛑 СТОП", command=stop_process, style="Red.TButton").pack(side="left", padx=(5, 0), fill="x", ipadx=20, ipady=8)
    
    lf_log = ttk.LabelFrame(bottom_frame, text=" Лог событий ", padding=5); lf_log.pack(fill="x", pady=(10, 0))
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

def create_databases_tab(parent, custom_path=None):
    DB_FOLDER = custom_path if custom_path else "прописанные базы"
    if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER)
    paned = ttk.PanedWindow(parent, orient="horizontal"); paned.pack(fill="both", expand=True, padx=10, pady=10)
    frame_list = ttk.Frame(paned); paned.add(frame_list, weight=1) 
    list_header = ttk.Frame(frame_list); list_header.pack(fill="x", pady=(0, 5))
    ttk.Label(list_header, text=f"📂 {os.path.basename(DB_FOLDER)}", font=("Segoe UI", 11, "bold"), foreground="#9D00FF").pack(side="left")
    
    btn_refresh = ttk.Button(list_header, text="🔄", width=4); btn_refresh.pack(side="right")
    tree_files = ttk.Treeview(frame_list, columns=("filename", "size"), show="headings", selectmode="browse")
    tree_files.heading("filename", text="Имя файла"); tree_files.heading("size", text="Размер")
    tree_files.column("filename", width=180); tree_files.column("size", width=70, anchor="center")
    sb_files = ttk.Scrollbar(frame_list, orient="vertical", command=tree_files.yview); tree_files.configure(yscrollcommand=sb_files.set)
    tree_files.pack(side="left", fill="both", expand=True); sb_files.pack(side="right", fill="y")

    frame_editor = ttk.Frame(paned); paned.add(frame_editor, weight=3)
    toolbar = ttk.Frame(frame_editor); toolbar.pack(fill="x", pady=(0, 5))
    lbl_current_file = ttk.Label(toolbar, text="Выберите файл...", font=("Consolas", 10, "bold"), foreground="#888")
    lbl_current_file.pack(side="left", padx=5)
    btn_del = ttk.Button(toolbar, text="🗑 Удалить", style="Red.TButton", state='disabled'); btn_del.pack(side="right")
    btn_save = ttk.Button(toolbar, text="💾 Сохранить", style="Green.TButton", state='disabled'); btn_save.pack(side="right", padx=5)
    txt_content = scrolledtext.ScrolledText(frame_editor, font=("Consolas", 10), bg="#0F0F0F", fg="#E0E0E0", insertbackground="#9D00FF", borderwidth=0)
    txt_content.pack(fill="both", expand=True); txt_content.config(state='disabled') 

    current_file_path = [None] 

    def refresh_file_list():
        for item in tree_files.get_children(): tree_files.delete(item)
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
        if not os.path.exists(full_path): refresh_file_list(); return
        current_file_path[0] = full_path
        lbl_current_file.config(text=f"📄 {filename}", foreground="#00E676")
        try:
            with open(full_path, "r", encoding="utf-8") as f: content = f.read()
            txt_content.config(state='normal'); txt_content.delete("1.0", tk.END); txt_content.insert("1.0", content)
            btn_save.config(state='normal', command=lambda: [open(current_file_path[0], "w", encoding="utf-8").write(txt_content.get("1.0", tk.END).strip()), messagebox.showinfo("Сохранено", "Успешно!"), refresh_file_list()])
            btn_del.config(state='normal', command=lambda: [os.remove(current_file_path[0]) if messagebox.askyesno("Удаление", "Удалить файл?") else None, refresh_file_list(), txt_content.delete("1.0", tk.END)])
        except: pass

    btn_refresh.config(command=refresh_file_list)
    tree_files.bind("<<TreeviewSelect>>", on_file_select)
    refresh_file_list()

class SidebarApp:
    def __init__(self, root):
        self.root = root; self.current_frame = None; self.frames = {}; self.buttons = {}
        root.grid_columnconfigure(0, weight=0); root.grid_columnconfigure(1, weight=1); root.grid_rowconfigure(0, weight=1)
        self.sidebar = tk.Frame(root, bg="#0F0F0F", width=200); self.sidebar.grid(row=0, column=0, sticky="nsew"); self.sidebar.grid_propagate(False)
        tk.Label(self.sidebar, text="Dark\nGroup", bg="#0F0F0F", fg="#9D00FF", font=("Segoe UI Black", 16, "bold"), pady=20).pack(fill="x")
        self.content_area = tk.Frame(root, bg="#121212"); self.content_area.grid(row=0, column=1, sticky="nsew")

        self.frames["Главная"] = ttk.Frame(self.content_area)
        self.frames["Accounts"] = ttk.Frame(self.content_area)
        self.frames["Настройки запуска"] = ttk.Frame(self.content_area)
        self.frames["Databases"] = ttk.Frame(self.content_area)
        self.frames["SavedBases"] = ttk.Frame(self.content_area)
        self.frames["Заметки"] = ttk.Frame(self.content_area)

        create_dashboard_tab(self.frames["Главная"])
        create_accounts_tab(self.frames["Accounts"])
        create_databases_tab(self.frames["Databases"], custom_path="прописанные базы")
        create_databases_tab(self.frames["SavedBases"], custom_path=os.path.join("прописанные базы", "отмена и схроненные"))
        create_settings_tab(self.frames["Настройки запуска"])
        
        note_nb = ttk.Notebook(self.frames["Заметки"])
        note_nb.pack(fill="both", expand=True, padx=10, pady=10)
        saved_notes = load_notes()
        if not saved_notes: saved_notes = {"General": ""}
        for title, content in saved_notes.items(): create_note_tab(note_nb, title, content)
        fr_plus = ttk.Frame(note_nb); note_nb.add(fr_plus, text="  ➕  "); note_nb.bind("<<NotebookTabChanged>>", on_tab_changed)

        self._add_menu_btn("🏠 Главная", "Главная")
        self._add_menu_btn("👥 Accounts", "Accounts")
        self._add_menu_btn("⚙ Настройки запуска", "Настройки запуска")
        self._add_menu_btn("📂 Пробитые Базы", "Databases")
        self._add_menu_btn("💾 Сохраненные", "SavedBases")
        self._add_menu_btn("📝 Заметки", "Заметки")
        tk.Label(self.sidebar, text="v24.2 Pro", bg="#0F0F0F", fg="#555", font=("Consolas", 8)).pack(side="bottom", pady=10)
        self.show_screen("Главная")

    def _add_menu_btn(self, text, screen_name):
        btn = tk.Button(self.sidebar, text=text, font=("Segoe UI", 11), bg="#0F0F0F", fg="#888", activebackground="#1E1E1E", activeforeground="white", bd=0, cursor="hand2", anchor="w", padx=20, pady=12, command=lambda: self.show_screen(screen_name))
        btn.pack(fill="x", pady=2); self.buttons[screen_name] = btn

    def show_screen(self, screen_name):
        if self.current_frame: self.current_frame.pack_forget()
        for name, btn in self.buttons.items():
            if name == screen_name: btn.config(bg="#1E1E1E", fg="#9D00FF", font=("Segoe UI", 11, "bold"))
            else: btn.config(bg="#0F0F0F", fg="#888", font=("Segoe UI", 11))
        frame = self.frames[screen_name]; frame.pack(fill="both", expand=True); self.current_frame = frame

def refresh_main_checks():
    if 'sc_fr' in globals() and sc_fr:
        for w in sc_fr.winfo_children(): w.destroy()
    if 'guest_group' in globals() and guest_group:
        for w in guest_group.winfo_children(): w.destroy()
    check_vars.clear()
    
    raw_filter = ""
    clean_filter = ""
    if 'ent_guest_search' in globals() and ent_guest_search:
        val = ent_guest_search.get().strip()
        if val.lower() != "поиск": raw_filter = val.lower()
        clean_filter = raw_filter.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if 'guest_group' in globals() and guest_group:
        if not raw_filter or "без" in raw_filter:
            rb0 = ttk.Radiobutton(guest_group, text="🚫 Без дира / Пропустить шаг", variable=guest_account_index, value=-1)
            rb0.pack(anchor="w", pady=5)
    
    sessions = load_sessions()
    for i, s in enumerate(sessions):
        name = s.get('name', 'Без имени'); uname = s.get('username', ''); phone = s.get('phone', '..')
        if 'sc_fr' in globals() and sc_fr:
            var = tk.IntVar()
            cb = ttk.Checkbutton(sc_fr, text=f"{phone}  | {name}", variable=var)
            cb.pack(anchor="w", padx=5, pady=3)
            check_vars.append(var)
        
        if 'guest_group' in globals() and guest_group:
            if raw_filter:
                db_phone_clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").lower()
                if not (clean_filter in db_phone_clean or raw_filter in name.lower() or raw_filter in uname.lower()): continue
            rb = ttk.Radiobutton(guest_group, text=f"{phone} | {name} | {'@'+uname if uname else ''}", variable=guest_account_index, value=i)
            rb.pack(anchor="w", pady=3)

class ManualModeWindow(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ручной режим (Manual Mode)"); self.geometry("600x650")
        try: self.geometry(f"+{(self.winfo_screenwidth()-600)//2}+{(self.winfo_screenheight()-650)//2}")
        except: pass
        self.configure(bg="#121212"); self.transient(parent)
        self.old_log_widget = globals().get('log_widget')
        
        cfg = load_config()
        top_frame = ttk.Frame(self, padding=20); top_frame.pack(fill="x")
        tf_grid = ttk.LabelFrame(top_frame, text=" 📝 Параметры групп ", padding=15); tf_grid.pack(fill="x")
        ttk.Label(tf_grid, text="Название:").grid(row=0, column=0, sticky="w", padx=(0,10))
        self.ent_name = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10)); self.ent_name.grid(row=0, column=1, sticky="w")
        ttk.Label(tf_grid, text="Кол-во:").grid(row=0, column=2, sticky="w", padx=(10,10))
        self.ent_count = ttk.Entry(tf_grid, width=8, font=("Segoe UI", 10)); self.ent_count.insert(0, "5"); self.ent_count.grid(row=0, column=3, sticky="w")
        ttk.Label(tf_grid, text="Username Дира:").grid(row=1, column=0, sticky="w", padx=(0,10), pady=(15,0))
        self.ent_user = ttk.Entry(tf_grid, width=30, font=("Segoe UI", 10)); self.ent_user.grid(row=1, column=1, sticky="w", pady=(15,0))
        
        info_frame = ttk.Frame(self, padding=(20, 0)); info_frame.pack(fill="x")
        s_dir = "ДА" if cfg.get("manual_default_dir") == "1" else "НЕТ"
        s_cont = "ДА" if cfg.get("manual_default_contact") == "1" else "НЕТ"
        s_greet = "ДА" if cfg.get("manual_default_greet") == "1" else "НЕТ"
        tk.Label(info_frame, text=f"ℹ Настройки (из Settings):\n• Добавлять Директора: {s_dir}\n• Инвайтить Контакты: {s_cont}\n• Слать Приветствие: {s_greet}", bg="#1E1E1E", fg="#9D00FF", font=("Consolas", 9), justify="left", padx=10, pady=10).pack(fill="x")

        btn_frame = ttk.Frame(self, padding=20); btn_frame.pack(fill="x")
        self.btn_start = ttk.Button(btn_frame, text="🚀 ЗАПУСТИТЬ", command=self.start_manual, style="Green.TButton"); self.btn_start.pack(fill="x", ipady=8)
        
        log_frame = ttk.LabelFrame(self, text=" Лог событий ", padding=5); log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.manual_log = scrolledtext.ScrolledText(log_frame, height=10, state='disabled', font=("Consolas", 9), bg="#050505", fg="#CCCCCC", insertbackground="#9D00FF", borderwidth=0)
        self.manual_log.pack(fill="both", expand=True)
        for t, c in TAG_COLORS.items(): self.manual_log.tag_config(t, foreground=c)
        globals()['log_widget'] = self.manual_log
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        globals()['log_widget'] = self.old_log_widget; self.destroy()

    def start_manual(self):
        try:
            base_name = self.ent_name.get().strip()
            try: count_per_maker = int(self.ent_count.get())
            except: messagebox.showerror("Error", "Количество - число!"); return
            cfg = load_config(); manual_username_input = self.ent_user.get().strip()
            sessions_data = load_sessions(); selected_indices = [i for i, v in enumerate(check_vars) if v.get()]
            if not selected_indices: messagebox.showwarning("!", "Выберите мейкеров в ГЛАВНОМ окне!"); return

            guest_idx = guest_account_index.get(); guest_session = None
            if int(cfg.get("manual_default_dir", "1")):
                if guest_idx != -1 and guest_idx < len(sessions_data):
                    guest_session = sessions_data[guest_idx]
                    if guest_idx in selected_indices: selected_indices.remove(guest_idx)
                elif manual_username_input: pass 
                else: messagebox.showwarning("!", "Директор включен, но не выбран!"); return
            
            main_sessions = [sessions_data[i] for i in selected_indices]
            if not main_sessions: messagebox.showwarning("!", "Список мейкеров пуст!"); return

            delays = {
                "creation": float(cfg.get("delay_creation", 180)), "delay_contact": float(cfg.get("delay_contact", 20)),
                "cleanup": 10, "random": 1, "manual_add_director": int(cfg.get("manual_default_dir", "1")), 
                "manual_add_contacts": int(cfg.get("manual_default_contact", "0")) 
            }
            if not base_name and not int(cfg.get("use_random_words", "1")): base_name = "Group"
            names = generate_group_names(base_name, count_per_maker)
            self.btn_start.config(state='disabled', text="⏳ РАБОТАЕМ...")
            
            def real_start_manual():
                threading.Thread(target=run_thread, args=(main_sessions, guest_session, names, delays, manual_username_input, cfg.get("greeting_text", ""), int(cfg.get("manual_default_greet", "1")), None), daemon=True).start()
                self.btn_start.config(text="⏳ ЗАПУЩЕНО")
            run_safety_check(main_sessions, real_start_manual)
        except Exception as e: messagebox.showerror("Error", str(e)); self.btn_start.config(state='normal', text="🚀 ЗАПУСТИТЬ")

def open_manual_mode_window():
    if not check_vars: messagebox.showwarning("Внимание", "Сначала загрузите аккаунты на главной вкладке!"); return
    ManualModeWindow(root)

def build_modern_ui():
    global root, guest_account_index
    root = tk.Tk(); root.title("GroupMega"); root.geometry("1100x700")
    root.minsize(900, 600); root.grid_columnconfigure(1, weight=1); root.grid_rowconfigure(0, weight=1)
    guest_account_index = tk.IntVar(value=-1)
    bg, fg = setup_dark_theme(); root.configure(bg=bg)
    enable_hotkeys(root)
    SidebarApp(root)
    refresh_main_checks()
    root.mainloop()

if __name__ == "__main__":
    build_modern_ui()