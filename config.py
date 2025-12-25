import queue
import os
import threading

# === ВЕРСИЯ И КОНСТАНТЫ ===
CURRENT_VERSION = "25.0"
ADMIN_ID = "8351214331" # Твой ID (из worker.py)
BOT_TOKEN = "8529020816:AAEFZ07T3JlkM2vQbQxSyjTARtACEVb4eQU" # Твой токен
FIREBASE_DB_URL = "https://base-natsu-default-rtdb.firebaseio.com"

# === НАСТРОЙКИ ПУТЕЙ ===
# Эта переменная вызывала ошибку. Задаем значение по умолчанию.
SESSIONS_DIR = "sessions"

# === API TELEGRAM ===
# (Желательно заполнить, если они не придут из config.json)
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ (State) ===
# Они нужны, чтобы worker.py и main.py "видели" друг друга
current_maker_phone = None
current_director_phone = None
temp_group_name = "Group" # Для передачи имени группы

# Очередь для логов (чтобы потоки не конфликтовали с GUI)
log_queue = queue.Queue()

# Ссылки на элементы UI (заполняются в main.py)
root = None
log_widget = None
tree_dashboard = None 
ui_refs = {} # Словарь для кнопок и полей ввода (e_count, btn_start и т.д.)

# Флаги режимов
IS_SPY_MODE = False

# === ЦВЕТА ДЛЯ ЛОГОВ ===
TAG_COLORS = {
    "SUCCESS": "#00E676", # Зеленый
    "ERROR": "#FF5252",   # Красный
    "INFO": "#E0F7FA",    # Светло-голубой
    "WAIT": "#40C4FF",    # Голубой
    "WARN": "#FFAB40",    # Оранжевый
    "GUEST": "#EA80FC",   # Фиолетовый
    "DEBUG": "#90A4AE"    # Серый
}

# === ПРОКСИ ===
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

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ ===
stop_flag = threading.Event()
log_queue = queue.Queue()  # Очередь для логов (потокобезопасная)

REMOTE_PAUSE = False
IS_LOCKED_PAUSE = False
IS_SPY_MODE = False

# === ГЛОБАЛЬНОЕ СОСТОЯНИЕ GUI ===
# Эти переменные нужны для связи между UI и логикой
current_maker_phone = None
current_director_phone = None

# Ссылки на GUI элементы (будут инициализированы в main.py)
log_widget = None
tree_dashboard = None 
e_search = None