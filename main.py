import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import time
import sys
import asyncio
import os
import random
from datetime import datetime

# Импорты Telethon (как в твоем файле)
from telethon import TelegramClient, functions, types
from telethon.tl.types import ChatAdminRights, InputUserSelf, InputPhoneContact
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError

# Модули проекта
import config
import utils
import styles
import tg_core
from ui_windows import MatchReviewWindow, ask_code_gui

# ==========================================
# 1. ЛОГИРОВАНИЕ (Адаптер)
# ==========================================
def log(tag, text):
    """Отправляет лог в очередь GUI"""
    config.log_queue.put((tag, text))

# ==========================================
# 2. ОСНОВНАЯ ЛОГИКА (WORKER ИЗ ЧЕК2.TXT)
# ==========================================

async def async_worker_logic(mode, maker_phone, director_phone, count, delay_cr, delay_cnt, specific_contacts=None):
    """
    Та самая функция, которая была внутри start_process в твоем файле.
    """
    client_maker = None
    client_director = None
    
    try:
        log("INFO", f"🚀 ЗАПУСК: {mode.upper()} | Maker: {maker_phone}")
        
        # 1. АВТОРИЗАЦИЯ MAKER
        client_maker = await tg_core.run_login_check(maker_phone)
        if not client_maker:
            log("ERROR", "❌ Maker не авторизован. Стоп.")
            return

        # 2. АВТОРИЗАЦИЯ DIRECTOR (Если есть)
        director_entity = None
        if director_phone and director_phone != maker_phone:
            log("INFO", f"🔑 Подключение Директора: {director_phone}")
            client_director = await tg_core.run_login_check(director_phone)
            
            if client_director:
                # Получаем entity директора для мейкера
                me_dir = await client_director.get_me()
                try:
                    # Попытка найти директора по username
                    if me_dir.username:
                        director_entity = await client_maker.get_input_entity(me_dir.username)
                    else:
                        # Если нет юзернейма, это сложнее, но попробуем по телефону (если он в контактах)
                        # В твоем коде был упор на username или добавление в контакты
                        director_entity = await client_maker.get_input_entity(me_dir.id)
                except Exception as e:
                    log("WARN", f"⚠️ Maker не видит Director'а (нужен контакт или username): {e}")

        # 3. ЦИКЛ СОЗДАНИЯ
        loop_range = count
        if mode == "contacts" and specific_contacts:
            loop_range = len(specific_contacts)

        for i in range(loop_range):
            if config.stop_event.is_set():
                log("WARN", "🛑 Остановка пользователем.")
                break

            # Формирование имени (как в твоем коде: 01, 02...)
            num_str = f"{i+1:02d}"
            
            # Определение названия и пользователей
            users_to_add = []
            
            if mode == "contacts" and specific_contacts:
                contact = specific_contacts[i]
                phone = contact['phone']
                name = contact['name']
                
                # Имя группы: "GroupName 01"
                group_title = f"{config.temp_group_name} {num_str}"
                
                # Попытка добавить контакт (нужно найти entity)
                try:
                    # В твоем коде был ImportContactsRequest или поиск
                    # Пробуем найти entity
                    user_ent = await client_maker.get_input_entity(phone)
                    users_to_add.append(user_ent)
                    log("INFO", f"   👤 Найден контакт для добавления: {name}")
                except:
                    log("WARN", f"   ⚠️ Не удалось найти контакт {phone} (возможно, нет в адресной книге)")
            else:
                # Режим SMART
                group_title = f"Group {num_str}"
            
            # Добавляем директора сразу при создании (если он есть)
            if director_entity:
                users_to_add.append(director_entity)

            log("INFO", f"--- [{i+1}/{loop_range}] Создаем: '{group_title}' ---")

            try:
                # === ГЛАВНЫЙ ЗАПРОС ИЗ ТВОЕГО ФАЙЛА ===
                # CreateChatRequest создает обычную группу (не супергруппу)
                # users должен содержать список InputUser
                
                # Если список пуст, Telethon требует хотя бы одного юзера или создает с собой
                # Но для CreateChatRequest нужен второй участник
                if not users_to_add:
                    # Если никого нет, создаем с собой (Telethon может ругаться, но попробуем)
                    # Обычно добавляют бота или второй акк
                    if director_entity:
                         users_to_add = [director_entity]
                    else:
                        # Если совсем никого, пропускаем (Telegram не дает создать группу одному)
                        log("WARN", "⚠️ Нет участников для создания группы (нужен Director или Контакт)")
                        continue

                result = await client_maker(functions.messages.CreateChatRequest(
                    users=users_to_add,
                    title=group_title
                ))
                
                # Получаем ID созданного чата
                # result.updates или result.chats
                created_chat = result.chats[0]
                log("SUCCESS", f"✅ Группа создана ID: {created_chat.id}")

                # Пауза (random_delay)
                time.sleep(random.uniform(1.0, 2.0))

                # === ЛОГИКА ЯКОРЯ (ПРАВА) ===
                if director_entity:
                    log("INFO", "   👑 Выдача прав Директору...")
                    
                    # Права (как в твоем коде)
                    rights = ChatAdminRights(
                        change_info=True,
                        post_messages=True,
                        edit_messages=True,
                        delete_messages=True,
                        ban_users=True,
                        invite_users=True,
                        pin_messages=True,
                        add_admins=True,
                        anonymous=False,
                        manage_call=True,
                        other=True
                    )
                    
                    await client_maker(functions.messages.EditChatAdminRequest(
                        chat_id=created_chat.id,
                        user_id=director_entity,
                        is_admin=True,
                        rights=rights
                    ))
                    log("SUCCESS", "      ✅ Права переданы!")
                    
                    # Опционально: выход мейкера (если было в коде)
                    # await client_maker(functions.messages.DeleteChatUserRequest(chat_id=created_chat.id, user_id=InputUserSelf()))

            except FloodWaitError as e:
                log("WAIT", f"⏳ Флуд! Ждем {e.seconds} сек...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log("ERROR", f"❌ Ошибка создания группы: {e}")

            # Задержка между группами
            total_delay = int(delay_cr) + random.randint(0, 5)
            log("WAIT", f"💤 Ожидание {total_delay} сек...")
            
            # Цикл ожидания с проверкой кнопки Стоп
            for _ in range(total_delay):
                if config.stop_event.is_set(): return
                await asyncio.sleep(1)

    except Exception as e:
        log("ERROR", f"CRITICAL WORKER ERROR: {e}")
    finally:
        if client_maker: await client_maker.disconnect()
        if client_director: await client_director.disconnect()
        log("INFO", "🏁 Процесс завершен")
        restore_ui()

# ==========================================
# 3. ФУНКЦИИ ЗАПУСКА (CONTROLLERS)
# ==========================================

def run_async_thread(coro):
    """Запускает асинхронную функцию в отдельном потоке"""
    def target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    threading.Thread(target=target, daemon=True).start()

def start_smart():
    """Кнопка START (Smart Mode)"""
    maker = config.current_maker_phone
    if not maker:
        messagebox.showwarning("!", "Не выбран Maker (зеленый)!")
        return

    # Чтение GUI
    try:
        cnt = int(config.ui_refs['e_count'].get())
        d_cr = int(config.ui_refs['e_delay'].get())
    except:
        cnt = 5
        d_cr = 180

    director = config.current_director_phone
    
    disable_ui()
    config.stop_event.clear()
    
    run_async_thread(async_worker_logic(
        mode="smart",
        maker_phone=maker,
        director_phone=director,
        count=cnt,
        delay_cr=d_cr,
        delay_cnt=10
    ))

def start_contacts():
    """Кнопка CONTACTS (Сначала парсинг, потом создание)"""
    maker = config.current_maker_phone
    if not maker:
        messagebox.showwarning("!", "Не выбран Maker!")
        return
        
    disable_ui()
    
    # 1. Сначала парсим контакты (в потоке)
    def fetch_contacts():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            log("INFO", "📂 Скачиваем контакты...")
            client = loop.run_until_complete(tg_core.run_login_check(maker))
            if not client: 
                restore_ui()
                return
            
            # GetContactsRequest
            contacts = loop.run_until_complete(client(functions.contacts.GetContactsRequest(hash=0)))
            loop.run_until_complete(client.disconnect())
            
            # Формируем список
            parsed_list = []
            for u in contacts.users:
                if u.phone:
                    name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                    parsed_list.append({"phone": u.phone, "name": name, "id": u.id})
            
            # Возвращаемся в GUI для показа окна
            config.root.after(0, lambda: show_review(parsed_list))
            
        except Exception as e:
            log("ERROR", f"Ошибка контактов: {e}")
            restore_ui()
        finally:
            loop.close()
            
    threading.Thread(target=fetch_contacts, daemon=True).start()

def show_review(contacts):
    """Показывает окно MatchReviewWindow (из ui_windows.py)"""
    win = MatchReviewWindow(config.root, contacts)
    
    if win.result_data:
        # User pressed Start inside the window
        data = win.result_data # {'group_name': '...', 'contacts': [...]}
        
        config.temp_group_name = data['group_name']
        selected = data['contacts']
        
        try:
            d_cr = int(config.ui_refs['e_delay'].get())
        except: d_cr = 180
        
        config.stop_event.clear()
        
        run_async_thread(async_worker_logic(
            mode="contacts",
            maker_phone=config.current_maker_phone,
            director_phone=config.current_director_phone,
            count=len(selected),
            delay_cr=d_cr,
            delay_cnt=10,
            specific_contacts=selected
        ))
    else:
        restore_ui()

def stop_process():
    log("WARN", "⛔ Нажата кнопка СТОП")
    config.stop_event.set()

# ==========================================
# 4. GUI УПРАВЛЕНИЕ
# ==========================================

def disable_ui():
    if 'btn_start' in config.ui_refs: config.ui_refs['btn_start'].config(state="disabled")
    if 'btn_cont' in config.ui_refs: config.ui_refs['btn_cont'].config(state="disabled")

def restore_ui():
    if config.root:
        config.root.after(0, _restore_tk)

def _restore_tk():
    if 'btn_start' in config.ui_refs: config.ui_refs['btn_start'].config(state="normal")
    if 'btn_cont' in config.ui_refs: config.ui_refs['btn_cont'].config(state="normal")

# ==========================================
# 5. ИНТЕРФЕЙС (DASHBOARD)
# ==========================================

def create_dashboard_tab(parent):
    # Разметка PanedWindow
    paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg="black", sashwidth=4)
    paned.pack(fill="both", expand=True)

    # --- ЛЕВАЯ ПАНЕЛЬ (ТАБЛИЦА) ---
    left_frame = tk.Frame(paned, bg="black")
    paned.add(left_frame, minsize=350)

    # Treeview
    cols = ("phone", "name", "role")
    tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
    tree.heading("phone", text="Телефон")
    tree.heading("name", text="Имя")
    tree.heading("role", text="Роль")
    tree.column("phone", width=120)
    tree.column("name", width=120)
    tree.column("role", width=80)
    
    sb = ttk.Scrollbar(left_frame, orient="vertical", command=tree.yview)
    tree.configure(yscroll=sb.set)
    tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    sb.pack(side="right", fill="y", pady=5)
    
    config.tree_dashboard = tree # Сохраняем в конфиг

    # Клик по таблице (ЛКМ - Мейкер, ПКМ - Директор)
    def on_click(event):
        item = tree.identify_row(event.y)
        if not item: return
        vals = tree.item(item)['values']
        phone = str(vals[0])
        
        # ЛКМ = Выбор Создателя
        if config.current_maker_phone == phone:
            config.current_maker_phone = None
        else:
            config.current_maker_phone = phone
        refresh_table()

    def on_rclick(event):
        item = tree.identify_row(event.y)
        if not item: return
        vals = tree.item(item)['values']
        phone = str(vals[0])
        
        # ПКМ = Выбор Директора
        if config.current_director_phone == phone:
            config.current_director_phone = None
        else:
            config.current_director_phone = phone
        refresh_table()

    tree.bind("<ButtonRelease-1>", on_click)
    tree.bind("<ButtonRelease-3>", on_rclick)

    # --- ПРАВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
    right_frame = tk.Frame(paned, bg="black")
    paned.add(right_frame, minsize=250)
    
    # Настройки
    lbl_set = tk.LabelFrame(right_frame, text="Настройки", bg="black", fg="#00E676")
    lbl_set.pack(fill="x", padx=10, pady=10)
    
    tk.Label(lbl_set, text="Кол-во групп:", bg="black", fg="white").grid(row=0, column=0, pady=5)
    e_cnt = tk.Entry(lbl_set, bg="#222", fg="white", width=8)
    e_cnt.insert(0, "5")
    e_cnt.grid(row=0, column=1, pady=5)
    config.ui_refs['e_count'] = e_cnt
    
    tk.Label(lbl_set, text="Пауза (сек):", bg="black", fg="white").grid(row=1, column=0, pady=5)
    e_del = tk.Entry(lbl_set, bg="#222", fg="white", width=8)
    e_del.insert(0, "180")
    e_del.grid(row=1, column=1, pady=5)
    config.ui_refs['e_delay'] = e_del
    
    # Кнопки
    btn_box = tk.Frame(right_frame, bg="black")
    btn_box.pack(fill="x", padx=10, pady=10)
    
    b_smart = tk.Button(btn_box, text="START (Smart)", command=start_smart, 
                        bg="#00E676", fg="black", font=("Segoe UI", 10, "bold"))
    b_smart.pack(fill="x", pady=5)
    config.ui_refs['btn_start'] = b_smart
    
    b_cont = tk.Button(btn_box, text="ПО КОНТАКТАМ", command=start_contacts,
                       bg="#2979FF", fg="white", font=("Segoe UI", 10, "bold"))
    b_cont.pack(fill="x", pady=5)
    config.ui_refs['btn_cont'] = b_cont
    
    b_stop = tk.Button(btn_box, text="ОСТАНОВИТЬ", command=stop_process,
                       bg="#D50000", fg="white", font=("Segoe UI", 10, "bold"))
    b_stop.pack(fill="x", pady=15)
    
    # Лог
    log_wdg = scrolledtext.ScrolledText(right_frame, bg="#111", fg="#00E676", height=15)
    log_wdg.pack(fill="both", expand=True, padx=5, pady=5)
    config.log_widget = log_wdg

# ==========================================
# 6. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def refresh_table():
    """Перерисовка таблицы с цветами"""
    t = config.tree_dashboard
    if not t: return
    
    # Очистка
    for x in t.get_children(): t.delete(x)
    
    sessions = utils.load_sessions()
    for s in sessions:
        ph = s.get('phone')
        nm = s.get('name', 'NoName')
        role = ""
        tags = []
        
        if ph == config.current_maker_phone:
            role = "MAKER"
            tags.append("maker")
        elif ph == config.current_director_phone:
            role = "ANCHOR"
            tags.append("anchor")
            
        t.insert("", "end", values=(ph, nm, role), tags=tags)
        
    t.tag_configure("maker", background="#2E7D32", foreground="white")
    t.tag_configure("anchor", background="#C62828", foreground="white")

def init_sessions():
    """Загрузка файлов сессий из папки"""
    if not os.path.exists(config.SESSIONS_DIR):
        os.makedirs(config.SESSIONS_DIR)
        
    files = [f for f in os.listdir(config.SESSIONS_DIR) if f.endswith(".session")]
    current = utils.load_sessions()
    known = [x['phone'] for x in current]
    
    updated = False
    for f in files:
        # session_7999.session -> 7999
        p = f.replace("session_", "").replace(".session", "")
        if p not in known:
            current.append({"phone": p, "name": "New"})
            updated = True
            
    if updated: utils.save_sessions(current)
    refresh_table()

def log_loop():
    """Вывод логов из очереди в GUI"""
    while not config.log_queue.empty():
        try:
            tag, text = config.log_queue.get_nowait()
            if config.log_widget:
                tm = time.strftime("[%H:%M:%S]")
                config.log_widget.insert(tk.END, f"{tm} {tag}: {text}\n")
                config.log_widget.see(tk.END)
        except: break
    if config.root: config.root.after(100, log_loop)

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    # Загружаем конфиг
    utils.load_config()
    
    root = tk.Tk()
    root.title("Natsu Manager v25.0")
    root.geometry("1000x700")
    root.configure(bg="black")
    config.root = root
    
    try:
        styles.setup_new_year_theme()
    except: pass
    
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    
    f_dash = tk.Frame(nb, bg="black")
    nb.add(f_dash, text="Dashboard")
    create_dashboard_tab(f_dash)
    
    init_sessions()
    log_loop()
    
    root.mainloop()