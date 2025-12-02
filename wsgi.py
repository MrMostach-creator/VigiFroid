# wsgi.py
import os
from dotenv import load_dotenv

# حمّل .env
load_dotenv()

from vigi import create_app

app = create_app("config.Config")

if __name__ == "__main__":
    app.run()
