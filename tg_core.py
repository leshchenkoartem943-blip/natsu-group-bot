import asyncio
import os
import random
import re
import time
import requests
from telethon import TelegramClient, functions, types
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError,
    UserPrivacyRestrictedError, PeerFloodError, UserAlreadyParticipantError,
    PhoneNumberBannedError, PasswordHashInvalidError
)
import config
import utils

# ==========================================
# ЛОГИРОВАНИЕ
# ==========================================

def log_msg(tag, text):
    """Отправляет лог в очередь для отображения в GUI"""
    if config.log_queue:
        config.log_queue.put((tag, text))
    else:
        print(f"[{tag}] {text}")

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

async def _add_guest(client, chat_entity, user_entity, username_str=None):
    """
    Добавляет пользователя в чат.
    """
    try:
        target_name = username_str if username_str else getattr(user_entity, 'username', 'Guest')
        
        input_user = None
        
        # 1. Ищем по строке юзернейма
        if username_str:
            try:
                input_user = await client.get_input_entity(username_str)
            except: 
                pass

        # 2. Ищем по сущности (если есть ID и хэш)
        if not input_user and user_entity:
            try:
                input_user = await client.get_input_entity(user_entity)
            except: 
                pass

        if not input_user:
            return False

        # Определяем тип чата (Мегагруппа/Канал или обычный чат)
        from telethon.tl.types import Channel
        is_broadcast = isinstance(chat_entity, Channel) or getattr(chat_entity, 'megagroup', False)
        
        try:
            if is_broadcast:
                await client(functions.channels.InviteToChannelRequest(
                    channel=chat_entity,
                    users=[input_user]
                ))
            else:
                await client(functions.messages.AddChatUserRequest(
                    chat_id=chat_entity.id,
                    user_id=input_user,
                    fwd_limit=0
                ))
            return True
            
        except UserPrivacyRestrictedError:
            # Пользователь запретил инвайт в настройках приватности
            return False
        except UserAlreadyParticipantError:
            return True
        except PeerFloodError:
            log_msg("WARN", "⏳ Слишком много инвайтов (PeerFlood)!")
            return False
        except Exception as e:
            # log_msg("ERROR", f"Ошибка инвайта: {e}")
            return False

    except Exception as e:
        log_msg("ERROR", f"Ошибка в _add_guest: {e}")
        return False