#!/usr/bin/env python3
"""
Quick test to verify app.py and bilol.py can communicate
"""
import requests
import time
import sys

def test_app_connection():
    """Test if app.py main API is responding"""
    try:
        response = requests.get('http://127.0.0.1:5000/api/orders/since?last_id=0', 
                              headers={'X-API-KEY': 'tfc_secret_key_2026_xyz_secure'},
                              timeout=5)
        if response.status_code == 200:
            print("✅ app.py (port 5000) is running and responding")
            return True
        else:
            print(f"❌ app.py returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to app.py on port 5000")
        print("   Make sure to run: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error connecting to app.py: {e}")
        return False

def test_admin_connection():
    """Test if bilol.py admin panel is responding"""
    try:
        response = requests.get('http://127.0.0.1:5001/', timeout=5)
        if response.status_code == 200:
            print("✅ bilol.py (port 5001) is running and responding")
            return True
        else:
            print(f"❌ bilol.py returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to bilol.py on port 5001")
        print("   Make sure to run: python bilol.py")
        return False
    except Exception as e:
        print(f"❌ Error connecting to bilol.py: {e}")
        return False

def main():
    print("=" * 60)
    print("TFC Project - Connection Test")
    print("=" * 60)
    print()
    
    print("Testing connections...")
    print()
    
    app_ok = test_app_connection()
    print()
    admin_ok = test_admin_connection()
    print()
    
    if app_ok and admin_ok:
        print("=" * 60)
        print("✅ SUCCESS! Both apps are running and connected")
        print("=" * 60)
        print()
        print("Access URLs:")
        print("  Main App:  http://127.0.0.1:5000")
        print("  Admin:     http://127.0.0.1:5001")
        print()
        return 0
    else:
        print("=" * 60)
        print("❌ CONNECTION FAILED")
        print("=" * 60)
        print()
        print("To fix this:")
        print("1. Open Terminal 1 and run: python app.py")
        print("2. Open Terminal 2 and run: python bilol.py")
        print("3. Wait for both to start (you'll see URLs printed)")
        print("4. Run this test again: python test_connection.py")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())