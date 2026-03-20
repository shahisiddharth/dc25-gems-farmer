"""
Dream Cricket 25 - ULTRA Gems Farmer
With Hacker Intro + Login + Full Farming UI
"""

from flask import Flask, jsonify, request, session
import requests as req
import json, time, base64, math, threading, os, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

URL      = "https://api-prod.dreamgamestudios.in/userdata/graphql"
GEMS_PER = 2
MAX_WORKERS = 200

ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "admin@dc25.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

_ts  = int(time.time())
_tsl = threading.Lock()
sessions_data = {}
sessions_lock = threading.Lock()

def uts():
    global _ts
    with _tsl:
        _ts += 1
        return str(_ts)

def mutation():
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 125968,
            "templateAttributes": [
                {"templateId":0,"groupAttributeId":3277,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3283,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3289,"attributeValue": uts()},
                {"templateId":0,"groupAttributeId":3290,"attributeValue":"0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{"currencyTypeId":2,"currencyAmount":GEMS_PER,"giveAwayType":11,"meta":"Reward"}]
        }]}
    }

def get_uid(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        return json.loads(base64.b64decode(p)).get('user-info', {}).get('id', '28788969')
    except: return '28788969'

def make_headers(token):
    return {
        "Host":"api-prod.dreamgamestudios.in","Accept":"*/*",
        "Accept-Encoding":"gzip, deflate",
        "Authorization":f"Bearer {token}",
        "Content-Type":"application/json; charset=utf-8",
        "X-SpineSDK":"0.1","gameId":"1","studioId":"1",
        "userId":get_uid(token),"game-env":"BLUE",
        "gameVersion":"1.5.55",
        "secretKey":"6b77f094-45e2-46d0-b6cc-827dcb5f6b85",
        "X-API-VERSION":"1",
        "User-Agent":"ProjectCricketUE4/++UE4+Release-4.27-CL-0 Android/15"
    }

def one_req(hdr, sid):
    try:
        r = req.post(URL, headers=hdr, json=mutation(), timeout=15)
        ok = r.status_code == 200
    except: ok = False
    with sessions_lock:
        if sid in sessions_data:
            if ok: sessions_data[sid]["success"] += 1
            else:  sessions_data[sid]["fail"]    += 1
    return ok

def run_job(sid, token, total, workers):
    hdr = make_headers(token)
    batches = math.ceil(total / workers)
    bt = []
    for b in range(batches):
        with sessions_lock:
            if sid not in sessions_data or not sessions_data[sid]["running"]: break
        sz = min(workers, total - sessions_data[sid]["completed"])
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs = [ex.submit(one_req, hdr, sid) for _ in range(sz)]
            for f in as_completed(fs): pass
        t1 = time.time()
        with sessions_lock:
            if sid not in sessions_data: break
            sessions_data[sid]["completed"] += sz
        bt.append(t1 - t0)
        if len(bt) > 10: bt.pop(0)
        avg = sum(bt) / len(bt)
        spd = round(workers / avg, 1)
        with sessions_lock:
            if sid in sessions_data:
                sessions_data[sid]["eta"]   = (batches - b - 1) * avg
                sessions_data[sid]["speed"] = spd
                sessions_data[sid]["speed_history"].append(spd)
                if len(sessions_data[sid]["speed_history"]) > 30:
                    sessions_data[sid]["speed_history"].pop(0)
    with sessions_lock:
        if sid in sessions_data:
            sessions_data[sid]["running"] = False
            sessions_data[sid]["done"]    = True
            elapsed = time.time() - sessions_data[sid]["start_time"]
            sessions_data[sid]["history"].insert(0, {
                "gems":    sessions_data[sid]["success"] * GEMS_PER,
                "success": sessions_data[sid]["success"],
                "total":   total, "workers": workers,
                "elapsed": round(elapsed, 1),
                "time":    datetime.now().strftime("%H:%M:%S")
            })
            if len(sessions_data[sid]["history"]) > 5:
                sessions_data[sid]["history"] = sessions_data[sid]["history"][:5]

def is_logged_in():
    return session.get("logged_in") == True

@app.route("/")
def index():
    if not is_logged_in(): return LOGIN_PAGE
    return MAIN_PAGE

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    email    = d.get("email","").strip().lower()
    password = d.get("password","").strip()
    if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
        session["logged_in"] = True
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid email or password"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/start", methods=["POST"])
def start():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    d = request.json
    token   = d.get("token","").strip()
    gems    = int(d.get("gems", 100))
    workers = min(int(d.get("workers", 20)), MAX_WORKERS)
    sid     = d.get("sid", "default")
    if not token: return jsonify({"error":"Token required"}), 400
    if gems < 2:  return jsonify({"error":"Min 2 gems"}), 400
    with sessions_lock:
        if sid in sessions_data and sessions_data[sid]["running"]:
            return jsonify({"error":"Already running"}), 400
        prev   = sessions_data[sid]["history"] if sid in sessions_data else []
        clicks = math.ceil(gems / GEMS_PER)
        sessions_data[sid] = {
            "running":True,"done":False,"success":0,"fail":0,
            "total":clicks,"completed":0,"start_time":time.time(),
            "eta":0,"speed":0,"speed_history":[],"history":prev,
        }
    threading.Thread(target=run_job, args=(sid,token,clicks,workers), daemon=True).start()
    return jsonify({"ok":True,"clicks":clicks})

@app.route("/stop", methods=["POST"])
def stop():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    sid = request.json.get("sid","default")
    with sessions_lock:
        if sid in sessions_data: sessions_data[sid]["running"] = False
    return jsonify({"ok":True})

@app.route("/status")
def status():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    sid = request.args.get("sid","default")
    with sessions_lock:
        j = dict(sessions_data.get(sid,{
            "running":False,"done":False,"success":0,"fail":0,
            "total":0,"completed":0,"start_time":0,
            "eta":0,"speed":0,"speed_history":[],"history":[]
        }))
    elapsed = time.time() - j["start_time"] if j["start_time"] else 0
    pct = round(j["completed"]/j["total"]*100,1) if j["total"] else 0
    return jsonify({
        "running":j["running"],"done":j["done"],
        "completed":j["completed"],"total":j["total"],"pct":pct,
        "gems":j["success"]*GEMS_PER,"success":j["success"],"fail":j["fail"],
        "eta":round(j.get("eta",0)),"speed":j.get("speed",0),
        "elapsed":round(elapsed),
        "speed_history":j.get("speed_history",[]),
        "history":j.get("history",[]),
    })

@app.route("/ping")
def ping(): return "pong", 200

# ═══════════════════════════════════════════════════════
# LOGIN PAGE WITH ULTRA HACKER INTRO
# ═══════════════════════════════════════════════════════
LOGIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 · ACCESS</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#000;overflow:hidden;font-family:'Share Tech Mono',monospace;cursor:none;}
.cursor{position:fixed;width:18px;height:18px;border:1px solid #00ff88;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:difference;}
.cursor::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:3px;height:3px;background:#00ff88;border-radius:50%;}
#matrix{position:fixed;inset:0;z-index:1;}
#hexGrid{position:fixed;inset:0;z-index:2;opacity:0.05;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100'%3E%3Cpath d='M28 66L0 50V16L28 0l28 16v34L28 66zm0-2l26-15V18L28 2 2 18v30l26 15z' fill='none' stroke='%2300ff88' stroke-width='0.5'/%3E%3C/svg%3E");}
#scanline{position:fixed;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(0,255,136,0.12),transparent);z-index:3;animation:scanMove 3s linear infinite;pointer-events:none;}
@keyframes scanMove{0%{top:-2px;}100%{top:100vh;}}

/* INTRO */
#intro{position:fixed;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.ring{position:absolute;border-radius:50%;border:1px solid rgba(0,255,136,0.12);top:50%;left:50%;transform:translate(-50%,-50%) scale(0);animation:ringPulse 4s ease-out infinite;}
.ring:nth-child(1){width:200px;height:200px;animation-delay:0s;}
.ring:nth-child(2){width:400px;height:400px;animation-delay:0.8s;}
.ring:nth-child(3){width:650px;height:650px;animation-delay:1.6s;}
.ring:nth-child(4){width:950px;height:950px;animation-delay:2.4s;}
@keyframes ringPulse{0%{transform:translate(-50%,-50%) scale(0);opacity:0.5;}100%{transform:translate(-50%,-50%) scale(1);opacity:0;}}
.corner{position:absolute;width:80px;height:80px;opacity:0;}
.corner.tl{top:16px;left:16px;border-top:2px solid #00ff88;border-left:2px solid #00ff88;animation:cIn .3s ease .2s forwards;}
.corner.tr{top:16px;right:16px;border-top:2px solid #00ff88;border-right:2px solid #00ff88;animation:cIn .3s ease .35s forwards;}
.corner.bl{bottom:16px;left:16px;border-bottom:2px solid #00ff88;border-left:2px solid #00ff88;animation:cIn .3s ease .5s forwards;}
.corner.br{bottom:16px;right:16px;border-bottom:2px solid #00ff88;border-right:2px solid #00ff88;animation:cIn .3s ease .65s forwards;}
@keyframes cIn{to{opacity:1;}}
#topBar{position:absolute;top:24px;left:50%;transform:translateX(-50%);display:flex;gap:20px;align-items:center;font-size:9px;color:#1a4a2a;letter-spacing:3px;opacity:0;animation:fUp .4s ease 1s forwards;white-space:nowrap;}
@keyframes fUp{to{opacity:1;}}
.dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:dBlink 1.5s infinite;}
.dot.r{background:#ff2244;animation-delay:.5s;}
.dot.y{background:#ffd600;animation-delay:1s;}
@keyframes dBlink{0%,100%{opacity:1;}50%{opacity:0.3;}}
#termPanel{position:absolute;left:14px;top:50%;transform:translateY(-50%);width:min(210px,26vw);background:rgba(0,255,100,0.03);border:1px solid rgba(0,255,100,0.08);border-radius:4px;padding:10px;font-size:8px;color:#1a5a2a;line-height:1.9;opacity:0;animation:fUp .5s ease 1.2s forwards;max-height:65vh;overflow:hidden;}
.pt{color:#00aa55;border-bottom:1px solid #0d2a1a;padding-bottom:5px;margin-bottom:7px;letter-spacing:3px;font-size:7px;}
.tl-ok{color:#00ff88;}.tl-w{color:#ffd600;}.tl-e{color:#ff2244;}
#dataPanel{position:absolute;right:14px;top:50%;transform:translateY(-50%);font-size:8px;color:#1a4a2a;line-height:2.1;letter-spacing:1px;opacity:0;animation:fUp .5s ease 1.4s forwards;text-align:right;}
.dr{display:flex;justify-content:flex-end;gap:8px;}
.dk{color:#1a3a2a;}.dv{color:#00cc66;font-size:9px;}
.dv.lv{color:#00ffaa;text-shadow:0 0 8px rgba(0,255,100,0.5);animation:vp 2s infinite;}
@keyframes vp{0%,100%{opacity:1;}50%{opacity:0.5;}}
#center{position:relative;z-index:5;text-align:center;opacity:0;animation:ctrIn .8s cubic-bezier(0.16,1,0.3,1) 2s forwards;}
@keyframes ctrIn{0%{opacity:0;transform:scale(0.85);}100%{opacity:1;transform:scale(1);}}
.gw{position:relative;display:inline-block;margin-bottom:18px;}
.gi{font-size:68px;display:block;filter:drop-shadow(0 0 30px rgba(0,255,136,0.8));animation:gf 3s ease-in-out infinite 2s;}
@keyframes gf{0%,100%{transform:translateY(0) rotate(0deg);}50%{transform:translateY(-8px) rotate(4deg);}}
.orb{position:absolute;border:1px solid rgba(0,255,136,0.18);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);}
.orb1{width:100px;height:100px;animation:os 4s linear infinite 2s;}
.orb2{width:140px;height:140px;animation:os 7s linear reverse infinite 2s;border-style:dashed;}
@keyframes os{to{transform:translate(-50%,-50%) rotate(360deg);}}
.od{position:absolute;width:5px;height:5px;background:#00ff88;border-radius:50%;top:-2px;left:50%;transform:translateX(-50%);box-shadow:0 0 8px #00ff88;}
.mt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(26px,7vw,56px);letter-spacing:8px;color:#00ffaa;text-shadow:0 0 30px rgba(0,255,136,0.6),0 0 60px rgba(0,255,136,0.25);position:relative;}
.mt::before{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#ff0044;opacity:0;animation:gr 5s infinite 3s;clip-path:polygon(0 20%,100% 20%,100% 40%,0 40%);}
.mt::after{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#00e5ff;opacity:0;animation:gb 5s infinite 3.1s;clip-path:polygon(0 60%,100% 60%,100% 80%,0 80%);}
@keyframes gr{0%,92%,100%{opacity:0;transform:translate(0);}93%{opacity:.8;transform:translate(-4px,0);}94%{opacity:0;}95%{opacity:.8;transform:translate(-2px,0);}96%{opacity:0;}}
@keyframes gb{0%,92%,100%{opacity:0;transform:translate(0);}93%{opacity:.8;transform:translate(4px,0);}94%{opacity:0;}95%{opacity:.8;transform:translate(2px,0);}96%{opacity:0;}}
.vtag{display:inline-block;background:rgba(0,255,100,0.06);border:1px solid rgba(0,255,100,0.18);border-radius:2px;padding:3px 12px;font-size:9px;color:#00aa55;letter-spacing:5px;margin-top:8px;}
.dtxt{font-size:10px;color:#00aa44;letter-spacing:3px;margin-top:8px;min-height:16px;}
#pw{margin-top:24px;width:min(360px,72vw);opacity:0;animation:fUp .4s ease 2.5s forwards;}
.ph{display:flex;justify-content:space-between;font-size:9px;color:#1a4a2a;margin-bottom:5px;letter-spacing:2px;}
.pt2{background:rgba(0,255,100,0.04);border:1px solid #0a2015;border-radius:2px;height:8px;overflow:hidden;position:relative;}
.pf{height:100%;width:0%;background:linear-gradient(90deg,#002a14,#00aa55,#00ffaa);box-shadow:0 0 12px rgba(0,255,100,0.4);}
.sps{margin-top:8px;display:flex;flex-direction:column;gap:4px;}
.sr{display:flex;align-items:center;gap:8px;font-size:8px;color:#1a3a2a;}
.sl2{width:90px;text-align:right;}.st{flex:1;height:3px;background:rgba(0,255,100,0.04);border-radius:1px;overflow:hidden;}
.sf{height:100%;width:0%;transition:width 1s ease;border-radius:1px;}
.sf.g{background:#00cc77;}.sf.c{background:#00e5ff;}.sf.y{background:#ffd600;}.sf.p{background:#c264fe;}
.sp2{width:28px;color:#00aa44;font-size:8px;}
#bs{margin-top:12px;font-size:10px;color:#00aa44;letter-spacing:2px;text-align:center;min-height:16px;opacity:0;animation:fUp .3s ease 2.8s forwards;}
#ag{position:fixed;inset:0;z-index:50;background:#000;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;}
.agb{border:2px solid #00ff88;padding:28px 50px;text-align:center;box-shadow:0 0 60px rgba(0,255,136,0.4),inset 0 0 30px rgba(0,255,136,0.05);}
.agi{font-size:44px;margin-bottom:10px;}
.agt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(16px,5vw,34px);letter-spacing:8px;color:#00ffaa;text-shadow:0 0 30px rgba(0,255,136,1);}
.ags{font-size:10px;color:#00aa55;letter-spacing:4px;margin-top:6px;}
#skipB{position:fixed;bottom:18px;right:18px;z-index:100;background:rgba(0,255,100,0.04);border:1px solid rgba(0,255,100,0.12);border-radius:3px;color:rgba(0,255,100,0.25);font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;padding:5px 12px;cursor:pointer;transition:all .2s;}
#skipB:hover{color:rgba(0,255,100,0.6);border-color:rgba(0,255,100,0.35);}

/* LOGIN CARD */
#loginWrap{position:fixed;inset:0;z-index:8;display:none;align-items:center;justify-content:center;background:rgba(3,5,10,0.97);}
#loginWrap.show{display:flex;}
.lcard{background:#0a1520;border:1px solid #0d2a1a;border-radius:8px;padding:36px 28px 32px;width:100%;max-width:360px;position:relative;overflow:hidden;margin:20px;}
.lcard::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#00ffaa,#00cc77,#00ffaa,transparent);}
.llogo{text-align:center;margin-bottom:26px;}
.lico{font-size:36px;margin-bottom:10px;}
.lh1{font-family:'Orbitron',monospace;font-weight:900;font-size:18px;letter-spacing:6px;background:linear-gradient(135deg,#00ffaa,#00e5ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.lp{font-size:9px;color:#2a4a35;letter-spacing:4px;margin-top:5px;}
.lf{margin-bottom:15px;}
.lf label{display:block;font-size:9px;color:#2a4a35;letter-spacing:3px;margin-bottom:6px;}
.lf input{width:100%;background:rgba(0,255,100,0.03);border:1px solid #0d2a1a;border-radius:4px;color:#00ffaa;font-family:'Share Tech Mono',monospace;font-size:14px;padding:12px 14px;outline:none;transition:border-color .2s,box-shadow .2s;}
.lf input:focus{border-color:#00cc77;box-shadow:0 0 12px rgba(0,255,100,0.1);}
.lbtn{width:100%;padding:15px;margin-top:6px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid #00cc77;border-radius:6px;color:#00ffaa;font-family:'Orbitron',monospace;font-weight:900;font-size:13px;letter-spacing:5px;cursor:pointer;transition:all .2s;text-shadow:0 0 12px rgba(0,255,100,0.5);position:relative;overflow:hidden;}
.lbtn::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,0.1),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.lbtn:hover{transform:translateY(-1px);box-shadow:0 0 40px rgba(0,255,100,0.18);}
.lbtn:disabled{opacity:.4;cursor:not-allowed;}
.lerr{display:none;background:rgba(255,34,68,.08);border:1px solid rgba(255,34,68,.25);border-radius:4px;color:#ff2244;font-size:11px;padding:10px;margin-top:10px;text-align:center;letter-spacing:1px;}
.lerr.show{display:block;}
</style>
</head>
<body>
<div class="cursor" id="cur"></div>
<canvas id="matrix"></canvas>
<div id="hexGrid"></div>
<div id="scanline"></div>

<!-- INTRO -->
<div id="intro">
  <div class="ring"></div><div class="ring"></div><div class="ring"></div><div class="ring"></div>
  <div class="corner tl"></div><div class="corner tr"></div>
  <div class="corner bl"></div><div class="corner br"></div>
  <div id="topBar">
    <div class="dot"></div>SYSTEM ONLINE
    <span style="color:#0d3a1a">|</span>
    <div class="dot y"></div>ENCRYPTION:AES-256
    <span style="color:#0d3a1a">|</span>
    <div class="dot r"></div>FIREWALL:BYPASSED
  </div>
  <div id="termPanel">
    <div class="pt">// BOOT LOG</div>
    <div id="tLines"></div>
  </div>
  <div id="dataPanel">
    <div class="dr"><span class="dk">NODE</span><span class="dv">RENDER-64</span></div>
    <div class="dr"><span class="dk">VERSION</span><span class="dv lv">v3.0.0</span></div>
    <div class="dr"><span class="dk">WORKERS</span><span class="dv lv">200</span></div>
    <div class="dr"><span class="dk">THREADS</span><span class="dv">ACTIVE</span></div>
    <div class="dr"><span class="dk">NET</span><span class="dv lv">SECURE</span></div>
    <div class="dr"><span class="dk">GEMS/s</span><span class="dv lv" id="gr2">--</span></div>
    <div class="dr"><span class="dk">STATUS</span><span class="dv lv">ONLINE</span></div>
    <div class="dr"><span class="dk">PING</span><span class="dv" id="pv">--ms</span></div>
  </div>
  <div id="center">
    <div class="gw">
      <div class="orb orb1"><div class="od"></div></div>
      <div class="orb orb2"><div class="od"></div></div>
      <span class="gi">💎</span>
    </div>
    <div class="mt">DC25 FARMER</div>
    <div class="vtag">ULTRA GEMS EDITION · v3.0</div>
    <div class="dtxt" id="dtxt">&nbsp;</div>
    <div id="pw">
      <div class="ph"><span id="plbl">INITIALIZING...</span><span id="pn">0%</span></div>
      <div class="pt2"><div class="pf" id="pfl"></div></div>
      <div class="sps">
        <div class="sr"><span class="sl2">CORE ENGINE</span><div class="st"><div class="sf g" id="s1"></div></div><span class="sp2" id="s1p">0%</span></div>
        <div class="sr"><span class="sl2">NETWORK</span><div class="st"><div class="sf c" id="s2"></div></div><span class="sp2" id="s2p">0%</span></div>
        <div class="sr"><span class="sl2">THREADS</span><div class="st"><div class="sf y" id="s3"></div></div><span class="sp2" id="s3p">0%</span></div>
        <div class="sr"><span class="sl2">SECURITY</span><div class="st"><div class="sf p" id="s4"></div></div><span class="sp2" id="s4p">0%</span></div>
      </div>
    </div>
    <div id="bs">▌</div>
  </div>
</div>

<!-- ACCESS GRANTED -->
<div id="ag">
  <div class="agb">
    <div class="agi">🔓</div>
    <div class="agt">ACCESS GRANTED</div>
    <div class="ags">WELCOME · KING SHAHI</div>
  </div>
</div>

<!-- LOGIN FORM -->
<div id="loginWrap">
  <div class="lcard">
    <div class="llogo">
      <div class="lico">💎</div>
      <div class="lh1">DC25 FARMER</div>
      <div class="lp">SECURE ACCESS REQUIRED</div>
    </div>
    <div class="lf">
      <label>EMAIL ADDRESS</label>
      <input type="email" id="em" placeholder="your@email.com" autocomplete="email"/>
    </div>
    <div class="lf">
      <label>PASSWORD</label>
      <input type="password" id="pw2" placeholder="••••••••" autocomplete="current-password"/>
    </div>
    <button class="lbtn" id="lbtn" onclick="doLogin()">▶ LOGIN</button>
    <div class="lerr" id="lerr"></div>
  </div>
</div>

<button id="skipB" onclick="skipAll()">SKIP ▶▶</button>

<script>
// Cursor
const cur=document.getElementById('cur');
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px';});

// Matrix
const cv=document.getElementById('matrix');
const cx=cv.getContext('2d');
cv.width=window.innerWidth;cv.height=window.innerHeight;
const cols=Math.floor(cv.width/14);
const drops=Array(cols).fill(1);
const CH='ｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵｶｷｸｺｻｼｽｾｿﾀﾁﾃﾄﾅﾆﾇﾈﾊﾋﾌﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEF<>{}[]';
function drawM(){
  cx.fillStyle='rgba(0,0,0,0.055)';cx.fillRect(0,0,cv.width,cv.height);
  drops.forEach((y,i)=>{
    const c=CH[Math.floor(Math.random()*CH.length)];
    const r=Math.random();
    cx.fillStyle=r>.97?'#fff':r>.85?'#00ffaa':r>.6?'#00994d':'#003322';
    cx.font=(r>.97?'bold ':'')+  '13px Share Tech Mono';
    cx.fillText(c,i*14,y*14);
    if(y*14>cv.height&&Math.random()>.975)drops[i]=0;
    drops[i]++;
  });
}
const mInt=setInterval(drawM,45);

// Fake stats
setInterval(()=>{
  document.getElementById('pv').textContent=(Math.floor(Math.random()*30)+10)+'ms';
  document.getElementById('gr2').textContent=Math.floor(Math.random()*12+18)+'/s';
},900);

// Terminal lines
const tls=[
  {t:'BIOS v2.1.0 INITIALIZED',c:''},
  {t:'CPU: ARM64 x8 DETECTED',c:''},
  {t:'RAM: 512MB ALLOCATED',c:'ok'},
  {t:'LOADING KERNEL MODULES...',c:''},
  {t:'net0: INTERFACE UP',c:'ok'},
  {t:'FIREWALL: BYPASSED !!!',c:'warn'},
  {t:'SSL HANDSHAKE COMPLETE',c:'ok'},
  {t:'TARGET: api-prod.dreamgame',c:''},
  {t:'INJECTION READY',c:'ok'},
  {t:'GEMS MODULE v3.0 LOADED',c:'ok'},
  {t:'200 THREADS SPAWNED',c:'ok'},
  {t:'ALL SYSTEMS READY',c:'ok'},
];
const tEl=document.getElementById('tLines');
let ti=0;
const tInt=setInterval(()=>{
  if(ti>=tls.length){clearInterval(tInt);return;}
  const l=tls[ti++];
  const el=document.createElement('div');
  const col=l.c==='ok'?'tl-ok':l.c==='warn'?'tl-w':l.c==='err'?'tl-e':'';
  el.innerHTML=`<span style="color:#0d3a1a">&gt;</span> <span class="${col}">${l.t}</span>`;
  el.style.cssText='opacity:0;animation:fUp .1s ease forwards;font-size:8px;line-height:1.9;';
  tEl.appendChild(el);
  tEl.scrollTop=tEl.scrollHeight;
},240);

// Decrypt animation
const dms=['DECRYPTING PAYLOAD...','BYPASSING AUTH...','LOADING GEMS ENGINE...','ESTABLISHING CHANNEL...','SYSTEM ARMED...'];
const hx='0123456789ABCDEF';
function decrypt(target,cb){
  const el=document.getElementById('dtxt');
  let it=0;
  const iv=setInterval(()=>{
    el.textContent=target.split('').map((c,i)=>i<it?c:c===' '?' ':hx[Math.floor(Math.random()*16)]).join('');
    it+=1.5;
    if(it>=target.length){el.textContent=target;clearInterval(iv);if(cb)setTimeout(cb,600);}
  },40);
}
let di=0;
function nextD(){if(di>=dms.length)return;decrypt(dms[di++],di<dms.length?nextD:null);}
setTimeout(nextD,2200);

// Progress
const lbls=['LOADING CORE...','SPAWNING THREADS...','CONNECTING...','DECRYPTING KEYS...','VERIFYING TOKENS...','CALIBRATING...','ARMED','READY'];
let pct=0,li=0;
const pfl=document.getElementById('pfl'),pn=document.getElementById('pn'),plbl=document.getElementById('plbl'),bsEl=document.getElementById('bs');
setTimeout(()=>{
  const iv=setInterval(()=>{
    pct+=Math.random()*3.5+0.5;
    if(pct>=100){pct=100;clearInterval(iv);setTimeout(showAG,300);}
    pfl.style.width=pct+'%';pn.textContent=Math.floor(pct)+'%';
    const nl=Math.floor((pct/100)*lbls.length);
    if(nl!==li&&nl<lbls.length){li=nl;plbl.textContent=lbls[li];bsEl.textContent='> '+lbls[li];}
    [['s1','s1p'],['s2','s2p'],['s3','s3p'],['s4','s4p']].forEach(([id,pid],i)=>{
      const v=Math.min(100,Math.max(0,(pct-i*25)*4));
      document.getElementById(id).style.width=v+'%';
      document.getElementById(pid).textContent=Math.floor(v)+'%';
    });
  },55);
},2600);

function showAG(){
  const ag=document.getElementById('ag');
  ag.style.opacity='1';ag.style.pointerEvents='auto';
  let f=0;
  const iv=setInterval(()=>{
    f++;ag.style.background=f%2===0?'#000':'rgba(0,255,100,0.04)';
    if(f>=6){clearInterval(iv);setTimeout(showLogin,500);}
  },130);
}

function showLogin(){
  const intro=document.getElementById('intro');
  const ag=document.getElementById('ag');
  const skip=document.getElementById('skipB');
  const lw=document.getElementById('loginWrap');
  [intro,ag].forEach(el=>{el.style.transition='opacity 0.7s';el.style.opacity='0';});
  skip.style.display='none';
  clearInterval(mInt);
  setTimeout(()=>{
    intro.style.display='none';ag.style.display='none';
    lw.classList.add('show');
    document.getElementById('em').focus();
  },750);
}

function skipAll(){clearInterval(tInt);showLogin();}

// Login
document.addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
async function doLogin(){
  const email=document.getElementById('em').value.trim();
  const pass=document.getElementById('pw2').value.trim();
  const btn=document.getElementById('lbtn');
  const err=document.getElementById('lerr');
  if(!email||!pass){showErr('Email aur password required!');return;}
  btn.disabled=true;btn.textContent='VERIFYING...';
  err.classList.remove('show');
  try{
    const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass})});
    const d=await r.json();
    if(d.ok){window.location.reload();}
    else{showErr(d.error||'Access denied!');}
  }catch(e){showErr('Connection error!');}
  btn.disabled=false;btn.textContent='▶ LOGIN';
}
function showErr(m){const e=document.getElementById('lerr');e.textContent=m;e.classList.add('show');}
window.addEventListener('resize',()=>{cv.width=window.innerWidth;cv.height=window.innerHeight;});
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════
# MAIN FARMING PAGE
# ═══════════════════════════════════════════════════════
MAIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 ULTRA FARMER</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#03050a;--panel:#0a1520;--border:#0d2a1a;--g1:#00ffaa;--g2:#00cc77;--g3:#004422;--cyan:#00e5ff;--red:#ff2244;--yellow:#ffd600;--purple:#c264fe;--text:#a8ffd0;--dim:#2a4a35;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 20% 0%,rgba(0,255,100,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(0,200,255,.03) 0%,transparent 60%),repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,255,100,.012) 40px,rgba(0,255,100,.012) 41px);pointer-events:none;z-index:0;}
body::after{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.15) 3px,rgba(0,0,0,.15) 4px);pointer-events:none;z-index:1;}
.wrap{position:relative;z-index:2;}
.hdr{padding:20px 20px 18px;text-align:center;border-bottom:1px solid var(--border);position:relative;}
.hdr::after{content:'';position:absolute;bottom:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--g1),var(--cyan),var(--g1),transparent);}
.hdr-badge{display:inline-block;background:rgba(0,255,100,.08);border:1px solid var(--g3);border-radius:2px;padding:2px 10px;font-size:10px;letter-spacing:4px;color:var(--g2);margin-bottom:8px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(18px,5vw,34px);letter-spacing:6px;background:linear-gradient(135deg,var(--g1),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;filter:drop-shadow(0 0 20px rgba(0,255,150,.4));}
.hdr p{color:var(--dim);font-size:10px;letter-spacing:3px;margin-top:4px;}
.logout-btn{position:absolute;top:18px;right:16px;background:transparent;border:1px solid rgba(255,34,68,.3);border-radius:3px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:10px;padding:5px 10px;cursor:pointer;letter-spacing:1px;transition:all .2s;}
.logout-btn:hover{background:rgba(255,34,68,.1);}
.page{max-width:680px;margin:0 auto;padding:18px 14px 40px;display:flex;flex-direction:column;gap:14px;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:18px;position:relative;overflow:hidden;}
.cg{position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g2),transparent);}
.cg.c{background:linear-gradient(90deg,transparent,var(--cyan),transparent);}
.cg.p{background:linear-gradient(90deg,transparent,var(--purple),transparent);}
.sec{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:4px;color:var(--dim);margin-bottom:12px;display:flex;align-items:center;gap:8px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}
textarea{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:12px;padding:12px;outline:none;resize:none;height:85px;transition:border-color .2s,box-shadow .2s;}
textarea:focus{border-color:var(--g2);box-shadow:0 0 12px rgba(0,255,100,.1);}
.cfg-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.cfg-item label{display:block;font-size:9px;letter-spacing:3px;color:var(--dim);margin-bottom:6px;}
input[type=number]{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:16px;padding:10px 12px;outline:none;transition:border-color .2s;}
input[type=number]:focus{border-color:var(--g2);}
.hint{font-size:10px;color:var(--dim);margin-top:4px;}
.presets{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;}
.pw{flex:1;min-width:40px;background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:12px;padding:6px 4px;cursor:pointer;transition:all .15s;text-align:center;}
.pw:hover,.pw.on{border-color:var(--g1);color:var(--g1);background:rgba(0,255,100,.08);}
.pw.hot{border-color:var(--red)!important;color:var(--red)!important;background:rgba(255,34,68,.08)!important;}
.btn-start{width:100%;padding:18px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid var(--g2);border-radius:6px;color:var(--g1);font-family:'Orbitron',monospace;font-weight:900;font-size:14px;letter-spacing:6px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;text-shadow:0 0 15px rgba(0,255,100,.6);box-shadow:0 0 30px rgba(0,255,100,.08);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,.12),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){background:linear-gradient(135deg,#003a1c,#006633,#004422);box-shadow:0 0 50px rgba(0,255,100,.2);transform:translateY(-2px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-stop{width:100%;padding:12px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:14px;letter-spacing:4px;cursor:pointer;transition:all .2s;display:none;}
.btn-stop:hover{background:rgba(255,34,68,.15);}
.prog-card{display:none;}.prog-card.show{display:block;}
.prog-top{display:flex;align-items:center;gap:20px;margin-bottom:16px;}
.ring-wrap{position:relative;width:90px;height:90px;flex-shrink:0;}
.ring-wrap svg{width:90px;height:90px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:var(--border);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s ease;}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g1);}
.prog-info{flex:1;}
.plbl{font-size:10px;color:var(--dim);letter-spacing:2px;margin-bottom:4px;}
.pval{font-family:'Orbitron',monospace;font-size:24px;font-weight:700;color:var(--g1);}
.psub{font-size:11px;color:var(--dim);margin-top:2px;}
.bar-wrap{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:3px;height:12px;overflow:hidden;margin-bottom:14px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));width:0%;transition:width .4s ease;box-shadow:0 0 10px rgba(0,255,100,.4);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.stat{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;padding:10px 8px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(13px,3.5vw,19px);font-weight:700;color:var(--g1);}
.sv.c{color:var(--cyan);}.sv.y{color:var(--yellow);}.sv.r{color:var(--red);}
.sl{font-size:8px;color:var(--dim);letter-spacing:2px;margin-top:3px;}
.graph-wrap{margin-top:12px;}
.glbl{font-size:9px;color:var(--dim);letter-spacing:3px;margin-bottom:6px;}
.graph{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:3px;height:52px;overflow:hidden;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:4px 4px 0;}
.gb{flex:1;min-width:3px;background:linear-gradient(to top,var(--g3),var(--g2));border-radius:1px 1px 0 0;transition:height .3s;}
.st{text-align:center;font-size:11px;color:var(--dim);letter-spacing:1px;margin-top:10px;min-height:16px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--g1);}.st.r{color:var(--red);}
.done-card{display:none;text-align:center;padding:24px;background:rgba(0,255,100,.04);border:1px solid var(--g2);border-radius:6px;animation:glo 2s infinite;}
@keyframes glo{0%,100%{box-shadow:0 0 15px rgba(0,255,100,.1);}50%{box-shadow:0 0 40px rgba(0,255,100,.25);}}
.done-icon{font-size:36px;margin-bottom:10px;}
.done-title{font-family:'Orbitron',monospace;font-size:18px;letter-spacing:6px;color:var(--g1);}
.done-sub{font-size:13px;color:var(--dim);margin-top:8px;line-height:1.8;}
.sess-list{display:flex;flex-direction:column;gap:8px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(0,255,100,.02);border:1px solid var(--border);border-radius:4px;padding:10px 14px;}
.si-gems{font-family:'Orbitron',monospace;font-size:16px;font-weight:700;color:var(--g1);}
.si-meta{font-size:11px;color:var(--dim);}
.si-time{font-size:10px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:12px;letter-spacing:2px;padding:10px;}
.cur2{animation:blink 1s step-end infinite;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:0;}}
</style>
</head>
<body>
<div class="wrap">
<div class="hdr">
  <div class="hdr-badge">DREAM CRICKET 25</div>
  <h1>ULTRA GEMS FARMER</h1>
  <p>TURBO PARALLEL · MAX 200 WORKERS</p>
  <button class="logout-btn" onclick="doLogout()">⏻ LOGOUT</button>
</div>
<div class="page">
  <div class="card"><div class="cg"></div><div class="sec">// BEARER TOKEN</div><textarea id="tok" placeholder="Paste Bearer token here..."></textarea></div>
  <div class="card">
    <div class="cg c"></div><div class="sec">// CONFIGURATION</div>
    <div class="cfg-row">
      <div class="cfg-item"><label>💎 DESIRED GEMS</label><input type="number" id="gems" value="5000" min="2" step="2"/><div class="hint">1 click = 2 gems</div></div>
      <div class="cfg-item"><label>⚡ PARALLEL WORKERS</label><input type="number" id="wrk" value="20" min="1" max="200"/>
        <div class="presets">
          <button class="pw" onclick="sw(10)">10</button>
          <button class="pw on" onclick="sw(20)">20</button>
          <button class="pw" onclick="sw(50)">50</button>
          <button class="pw" onclick="sw(100)">100</button>
          <button class="pw hot" onclick="sw(200)">200🔥</button>
        </div>
      </div>
    </div>
  </div>
  <button class="btn-start" id="btnS" onclick="go()">▶ LAUNCH FARMING</button>
  <button class="btn-stop" id="btnX" onclick="halt()">■ STOP FARMING</button>
  <div class="card prog-card" id="progCard">
    <div class="cg"></div><div class="sec">// LIVE PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs><linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#00cc77"/><stop offset="100%" style="stop-color:#00ffaa"/></linearGradient></defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="ring" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpct">0%</div>
      </div>
      <div class="prog-info"><div class="plbl">GEMS ADDED</div><div class="pval" id="pGems">0</div><div class="psub" id="pClicks">0 / 0 clicks</div></div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpd">0</div><div class="sl">REQ/SEC</div></div>
      <div class="stat"><div class="sv y" id="sEta">--</div><div class="sl">ETA</div></div>
      <div class="stat"><div class="sv" id="sOk">0</div><div class="sl">SUCCESS</div></div>
      <div class="stat"><div class="sv r" id="sFail">0</div><div class="sl">FAILED</div></div>
    </div>
    <div class="graph-wrap"><div class="glbl">// SPEED GRAPH (req/s)</div><div class="graph"><div class="gbars" id="gBars"></div></div></div>
    <div class="st" id="stLine"><span class="cur2">_</span> Ready</div>
  </div>
  <div class="done-card" id="doneCard">
    <div class="done-icon">💎</div>
    <div class="done-title">FARMING COMPLETE</div>
    <div class="done-sub" id="doneSub"></div>
  </div>
  <div class="card">
    <div class="cg p"></div><div class="sec">// SESSION HISTORY</div>
    <div class="sess-list" id="sessList"><div class="empty">NO SESSIONS YET <span class="cur2">_</span></div></div>
  </div>
</div>
</div>
<script>
const CIRC=245,SID=Math.random().toString(36).slice(2,10);
let poll=null;
function sw(v){document.getElementById('wrk').value=v;document.querySelectorAll('.pw').forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));}
function fmt(s){s=Math.max(0,Math.round(s));if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';}
function ring(p){document.getElementById('ring').style.strokeDashoffset=CIRC-(CIRC*p/100);document.getElementById('rpct').textContent=p.toFixed(1)+'%';}
function graph(h){const w=document.getElementById('gBars');if(!h.length)return;const mx=Math.max(...h,1);w.innerHTML=h.map(v=>`<div class="gb" style="height:${Math.max(4,(v/mx)*44)}px"></div>`).join('');}
function renderSess(list){const el=document.getElementById('sessList');if(!list.length){el.innerHTML='<div class="empty">NO SESSIONS YET <span class="cur2">_</span></div>';return;}el.innerHTML=list.map(s=>`<div class="si"><div><div class="si-gems">+${s.gems} 💎</div><div class="si-meta">${s.success}/${s.total} · ${s.workers}w</div></div><div class="si-time">${s.time}<br/>${fmt(s.elapsed)}</div></div>`).join('');}
function setSt(m,c){const e=document.getElementById('stLine');e.textContent=m;e.className='st '+(c||'');}
async function go(){
  const tok=document.getElementById('tok').value.trim();
  const gems=parseInt(document.getElementById('gems').value);
  const wrk=parseInt(document.getElementById('wrk').value);
  if(!tok){alert('Token paste karo!');return;}
  if(gems<2){alert('Gems enter karo!');return;}
  document.getElementById('doneCard').style.display='none';
  document.getElementById('progCard').classList.add('show');
  document.getElementById('btnS').disabled=true;
  document.getElementById('btnX').style.display='block';
  ring(0);document.getElementById('bar').style.width='0%';
  ['pGems','sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';
  document.getElementById('pClicks').textContent='0 / 0 clicks';
  document.getElementById('gBars').innerHTML='';setSt('Launching...','g');
  const res=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:tok,gems,workers:wrk,sid:SID})});
  const data=await res.json();
  if(data.error){alert(data.error);resetUI();return;}
  setSt(`Running ${data.clicks} clicks · ${wrk} workers`,'g');
  poll=setInterval(tick,700);
}
async function tick(){
  try{
    const r=await fetch('/status?sid='+SID);
    if(r.status===401){clearInterval(poll);window.location.reload();return;}
    const d=await r.json();
    ring(d.pct);document.getElementById('bar').style.width=d.pct+'%';
    document.getElementById('pGems').textContent=d.gems;
    document.getElementById('pClicks').textContent=`${d.completed}/${d.total} clicks`;
    document.getElementById('sSpd').textContent=d.speed;
    document.getElementById('sEta').textContent=fmt(d.eta);
    document.getElementById('sOk').textContent=d.success;
    document.getElementById('sFail').textContent=d.fail;
    graph(d.speed_history);renderSess(d.history);
    if(d.running)setSt(`${d.completed}/${d.total} · ${fmt(d.elapsed)} elapsed`,'g');
    if(d.done){clearInterval(poll);resetUI();ring(100);document.getElementById('bar').style.width='100%';document.getElementById('doneCard').style.display='block';document.getElementById('doneSub').innerHTML=`<strong style="color:var(--g1)">+${d.gems} GEMS</strong> added!<br/>${d.success}/${d.total} success · ${fmt(d.elapsed)} total`;setSt('Complete!','g');}
  }catch(e){setSt('Connection error...','r');}
}
async function halt(){await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:SID})});clearInterval(poll);setSt('Stopped.','r');resetUI();}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}
function resetUI(){document.getElementById('btnS').disabled=false;document.getElementById('btnX').style.display='none';}
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"\033[92m")
    print("╔══════════════════════════════════════════╗")
    print("║  DC25 ULTRA GEMS FARMER - FULL VERSION   ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  Email  : {ADMIN_EMAIL:<31}║")
    print("║  Open   : http://localhost:5000          ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=5000, debug=False)
