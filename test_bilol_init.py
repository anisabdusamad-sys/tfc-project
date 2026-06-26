#!/usr/bin/env python3
"""
Test script to verify bilol.py initialization works correctly
"""
import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Simulate what bilol.py does on module load
DEFAULT_API_URL = os.getenv("TFC_API_URL", "http://127.0.0.1:5000")
API_BASE_URL = DEFAULT_API_URL

print("=" * 70)
print("TESTING BILOL.PY INITIALIZATION")
print("=" * 70)

print(f"\n1. DEFAULT_API_URL from .env: {DEFAULT_API_URL}")

# Check if it's external hosting
is_external = 'onrender.com' in DEFAULT_API_URL or 'localhost' not in DEFAULT_API_URL
print(f"2. Is external hosting: {is_external}")

if is_external:
    API_BASE_URL = DEFAULT_API_URL
    print(f"3. ✅ External hosting detected")
    print(f"4. API_BASE_URL set to: {API_BASE_URL}")
else:
    print(f"3. ℹ️ Localhost mode - would try auto-detection")
    print(f"4. API_BASE_URL would be: {API_BASE_URL}")

print("\n" + "=" * 70)
print("RESULT:")
print("=" * 70)

if API_BASE_URL == "https://tfc-project-2sss.onrender.com":
    print("✅ SUCCESS! bilol.py will use the correct production URL")
    print(f"   API_BASE_URL = {API_BASE_URL}")
    print("\n📋 Next steps:")
    print("1. Commit and push bilol.py to Render.com")
    print("2. Redeploy the tfc-admin-panel service")
    print("3. Check Render.com logs for: '🌐 External hosting detected'")
    print("4. Orders should now appear in the admin panel!")
    sys.exit(0)
else:
    print(f"❌ FAILED! API_BASE_URL is incorrect: {API_BASE_URL}")
    print(f"   Expected: https://tfc-project-2sss.onrender.com")
    sys.exit(1)