import subprocess
import sys
import time
import webbrowser
import socket

def get_local_ip():
    """Функсия барои ёфтани суроғаи IP-и компютер дар шабакаи Wi-Fi"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Мо ба сервери Google "пайваст" мешавем, то IP-и худро бинем
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()

def run_tfc():
    print("--- TFC System Starting ---")
    
    # Sar kardani Admin Panel (bilol.py)
    admin = subprocess.Popen([sys.executable, "bilol.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    # Sar kardani Menu Website (app.py)
    menu = subprocess.Popen([sys.executable, "app.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    admin_port = 5001
    menu_port = 5000
    local_ip = get_local_ip()

    admin_url_localhost = f"http://127.0.0.1:{admin_port}"
    menu_url_localhost = f"http://127.0.0.1:{menu_port}"
    admin_url_phone = f"http://{local_ip}:{admin_port}"
    menu_url_phone = f"http://{local_ip}:{menu_port}"

    print(f"Admin Panel (на этом ПК): {admin_url_localhost}")
    print(f"Customer Menu (на этом ПК): {menu_url_localhost}")
    print(f"------------------------------------------------------")
    print(f"АДРЕС ДЛЯ ТЕЛЕФОНА (Панель админ): {admin_url_phone}")
    print(f"АДРЕС ДЛЯ ТЕЛЕФОНА (Меню): {menu_url_phone}")
    print(f"Если страница не открывается:")
    print(f"1. Временно отключите Windows Firewall.")
    print(f"2. Установите тип сети Wi-Fi в Windows на 'Private'.")
    print(f"------------------------------------------------------")

    # Hila: Avtomatiki kushodani brauzer bad az 2 soniya (to ki serverho sar shavand)
    time.sleep(0.1)
    webbrowser.open(menu_url_localhost)
    webbrowser.open(admin_url_localhost)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping TFC Servers...")
        admin.terminate()
        menu.terminate()

if __name__ == "__main__":
    run_tfc()