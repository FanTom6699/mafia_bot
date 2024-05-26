import os
from telebot import types
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

INACTIVITY_TIMEOUT = 300

MIN_USER_IN_GAME = 5
MAX_USER_IN_GAME = 8
LOSE_MAFIA = 0

DB_NAME_SQLITE = "database.db"
DB_NAME_JSON = 'data_base.json'


MARKUP_TG = types.InlineKeyboardMarkup()
MARKUP_TG.add(types.InlineKeyboardButton(text="🤖💬", url='https://t.me/online_mafia_game_bot'))
