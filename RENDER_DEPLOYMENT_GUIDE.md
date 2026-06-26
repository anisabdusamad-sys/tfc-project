# Render.com Deployment Guide for TFC Project

## 🚀 Deploying to Render.com

You have TWO separate services to deploy:

### 1. **app.py** (Menu Website)
**Service Name**: `tfc-project-2sss`  
**URL**: https://tfc-project-2sss.onrender.com

### 2. **bilol.py** (Admin Panel)  
**Service Name**: `tfc-admin-panel`  
**URL**: https://tfc-admin-panel.onrender.com

---

## ⚙️ Required Configuration

### For **bilol.py** (Admin Panel) - IMPORTANT!

You MUST set this environment variable in Render.com:

```
TFC_API_URL=https://tfc-project-2sss.onrender.com
```

**How to set it:**

1. Go to https://dashboard.render.com
2. Select your `tfc-admin-panel` service
3. Click on **"Environment"** tab
4. Add new environment variable:
   - **Key**: `TFC_API_URL`
   - **Value**: `https://tfc-project-2sss.onrender.com`
5. Click **"Save Changes"**
6. Redeploy the service

### For **app.py** (Menu Website)

No special environment variables needed (it already has the `/api/host-info` endpoint).

---

## 🔍 How to Verify It's Working

### Step 1: Test app.py
```bash
curl https://tfc-project-2sss.onrender.com/api/host-info
```

Expected response:
```json
{
  "api_url": "https://tfc-project-2sss.onrender.com/api",
  "host": "https://tfc-project-2sss.onrender.com",
  "ok": true
}
```

### Step 2: Test bilol.py
```bash
curl https://tfc-admin-panel.onrender.com/
```

Should return HTML (the admin panel page).

### Step 3: Test API Connection
```bash
curl https://tfc-admin-panel.onrender.com/api/orders/since?last_id=0 \
  -H "X-API-KEY: tfc_secret_key_2026_xyz_secure"
```

Should return orders from the database.

---

## 🐛 Common Issues

### Issue 1: "Orders not showing in admin panel"

**Cause**: bilol.py doesn't know the correct API URL

**Solution**: 
1. Check Render.com environment variables for bilol.py
2. Make sure `TFC_API_URL=https://tfc-project-2sss.onrender.com` is set
3. Redeploy bilol.py

### Issue 2: "CORS errors in browser console"

**Cause**: CORS not configured properly

**Solution**: Already fixed in app.py with:
```python
@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp
```

### Issue 3: "Connection timeout"

**Cause**: Service is sleeping (Render.com free tier)

**Solution**: 
- First request after inactivity takes 30-60 seconds to wake up
- Subsequent requests are fast
- Consider upgrading to paid plan for always-on service

---

## 📋 Deployment Checklist

### Before Deploying:

- [ ] Both services are deployed on Render.com
- [ ] `tfc-project-2sss` (app.py) is running
- [ ] `tfc-admin-panel` (bilol.py) is running
- [ ] Environment variable `TFC_API_URL` is set in bilol.py service
- [ ] Both services have the same `TFC_API_KEY`
- [ ] Database file (`tfc_admin.db`) is included in both services

### After Deploying:

1. **Test app.py**: Visit https://tfc-project-2sss.onrender.com
2. **Test bilol.py**: Visit https://tfc-admin-panel.onrender.com
3. **Place test order** on menu website
4. **Check admin panel** - order should appear within 1 second
5. **Update order status** in admin panel
6. **Verify push notification** (if configured)

---

## 🔧 Render.com Settings

### Build & Start Commands

**For app.py:**
```
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

**For bilol.py:**
```
Build Command: pip install -r requirements.txt
Start Command: gunicorn -w 4 -b 0.0.0.0:$PORT bilol:app
```

**Note**: bilol.py uses `gunicorn` for production (already configured in the code comments).

### Environment Variables (Both Services)

```bash
TFC_API_KEY=tfc_secret_key_2026_xyz_secure
FLASK_SECRET_KEY=your_flask_secret_key_here_change_in_production
```

### Environment Variables (bilol.py ONLY)

```bash
TFC_API_URL=https://tfc-project-2sss.onrender.com
```

---

## 📊 Expected Behavior

### Normal Operation:

1. **Customer places order** on https://tfc-project-2sss.onrender.com
2. **Order saved** to SQLite database
3. **bilol.py polls** app.py API every 1 second
4. **New order appears** in admin panel automatically
5. **Admin updates** order status (accepted → ready → delivered)
6. **Push notification** sent to customer (if subscribed)

### First Load (Cold Start):

- Render.com free tier sleeps after 15 minutes of inactivity
- First request takes 30-60 seconds to wake up
- You'll see "Starting..." in Render.com dashboard
- Once awake, everything works normally

---

## 🎯 Quick Test

After setting up environment variables, run this test:

```bash
# Test 1: Check app.py
curl https://tfc-project-2sss.onrender.com/api/host-info

# Test 2: Check bilol.py can reach app.py
curl "https://tfc-admin-panel.onrender.com/api/orders/since?last_id=0" \
  -H "X-API-KEY: tfc_secret_key_2026_xyz_secure"

# Test 3: Create test order
curl -X POST "https://tfc-project-2sss.onrender.com/api/orders/new" \
  -H "X-API-KEY: tfc_secret_key_2026_xyz_secure" \
  -H "Content-Type: application/json" \
  -d '{"customer":"Test","food":"Test Food","price":"100"}'

# Test 4: Verify order appears in bilol.py
curl "https://tfc-admin-panel.onrender.com/api/orders/since?last_id=0" \
  -H "X-API-KEY: tfc_secret_key_2026_xyz_secure"
```

---

## ✅ Success Indicators

- ✅ app.py loads in browser
- ✅ bilol.py loads in browser  
- ✅ Admin panel shows existing orders
- ✅ New orders appear within 1-2 seconds
- ✅ Can update order status
- ✅ No CORS errors in browser console
- ✅ No connection errors

---

## 🆘 If It's Still Not Working

1. **Check Render.com logs** for both services
2. **Verify environment variables** are set correctly
3. **Test API endpoints** directly with curl
4. **Check browser console** for JavaScript errors
5. **Ensure both services are running** (not crashed)
6. **Wait 30-60 seconds** for cold start

---

**Most Common Issue**: Forgot to set `TFC_API_URL` environment variable in bilol.py service on Render.com!

**Solution**: Set it to `https://tfc-project-2sss.onrender.com` and redeploy.