@echo off
cd /d "c:\Users\Anis\Desktop\qwer"
echo TFC System Starting...
start python app.py
timeout /t 3
start http://127.0.0.1:5000
start http://127.0.0.1:5000/admin