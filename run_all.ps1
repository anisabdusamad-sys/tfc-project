cd "c:\Users\Anis\Desktop\qwer"
Write-Host "Starting TFC Admin and Menu..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "python bilol.py"
python app.pyz
& "C:\Users\Anis\AppData\Local\Android\Sdk\platform-tools\adb.exe" connect 127.0.0.1:5555
flutter run -d 127.0.0.1:5555