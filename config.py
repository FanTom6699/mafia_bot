import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('TOKEN')

INACTIVITY_TIMEOUT = timedelta(minutes=5)

MIN_USER_IN_GAME = 5
MAX_USER_IN_GAME = 8
LOSE_MAFIA = 0

DB_NAME_SQLITE = "database.db"
DB_NAME_JSON = 'data_base.json'
