import os
from telebot import types
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

INACTIVITY_TIMEOUT = 300

MIN_USER_IN_GAME = 5
MAX_USER_IN_GAME = 8
LOSE_MAFIA = 0

HOME_DIR = os.path.dirname(os.path.abspath(__file__))  # относительный путь
DB_NAME_SQLITE = os.path.join(HOME_DIR, "../database.db")
DB_NAME_JSON = os.path.join(HOME_DIR, "../data_base.json")

MARKUP_TG = types.InlineKeyboardMarkup()
MARKUP_TG.add(types.InlineKeyboardButton(text="🤖💬", url='https://t.me/TopMafiozi_bot'))
