@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

cd /d C:\Users\samsung\Desktop\VigiFroid_App
if not exist logs mkdir logs

C:\Users\samsung\Desktop\VigiFroid_App\venv\Scripts\python.exe -m flask --app wsgi.py autoexport --lang fr >> logs\autoexport_task.log 2>&1
