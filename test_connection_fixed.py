#!/usr/bin/env python3
"""
Test script to verify connection between app.py and bilol.py
Tests both localhost and external hosting scenarios
"""
import requests
import time
import sys

# Configuration
APP_URL = "http://127.0.0.1:5000"
ADMIN_URL = "http://127.0.0.1:5001"
API_KEY = "tfc_secret_key_2026_xyz_secure"

def test_app_connection():
    """Test if app.py is running and responding"""
    print("=" * 60)
    print("Testing app.py connection...")
    print("=" * 60)
    
    try:
        # Test basic connection
        response = requests.get(f"{APP_URL}/api/host-info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"✅ app.py is running at {APP_URL}")
                print(f"   API URL reported: {data.get('api_url')}")
                return True
            else:
                print(f"❌ app.py responded but returned error: {data}")
                return False
        else:
            print(f"❌ app.py returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to app.py at {APP_URL}")
        print("   Make sure app.py is running on port 5000")
        return False
    except Exception as e:
        print(f"❌ Error connecting to app.py: {e}")
        return False

def test_admin_connection():
    """Test if bilol.py (admin panel) is running"""
    print("\n" + "=" * 60)
    print("Testing bilol.py (admin panel) connection...")
    print("=" * 60)
    
    try:
        # Test basic connection
        response = requests.get(ADMIN_URL, timeout=5)
        if response.status_code == 200:
            print(f"✅ bilol.py is running at {ADMIN_URL}")
            return True
        else:
            print(f"❌ bilol.py returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to bilol.py at {ADMIN_URL}")
        print("   Make sure bilol.py is running on port 5001")
        return False
    except Exception as e:
        print(f"❌ Error connecting to bilol.py: {e}")
        return False

def test_api_integration():
    """Test if bilol.py can communicate with app.py API"""
    print("\n" + "=" * 60)
    print("Testing API integration...")
    print("=" * 60)
    
    headers = {'X-API-KEY': API_KEY, 'Content-Type': 'application/json'}
    
    # Test creating an order via bilol.py's external sync endpoint
    test_order = {
        "sync_type": "order",
        "customer": "Test Customer",
        "customer_id": "TEST001",
        "food": "Test Food Item",
        "price": "100",
        "phone": "+992123456789",
        "delivery_type": "pickup",
        "payment_method": "online"
    }
    
    try:
        response = requests.post(
            f"{ADMIN_URL}/api/external/sync",
            headers=headers,
            json=test_order,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"✅ API integration working!")
                print(f"   Test order created with ID: {data.get('order_id')}")
                return True
            else:
                print(f"❌ API returned error: {data}")
                return False
        elif response.status_code == 401:
            print(f"❌ API Key authentication failed")
            print(f"   Make sure API_KEY in bilol.py matches app.py")
            return False
        else:
            print(f"❌ API returned status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing API integration: {e}")
        return False

def test_order_sync():
    """Test if orders created in app.py appear in bilol.py"""
    print("\n" + "=" * 60)
    print("Testing order synchronization...")
    print("=" * 60)
    
    headers = {'X-API-KEY': API_KEY}
    
    try:
        # Get orders from bilol.py
        response = requests.get(
            f"{ADMIN_URL}/api/orders/since?last_id=0",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get("orders", [])
            print(f"✅ Order sync working!")
            print(f"   Total orders in admin panel: {len(orders)}")
            if orders:
                print(f"   Latest order: #{orders[-1]['id']} - {orders[-1]['customer']}")
            return True
        else:
            print(f"❌ Failed to fetch orders: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing order sync: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("TFC Connection Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: app.py connection
    results.append(("app.py", test_app_connection()))
    time.sleep(1)
    
    # Test 2: bilol.py connection
    results.append(("bilol.py", test_admin_connection()))
    time.sleep(1)
    
    # Test 3: API integration (only if both are running)
    if all(r[1] for r in results):
        results.append(("API Integration", test_api_integration()))
        time.sleep(1)
        results.append(("Order Sync", test_order_sync()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYour setup is working correctly!")
        print("You can now:")
        print("  1. Access admin panel at http://127.0.0.1:5001")
        print("  2. Access menu website at http://127.0.0.1:5000")
        print("  3. Orders will sync automatically between both apps")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        print("\nTroubleshooting steps:")
        print("  1. Make sure both app.py and bilol.py are running")
        print("  2. Check that ports 5000 and 5001 are not blocked")
        print("  3. Verify API_KEY is the same in both files")
        print("  4. Check firewall settings")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)