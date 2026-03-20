"""
Dream Cricket 25 - ULTRA Farmer v4.2
- Token auto-hide with cool animation after start
- Per-user history
- 20 sec auto-clear
- BG Jobs + Auto-ping
- Gems + Tickets
"""

from flask import Flask, jsonify, request, session
import requests as req
import json, time, base64, math, threading, os, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

URL            = "https://api-prod.dreamgamestudios.in/userdata/graphql"
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "admin@dc25.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
MAX_WORKERS    = 200

MODES = {
    "gems":    {"label":"💎 Gems",              "templateId":125968, "currencyTypeId":2,  "amount":2,  "unit":"Gems"},
    "tickets": {"label":"🎫 World Cup Tickets", "templateId":124339, "currencyTypeId":23, "amount":30, "unit":"Tickets"},
}

_ts  = int(time.time())
_tsl = threading.Lock()
jobs      = {}
jobs_lock = threading.Lock()
user_history      = {}
user_history_lock = threading.Lock()

SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
def auto_ping():
    while True:
        time.sleep(600)
        try: req.get(f"{SELF_URL}/ping", timeout=10)
        except: pass
threading.Thread(target=auto_ping, daemon=True).start()

def uts():
    global _ts
    with _tsl:
        _ts += 1
        return str(_ts)

def build_mutation(mode_key):
    m = MODES.get(mode_key, MODES["gems"])
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": m["templateId"],
            "templateAttributes": [
                {"templateId":0,"groupAttributeId":3277,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3283,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3289,"attributeValue": uts()},
                {"templateId":0,"groupAttributeId":3290,"attributeValue":"0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{
                "currencyTypeId": m["currencyTypeId"],
                "currencyAmount": m["amount"],
                "giveAwayType": 11, "meta": "Reward"
            }]
        }]}
    }

def get_uid(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        return json.loads(base64.b64decode(p)).get('user-info', {}).get('id', 'unknown')
    except: return 'unknown'

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

def one_req(hdr, job_id, mode_key):
    try:
        r = req.post(URL, headers=hdr, json=build_mutation(mode_key), timeout=15)
        ok = r.status_code == 200
    except: ok = False
    with jobs_lock:
        if job_id in jobs:
            if ok: jobs[job_id]["success"] += 1
            else:  jobs[job_id]["fail"]    += 1
    return ok

def run_job(job_id):
    with jobs_lock:
        if job_id not in jobs: return
        token    = jobs[job_id]["token"]
        total    = jobs[job_id]["total"]
        workers  = jobs[job_id]["workers"]
        mode_key = jobs[job_id]["mode_key"]
        uid      = jobs[job_id]["uid"]
    hdr     = make_headers(token)
    batches = math.ceil(total / workers)
    bt      = []
    for b in range(batches):
        with jobs_lock:
            if job_id not in jobs or not jobs[job_id]["running"]: break
        sz = min(workers, total - jobs[job_id]["completed"])
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs = [ex.submit(one_req, hdr, job_id, mode_key) for _ in range(sz)]
            for f in as_completed(fs): pass
        t1 = time.time()
        with jobs_lock:
            if job_id not in jobs: break
            jobs[job_id]["completed"] += sz
        bt.append(t1 - t0)
        if len(bt) > 10: bt.pop(0)
        avg = sum(bt) / len(bt)
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["eta"]   = (batches - b - 1) * avg
                jobs[job_id]["speed"] = round(workers / avg, 1)
                jobs[job_id]["speed_history"].append(round(workers / avg, 1))
                if len(jobs[job_id]["speed_history"]) > 30:
                    jobs[job_id]["speed_history"].pop(0)
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["running"]  = False
            jobs[job_id]["done"]     = True
            jobs[job_id]["end_time"] = time.time()
            m = MODES.get(mode_key, MODES["gems"])
            elapsed = jobs[job_id]["end_time"] - jobs[job_id]["start_time"]
            entry = {
                "job_id":  job_id,
                "reward":  jobs[job_id]["success"] * m["amount"],
                "unit":    m["unit"],
                "label":   m["label"],
                "success": jobs[job_id]["success"],
                "total":   total,
                "workers": workers,
                "elapsed": round(elapsed, 1),
                "time":    datetime.now().strftime("%H:%M:%S"),
                "date":    datetime.now().strftime("%d %b"),
            }
            with user_history_lock:
                if uid not in user_history:
                    user_history[uid] = []
                user_history[uid].insert(0, entry)
                if len(user_history[uid]) > 10:
                    user_history[uid] = user_history[uid][:10]

def is_logged_in():
    return session.get("logged_in") == True

def active_job():
    with jobs_lock:
        for jid, j in jobs.items():
            if j["running"]:
                return jid, dict(j)
    return None, None

@app.route("/")
def index():
    if not is_logged_in(): return LOGIN_PAGE
    return MAIN_PAGE

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    if d.get("email","").strip().lower() == ADMIN_EMAIL.lower() and d.get("password","").strip() == ADMIN_PASSWORD:
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
    jid, _ = active_job()
    if jid: return jsonify({"error":"Job already running! Stop it first."}), 400
    d        = request.json
    token    = d.get("token","").strip()
    desired  = int(d.get("desired", 100))
    workers  = min(int(d.get("workers", 20)), MAX_WORKERS)
    mode_key = d.get("mode", "gems")
    if mode_key not in MODES: mode_key = "gems"
    if not token: return jsonify({"error":"Token required"}), 400
    m      = MODES[mode_key]
    clicks = math.ceil(desired / m["amount"])
    uid    = get_uid(token)
    job_id = f"job_{int(time.time())}"
    with jobs_lock:
        jobs[job_id] = {
            "running":True,"done":False,
            "success":0,"fail":0,
            "total":clicks,"completed":0,
            "start_time":time.time(),"end_time":0,
            "eta":0,"speed":0,"speed_history":[],
            "token":token,"workers":workers,
            "mode_key":mode_key,"uid":uid,
        }
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return jsonify({"ok":True,"job_id":job_id,"clicks":clicks,"unit":m["unit"],"amount":m["amount"],"uid":uid})

@app.route("/stop", methods=["POST"])
def stop():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    job_id = request.json.get("job_id","")
    with jobs_lock:
        if job_id and job_id in jobs:
            jobs[job_id]["running"] = False
        else:
            for jid in jobs:
                if jobs[jid]["running"]:
                    jobs[jid]["running"] = False
    return jsonify({"ok":True})

@app.route("/status")
def status():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    job_id = request.args.get("job_id","")
    uid    = request.args.get("uid","unknown")
    with jobs_lock:
        if job_id and job_id in jobs:
            j = dict(jobs[job_id])
        elif jobs:
            latest = max(jobs.keys())
            j = dict(jobs[latest])
            job_id = latest
        else:
            j = None
    with user_history_lock:
        hist = list(user_history.get(uid, []))
    if not j:
        return jsonify({
            "running":False,"done":False,"completed":0,"total":0,"pct":0,
            "reward":0,"unit":"Gems","success":0,"fail":0,
            "eta":0,"speed":0,"elapsed":0,
            "speed_history":[],"history":hist,"job_id":"","has_active":False,
        })
    elapsed = (time.time() if j["running"] else j["end_time"]) - j["start_time"]
    pct = round(j["completed"]/j["total"]*100,1) if j["total"] else 0
    m = MODES.get(j["mode_key"], MODES["gems"])
    return jsonify({
        "running":j["running"],"done":j["done"],
        "completed":j["completed"],"total":j["total"],"pct":pct,
        "reward":j["success"]*m["amount"],"unit":m["unit"],"label":m["label"],
        "success":j["success"],"fail":j["fail"],
        "eta":round(j.get("eta",0)),"speed":j.get("speed",0),
        "elapsed":round(elapsed),
        "speed_history":j.get("speed_history",[]),
        "history":hist,
        "job_id":job_id,
        "has_active":j["running"],
        "mode_key":j["mode_key"],
    })

@app.route("/active")
def active():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    jid, j = active_job()
    if jid and j:
        m = MODES.get(j["mode_key"], MODES["gems"])
        elapsed = time.time() - j["start_time"]
        pct = round(j["completed"]/j["total"]*100,1) if j["total"] else 0
        return jsonify({
            "has_active":True,"job_id":jid,"pct":pct,
            "completed":j["completed"],"total":j["total"],
            "reward":j["success"]*m["amount"],"unit":m["unit"],
            "elapsed":round(elapsed),"mode_key":j["mode_key"],"uid":j["uid"],
        })
    return jsonify({"has_active":False})

@app.route("/ping")
def ping(): return "pong", 200

LOGIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 · ACCESS</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#000;overflow:hidden;font-family:'Share Tech Mono',monospace;cursor:none;}
.cur{position:fixed;width:18px;height:18px;border:1px solid #00ff88;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:difference;}
.cur::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:3px;height:3px;background:#00ff88;border-radius:50%;}
#cv{position:fixed;inset:0;z-index:1;}
#sl{position:fixed;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(0,255,136,.12),transparent);z-index:3;animation:sm 3s linear infinite;pointer-events:none;}
@keyframes sm{0%{top:-2px}100%{top:100vh}}
#intro{position:fixed;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.ring{position:absolute;border-radius:50%;border:1px solid rgba(0,255,136,.1);top:50%;left:50%;transform:translate(-50%,-50%) scale(0);animation:rp 4s ease-out infinite;}
.ring:nth-child(1){width:200px;height:200px;}
.ring:nth-child(2){width:400px;height:400px;animation-delay:.8s;}
.ring:nth-child(3){width:650px;height:650px;animation-delay:1.6s;}
.ring:nth-child(4){width:950px;height:950px;animation-delay:2.4s;}
@keyframes rp{0%{transform:translate(-50%,-50%) scale(0);opacity:.5}100%{transform:translate(-50%,-50%) scale(1);opacity:0}}
.co{position:absolute;width:80px;height:80px;opacity:0;}
.co.tl{top:16px;left:16px;border-top:2px solid #00ff88;border-left:2px solid #00ff88;animation:ci .3s ease .2s forwards;}
.co.tr{top:16px;right:16px;border-top:2px solid #00ff88;border-right:2px solid #00ff88;animation:ci .3s ease .35s forwards;}
.co.bl{bottom:16px;left:16px;border-bottom:2px solid #00ff88;border-left:2px solid #00ff88;animation:ci .3s ease .5s forwards;}
.co.br{bottom:16px;right:16px;border-bottom:2px solid #00ff88;border-right:2px solid #00ff88;animation:ci .3s ease .65s forwards;}
@keyframes ci{to{opacity:1}}
#tb{position:absolute;top:24px;left:50%;transform:translateX(-50%);display:flex;gap:16px;align-items:center;font-size:9px;color:#1a4a2a;letter-spacing:3px;opacity:0;animation:fu .4s ease 1s forwards;white-space:nowrap;}
@keyframes fu{to{opacity:1}}
.dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:db 1.5s infinite;}
.dot.r{background:#ff2244;animation-delay:.5s;}.dot.y{background:#ffd600;animation-delay:1s;}
@keyframes db{0%,100%{opacity:1}50%{opacity:.3}}
#ctr{position:relative;z-index:5;text-align:center;opacity:0;animation:cn .8s cubic-bezier(.16,1,.3,1) 2s forwards;}
@keyframes cn{0%{opacity:0;transform:scale(.85)}100%{opacity:1;transform:scale(1)}}
.gw{position:relative;display:inline-block;margin-bottom:16px;}
.gi{font-size:64px;display:block;filter:drop-shadow(0 0 30px rgba(0,255,136,.8));animation:gfl 3s ease-in-out infinite 2s;}
@keyframes gfl{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.orb{position:absolute;border:1px solid rgba(0,255,136,.15);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);}
.orb1{width:100px;height:100px;animation:os 4s linear infinite 2s;}
.orb2{width:140px;height:140px;animation:os 7s linear reverse infinite 2s;border-style:dashed;}
@keyframes os{to{transform:translate(-50%,-50%) rotate(360deg)}}
.od{position:absolute;width:5px;height:5px;background:#00ff88;border-radius:50%;top:-2px;left:50%;transform:translateX(-50%);box-shadow:0 0 8px #00ff88;}
.mt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(24px,7vw,52px);letter-spacing:8px;color:#00ffaa;text-shadow:0 0 30px rgba(0,255,136,.6);position:relative;}
.mt::before{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#ff0044;opacity:0;animation:gr 5s infinite 3s;clip-path:polygon(0 20%,100% 20%,100% 40%,0 40%);}
.mt::after{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#00e5ff;opacity:0;animation:gb 5s infinite 3.1s;clip-path:polygon(0 60%,100% 60%,100% 80%,0 80%);}
@keyframes gr{0%,92%,100%{opacity:0}93%{opacity:.8;transform:translate(-4px,0)}94%{opacity:0}95%{opacity:.8;transform:translate(-2px,0)}96%{opacity:0}}
@keyframes gb{0%,92%,100%{opacity:0}93%{opacity:.8;transform:translate(4px,0)}94%{opacity:0}95%{opacity:.8;transform:translate(2px,0)}96%{opacity:0}}
.vt{display:inline-block;background:rgba(0,255,100,.06);border:1px solid rgba(0,255,100,.18);border-radius:2px;padding:3px 12px;font-size:9px;color:#00aa55;letter-spacing:5px;margin-top:8px;}
#pw{margin-top:22px;width:min(340px,70vw);opacity:0;animation:fu .4s ease 2.5s forwards;}
.ph{display:flex;justify-content:space-between;font-size:9px;color:#1a4a2a;margin-bottom:5px;letter-spacing:2px;}
.pt2{background:rgba(0,255,100,.04);border:1px solid #0a2015;border-radius:2px;height:8px;overflow:hidden;}
.pf{height:100%;width:0%;background:linear-gradient(90deg,#002a14,#00aa55,#00ffaa);}
.sps{margin-top:6px;display:flex;flex-direction:column;gap:3px;}
.sr{display:flex;align-items:center;gap:8px;font-size:7px;color:#1a3a2a;}
.sl{width:80px;text-align:right;}.sts{flex:1;height:3px;background:rgba(0,255,100,.04);border-radius:1px;overflow:hidden;}
.sf{height:100%;width:0%;transition:width 1s;border-radius:1px;}
.sf.g{background:#00cc77;}.sf.c{background:#00e5ff;}.sf.y{background:#ffd600;}.sf.p{background:#c264fe;}
.sp{width:26px;color:#00aa44;font-size:7px;}
#bs{margin-top:10px;font-size:10px;color:#00aa44;letter-spacing:2px;text-align:center;min-height:16px;opacity:0;animation:fu .3s ease 2.8s forwards;}
#ag{position:fixed;inset:0;z-index:50;background:#000;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;}
.agb{border:2px solid #00ff88;padding:28px 50px;text-align:center;box-shadow:0 0 60px rgba(0,255,136,.4);}
.agi{font-size:44px;margin-bottom:10px;}
.agt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(16px,5vw,32px);letter-spacing:8px;color:#00ffaa;}
.ags{font-size:10px;color:#00aa55;letter-spacing:4px;margin-top:6px;}
#sk{position:fixed;bottom:18px;right:18px;z-index:100;background:rgba(0,255,100,.04);border:1px solid rgba(0,255,100,.12);border-radius:3px;color:rgba(0,255,100,.25);font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;padding:5px 12px;cursor:pointer;}
#lw{position:fixed;inset:0;z-index:8;display:none;align-items:center;justify-content:center;background:rgba(3,5,10,.97);}
#lw.show{display:flex;}
.lc{background:#0a1520;border:1px solid #0d2a1a;border-radius:8px;padding:36px 28px 32px;width:100%;max-width:360px;position:relative;overflow:hidden;margin:20px;}
.lc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#00ffaa,#00cc77,#00ffaa,transparent);}
.ll{text-align:center;margin-bottom:24px;}
.li{font-size:36px;margin-bottom:10px;}
.lh{font-family:'Orbitron',monospace;font-weight:900;font-size:18px;letter-spacing:6px;background:linear-gradient(135deg,#00ffaa,#00e5ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.lp{font-size:9px;color:#2a4a35;letter-spacing:4px;margin-top:5px;}
.lf{margin-bottom:14px;}
.lf label{display:block;font-size:9px;color:#2a4a35;letter-spacing:3px;margin-bottom:6px;}
.lf input{width:100%;background:rgba(0,255,100,.03);border:1px solid #0d2a1a;border-radius:4px;color:#00ffaa;font-family:'Share Tech Mono',monospace;font-size:14px;padding:12px 14px;outline:none;transition:border-color .2s;}
.lf input:focus{border-color:#00cc77;}
.lb{width:100%;padding:15px;margin-top:6px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid #00cc77;border-radius:6px;color:#00ffaa;font-family:'Orbitron',monospace;font-weight:900;font-size:13px;letter-spacing:5px;cursor:pointer;position:relative;overflow:hidden;}
.lb::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,.1),transparent);transform:skewX(-20deg);animation:sh 3s infinite;}
@keyframes sh{0%{left:-60%}100%{left:160%}}
.lb:disabled{opacity:.4;cursor:not-allowed;}
.le{display:none;background:rgba(255,34,68,.08);border:1px solid rgba(255,34,68,.25);border-radius:4px;color:#ff2244;font-size:11px;padding:10px;margin-top:10px;text-align:center;}
.le.show{display:block;}
</style>
</head>
<body>
<div class="cur" id="cur"></div>
<canvas id="cv"></canvas>
<div id="sl"></div>
<div id="intro">
  <div class="ring"></div><div class="ring"></div><div class="ring"></div><div class="ring"></div>
  <div class="co tl"></div><div class="co tr"></div><div class="co bl"></div><div class="co br"></div>
  <div id="tb"><div class="dot"></div>SYSTEM ONLINE<span style="color:#0d3a1a">|</span><div class="dot y"></div>AES-256<span style="color:#0d3a1a">|</span><div class="dot r"></div>BYPASSED</div>
  <div id="ctr">
    <div class="gw">
      <div class="orb orb1"><div class="od"></div></div>
      <div class="orb orb2"><div class="od"></div></div>
      <span class="gi">💎</span>
    </div>
    <div class="mt">DC25 FARMER</div>
    <div class="vt">TOKEN SECURE · v4.2</div>
    <div id="pw">
      <div class="ph"><span id="pl">INITIALIZING...</span><span id="pn">0%</span></div>
      <div class="pt2"><div class="pf" id="pfl"></div></div>
      <div class="sps">
        <div class="sr"><span class="sl">CORE ENGINE</span><div class="sts"><div class="sf g" id="s1"></div></div><span class="sp" id="s1p">0%</span></div>
        <div class="sr"><span class="sl">NETWORK</span><div class="sts"><div class="sf c" id="s2"></div></div><span class="sp" id="s2p">0%</span></div>
        <div class="sr"><span class="sl">TOKEN VAULT</span><div class="sts"><div class="sf y" id="s3"></div></div><span class="sp" id="s3p">0%</span></div>
        <div class="sr"><span class="sl">AUTO-PING</span><div class="sts"><div class="sf p" id="s4"></div></div><span class="sp" id="s4p">0%</span></div>
      </div>
    </div>
    <div id="bs">▌</div>
  </div>
</div>
<div id="ag"><div class="agb"><div class="agi">🔓</div><div class="agt">ACCESS GRANTED</div><div class="ags">WELCOME · KING SHAHI</div></div></div>
<div id="lw">
  <div class="lc">
    <div class="ll"><div class="li">💎</div><div class="lh">DC25 FARMER</div><div class="lp">SECURE ACCESS REQUIRED</div></div>
    <div class="lf"><label>EMAIL ADDRESS</label><input type="email" id="em" placeholder="your@email.com" autocomplete="email"/></div>
    <div class="lf"><label>PASSWORD</label><input type="password" id="pw2" placeholder="••••••••" autocomplete="current-password"/></div>
    <button class="lb" id="lb" onclick="doLogin()">▶ LOGIN</button>
    <div class="le" id="le"></div>
  </div>
</div>
<button id="sk" onclick="skipAll()">SKIP ▶▶</button>
<script>
const cur=document.getElementById('cur');
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px';});
const cv=document.getElementById('cv'),cx=cv.getContext('2d');
cv.width=window.innerWidth;cv.height=window.innerHeight;
const cols=Math.floor(cv.width/14),drops=Array(cols).fill(1);
const CH='ｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵｶｷｸｺｻｼｽｾｿﾀﾁﾃﾄﾅﾆﾇﾈﾊﾋﾌﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEF<>{}[]';
function drawM(){cx.fillStyle='rgba(0,0,0,0.055)';cx.fillRect(0,0,cv.width,cv.height);drops.forEach((y,i)=>{const c=CH[Math.floor(Math.random()*CH.length)];const r=Math.random();cx.fillStyle=r>.97?'#fff':r>.85?'#00ffaa':r>.6?'#00994d':'#003322';cx.font=(r>.97?'bold ':'')+  '13px Share Tech Mono';cx.fillText(c,i*14,y*14);if(y*14>cv.height&&Math.random()>.975)drops[i]=0;drops[i]++;});}
const mI=setInterval(drawM,45);
let pct=0,li=0;
const lbls=['LOADING...','NETWORK...','TOKEN VAULT...','PING...','READY'];
const pfl=document.getElementById('pfl'),pn=document.getElementById('pn'),plbl=document.getElementById('pl'),bsEl=document.getElementById('bs');
setTimeout(()=>{const iv=setInterval(()=>{pct+=Math.random()*4+0.5;if(pct>=100){pct=100;clearInterval(iv);setTimeout(showAG,300);}pfl.style.width=pct+'%';pn.textContent=Math.floor(pct)+'%';const nl=Math.floor((pct/100)*lbls.length);if(nl!==li&&nl<lbls.length){li=nl;plbl.textContent=lbls[li];bsEl.textContent='> '+lbls[li];}[['s1','s1p'],['s2','s2p'],['s3','s3p'],['s4','s4p']].forEach(([id,pid],i)=>{const v=Math.min(100,Math.max(0,(pct-i*25)*4));document.getElementById(id).style.width=v+'%';document.getElementById(pid).textContent=Math.floor(v)+'%';});},55);},2200);
function showAG(){const ag=document.getElementById('ag');ag.style.opacity='1';ag.style.pointerEvents='auto';let f=0;const iv=setInterval(()=>{f++;ag.style.background=f%2===0?'#000':'rgba(0,255,100,.04)';if(f>=6){clearInterval(iv);setTimeout(showLogin,500);}},130);}
function showLogin(){const intro=document.getElementById('intro'),ag=document.getElementById('ag'),sk=document.getElementById('sk'),lw=document.getElementById('lw');[intro,ag].forEach(el=>{el.style.transition='opacity 0.7s';el.style.opacity='0';});sk.style.display='none';clearInterval(mI);setTimeout(()=>{intro.style.display='none';ag.style.display='none';lw.classList.add('show');document.getElementById('em').focus();},750);}
function skipAll(){showLogin();}
document.addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
async function doLogin(){
  const em=document.getElementById('em').value.trim(),pw=document.getElementById('pw2').value.trim();
  const btn=document.getElementById('lb');
  if(!em||!pw){showE('Email aur password required!');return;}
  btn.disabled=true;btn.textContent='VERIFYING...';
  document.getElementById('le').classList.remove('show');
  try{const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em,password:pw})});const d=await r.json();if(d.ok){window.location.reload();}else{showE(d.error||'Access denied!');}}catch(e){showE('Connection error!');}
  btn.disabled=false;btn.textContent='▶ LOGIN';
}
function showE(m){const e=document.getElementById('le');e.textContent=m;e.classList.add('show');}
window.addEventListener('resize',()=>{cv.width=window.innerWidth;cv.height=window.innerHeight;});
</script>
</body>
</html>"""

MAIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 ULTRA FARMER v4.2</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#03050a;--panel:#0a1520;--border:#0d2a1a;--g1:#00ffaa;--g2:#00cc77;--g3:#004422;--cyan:#00e5ff;--red:#ff2244;--yellow:#ffd600;--purple:#c264fe;--orange:#ff8c00;--text:#a8ffd0;--dim:#2a4a35;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 20% 0%,rgba(0,255,100,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(0,200,255,.03) 0%,transparent 60%),repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,255,100,.012) 40px,rgba(0,255,100,.012) 41px);pointer-events:none;z-index:0;}
body::after{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.15) 3px,rgba(0,0,0,.15) 4px);pointer-events:none;z-index:1;}
.wrap{position:relative;z-index:2;}
.hdr{padding:18px 20px 16px;text-align:center;border-bottom:1px solid var(--border);position:relative;}
.hdr::after{content:'';position:absolute;bottom:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--g1),var(--cyan),var(--g1),transparent);}
.hdr-badge{display:inline-block;background:rgba(0,255,100,.08);border:1px solid var(--g3);border-radius:2px;padding:2px 10px;font-size:10px;letter-spacing:4px;color:var(--g2);margin-bottom:6px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(16px,5vw,30px);letter-spacing:6px;background:linear-gradient(135deg,var(--g1),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr p{color:var(--dim);font-size:9px;letter-spacing:3px;margin-top:3px;}
.logout-btn{position:absolute;top:16px;right:14px;background:transparent;border:1px solid rgba(255,34,68,.3);border-radius:3px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:10px;padding:4px 9px;cursor:pointer;}
.ping-badge{position:absolute;top:18px;left:14px;display:flex;align-items:center;gap:5px;font-size:9px;color:var(--g2);letter-spacing:1px;}
.ping-dot{width:6px;height:6px;border-radius:50%;background:var(--g1);animation:pd 2s infinite;}
@keyframes pd{0%,100%{opacity:1;box-shadow:0 0 4px var(--g1);}50%{opacity:.4;box-shadow:none;}}
#activeBanner{display:none;background:rgba(0,255,100,.06);border:1px solid var(--g2);border-radius:6px;padding:12px 16px;margin:12px 14px 0;}
#activeBanner.show{display:block;}
.ab-title{font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;color:var(--g1);margin-bottom:8px;}
.ab-row{display:flex;justify-content:space-between;align-items:center;gap:10px;}
.ab-info{font-size:11px;color:var(--text);}
.ab-stop{background:rgba(255,34,68,.1);border:1px solid var(--red);border-radius:4px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:11px;padding:5px 12px;cursor:pointer;white-space:nowrap;}
.ab-bar{margin-top:6px;background:rgba(0,255,100,.05);border:1px solid var(--border);border-radius:2px;height:5px;overflow:hidden;}
.ab-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));transition:width .5s;}
.page{max-width:680px;margin:0 auto;padding:12px 14px 40px;display:flex;flex-direction:column;gap:12px;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:16px;position:relative;overflow:hidden;}
.cg{position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g2),transparent);}
.cg.c{background:linear-gradient(90deg,transparent,var(--cyan),transparent);}
.cg.p{background:linear-gradient(90deg,transparent,var(--purple),transparent);}
.cg.o{background:linear-gradient(90deg,transparent,var(--orange),transparent);}
.sec{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:4px;color:var(--dim);margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}

/* ── TOKEN VAULT SECTION ── */
.tok-section{position:relative;}
/* Normal textarea */
#tokArea{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:12px;padding:10px;outline:none;resize:none;height:78px;transition:border-color .2s,opacity .3s;}
#tokArea:focus{border-color:var(--g2);}

/* Secure vault — shown after job starts */
#tokVault{
  display:none;
  height:78px;
  background:rgba(0,255,100,.02);
  border:1px solid rgba(0,255,100,.2);
  border-radius:4px;
  position:relative;
  overflow:hidden;
  align-items:center;
  justify-content:center;
  flex-direction:column;
  gap:6px;
  cursor:pointer;
}
#tokVault.show{display:flex;}
/* Matrix canvas inside vault */
#vaultCanvas{position:absolute;inset:0;opacity:0.18;}
.vault-content{position:relative;z-index:2;text-align:center;}
.vault-icon{font-size:26px;margin-bottom:4px;animation:vPulse 2s infinite;}
@keyframes vPulse{0%,100%{filter:drop-shadow(0 0 6px rgba(0,255,136,.6));}50%{filter:drop-shadow(0 0 18px rgba(0,255,136,1));}}
.vault-title{font-family:'Orbitron',monospace;font-size:11px;letter-spacing:4px;color:var(--g1);text-shadow:0 0 10px rgba(0,255,136,.5);}
.vault-sub{font-size:9px;color:var(--dim);letter-spacing:2px;margin-top:3px;}
.vault-dots{display:flex;gap:4px;justify-content:center;margin-top:6px;}
.vault-dot{width:5px;height:5px;border-radius:50%;background:var(--g3);animation:vd 1.5s infinite;}
.vault-dot:nth-child(2){animation-delay:.2s;}
.vault-dot:nth-child(3){animation-delay:.4s;}
.vault-dot:nth-child(4){animation-delay:.6s;}
.vault-dot:nth-child(5){animation-delay:.8s;}
@keyframes vd{0%,100%{background:var(--g3);}50%{background:var(--g1);box-shadow:0 0 6px var(--g1);}}
/* Scanning line on vault */
.vault-scan{position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g1),transparent);animation:vScan 2s linear infinite;opacity:0.4;}
@keyframes vScan{0%{top:0;}100%{top:100%;}}
.tok-hint{font-size:9px;color:var(--dim);margin-top:5px;letter-spacing:1px;}

.mode-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.mode-btn{padding:12px 10px;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:5px;cursor:pointer;transition:all .2s;text-align:center;}
.mode-btn.active.gems{border-color:var(--g1);background:rgba(0,255,100,.08);}
.mode-btn.active.tickets{border-color:var(--orange);background:rgba(255,140,0,.08);}
.mi{font-size:26px;margin-bottom:4px;}
.ml{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;color:var(--dim);}
.mode-btn.active.gems .ml{color:var(--g1);}
.mode-btn.active.tickets .ml{color:var(--orange);}
.ms{font-size:9px;color:var(--dim);margin-top:2px;}
.cfg-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.cfg-item label{display:block;font-size:9px;letter-spacing:3px;color:var(--dim);margin-bottom:6px;}
input[type=number]{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:16px;padding:10px 12px;outline:none;}
.hint{font-size:10px;color:var(--dim);margin-top:4px;}
.presets{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;}
.pw{flex:1;min-width:38px;background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:12px;padding:6px 4px;cursor:pointer;transition:all .15s;text-align:center;}
.pw:hover,.pw.on{border-color:var(--g1);color:var(--g1);background:rgba(0,255,100,.08);}
.pw.hot{border-color:var(--red)!important;color:var(--red)!important;background:rgba(255,34,68,.08)!important;}
.btn-start{width:100%;padding:16px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid var(--g2);border-radius:6px;color:var(--g1);font-family:'Orbitron',monospace;font-weight:900;font-size:13px;letter-spacing:5px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;text-shadow:0 0 15px rgba(0,255,100,.6);}
.btn-start.tm{background:linear-gradient(135deg,#2a1400,#503000,#3a1c00);border-color:var(--orange);color:var(--orange);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,.12),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){transform:translateY(-2px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-stop{width:100%;padding:12px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:14px;letter-spacing:4px;cursor:pointer;transition:all .2s;display:none;}
.prog-card{display:none;}.prog-card.show{display:block;}
.prog-top{display:flex;align-items:center;gap:18px;margin-bottom:14px;}
.ring-wrap{position:relative;width:84px;height:84px;flex-shrink:0;}
.ring-wrap svg{width:84px;height:84px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:var(--border);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s;}
.ring-fg.t{stroke:url(#rgt);}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:14px;font-weight:900;color:var(--g1);}
.ring-pct.t{color:var(--orange);}
.prog-info{flex:1;}
.plbl{font-size:10px;color:var(--dim);letter-spacing:2px;margin-bottom:3px;}
.pval{font-family:'Orbitron',monospace;font-size:22px;font-weight:700;color:var(--g1);}
.pval.t{color:var(--orange);}
.psub{font-size:11px;color:var(--dim);margin-top:2px;}
.bar-wrap{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:3px;height:10px;overflow:hidden;margin-bottom:12px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));width:0%;transition:width .4s;box-shadow:0 0 10px rgba(0,255,100,.4);}
.bar-fill.t{background:linear-gradient(90deg,#3a1c00,#995500,#ff8c00);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.stat{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;padding:9px 6px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(12px,3vw,17px);font-weight:700;color:var(--g1);}
.sv.c{color:var(--cyan);}.sv.y{color:var(--yellow);}.sv.r{color:var(--red);}
.sl2{font-size:8px;color:var(--dim);letter-spacing:2px;margin-top:2px;}
.graph-wrap{margin-top:10px;}
.glbl{font-size:9px;color:var(--dim);letter-spacing:3px;margin-bottom:5px;}
.graph{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:3px;height:46px;overflow:hidden;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:3px 3px 0;}
.gb{flex:1;min-width:3px;background:linear-gradient(to top,var(--g3),var(--g2));border-radius:1px 1px 0 0;}
.gb.t{background:linear-gradient(to top,#3a1c00,#ff8c00);}
.st{text-align:center;font-size:10px;color:var(--dim);letter-spacing:1px;margin-top:8px;min-height:14px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--g1);}.st.r{color:var(--red);}
.done-card{display:none;text-align:center;padding:20px;background:rgba(0,255,100,.04);border:1px solid var(--g2);border-radius:6px;animation:glo 2s infinite;}
.done-card.t{background:rgba(255,140,0,.04);border-color:var(--orange);}
@keyframes glo{0%,100%{box-shadow:0 0 15px rgba(0,255,100,.1);}50%{box-shadow:0 0 40px rgba(0,255,100,.25);}}
.done-icon{font-size:34px;margin-bottom:8px;}
.done-title{font-family:'Orbitron',monospace;font-size:16px;letter-spacing:6px;color:var(--g1);}
.done-title.t{color:var(--orange);}
.done-sub{font-size:12px;color:var(--dim);margin-top:6px;line-height:1.8;}
.done-countdown{margin-top:12px;background:rgba(0,255,100,.05);border:1px solid var(--border);border-radius:2px;height:4px;overflow:hidden;}
.done-cd-fill{height:100%;background:var(--g2);width:100%;}
.done-cd-txt{font-size:9px;color:var(--dim);margin-top:5px;letter-spacing:2px;}
.sess-list{display:flex;flex-direction:column;gap:8px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(0,255,100,.02);border:1px solid var(--border);border-radius:4px;padding:9px 12px;}
.si.t{background:rgba(255,140,0,.02);border-color:rgba(255,140,0,.15);}
.si-r{font-family:'Orbitron',monospace;font-size:15px;font-weight:700;color:var(--g1);}
.si-r.t{color:var(--orange);}
.si-m{font-size:10px;color:var(--dim);}
.si-tm{font-size:9px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:12px;letter-spacing:2px;padding:10px;}
.blink{animation:bl 1s step-end infinite;}
@keyframes bl{0%,100%{opacity:1;}50%{opacity:0;}}
.bg-notice{background:rgba(0,229,255,.04);border:1px solid rgba(0,229,255,.15);border-radius:4px;padding:8px 12px;font-size:10px;color:#00e5ff;letter-spacing:1px;text-align:center;margin-top:4px;}
</style>
</head>
<body>
<div class="wrap">
<div class="hdr">
  <div class="ping-badge"><div class="ping-dot"></div>AUTO-PING</div>
  <div class="hdr-badge">DREAM CRICKET 25</div>
  <h1>ULTRA FARMER v4.2</h1>
  <p>💎 GEMS · 🎫 TICKETS · 🔒 TOKEN VAULT · BG JOBS</p>
  <button class="logout-btn" onclick="doLogout()">⏻ LOGOUT</button>
</div>

<div id="activeBanner">
  <div class="ab-title">⚡ JOB RUNNING IN BACKGROUND</div>
  <div class="ab-row">
    <div class="ab-info" id="abInfo">Loading...</div>
    <button class="ab-stop" onclick="emergencyStop()">⛔ STOP NOW</button>
  </div>
  <div class="ab-bar"><div class="ab-fill" id="abFill"></div></div>
</div>

<div class="page">

  <!-- TOKEN VAULT CARD -->
  <div class="card">
    <div class="cg"></div>
    <div class="sec">// BEARER TOKEN</div>
    <div class="tok-section">
      <!-- Normal input -->
      <textarea id="tokArea" placeholder="Paste Bearer token here..."></textarea>
      <!-- Vault (shown after job starts) -->
      <div id="tokVault" onclick="showTokenReveal()">
        <canvas id="vaultCanvas"></canvas>
        <div class="vault-scan"></div>
        <div class="vault-content">
          <div class="vault-icon">🔒</div>
          <div class="vault-title">TOKEN SECURED</div>
          <div class="vault-sub">Tap to reveal</div>
          <div class="vault-dots">
            <div class="vault-dot"></div>
            <div class="vault-dot"></div>
            <div class="vault-dot"></div>
            <div class="vault-dot"></div>
            <div class="vault-dot"></div>
          </div>
        </div>
      </div>
      <div class="tok-hint" id="tokHint">Token yahan paste karo — job shuru hone ke baad auto-hide ho jaega 🔒</div>
    </div>
  </div>

  <!-- Mode -->
  <div class="card">
    <div class="cg o"></div><div class="sec">// SELECT MODE</div>
    <div class="mode-row">
      <div class="mode-btn active gems" id="mG" onclick="setMode('gems')"><div class="mi">💎</div><div class="ml">GEMS</div><div class="ms">+2 per click</div></div>
      <div class="mode-btn tickets" id="mT" onclick="setMode('tickets')"><div class="mi">🎫</div><div class="ml">WORLD CUP</div><div class="ms">+30 per click</div></div>
    </div>
  </div>

  <!-- Config -->
  <div class="card">
    <div class="cg c"></div><div class="sec">// CONFIGURATION</div>
    <div class="cfg-row">
      <div class="cfg-item"><label id="dLabel">💎 DESIRED GEMS</label><input type="number" id="desired" value="5000" min="2" step="2"/><div class="hint" id="hTxt">1 click = 2 gems</div></div>
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
    <div class="bg-notice">🔁 Phone/browser band karo — job server pe chalta rahega!</div>
  </div>

  <button class="btn-start" id="btnS" onclick="go()">▶ LAUNCH BACKGROUND JOB</button>
  <button class="btn-stop" id="btnX" onclick="stopJob()">■ STOP JOB</button>

  <!-- Progress -->
  <div class="card prog-card" id="progCard">
    <div class="cg"></div><div class="sec">// LIVE PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#00cc77"/><stop offset="100%" style="stop-color:#00ffaa"/></linearGradient>
            <linearGradient id="rgt" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#995500"/><stop offset="100%" style="stop-color:#ff8c00"/></linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="ring" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpct">0%</div>
      </div>
      <div class="prog-info">
        <div class="plbl" id="rLabel">GEMS ADDED</div>
        <div class="pval" id="pR">0</div>
        <div class="psub" id="pClicks">0 / 0 clicks</div>
      </div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpd">0</div><div class="sl2">REQ/SEC</div></div>
      <div class="stat"><div class="sv y" id="sEta">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv" id="sOk">0</div><div class="sl2">SUCCESS</div></div>
      <div class="stat"><div class="sv r" id="sFail">0</div><div class="sl2">FAILED</div></div>
    </div>
    <div class="graph-wrap"><div class="glbl">// SPEED GRAPH</div><div class="graph"><div class="gbars" id="gBars"></div></div></div>
    <div class="st" id="stLine"><span class="blink">_</span> Ready</div>
  </div>

  <div class="done-card" id="doneCard">
    <div class="done-icon" id="dIcon">💎</div>
    <div class="done-title" id="dTitle">JOB COMPLETE</div>
    <div class="done-sub" id="dSub"></div>
    <div class="done-countdown"><div class="done-cd-fill" id="cdFill"></div></div>
    <div class="done-cd-txt" id="cdTxt">Auto-clear in 20s...</div>
  </div>

  <div class="card">
    <div class="cg p"></div><div class="sec">// YOUR JOB HISTORY (last 10)</div>
    <div class="sess-list" id="hist"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div>
  </div>
</div>
</div>

<script>
const CIRC=245;
let poll=null,currentMode='gems',currentJobId='',currentUid='';
let vaultCv,vaultCx,vaultDrops,vaultInterval;

// Vault mini-matrix
function initVaultMatrix(){
  vaultCv=document.getElementById('vaultCanvas');
  const wrap=document.getElementById('tokVault');
  vaultCv.width=wrap.offsetWidth;
  vaultCv.height=wrap.offsetHeight;
  vaultCx=vaultCv.getContext('2d');
  const cols=Math.floor(vaultCv.width/10);
  vaultDrops=Array(cols).fill(1);
  const CH='01アイウカキクサシスタチナニハヒABCDEF<>{};';
  function draw(){
    vaultCx.fillStyle='rgba(0,0,0,0.08)';
    vaultCx.fillRect(0,0,vaultCv.width,vaultCv.height);
    vaultDrops.forEach((y,i)=>{
      const c=CH[Math.floor(Math.random()*CH.length)];
      vaultCx.fillStyle=Math.random()>.9?'#00ffaa':'#00441a';
      vaultCx.font='9px Share Tech Mono';
      vaultCx.fillText(c,i*10,y*10);
      if(y*10>vaultCv.height&&Math.random()>.97)vaultDrops[i]=0;
      vaultDrops[i]++;
    });
  }
  vaultInterval=setInterval(draw,60);
}

function lockToken(){
  document.getElementById('tokArea').style.display='none';
  document.getElementById('tokVault').classList.add('show');
  document.getElementById('tokHint').textContent='🔒 Token secured — tap vault to reveal';
  initVaultMatrix();
}

function unlockToken(){
  document.getElementById('tokArea').style.display='block';
  document.getElementById('tokVault').classList.remove('show');
  document.getElementById('tokHint').textContent='Token yahan paste karo — job shuru hone ke baad auto-hide ho jaega 🔒';
  if(vaultInterval)clearInterval(vaultInterval);
}

function showTokenReveal(){
  // Briefly show token for 3 seconds then re-lock
  const tok=document.getElementById('tokArea');
  document.getElementById('tokVault').classList.remove('show');
  if(vaultInterval)clearInterval(vaultInterval);
  tok.style.display='block';
  tok.style.filter='blur(4px)';
  setTimeout(()=>tok.style.filter='none',200);
  document.getElementById('tokHint').textContent='👁 Token visible — 3 sec mein re-lock hoga...';
  setTimeout(()=>{
    if(currentJobId){lockToken();}
  },3000);
}

// On page load — check active job
window.addEventListener('load',async()=>{
  try{
    const r=await fetch('/active');
    const d=await r.json();
    if(d.has_active){
      currentJobId=d.job_id;
      currentUid=d.uid||'';
      showActiveBanner(d);
      document.getElementById('progCard').classList.add('show');
      lockToken();
      if(poll)clearInterval(poll);
      poll=setInterval(tick,800);
    }
  }catch(e){}
});

function showActiveBanner(d){
  document.getElementById('activeBanner').classList.add('show');
  const isT=d.unit==='Tickets';
  document.getElementById('abInfo').textContent=`${isT?'🎫':'💎'} ${d.reward} ${d.unit} · ${d.completed}/${d.total} clicks · ${fmt(d.elapsed)} elapsed`;
  document.getElementById('abFill').style.width=(d.pct||0)+'%';
}
function hideActiveBanner(){document.getElementById('activeBanner').classList.remove('show');}

let clearTimer=null;
function startAutoClear(){
  const fill=document.getElementById('cdFill');
  const txt=document.getElementById('cdTxt');
  const SECS=20;
  fill.style.transition='none';
  fill.style.width='100%';
  let remaining=SECS;
  setTimeout(()=>{fill.style.transition=`width ${SECS}s linear`;fill.style.width='0%';},100);
  clearTimer=setInterval(()=>{
    remaining--;
    txt.textContent=`Auto-clear in ${remaining}s...`;
    if(remaining<=0){clearInterval(clearTimer);autoClearDone();}
  },1000);
}

function autoClearDone(){
  document.getElementById('doneCard').style.display='none';
  document.getElementById('progCard').classList.remove('show');
  ring(0,false);
  document.getElementById('bar').style.width='0%';
  document.getElementById('pR').textContent='0';
  document.getElementById('pClicks').textContent='0 / 0 clicks';
  ['sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';
  document.getElementById('gBars').innerHTML='';
  setSt('Ready','');
  unlockToken();
  currentJobId='';
}

function setMode(m){
  currentMode=m;
  const isT=m==='tickets';
  document.getElementById('mG').className='mode-btn'+(m==='gems'?' active gems':' gems');
  document.getElementById('mT').className='mode-btn'+(m==='tickets'?' active tickets':' tickets');
  document.getElementById('dLabel').textContent=isT?'🎫 DESIRED TICKETS':'💎 DESIRED GEMS';
  document.getElementById('hTxt').textContent=isT?'1 click = 30 tickets':'1 click = 2 gems';
  document.getElementById('desired').value=isT?'300':'5000';
  document.getElementById('desired').step=isT?'30':'2';
  const btn=document.getElementById('btnS');
  btn.textContent=isT?'▶ LAUNCH TICKET JOB':'▶ LAUNCH BACKGROUND JOB';
  btn.className='btn-start'+(isT?' tm':'');
}

function sw(v){document.getElementById('wrk').value=v;document.querySelectorAll('.pw').forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));}
function fmt(s){s=Math.max(0,Math.round(s));if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';}
function ring(p,isT){document.getElementById('ring').style.strokeDashoffset=CIRC-(CIRC*p/100);document.getElementById('ring').className='ring-fg'+(isT?' t':'');document.getElementById('rpct').textContent=p.toFixed(1)+'%';document.getElementById('rpct').className='ring-pct'+(isT?' t':'');}
function graph(h,isT){const w=document.getElementById('gBars');if(!h.length)return;const mx=Math.max(...h,1);w.innerHTML=h.map(v=>`<div class="gb${isT?' t':''}" style="height:${Math.max(3,(v/mx)*40)}px"></div>`).join('');}
function renderHist(list){
  const el=document.getElementById('hist');
  if(!list.length){el.innerHTML='<div class="empty">NO JOBS YET <span class="blink">_</span></div>';return;}
  el.innerHTML=list.map(s=>{
    const isT=s.unit==='Tickets';
    return `<div class="si${isT?' t':''}">
      <div><div class="si-r${isT?' t':''}">+${s.reward} ${s.label}</div>
      <div class="si-m">${s.success}/${s.total} · ${s.workers}w</div></div>
      <div class="si-tm">${s.time} ${s.date}<br/>${fmt(s.elapsed)}</div>
    </div>`;
  }).join('');
}
function setSt(m,c){const e=document.getElementById('stLine');e.textContent=m;e.className='st '+(c||'');}

async function go(){
  const tok=document.getElementById('tokArea').value.trim();
  const desired=parseInt(document.getElementById('desired').value);
  const wrk=parseInt(document.getElementById('wrk').value);
  if(!tok){alert('Token paste karo!');return;}
  if(desired<1){alert('Amount enter karo!');return;}
  const isT=currentMode==='tickets';
  if(clearTimer)clearInterval(clearTimer);
  document.getElementById('doneCard').style.display='none';
  setSt('Starting background job...','g');
  const res=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:tok,desired,workers:wrk,mode:currentMode})});
  const data=await res.json();
  if(data.error){alert(data.error);setSt('','');return;}
  currentJobId=data.job_id;
  currentUid=data.uid||'';

  // 🔒 Lock token immediately!
  lockToken();

  document.getElementById('progCard').classList.add('show');
  document.getElementById('btnS').disabled=true;
  document.getElementById('btnX').style.display='block';
  ring(0,isT);
  document.getElementById('bar').style.width='0%';
  document.getElementById('bar').className='bar-fill'+(isT?' t':'');
  document.getElementById('pR').textContent='0';
  document.getElementById('pR').className='pval'+(isT?' t':'');
  document.getElementById('rLabel').textContent=isT?'TICKETS ADDED':'GEMS ADDED';
  ['sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';
  document.getElementById('pClicks').textContent='0 / 0 clicks';
  document.getElementById('gBars').innerHTML='';
  setSt(`BG Job started · ${data.clicks} clicks · ${wrk} workers`,'g');
  if(poll)clearInterval(poll);
  poll=setInterval(tick,800);
}

async function tick(){
  try{
    const r=await fetch(`/status?job_id=${currentJobId}&uid=${currentUid}`);
    if(r.status===401){clearInterval(poll);window.location.reload();return;}
    const d=await r.json();
    const isT=d.unit==='Tickets';
    ring(d.pct,isT);
    document.getElementById('bar').style.width=d.pct+'%';
    document.getElementById('bar').className='bar-fill'+(isT?' t':'');
    document.getElementById('pR').textContent=d.reward;
    document.getElementById('pClicks').textContent=`${d.completed}/${d.total} clicks`;
    document.getElementById('sSpd').textContent=d.speed;
    document.getElementById('sEta').textContent=fmt(d.eta);
    document.getElementById('sOk').textContent=d.success;
    document.getElementById('sFail').textContent=d.fail;
    graph(d.speed_history,isT);
    renderHist(d.history);
    if(d.has_active){
      showActiveBanner(d);
      setSt(`${d.completed}/${d.total} · ${fmt(d.elapsed)} elapsed · server pe chal raha hai ✓`,'g');
    }
    if(d.done){
      clearInterval(poll);
      resetUI();
      hideActiveBanner();
      ring(100,isT);
      document.getElementById('bar').style.width='100%';
      const dc=document.getElementById('doneCard');
      dc.style.display='block';
      dc.className='done-card'+(isT?' t':'');
      document.getElementById('dIcon').textContent=isT?'🎫':'💎';
      document.getElementById('dTitle').className='done-title'+(isT?' t':'');
      const col=isT?'var(--orange)':'var(--g1)';
      document.getElementById('dSub').innerHTML=`<strong style="color:${col}">+${d.reward} ${d.unit}</strong> added!<br/>${d.success}/${d.total} success · ${fmt(d.elapsed)} total`;
      setSt('Job complete! ✅','g');
      startAutoClear();
    }
  }catch(e){setSt('Reconnecting...','');}
}

async function stopJob(){
  await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:currentJobId})});
  clearInterval(poll);setSt('Job stopped.','r');resetUI();hideActiveBanner();unlockToken();currentJobId='';
}
async function emergencyStop(){
  if(!confirm('Job stop karna hai?'))return;
  await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:currentJobId})});
  clearInterval(poll);setSt('⛔ Emergency stop!','r');resetUI();hideActiveBanner();unlockToken();currentJobId='';
}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}
function resetUI(){document.getElementById('btnS').disabled=false;document.getElementById('btnX').style.display='none';}
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"\033[92m")
    print("╔══════════════════════════════════════════╗")
    print("║  DC25 ULTRA FARMER v4.2                  ║")
    print("║  Token Vault + BG Jobs + Auto-Ping       ║")
    print(f"║  Email : {ADMIN_EMAIL:<32}║")
    print("║  Open  : http://localhost:5000           ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=5000, debug=False)
