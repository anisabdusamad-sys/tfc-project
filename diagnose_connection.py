#!/usr/bin/env python3
"""
Diagnostic tool to check why bilol.py admin panel isn't showing orders
"""
import requests
import json
import sys

# Configuration
APP_URL = "https://tfc-project-2sss.onrender.com"
ADMIN_URL = "https://tfc-admin-panel.onrender.com"
API_KEY = "tfc_secret_key_2026_xyz_secure"

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_backend_connection():
    """Test if backend API is accessible"""
    print_section("1. TESTING BACKEND API (app.py)")
    
    try:
        # Test host-info endpoint
        response = requests.get(f"{APP_URL}/api/host-info", timeout=10)
        print(f"✅ app.py is accessible")
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   API URL: {data.get('api_url')}")
        print(f"   Host: {data.get('host')}")
        return True
    except Exception as e:
        print(f"❌ Cannot reach app.py: {e}")
        return False

def test_admin_panel():
    """Test if admin panel is accessible"""
    print_section("2. TESTING ADMIN PANEL (bilol.py)")
    
    try:
        response = requests.get(ADMIN_URL, timeout=10)
        print(f"✅ Admin panel is accessible")
        print(f"   Status: {response.status_code}")
        print(f"   Response size: {len(response.text)} bytes")
        
        # Check if it contains the API_BASE_URL template
        if "{{ API_BASE_URL }}" in response.text:
            print(f"   ⚠️  WARNING: API_BASE_URL not rendered (template not processed)")
            return False
        
        # Check if it contains the actual API URL
        if APP_URL in response.text:
            print(f"   ✅ API_BASE_URL correctly set to: {APP_URL}")
        else:
            print(f"   ⚠️  WARNING: API_BASE_URL might be incorrect")
            print(f"   Looking for: {APP_URL}")
        
        return True
    except Exception as e:
        print(f"❌ Cannot reach admin panel: {e}")
        return False

def test_api_key():
    """Test if API key works"""
    print_section("3. TESTING API KEY AUTHENTICATION")
    
    headers = {'X-API-KEY': API_KEY}
    
    try:
        response = requests.get(
            f"{APP_URL}/api/orders/since?last_id=0",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            print(f"✅ API key is valid")
            print(f"   Found {len(orders)} orders in database")
            if orders:
                print(f"   Latest order: #{orders[-1]['id']} - {orders[-1]['customer']}")
            return True
        elif response.status_code == 401:
            print(f"❌ API key is INVALID or missing")
            print(f"   Response: {response.text}")
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False

def test_cors():
    """Test CORS headers"""
    print_section("4. TESTING CORS HEADERS")
    
    try:
        # Send OPTIONS request (preflight)
        headers = {
            'Origin': 'https://tfc-admin-panel.onrender.com',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-API-KEY'
        }
        
        response = requests.options(
            f"{APP_URL}/api/orders/since",
            headers=headers,
            timeout=10
        )
        
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        cors_methods = response.headers.get('Access-Control-Allow-Methods')
        
        print(f"CORS Headers:")
        print(f"   Allow-Origin: {cors_origin}")
        print(f"   Allow-Methods: {cors_methods}")
        
        if cors_origin == '*' or 'tfc-admin-panel.onrender.com' in str(cors_origin):
            print(f"✅ CORS is configured correctly")
            return True
        else:
            print(f"⚠️  CORS might not be configured")
            return False
    except Exception as e:
        print(f"❌ Error testing CORS: {e}")
        return False

def simulate_bilol_polling():
    """Simulate what bilol.py does when polling for orders"""
    print_section("5. SIMULATING BILOL.PY POLLING")
    
    headers = {'X-API-KEY': API_KEY}
    
    try:
        # This is exactly what bilol.py does
        response = requests.get(
            f"{APP_URL}/api/orders/since?last_id=0",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            
            print(f"✅ bilol.py would successfully fetch orders")
            print(f"   Orders found: {len(orders)}")
            
            if orders:
                print(f"\n   First 3 orders:")
                for i, order in enumerate(orders[:3], 1):
                    print(f"   {i}. #{order['id']} - {order['customer']} - {order['food'][:50]}...")
            
            return True
        else:
            print(f"❌ bilol.py would fail to fetch orders")
            print(f"   Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_environment_variable():
    """Check if TFC_API_URL is set correctly"""
    print_section("6. CHECKING ENVIRONMENT VARIABLE")
    
    print("On your LOCAL machine:")
    print(f"   TFC_API_URL = {APP_URL}")
    print()
    print("On RENDER.COM (bilol.py service):")
    print("   You MUST set this environment variable:")
    print(f"   Key: TFC_API_URL")
    print(f"   Value: {APP_URL}")
    print()
    print("   How to set:")
    print("   1. Go to https://dashboard.render.com")
    print("   2. Select 'tfc-admin-panel' service")
    print("   3. Click 'Environment' tab")
    print("   4. Add: TFC_API_URL = https://tfc-project-2sss.onrender.com")
    print("   5. Click 'Save Changes'")
    print("   6. Redeploy the service")

def main():
    print("\n" + "=" * 70)
    print("  TFC CONNECTION DIAGNOSTIC TOOL")
    print("=" * 70)
    
    results = []
    
    # Run all tests
    results.append(("Backend API", test_backend_connection()))
    results.append(("Admin Panel", test_admin_panel()))
    results.append(("API Key", test_api_key()))
    results.append(("CORS", test_cors()))
    results.append(("Polling Simulation", simulate_bilol_polling()))
    
    # Check environment variable
    check_environment_variable()
    
    # Summary
    print_section("DIAGNOSTIC SUMMARY")
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("✅ ALL BACKEND TESTS PASSED!")
        print("=" * 70)
        print("\nThe backend connection is working perfectly!")
        print("\nIf orders still don't show in the admin panel UI:")
        print("1. Open browser console (F12) and check for errors")
        print("2. Make sure bilol.py was redeployed after setting TFC_API_URL")
        print("3. Try hard refresh (Ctrl+Shift+R) to clear cache")
        print("4. Check if JavaScript is enabled in browser")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        print("\nMost likely issue:")
        print("→ bilol.py on Render.com doesn't have TFC_API_URL set")
        print("\nSolution:")
        print("1. Go to Render.com dashboard")
        print("2. Select tfc-admin-panel service")
        print("3. Set environment variable: TFC_API_URL=https://tfc-project-2sss.onrender.com")
        print("4. Redeploy the service")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted")
        sys.exit(1)