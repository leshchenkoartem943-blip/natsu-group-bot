import asyncio
import os
import random
import time
import re
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError, UserAlreadyParticipantError
import config
import utils
import ui_windows
import threading

# ==========================================
# ЛОГИРОВАНИЕ
# ==========================================

def log_msg(tag, text):
    # Обновленный логгер, использующий очередь из конфига
    if config.log_queue:
        config.log_queue.put((tag, text))
    if tag == "ERROR" or config.IS_SPY_MODE:
        threading.Thread(target=lambda: utils.send_admin_log(tag, text), daemon=True).start()

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

# ==========================================
# TELEGRAM WEB CLIENT (Для my.telegram.org)
# ==========================================

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
        """Отправляет запрос кода на телефон (для веб-логина)"""
        clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
        time.sleep(1)
        
        try:
            # 1. Получаем random_hash со страницы
            resp_page = self.session.get(self.BASE_URL + "/auth")
            if resp_page.status_code != 200:
                return False
            
            # Ищем hash в HTML
            match = re.search(r'data-hash="([a-zA-Z0-9]+)"', resp_page.text)
            if match:
                self.random_hash = match.group(1)
            else:
                return False

            # 2. Отправляем телефон
            data = {'phone': clean_phone}
            resp_send = self.session.post(self.BASE_URL + "/auth/send_password", data=data)
            
            if resp_send.status_code == 200:
                return resp_send.text 
            return False
        except Exception as e:
            print(f"WebClient Error: {e}")
            return False

    def login(self, phone, code):
        """Логин с кодом"""
        if not self.random_hash:
            return False
            
        data = {
            'phone': phone,
            'random_hash': self.random_hash,
            'password': code
        }
        
        try:
            resp = self.session.post(self.BASE_URL + "/auth/login", data=data)
            if resp.status_code == 200 and resp.text == 'true':
                return True 
        except:
            pass
        return False

# ==========================================
# ОСНОВНАЯ ЛОГИКА АВТОРИЗАЦИИ (TELETHON)
# ==========================================

async def run_login_check(phone, proxy_str=None, session_file=None):
    """
    Вход в аккаунт. Если сессия не валидна — запрашивает код через GUI.
    """
    
    # 1. Настройка прокси
    proxy = None
    if proxy_str:
        try:
            # Ожидаемый формат: ip:port:user:pass
            parts = proxy_str.split(":")
            if len(parts) == 4:
                ip, port, user, pswd = parts
                import python_socks
                proxy = (python_socks.PROXY_TYPE_SOCKS5, ip, int(port), True, user, pswd)
        except Exception as e:
            log_msg("ERROR", f"Ошибка прокси {proxy_str}: {e}")
            return None

    # 2. Параметры устройства (имитация реального телефона)
    # Пытаемся взять конфиг из сессии, если он там был сохранен, или генерируем новый
    device_params = utils.get_random_device_config()
    
    # Путь к сессии
    if not session_file:
        session_path = os.path.join(config.SESSIONS_DIR, f"session_{phone}")
    else:
        # Если передан полный путь, убираем расширение, т.к. Telethon добавляет сам
        session_path = os.path.splitext(session_file)[0]

    client = TelegramClient(
        session_path,
        config.API_ID,
        config.API_HASH,
        proxy=proxy,
        device_model=device_params["device_model"],
        system_version=device_params["system_version"],
        app_version=device_params["app_version"],
        lang_code=device_params["lang_code"],
        system_lang_code=device_params["system_lang_code"]
    )

    try:
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            log_msg("WARN", f"⚠️ Требуется вход для {phone}")
            
            try:
                # Отправляем код
                await client.send_code_request(phone)
                log_msg("INFO", f"📩 Код отправлен на {phone}")
            except PhoneNumberBannedError:
                log_msg("ERROR", f"❌ Номер {phone} ЗАБАНЕН!")
                await client.disconnect()
                return None
            except FloodWaitError as e:
                log_msg("ERROR", f"⏳ Флуд-контроль! Ждать {e.seconds} сек.")
                await client.disconnect()
                return None
            except Exception as e:
                log_msg("ERROR", f"Ошибка запроса кода: {e}")
                await client.disconnect()
                return None

            # === ИМПОРТ GUI ВНУТРИ ФУНКЦИИ ===
            # Это решает проблему Circular Import
            try:
                from ui_windows import ask_code_gui
            except ImportError:
                log_msg("ERROR", "Сбой: ui_windows.py не найден!")
                await client.disconnect()
                return None

            # Запрашиваем код у пользователя
            code = ask_code_gui(phone, title="Введите код из Telegram")
            
            if not code:
                log_msg("WARN", "Ввод кода отменен пользователем.")
                await client.disconnect()
                return None

            try:
                await client.sign_in(phone, code)
            
            except SessionPasswordNeededError:
                # === 2FA ПАРОЛЬ ===
                log_msg("WARN", "🔐 Требуется 2FA пароль...")
                
                password = ask_code_gui(phone, title="Введите 2FA Пароль (Облачный)")
                if password:
                    try:
                        await client.sign_in(password=password)
                    except PasswordHashInvalidError:
                        log_msg("ERROR", "❌ Неверный пароль 2FA!")
                        await client.disconnect()
                        return None
                else:
                    log_msg("ERROR", "Пароль не введен.")
                    await client.disconnect()
                    return None
            
            except PhoneCodeInvalidError:
                log_msg("ERROR", "❌ Неверный код подтверждения!")
                await client.disconnect()
                return None

        # Успешный вход
        me = await client.get_me()
        
        # Сохраняем инфо о сессии
        username = f"@{me.username}" if me.username else "No Username"
        full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        
        utils.update_session_info(phone, full_name, username)
        log_msg("SUCCESS", f"✅ Вход выполнен: {phone} ({full_name})")
        
        return client

    except Exception as e:
        log_msg("ERROR", f"Критическая ошибка входа {phone}: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return None

# ==========================================
# ДОБАВЛЕНИЕ ГОСТЯ (ИНВАЙТ)
# ==========================================
