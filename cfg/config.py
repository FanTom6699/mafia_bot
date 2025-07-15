import os
from telebot import types
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('7891995522:AAG_i8k8MtCSXP9SltFhDxaBiS5EQI-rc3w')

INACTIVITY_TIMEOUT = 300

MIN_USER_IN_GAME = 5
MAX_USER_IN_GAME = 8
LOSE_MAFIA = 0

HOME_DIR = '/home/student/mafia_bot'
DB_NAME_SQLITE = f"{HOME_DIR}/database.db"
DB_NAME_JSON = f'{HOME_DIR}/data_base.json'


MARKUP_TG = types.InlineKeyboardMarkup()
MARKUP_TG.add(types.InlineKeyboardButton(text="🤖💬", url='https://t.me/online_mafia_game_bot'))
