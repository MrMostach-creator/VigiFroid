VigiFroid Project
Description
VigiFroid is a Flask-based application for monitoring the expiration dates of products (Loctite, Graisse, Vernelec) stored in a refrigerator, with support for multiple languages (French 🇫🇷, English 🇺🇸, Arabic 🇲🇦) and advanced features like email alerts, backups, and logs.
Prerequisites

Python 3.x
Visual Studio Code (recommended)
SQLite (download from [sqlite.org]([invalid url, do not cite]))

Installation

Clone or Download the Repository

Download the VigiFroid folder and extract it to C:\Users\samsung\Desktop\VigiFroid_App.


Install Dependencies

Open a terminal in the VigiFroid_App folder.
Run: pip install -r requirements.txt


Install SQLite

Download SQLite tools from [sqlite.org]([invalid url, do not cite]).
Extract to C:\sqlite and add to system PATH.


Initialize the Database

Run: sqlite3 database.db < schema.sql


Compile Translations

Run: pybabel compile -d translations



Add Product Images

Place loctite.png, graisse.png, vernelec.png in static/images/.


Configure Email

Update send_email_alert in app.py with your Gmail address and app password.


Run the Application

Run: python app.py
Open `[invalid url, do not cite] in your browser.


Login

Username: admin
Password: admin



Usage

Switch languages using flags (🇫🇷, 🇺🇸, 🇲🇦).
Admins can add, edit, or delete products.
Backup the database or view logs.
Alerts (visual,
