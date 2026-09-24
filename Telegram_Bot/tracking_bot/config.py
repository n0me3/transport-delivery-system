import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ONEC_BASE_URL = os.getenv("ONEC_BASE_URL")
ONEC_USERNAME = os.getenv("ONEC_USERNAME")
ONEC_PASSWORD = os.getenv("ONEC_PASSWORD")
PROXY_URL = os.getenv("PROXY_URL")