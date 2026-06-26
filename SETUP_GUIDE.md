# TFC Project - Setup Guide

## Local Development Setup

### 1. Start the Main App (app.py)
```bash
python app.py
```
This will run on: `http://127.0.0.1:5000`

### 2. Start the Admin Panel (bilol.py)
```bash
python bilol.py
```
This will run on: `http://127.0.0.1:5001`

## Configuration

### Current .env Settings (for localhost):
```env
TFC_API_URL=http://127.0.0.1:5000
TFC_API_KEY=tfc_secret_key_2026_xyz_secure
```

### For Production (when deployed):
```env
TFC_API_URL=https://tfc-project-2sss.onrender.com
TFC_API_KEY=tfc_secret_key_2026_xyz_secure
```

## How It Works

1. **bilol.py** (Admin Panel) reads `TFC_API_URL` from `.env`
2. All API calls from admin panel use this URL to communicate with main app
3. Both apps share the same `TFC_API_KEY` for secure communication

## Testing the Connection

### Test 1: Check if app.py is running
Open browser: `http://127.0.0.1:5000`
You should see the TFC website

### Test 2: Check if bilol.py is running
Open browser: `http://127.0.0.1:5001`
You should see the Admin Panel

### Test 3: Verify API connection
In the admin panel (bilol.py):
1. Open browser console (F12)
2. Look for any red errors
3. Check if orders are loading from the main app

## Common Issues

### Issue: "Failed to fetch" errors
**Solution:** Make sure both apps are running:
- Terminal 1: `python app.py` (port 5000)
- Terminal 2: `python bilol.py` (port 5001)

### Issue: CORS errors
**Solution:** Both apps already have CORS enabled. Make sure you're using the correct ports.

### Issue: API Key errors
**Solution:** Verify both `.env` files (if separate) have the same `TFC_API_KEY`

## Switching Between Localhost and Production

### For Localhost:
```env
TFC_API_URL=http://127.0.0.1:5000
```

### For Production:
```env
TFC_API_URL=https://tfc-project-2sss.onrender.com
```

Then restart both apps.

## Ports Summary
- **app.py**: Port 5000 (Main TFC Website)
- **bilol.py**: Port 5001 (Admin Panel)
- **Communication**: bilol.py → app.py via TFC_API_URL