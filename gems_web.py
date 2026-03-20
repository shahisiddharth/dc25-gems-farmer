"""
Dream Cricket 25 - ULTRA Farmer v5.1
AUTO-CHAIN: Legendary/Champion = auto elite farm + auto exchange
Modes:
  💎 Gems
  🎫 World Cup Tickets
  🃏 Elite Cards
  ⭐ Legendary Cards (AUTO: farm elite → exchange)
  👑 Champion Cards  (AUTO: farm elite → exchange)
"""

from flask import Flask, jsonify, request, session
import requests as req
import json, time, base64, math, threading, os, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

URL_USERDATA = "https://api-prod.dreamgamestudios.in/userdata/graphql"
URL_RECEIPT  = "https://api-prod.dreamgamestudios.in/receiptvalidator/graphql"
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "admin@dc25.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
MAX_WORKERS    = 200

MODES = {
    "gems":    {"label":"💎 Gems",     "unit":"Gems",     "type":"reward", "templateId":125968,"currencyTypeId":2,  "amount":2},
    "tickets": {"label":"🎫 Tickets",  "unit":"Tickets",  "type":"reward", "templateId":124339,"currencyTypeId":23, "amount":30},
    "elite":   {"label":"🃏 Elite",    "unit":"Elite",    "type":"reward", "templateId":122012,"currencyTypeId":14, "amount":1},
    "legendary":{"label":"⭐ Legendary","unit":"Legendary","type":"chain",
        "elite_per_card":10,
        "reward_currencyTypeId":15, "reward_amount":1,
        "cost_currencyTypeId":14,   "cost_amount":10,
        "attr_2770":"5.000000", "amount":1,
    },
    "champion": {"label":"👑 Champion", "unit":"Champion", "type":"chain",
        "elite_per_card":10,
        "reward_currencyTypeId":16, "reward_amount":1,
        "cost_currencyTypeId":14,   "cost_amount":10,
        "attr_2770":"49.000000", "amount":1,
    },
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

def build_elite_mutation():
    """Farm 1 elite card"""
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 122012,
            "templateAttributes": [
                {"templateId":0,"groupAttributeId":3277,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3283,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3289,"attributeValue": uts()},
                {"templateId":0,"groupAttributeId":3290,"attributeValue":"0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{"currencyTypeId":14,"currencyAmount":1,"giveAwayType":11,"meta":"Reward"}]
        }]}
    }

def build_reward_mutation(mode_key):
    m = MODES[mode_key]
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
            "currencyRewards": [{"currencyTypeId":m["currencyTypeId"],"currencyAmount":m["amount"],"giveAwayType":11,"meta":"Reward"}]
        }]}
    }

def build_exchange_mutation(mode_key):
    m = MODES[mode_key]
    return {
        "query": """mutation assignStorePurchase ($input: ProductPurchaseAndAssignInput) {
            assignStorePurchase (input: $input) {
                purchaseState purchaseType acknowledgementState
                consumptionState orderId validPurchase kind rewardSuccess
            }
        }""",
        "variables": {"input": {
            "productPurchaseInput": {
                "packageName":"","productId":"","purchaseToken":"",
                "platform":"","orderId":"","price":0,"currencyCode":"","priceText":""
            },
            "productInfoInput": {
                "templateAttributeInputs": [
                    {"templateId":104716,"groupAttributeId":2758,"attributeValue":"1"},
                    {"templateId":104716,"groupAttributeId":2764,"attributeValue":"0.000000"},
                    {"templateId":104716,"groupAttributeId":2770,"attributeValue":m["attr_2770"]},
                    {"templateId":104716,"groupAttributeId":2775,"attributeValue":"0.000000"},
                    {"templateId":104716,"groupAttributeId":2780,"attributeValue":"0.000000"},
                    {"templateId":104716,"groupAttributeId":2795,"attributeValue":"946645200000"},
                    {"templateId":104716,"groupAttributeId":2804,"attributeValue":"0"}
                ],
                "gameItemInputs": [], "userOwnedItemInputs": [],
                "currencyInputs": [{"currencyTypeId":m["reward_currencyTypeId"],"currencyAmount":m["reward_amount"]}],
                "storeListingInput": {"storeId":945961900,"storeItemListingId":104716,"bundleId":563354144}
            },
            "currencyDebit": [{"currencyTypeId":m["cost_currencyTypeId"],"currencyAmount":m["cost_amount"]}]
        }}
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

def do_single_reward(hdr, mode_key):
    try:
        r = req.post(URL_USERDATA, headers=hdr, json=build_reward_mutation(mode_key), timeout=15)
        return r.status_code == 200
    except: return False

def do_single_elite(hdr):
    try:
        r = req.post(URL_USERDATA, headers=hdr, json=build_elite_mutation(), timeout=15)
        return r.status_code == 200
    except: return False

def do_single_exchange(hdr, mode_key):
    try:
        r = req.post(URL_RECEIPT, headers=hdr, json=build_exchange_mutation(mode_key), timeout=15)
        if r.status_code == 200:
            return r.json().get("data",{}).get("assignStorePurchase",{}).get("rewardSuccess") == True
        return False
    except: return False

def update_job(job_id, success=0, fail=0):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["success"] += success
            jobs[job_id]["fail"]    += fail

def run_phase(job_id, hdr, total, workers, phase_fn, phase_name):
    """
    Run a phase (elite farming or exchange).
    Returns (success_count, fail_count)
    """
    batches = math.ceil(total / workers)
    bt = []
    phase_success = 0
    phase_fail    = 0

    for b in range(batches):
        with jobs_lock:
            if job_id not in jobs or not jobs[job_id]["running"]:
                return phase_success, phase_fail

        sz = min(workers, total - (b * workers))
        if sz <= 0: break
        t0 = time.time()

        results = []
        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs = [ex.submit(phase_fn) for _ in range(sz)]
            for f in as_completed(fs):
                results.append(f.result())

        t1 = time.time()
        ok  = sum(1 for r in results if r)
        bad = sum(1 for r in results if not r)
        phase_success += ok
        phase_fail    += bad

        bt.append(t1 - t0)
        if len(bt) > 10: bt.pop(0)
        avg = sum(bt) / len(bt)
        spd = round(workers / avg, 1)
        eta = (batches - b - 1) * avg

        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase_completed"] = (b + 1) * workers
                jobs[job_id]["eta"]   = eta
                jobs[job_id]["speed"] = spd
                jobs[job_id]["speed_history"].append(spd)
                if len(jobs[job_id]["speed_history"]) > 30:
                    jobs[job_id]["speed_history"].pop(0)

    return phase_success, phase_fail

def run_job(job_id):
    with jobs_lock:
        if job_id not in jobs: return
        token    = jobs[job_id]["token"]
        total    = jobs[job_id]["total"]   # desired cards (legendary/champion) OR clicks
        workers  = jobs[job_id]["workers"]
        mode_key = jobs[job_id]["mode_key"]
        uid      = jobs[job_id]["uid"]

    hdr = make_headers(token)
    m   = MODES[mode_key]

    if m["type"] == "chain":
        # ── AUTO CHAIN ──
        # Phase 1: Farm elite cards
        elite_needed = total * m["elite_per_card"]

        with jobs_lock:
            jobs[job_id]["phase"] = 1
            jobs[job_id]["phase1_total"] = elite_needed
            jobs[job_id]["phase2_total"] = total
            jobs[job_id]["phase_completed"] = 0
            jobs[job_id]["phase1_success"] = 0
            jobs[job_id]["phase2_success"] = 0

        # Phase 1 — farm elite
        p1_ok, p1_fail = run_phase(
            job_id, hdr, elite_needed, workers,
            lambda: do_single_elite(hdr), "elite"
        )
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase1_success"] = p1_ok
                jobs[job_id]["phase"] = 2
                jobs[job_id]["phase_completed"] = 0

        # Check if stopped
        with jobs_lock:
            still_running = job_id in jobs and jobs[job_id]["running"]
        if not still_running:
            _finish_job(job_id, uid, mode_key, total, workers, p1_ok, p1_fail)
            return

        # Phase 2 — exchange elite → legendary/champion
        # Only exchange as many as we successfully farmed
        cards_possible = p1_ok // m["elite_per_card"]
        p2_ok, p2_fail = run_phase(
            job_id, hdr, cards_possible, max(1, workers // 5),
            lambda: do_single_exchange(hdr, mode_key), "exchange"
        )
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase2_success"] = p2_ok
                jobs[job_id]["success"] = p2_ok
                jobs[job_id]["fail"]    = p2_fail

        _finish_job(job_id, uid, mode_key, total, workers, p2_ok, p2_fail)

    else:
        # ── NORMAL MODE (gems, tickets, elite) ──
        batches = math.ceil(total / workers)
        bt = []
        for b in range(batches):
            with jobs_lock:
                if job_id not in jobs or not jobs[job_id]["running"]: break
            sz = min(workers, total - jobs[job_id]["completed"])
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=sz) as ex:
                fs = [ex.submit(
                    do_single_reward if m["type"]=="reward" else do_single_exchange,
                    hdr, *([] if m["type"]=="reward" else [mode_key])
                ) for _ in range(sz)]
                # Actually for reward mode
                if m["type"] == "reward":
                    fs2 = [ex.submit(do_single_reward, hdr, mode_key) for _ in range(sz)]
                    results = [f.result() for f in as_completed(fs2)]
                else:
                    results = [f.result() for f in as_completed(fs)]
            t1 = time.time()
            ok  = sum(1 for r in results if r)
            bad = sz - ok
            with jobs_lock:
                if job_id not in jobs: break
                jobs[job_id]["success"]   += ok
                jobs[job_id]["fail"]      += bad
                jobs[job_id]["completed"] += sz
            bt.append(t1-t0)
            if len(bt)>10: bt.pop(0)
            avg = sum(bt)/len(bt)
            with jobs_lock:
                if job_id in jobs:
                    jobs[job_id]["eta"]   = (batches-b-1)*avg
                    jobs[job_id]["speed"] = round(workers/avg,1)
                    jobs[job_id]["speed_history"].append(round(workers/avg,1))
                    if len(jobs[job_id]["speed_history"])>30:
                        jobs[job_id]["speed_history"].pop(0)
        with jobs_lock:
            if job_id in jobs:
                s = jobs[job_id]["success"]
                f = jobs[job_id]["fail"]
        _finish_job(job_id, uid, mode_key, total, workers, s, f)

def _finish_job(job_id, uid, mode_key, total, workers, success, fail):
    with jobs_lock:
        if job_id not in jobs: return
        jobs[job_id]["running"]  = False
        jobs[job_id]["done"]     = True
        jobs[job_id]["end_time"] = time.time()
        elapsed = jobs[job_id]["end_time"] - jobs[job_id]["start_time"]
        m = MODES[mode_key]
        entry = {
            "reward":  success * m["amount"],
            "unit":    m["unit"], "label": m["label"],
            "mode_key": mode_key,
            "success": success, "total": total, "workers": workers,
            "elapsed": round(elapsed,1),
            "time":    datetime.now().strftime("%H:%M:%S"),
            "date":    datetime.now().strftime("%d %b"),
        }
    with user_history_lock:
        if uid not in user_history: user_history[uid] = []
        user_history[uid].insert(0, entry)
        if len(user_history[uid]) > 10:
            user_history[uid] = user_history[uid][:10]

def is_logged_in(): return session.get("logged_in") == True

def active_job():
    with jobs_lock:
        for jid,j in jobs.items():
            if j["running"]: return jid, dict(j)
    return None, None

# ── Routes ──
@app.route("/")
def index():
    if not is_logged_in(): return LOGIN_PAGE
    return MAIN_PAGE

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    if d.get("email","").strip().lower()==ADMIN_EMAIL.lower() and d.get("password","").strip()==ADMIN_PASSWORD:
        session["logged_in"]=True; session.permanent=True
        return jsonify({"ok":True})
    return jsonify({"error":"Invalid email or password"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return jsonify({"ok":True})

@app.route("/start", methods=["POST"])
def start():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    jid,_ = active_job()
    if jid: return jsonify({"error":"Job already running! Stop it first."}), 400
    d        = request.json
    token    = d.get("token","").strip()
    desired  = int(d.get("desired",10))
    workers  = min(int(d.get("workers",20)), MAX_WORKERS)
    mode_key = d.get("mode","gems")
    if mode_key not in MODES: mode_key="gems"
    if not token: return jsonify({"error":"Token required"}), 400

    m      = MODES[mode_key]
    uid    = get_uid(token)
    job_id = f"job_{int(time.time())}"

    # For chain modes, total = desired cards
    # For normal modes, total = clicks needed
    if m["type"] == "chain":
        total = desired
    else:
        total = math.ceil(desired / m["amount"])

    with jobs_lock:
        jobs[job_id] = {
            "running":True,"done":False,"success":0,"fail":0,
            "total":total,"completed":0,
            "start_time":time.time(),"end_time":0,
            "eta":0,"speed":0,"speed_history":[],
            "token":token,"workers":workers,
            "mode_key":mode_key,"uid":uid,
            # chain specific
            "phase":1,
            "phase1_total": total * m.get("elite_per_card",1) if m["type"]=="chain" else 0,
            "phase2_total": total if m["type"]=="chain" else 0,
            "phase_completed":0,
            "phase1_success":0,
            "phase2_success":0,
        }
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return jsonify({
        "ok":True,"job_id":job_id,
        "unit":m["unit"],"amount":m["amount"],"uid":uid,
        "mode_key":mode_key,"is_chain":m["type"]=="chain",
        "elite_needed": total * m.get("elite_per_card",1) if m["type"]=="chain" else 0,
    })

@app.route("/stop", methods=["POST"])
def stop():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    job_id = request.json.get("job_id","")
    with jobs_lock:
        if job_id and job_id in jobs: jobs[job_id]["running"]=False
        else:
            for jid in jobs:
                if jobs[jid]["running"]: jobs[jid]["running"]=False
    return jsonify({"ok":True})

@app.route("/status")
def status():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    job_id = request.args.get("job_id","")
    uid    = request.args.get("uid","unknown")
    with jobs_lock:
        if job_id and job_id in jobs: j=dict(jobs[job_id])
        elif jobs: latest=max(jobs.keys()); j=dict(jobs[latest]); job_id=latest
        else: j=None
    with user_history_lock: hist=list(user_history.get(uid,[]))
    if not j:
        return jsonify({"running":False,"done":False,"completed":0,"total":0,"pct":0,
            "reward":0,"unit":"","success":0,"fail":0,"eta":0,"speed":0,"elapsed":0,
            "speed_history":[],"history":hist,"job_id":"","has_active":False,
            "phase":1,"phase1_total":0,"phase2_total":0,"phase_completed":0,
            "phase1_success":0,"phase2_success":0,"is_chain":False})
    elapsed=(time.time() if j["running"] else j["end_time"])-j["start_time"]
    mk = j["mode_key"]
    m  = MODES.get(mk, MODES["gems"])
    is_chain = m["type"]=="chain"

    if is_chain:
        phase = j.get("phase",1)
        p1t   = j.get("phase1_total",0)
        p2t   = j.get("phase2_total",0)
        pc    = j.get("phase_completed",0)
        total_steps = p1t + p2t
        done_steps  = (p1t if phase==2 else pc) + (pc if phase==2 else 0)
        pct = round(done_steps/total_steps*100,1) if total_steps else 0
        reward = j.get("phase2_success",0) * m["amount"]
    else:
        pct    = round(j["completed"]/j["total"]*100,1) if j["total"] else 0
        reward = j["success"] * m["amount"]

    return jsonify({
        "running":j["running"],"done":j["done"],
        "completed":j.get("completed",0),"total":j["total"],"pct":pct,
        "reward":reward,"unit":m["unit"],"label":m["label"],
        "success":j["success"],"fail":j["fail"],
        "eta":round(j.get("eta",0)),"speed":j.get("speed",0),
        "elapsed":round(elapsed),
        "speed_history":j.get("speed_history",[]),
        "history":hist,"job_id":job_id,
        "has_active":j["running"],"mode_key":mk,
        "is_chain":is_chain,
        "phase":j.get("phase",1),
        "phase1_total":j.get("phase1_total",0),
        "phase2_total":j.get("phase2_total",0),
        "phase_completed":j.get("phase_completed",0),
        "phase1_success":j.get("phase1_success",0),
        "phase2_success":j.get("phase2_success",0),
    })

@app.route("/active")
def active():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    jid,j = active_job()
    if jid and j:
        m=MODES.get(j["mode_key"],MODES["gems"])
        elapsed=time.time()-j["start_time"]
        pct=round(j["completed"]/j["total"]*100,1) if j["total"] else 0
        return jsonify({"has_active":True,"job_id":jid,"pct":pct,
            "completed":j["completed"],"total":j["total"],
            "reward":j["success"]*m["amount"],"unit":m["unit"],
            "elapsed":round(elapsed),"mode_key":j["mode_key"],"uid":j["uid"]})
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
#tb{position:absolute;top:24px;left:50%;transform:translateX(-50%);display:flex;gap:14px;align-items:center;font-size:9px;color:#1a4a2a;letter-spacing:3px;opacity:0;animation:fu .4s ease 1s forwards;white-space:nowrap;}
@keyframes fu{to{opacity:1}}
.dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:db 1.5s infinite;}
.dot.r{background:#ff2244;animation-delay:.5s;}.dot.y{background:#ffd600;animation-delay:1s;}
@keyframes db{0%,100%{opacity:1}50%{opacity:.3}}
#ctr{position:relative;z-index:5;text-align:center;opacity:0;animation:cn .8s cubic-bezier(.16,1,.3,1) 2s forwards;}
@keyframes cn{0%{opacity:0;transform:scale(.85)}100%{opacity:1;transform:scale(1)}}
.gw{position:relative;display:inline-block;margin-bottom:14px;}
.gi{font-size:60px;display:block;filter:drop-shadow(0 0 30px rgba(0,255,136,.8));animation:gfl 3s ease-in-out infinite 2s;}
@keyframes gfl{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.orb{position:absolute;border:1px solid rgba(0,255,136,.15);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);}
.orb1{width:100px;height:100px;animation:os 4s linear infinite 2s;}
.orb2{width:140px;height:140px;animation:os 7s linear reverse infinite 2s;border-style:dashed;}
@keyframes os{to{transform:translate(-50%,-50%) rotate(360deg)}}
.od{position:absolute;width:5px;height:5px;background:#00ff88;border-radius:50%;top:-2px;left:50%;transform:translateX(-50%);box-shadow:0 0 8px #00ff88;}
.mt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(22px,6vw,46px);letter-spacing:8px;color:#00ffaa;text-shadow:0 0 30px rgba(0,255,136,.6);position:relative;}
.mt::before{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#ff0044;opacity:0;animation:gr 5s infinite 3s;clip-path:polygon(0 20%,100% 20%,100% 40%,0 40%);}
.mt::after{content:'DC25 FARMER';position:absolute;top:0;left:0;right:0;color:#00e5ff;opacity:0;animation:gb 5s infinite 3.1s;clip-path:polygon(0 60%,100% 60%,100% 80%,0 80%);}
@keyframes gr{0%,92%,100%{opacity:0}93%{opacity:.8;transform:translate(-4px,0)}94%{opacity:0}95%{opacity:.8;transform:translate(-2px,0)}96%{opacity:0}}
@keyframes gb{0%,92%,100%{opacity:0}93%{opacity:.8;transform:translate(4px,0)}94%{opacity:0}95%{opacity:.8;transform:translate(2px,0)}96%{opacity:0}}
.vt{display:inline-block;background:rgba(0,255,100,.06);border:1px solid rgba(0,255,100,.18);border-radius:2px;padding:3px 12px;font-size:9px;color:#00aa55;letter-spacing:4px;margin-top:8px;}
#pw{margin-top:20px;width:min(320px,68vw);opacity:0;animation:fu .4s ease 2.5s forwards;}
.ph{display:flex;justify-content:space-between;font-size:9px;color:#1a4a2a;margin-bottom:5px;}
.pt2{background:rgba(0,255,100,.04);border:1px solid #0a2015;border-radius:2px;height:7px;overflow:hidden;}
.pf{height:100%;width:0%;background:linear-gradient(90deg,#002a14,#00aa55,#00ffaa);}
.sps{margin-top:5px;display:flex;flex-direction:column;gap:3px;}
.sr{display:flex;align-items:center;gap:8px;font-size:7px;color:#1a3a2a;}
.sl{width:80px;text-align:right;}.sts{flex:1;height:3px;background:rgba(0,255,100,.04);border-radius:1px;overflow:hidden;}
.sf{height:100%;width:0%;transition:width 1s;border-radius:1px;}
.sf.g{background:#00cc77;}.sf.c{background:#00e5ff;}.sf.y{background:#ffd600;}.sf.p{background:#c264fe;}
.sp{width:26px;color:#00aa44;font-size:7px;}
#bs{margin-top:8px;font-size:10px;color:#00aa44;letter-spacing:2px;text-align:center;min-height:14px;opacity:0;animation:fu .3s ease 2.8s forwards;}
#ag{position:fixed;inset:0;z-index:50;background:#000;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;}
.agb{border:2px solid #00ff88;padding:26px 45px;text-align:center;box-shadow:0 0 60px rgba(0,255,136,.4);}
.agi{font-size:40px;margin-bottom:8px;}
.agt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(14px,4vw,30px);letter-spacing:8px;color:#00ffaa;}
.ags{font-size:10px;color:#00aa55;letter-spacing:4px;margin-top:5px;}
#sk{position:fixed;bottom:16px;right:16px;z-index:100;background:rgba(0,255,100,.04);border:1px solid rgba(0,255,100,.1);border-radius:3px;color:rgba(0,255,100,.22);font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;padding:4px 10px;cursor:pointer;}
#lw{position:fixed;inset:0;z-index:8;display:none;align-items:center;justify-content:center;background:rgba(3,5,10,.97);}
#lw.show{display:flex;}
.lc{background:#0a1520;border:1px solid #0d2a1a;border-radius:8px;padding:32px 26px 28px;width:100%;max-width:360px;position:relative;overflow:hidden;margin:18px;}
.lc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#00ffaa,#00cc77,#00ffaa,transparent);}
.ll{text-align:center;margin-bottom:22px;}
.li{font-size:34px;margin-bottom:8px;}
.lh{font-family:'Orbitron',monospace;font-weight:900;font-size:17px;letter-spacing:6px;background:linear-gradient(135deg,#00ffaa,#00e5ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.lp{font-size:9px;color:#2a4a35;letter-spacing:4px;margin-top:4px;}
.lf{margin-bottom:13px;}
.lf label{display:block;font-size:9px;color:#2a4a35;letter-spacing:3px;margin-bottom:5px;}
.lf input{width:100%;background:rgba(0,255,100,.03);border:1px solid #0d2a1a;border-radius:4px;color:#00ffaa;font-family:'Share Tech Mono',monospace;font-size:14px;padding:11px 13px;outline:none;transition:border-color .2s;}
.lf input:focus{border-color:#00cc77;}
.lb{width:100%;padding:14px;margin-top:5px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid #00cc77;border-radius:6px;color:#00ffaa;font-family:'Orbitron',monospace;font-weight:900;font-size:12px;letter-spacing:5px;cursor:pointer;position:relative;overflow:hidden;}
.lb::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,.1),transparent);transform:skewX(-20deg);animation:sh 3s infinite;}
@keyframes sh{0%{left:-60%}100%{left:160%}}
.lb:disabled{opacity:.4;cursor:not-allowed;}
.le{display:none;background:rgba(255,34,68,.08);border:1px solid rgba(255,34,68,.25);border-radius:4px;color:#ff2244;font-size:11px;padding:9px;margin-top:9px;text-align:center;}
.le.show{display:block;}
</style>
</head>
<body>
<div class="cur" id="cur"></div>
<canvas id="cv"></canvas><div id="sl"></div>
<div id="intro">
  <div class="ring"></div><div class="ring"></div><div class="ring"></div><div class="ring"></div>
  <div class="co tl"></div><div class="co tr"></div><div class="co bl"></div><div class="co br"></div>
  <div id="tb"><div class="dot"></div>ONLINE<span style="color:#0d3a1a">|</span><div class="dot y"></div>AES-256<span style="color:#0d3a1a">|</span><div class="dot r"></div>BYPASSED</div>
  <div id="ctr">
    <div class="gw"><div class="orb orb1"><div class="od"></div></div><div class="orb orb2"><div class="od"></div></div><span class="gi">💎</span></div>
    <div class="mt">DC25 FARMER</div>
    <div class="vt">AUTO-CHAIN · v5.1</div>
    <div id="pw">
      <div class="ph"><span id="pl">INITIALIZING...</span><span id="pn">0%</span></div>
      <div class="pt2"><div class="pf" id="pfl"></div></div>
      <div class="sps">
        <div class="sr"><span class="sl">GEMS+TICKETS</span><div class="sts"><div class="sf g" id="s1"></div></div><span class="sp" id="s1p">0%</span></div>
        <div class="sr"><span class="sl">CARD ENGINE</span><div class="sts"><div class="sf c" id="s2"></div></div><span class="sp" id="s2p">0%</span></div>
        <div class="sr"><span class="sl">AUTO-CHAIN</span><div class="sts"><div class="sf y" id="s3"></div></div><span class="sp" id="s3p">0%</span></div>
        <div class="sr"><span class="sl">AUTO-PING</span><div class="sts"><div class="sf p" id="s4"></div></div><span class="sp" id="s4p">0%</span></div>
      </div>
    </div>
    <div id="bs">▌</div>
  </div>
</div>
<div id="ag"><div class="agb"><div class="agi">🔓</div><div class="agt">ACCESS GRANTED</div><div class="ags">WELCOME · KING SHAHI</div></div></div>
<div id="lw">
  <div class="lc">
    <div class="ll"><div class="li">💎</div><div class="lh">DC25 FARMER</div><div class="lp">SECURE ACCESS</div></div>
    <div class="lf"><label>EMAIL</label><input type="email" id="em" placeholder="your@email.com" autocomplete="email"/></div>
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
const lbls=['LOADING...','CARD ENGINE...','AUTO-CHAIN...','AUTO-PING...','READY'];
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
<title>DC25 ULTRA FARMER v5.1</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#03050a;--panel:#0a1520;--border:#0d2a1a;--g1:#00ffaa;--g2:#00cc77;--g3:#004422;--cyan:#00e5ff;--red:#ff2244;--yellow:#ffd600;--purple:#c264fe;--orange:#ff8c00;--gold:#ffd700;--text:#a8ffd0;--dim:#2a4a35;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 20% 0%,rgba(0,255,100,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(0,200,255,.03) 0%,transparent 60%),repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,255,100,.012) 40px,rgba(0,255,100,.012) 41px);pointer-events:none;z-index:0;}
body::after{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.15) 3px,rgba(0,0,0,.15) 4px);pointer-events:none;z-index:1;}
.wrap{position:relative;z-index:2;}
.hdr{padding:15px 18px 13px;text-align:center;border-bottom:1px solid var(--border);position:relative;}
.hdr::after{content:'';position:absolute;bottom:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--g1),var(--cyan),var(--g1),transparent);}
.hdr-badge{display:inline-block;background:rgba(0,255,100,.08);border:1px solid var(--g3);border-radius:2px;padding:2px 10px;font-size:9px;letter-spacing:4px;color:var(--g2);margin-bottom:5px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(14px,4.2vw,26px);letter-spacing:5px;background:linear-gradient(135deg,var(--g1),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr p{color:var(--dim);font-size:8px;letter-spacing:2px;margin-top:3px;}
.logout-btn{position:absolute;top:14px;right:12px;background:transparent;border:1px solid rgba(255,34,68,.3);border-radius:3px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:9px;padding:4px 8px;cursor:pointer;}
.ping-badge{position:absolute;top:16px;left:12px;display:flex;align-items:center;gap:4px;font-size:8px;color:var(--g2);}
.ping-dot{width:5px;height:5px;border-radius:50%;background:var(--g1);animation:pd 2s infinite;}
@keyframes pd{0%,100%{opacity:1;box-shadow:0 0 4px var(--g1);}50%{opacity:.4;}}
#ab{display:none;background:rgba(0,255,100,.06);border:1px solid var(--g2);border-radius:6px;padding:10px 14px;margin:10px 12px 0;}
#ab.show{display:block;}
.abt{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;color:var(--g1);margin-bottom:6px;}
.abr{display:flex;justify-content:space-between;align-items:center;gap:8px;}
.abi{font-size:10px;color:var(--text);}
.abs{background:rgba(255,34,68,.1);border:1px solid var(--red);border-radius:4px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:10px;padding:4px 10px;cursor:pointer;white-space:nowrap;}
.abb{margin-top:5px;background:rgba(0,255,100,.05);border:1px solid var(--border);border-radius:2px;height:4px;overflow:hidden;}
.abf{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));transition:width .5s;}
.page{max-width:680px;margin:0 auto;padding:10px 12px 40px;display:flex;flex-direction:column;gap:10px;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:14px;position:relative;overflow:hidden;}
.cg{position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g2),transparent);}
.cg.c{background:linear-gradient(90deg,transparent,var(--cyan),transparent);}
.cg.p{background:linear-gradient(90deg,transparent,var(--purple),transparent);}
.cg.gold{background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.sec{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:4px;color:var(--dim);margin-bottom:8px;display:flex;align-items:center;gap:8px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}
#tokArea{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:11px;padding:9px;outline:none;resize:none;height:70px;transition:border-color .2s;}
#tokArea:focus{border-color:var(--g2);}
#tokVault{display:none;height:70px;background:rgba(0,255,100,.02);border:1px solid rgba(0,255,100,.2);border-radius:4px;position:relative;overflow:hidden;align-items:center;justify-content:center;flex-direction:column;gap:4px;cursor:pointer;}
#tokVault.show{display:flex;}
#vCv{position:absolute;inset:0;opacity:0.15;}
.vc{position:relative;z-index:2;text-align:center;}
.vi{font-size:20px;animation:vp 2s infinite;}
@keyframes vp{0%,100%{filter:drop-shadow(0 0 6px rgba(0,255,136,.6));}50%{filter:drop-shadow(0 0 16px rgba(0,255,136,1));}}
.vtt{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:4px;color:var(--g1);}
.vsb{font-size:8px;color:var(--dim);letter-spacing:2px;margin-top:2px;}
.vdots{display:flex;gap:4px;justify-content:center;margin-top:4px;}
.vd{width:4px;height:4px;border-radius:50%;background:var(--g3);animation:vd 1.5s infinite;}
.vd:nth-child(2){animation-delay:.2s;}.vd:nth-child(3){animation-delay:.4s;}.vd:nth-child(4){animation-delay:.6s;}.vd:nth-child(5){animation-delay:.8s;}
@keyframes vd{0%,100%{background:var(--g3);}50%{background:var(--g1);box-shadow:0 0 5px var(--g1);}}
.vscan{position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g1),transparent);animation:vscan 2s linear infinite;opacity:.3;}
@keyframes vscan{0%{top:0}100%{top:100%}}
.tok-hint{font-size:8px;color:var(--dim);margin-top:4px;letter-spacing:1px;}
.mode-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;}
.mb{padding:9px 3px;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;cursor:pointer;transition:all .2s;text-align:center;}
.mb.on.gems{border-color:var(--g1);background:rgba(0,255,100,.08);}
.mb.on.tickets{border-color:var(--orange);background:rgba(255,140,0,.08);}
.mb.on.elite{border-color:var(--cyan);background:rgba(0,229,255,.08);}
.mb.on.legendary{border-color:var(--purple);background:rgba(194,100,254,.08);}
.mb.on.champion{border-color:var(--gold);background:rgba(255,215,0,.08);}
.mbi{font-size:18px;margin-bottom:2px;}
.mbl{font-family:'Orbitron',monospace;font-size:6px;letter-spacing:1px;color:var(--dim);}
.mb.on.gems .mbl{color:var(--g1);}
.mb.on.tickets .mbl{color:var(--orange);}
.mb.on.elite .mbl{color:var(--cyan);}
.mb.on.legendary .mbl{color:var(--purple);}
.mb.on.champion .mbl{color:var(--gold);}
.mbs{font-size:7px;color:var(--dim);margin-top:1px;}

/* Chain info box */
#chainBox{display:none;margin-top:8px;border-radius:4px;padding:10px 12px;}
#chainBox.show{display:block;}
#chainBox.legendary{background:rgba(194,100,254,.05);border:1px solid rgba(194,100,254,.2);}
#chainBox.champion{background:rgba(255,215,0,.05);border:1px solid rgba(255,215,0,.2);}
.chain-title{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;margin-bottom:8px;}
#chainBox.legendary .chain-title{color:var(--purple);}
#chainBox.champion .chain-title{color:var(--gold);}
.chain-steps{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.cs{background:rgba(0,0,0,.3);border-radius:3px;padding:5px 8px;font-size:10px;text-align:center;}
.cs-icon{font-size:16px;}
.cs-lbl{font-size:8px;color:var(--dim);margin-top:2px;}
.cs-arrow{color:var(--dim);font-size:14px;}
.chain-calc{margin-top:8px;font-size:10px;color:var(--dim);letter-spacing:1px;}
.chain-calc span{font-family:'Orbitron',monospace;font-size:11px;}
#chainBox.legendary .chain-calc span{color:var(--purple);}
#chainBox.champion .chain-calc span{color:var(--gold);}

.cfg-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.cfg-item label{display:block;font-size:9px;letter-spacing:3px;color:var(--dim);margin-bottom:5px;}
input[type=number]{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:15px;padding:9px 11px;outline:none;}
.hint{font-size:9px;color:var(--dim);margin-top:3px;}
.presets{display:flex;gap:5px;margin-top:6px;flex-wrap:wrap;}
.pw{flex:1;min-width:34px;background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:11px;padding:5px 3px;cursor:pointer;transition:all .15s;text-align:center;}
.pw:hover,.pw.on{border-color:var(--g1);color:var(--g1);background:rgba(0,255,100,.08);}
.pw.hot{border-color:var(--red)!important;color:var(--red)!important;background:rgba(255,34,68,.08)!important;}
.btn-start{width:100%;padding:14px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid var(--g2);border-radius:6px;color:var(--g1);font-family:'Orbitron',monospace;font-weight:900;font-size:12px;letter-spacing:4px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;}
.btn-start.tickets{border-color:var(--orange);color:var(--orange);background:linear-gradient(135deg,#2a1400,#503000,#3a1c00);}
.btn-start.elite{border-color:var(--cyan);color:var(--cyan);background:linear-gradient(135deg,#002a2a,#005050,#003a3a);}
.btn-start.legendary{border-color:var(--purple);color:var(--purple);background:linear-gradient(135deg,#1a0028,#350050,#28003a);}
.btn-start.champion{border-color:var(--gold);color:var(--gold);background:linear-gradient(135deg,#2a2000,#504000,#3a3000);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){transform:translateY(-1px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-stop{width:100%;padding:10px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:13px;letter-spacing:4px;cursor:pointer;display:none;}
.prog-card{display:none;}.prog-card.show{display:block;}

/* Chain phase progress */
#chainProgress{display:none;margin-bottom:12px;padding:10px 12px;border-radius:4px;}
#chainProgress.show{display:block;}
#chainProgress.legendary{background:rgba(194,100,254,.04);border:1px solid rgba(194,100,254,.15);}
#chainProgress.champion{background:rgba(255,215,0,.04);border:1px solid rgba(255,215,0,.15);}
.cp-title{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;margin-bottom:8px;}
#chainProgress.legendary .cp-title{color:var(--purple);}
#chainProgress.champion .cp-title{color:var(--gold);}
.cp-phases{display:flex;gap:8px;}
.cp-phase{flex:1;text-align:center;}
.cp-ph-label{font-size:8px;color:var(--dim);letter-spacing:2px;margin-bottom:4px;}
.cp-ph-bar{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:2px;height:6px;overflow:hidden;}
.cp-ph-fill{height:100%;transition:width .4s;}
.cp-ph-fill.p1{background:linear-gradient(90deg,var(--g3),var(--cyan));}
.cp-ph-fill.p2l{background:linear-gradient(90deg,#280038,var(--purple));}
.cp-ph-fill.p2c{background:linear-gradient(90deg,#3a3000,var(--gold));}
.cp-ph-val{font-size:8px;color:var(--dim);margin-top:3px;}
.cp-arrow{display:flex;align-items:center;color:var(--dim);font-size:16px;padding-top:14px;}

.prog-top{display:flex;align-items:center;gap:14px;margin-bottom:10px;}
.ring-wrap{position:relative;width:76px;height:76px;flex-shrink:0;}
.ring-wrap svg{width:76px;height:76px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:var(--border);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s;}
.ring-fg.tickets{stroke:url(#rgt);}
.ring-fg.elite{stroke:url(#rge);}
.ring-fg.legendary{stroke:url(#rgl);}
.ring-fg.champion{stroke:url(#rgc);}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:12px;font-weight:900;color:var(--g1);}
.ring-pct.tickets{color:var(--orange);}
.ring-pct.elite{color:var(--cyan);}
.ring-pct.legendary{color:var(--purple);}
.ring-pct.champion{color:var(--gold);}
.plbl{font-size:9px;color:var(--dim);letter-spacing:2px;margin-bottom:2px;}
.pval{font-family:'Orbitron',monospace;font-size:20px;font-weight:700;color:var(--g1);}
.pval.tickets{color:var(--orange);}.pval.elite{color:var(--cyan);}
.pval.legendary{color:var(--purple);}.pval.champion{color:var(--gold);}
.psub{font-size:10px;color:var(--dim);margin-top:2px;}
.bar-wrap{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:3px;height:8px;overflow:hidden;margin-bottom:10px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));width:0%;transition:width .4s;}
.bar-fill.tickets{background:linear-gradient(90deg,#3a1c00,#995500,#ff8c00);}
.bar-fill.elite{background:linear-gradient(90deg,#003a3a,#009999,#00e5ff);}
.bar-fill.legendary{background:linear-gradient(90deg,#280038,#6600aa,#c264fe);}
.bar-fill.champion{background:linear-gradient(90deg,#3a3000,#aa8800,#ffd700);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
.stat{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;padding:7px 5px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(11px,2.6vw,15px);font-weight:700;color:var(--g1);}
.sv.c{color:var(--cyan);}.sv.y{color:var(--yellow);}.sv.r{color:var(--red);}
.sl2{font-size:7px;color:var(--dim);letter-spacing:2px;margin-top:2px;}
.graph-wrap{margin-top:8px;}
.glbl{font-size:8px;color:var(--dim);letter-spacing:3px;margin-bottom:4px;}
.graph{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:3px;height:40px;overflow:hidden;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:3px 3px 0;}
.gb{flex:1;min-width:2px;background:linear-gradient(to top,var(--g3),var(--g2));border-radius:1px 1px 0 0;}
.gb.tickets{background:linear-gradient(to top,#3a1c00,#ff8c00);}
.gb.elite{background:linear-gradient(to top,#003a3a,#00e5ff);}
.gb.legendary{background:linear-gradient(to top,#280038,#c264fe);}
.gb.champion{background:linear-gradient(to top,#3a3000,#ffd700);}
.st{text-align:center;font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:6px;min-height:13px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--g1);}.st.r{color:var(--red);}
.done-card{display:none;text-align:center;padding:16px;background:rgba(0,255,100,.04);border:1px solid var(--g2);border-radius:6px;animation:glo 2s infinite;}
@keyframes glo{0%,100%{box-shadow:0 0 12px rgba(0,255,100,.1);}50%{box-shadow:0 0 35px rgba(0,255,100,.22);}}
.done-icon{font-size:28px;margin-bottom:6px;}
.done-title{font-family:'Orbitron',monospace;font-size:13px;letter-spacing:5px;color:var(--g1);}
.done-sub{font-size:11px;color:var(--dim);margin-top:5px;line-height:1.8;}
.done-countdown{margin-top:10px;background:rgba(0,255,100,.05);border:1px solid var(--border);border-radius:2px;height:3px;overflow:hidden;}
.done-cd-fill{height:100%;background:var(--g2);width:100%;}
.done-cd-txt{font-size:8px;color:var(--dim);margin-top:4px;letter-spacing:2px;}
.sess-list{display:flex;flex-direction:column;gap:6px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(0,255,100,.02);border:1px solid var(--border);border-radius:4px;padding:7px 10px;}
.si-r{font-family:'Orbitron',monospace;font-size:13px;font-weight:700;color:var(--g1);}
.si-m{font-size:9px;color:var(--dim);}
.si-tm{font-size:8px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:11px;letter-spacing:2px;padding:10px;}
.blink{animation:bl 1s step-end infinite;}
@keyframes bl{0%,100%{opacity:1;}50%{opacity:0;}}
.bg-notice{background:rgba(0,229,255,.04);border:1px solid rgba(0,229,255,.13);border-radius:4px;padding:6px 10px;font-size:9px;color:#00e5ff;letter-spacing:1px;text-align:center;margin-top:4px;}
</style>
</head>
<body>
<div class="wrap">
<div class="hdr">
  <div class="ping-badge"><div class="ping-dot"></div>AUTO-PING</div>
  <div class="hdr-badge">DC25</div>
  <h1>ULTRA FARMER v5.1</h1>
  <p>💎 GEMS · 🎫 TICKETS · 🃏 ELITE · ⭐ LEGENDARY · 👑 CHAMPION</p>
  <button class="logout-btn" onclick="doLogout()">⏻ OUT</button>
</div>

<div id="ab">
  <div class="abt">⚡ JOB RUNNING IN BACKGROUND</div>
  <div class="abr"><div class="abi" id="abInfo">Loading...</div><button class="abs" onclick="emergencyStop()">⛔ STOP</button></div>
  <div class="abb"><div class="abf" id="abFill"></div></div>
</div>

<div class="page">

  <!-- Token Vault -->
  <div class="card">
    <div class="cg"></div><div class="sec">// BEARER TOKEN</div>
    <textarea id="tokArea" placeholder="Paste Bearer token here..."></textarea>
    <div id="tokVault" onclick="showTokenReveal()">
      <canvas id="vCv"></canvas><div class="vscan"></div>
      <div class="vc"><div class="vi">🔒</div><div class="vtt">TOKEN SECURED</div><div class="vsb">Tap to reveal</div>
        <div class="vdots"><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div></div>
      </div>
    </div>
    <div class="tok-hint" id="tokHint">Token paste karo → start hone ke baad auto-hide 🔒</div>
  </div>

  <!-- Mode -->
  <div class="card">
    <div class="cg gold"></div><div class="sec">// SELECT MODE</div>
    <div class="mode-grid">
      <div class="mb on gems"     id="m_gems"      onclick="setMode('gems')">     <div class="mbi">💎</div><div class="mbl">GEMS</div><div class="mbs">+2/click</div></div>
      <div class="mb tickets"     id="m_tickets"   onclick="setMode('tickets')">  <div class="mbi">🎫</div><div class="mbl">TICKETS</div><div class="mbs">+30/click</div></div>
      <div class="mb elite"       id="m_elite"     onclick="setMode('elite')">    <div class="mbi">🃏</div><div class="mbl">ELITE</div><div class="mbs">+1/click</div></div>
      <div class="mb legendary"   id="m_legendary" onclick="setMode('legendary')"><div class="mbi">⭐</div><div class="mbl">LEGEND</div><div class="mbs">AUTO⚡</div></div>
      <div class="mb champion"    id="m_champion"  onclick="setMode('champion')"> <div class="mbi">👑</div><div class="mbl">CHAMP</div><div class="mbs">AUTO⚡</div></div>
    </div>

    <!-- Chain info box -->
    <div id="chainBox">
      <div class="chain-title" id="chainTitle">⚡ AUTO-CHAIN MODE</div>
      <div class="chain-steps">
        <div class="cs"><div class="cs-icon">🃏</div><div class="cs-lbl">FARM ELITE</div></div>
        <div class="cs-arrow">→</div>
        <div class="cs"><div class="cs-icon" id="chainIcon2">⭐</div><div class="cs-lbl">EXCHANGE</div></div>
        <div class="cs-arrow">→</div>
        <div class="cs"><div class="cs-icon" id="chainIcon3">⭐</div><div class="cs-lbl">DONE!</div></div>
      </div>
      <div class="chain-calc" id="chainCalc">Enter amount to see calculation</div>
    </div>
  </div>

  <!-- Config -->
  <div class="card">
    <div class="cg c"></div><div class="sec">// CONFIGURATION</div>
    <div class="cfg-row">
      <div class="cfg-item">
        <label id="dLabel">💎 DESIRED GEMS</label>
        <input type="number" id="desired" value="5000" min="1" step="2" oninput="updateCalc()"/>
        <div class="hint" id="hTxt">1 click = 2 gems</div>
      </div>
      <div class="cfg-item">
        <label>⚡ WORKERS</label>
        <input type="number" id="wrk" value="20" min="1" max="200"/>
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

    <!-- Chain phase bars -->
    <div id="chainProgress">
      <div class="cp-title" id="cpTitle">⚡ AUTO-CHAIN PROGRESS</div>
      <div class="cp-phases">
        <div class="cp-phase">
          <div class="cp-ph-label">PHASE 1 · ELITE FARMING</div>
          <div class="cp-ph-bar"><div class="cp-ph-fill p1" id="p1Fill"></div></div>
          <div class="cp-ph-val" id="p1Val">0 / 0</div>
        </div>
        <div class="cp-arrow">→</div>
        <div class="cp-phase">
          <div class="cp-ph-label" id="p2Label">PHASE 2 · EXCHANGE</div>
          <div class="cp-ph-bar"><div class="cp-ph-fill p2l" id="p2Fill"></div></div>
          <div class="cp-ph-val" id="p2Val">0 / 0</div>
        </div>
      </div>
    </div>

    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rg"  x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#00cc77"/><stop offset="100%" style="stop-color:#00ffaa"/></linearGradient>
            <linearGradient id="rgt" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#995500"/><stop offset="100%" style="stop-color:#ff8c00"/></linearGradient>
            <linearGradient id="rge" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#009999"/><stop offset="100%" style="stop-color:#00e5ff"/></linearGradient>
            <linearGradient id="rgl" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#6600aa"/><stop offset="100%" style="stop-color:#c264fe"/></linearGradient>
            <linearGradient id="rgc" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#aa8800"/><stop offset="100%" style="stop-color:#ffd700"/></linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="ring" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpct">0%</div>
      </div>
      <div>
        <div class="plbl" id="rLabel">REWARD ADDED</div>
        <div class="pval" id="pR">0</div>
        <div class="psub" id="pClicks">0 / 0 steps</div>
      </div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpd">0</div><div class="sl2">REQ/SEC</div></div>
      <div class="stat"><div class="sv y" id="sEta">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv"  id="sOk">0</div><div class="sl2">SUCCESS</div></div>
      <div class="stat"><div class="sv r" id="sFail">0</div><div class="sl2">FAILED</div></div>
    </div>
    <div class="graph-wrap"><div class="glbl">// SPEED</div><div class="graph"><div class="gbars" id="gBars"></div></div></div>
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
    <div class="cg p"></div><div class="sec">// YOUR JOB HISTORY</div>
    <div class="sess-list" id="hist"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div>
  </div>
</div>
</div>

<script>
const CIRC=245;
let poll=null,curMode='gems',jobId='',uid='';
let vCv,vCx,vDrops,vInt;

const MCFG={
  gems:     {lbl:'💎 DESIRED GEMS',   hint:'1 click = 2 gems',    btn:'▶ LAUNCH GEMS JOB',      cls:'',        chain:false},
  tickets:  {lbl:'🎫 DESIRED TICKETS',hint:'1 click = 30 tickets',btn:'▶ LAUNCH TICKETS JOB',  cls:'tickets', chain:false},
  elite:    {lbl:'🃏 DESIRED ELITE',   hint:'1 click = 1 card',   btn:'▶ LAUNCH ELITE JOB',     cls:'elite',   chain:false},
  legendary:{lbl:'⭐ DESIRED LEGENDARY',hint:'AUTO: 10 elite → 1 legendary',btn:'⚡ AUTO-CHAIN LEGENDARY',cls:'legendary',chain:true,icon:'⭐',epc:10},
  champion: {lbl:'👑 DESIRED CHAMPION', hint:'AUTO: 10 elite → 1 champion', btn:'⚡ AUTO-CHAIN CHAMPION', cls:'champion', chain:true,icon:'👑',epc:10},
};
const COLS={gems:'var(--g1)',tickets:'var(--orange)',elite:'var(--cyan)',legendary:'var(--purple)',champion:'var(--gold)'};
const ICONS={gems:'💎',tickets:'🎫',elite:'🃏',legendary:'⭐',champion:'👑'};

function initVault(){
  vCv=document.getElementById('vCv');
  const w=document.getElementById('tokVault');
  vCv.width=w.offsetWidth;vCv.height=w.offsetHeight;
  vCx=vCv.getContext('2d');
  const cols=Math.floor(vCv.width/10);vDrops=Array(cols).fill(1);
  const CH='01アイウカキABCDEF<>{};';
  function draw(){vCx.fillStyle='rgba(0,0,0,0.08)';vCx.fillRect(0,0,vCv.width,vCv.height);vDrops.forEach((y,i)=>{const c=CH[Math.floor(Math.random()*CH.length)];vCx.fillStyle=Math.random()>.9?'#00ffaa':'#00441a';vCx.font='9px Share Tech Mono';vCx.fillText(c,i*10,y*10);if(y*10>vCv.height&&Math.random()>.97)vDrops[i]=0;vDrops[i]++;});}
  vInt=setInterval(draw,60);
}
function lockToken(){document.getElementById('tokArea').style.display='none';document.getElementById('tokVault').classList.add('show');document.getElementById('tokHint').textContent='🔒 Token secured — tap to reveal';initVault();}
function unlockToken(){document.getElementById('tokArea').style.display='block';document.getElementById('tokVault').classList.remove('show');document.getElementById('tokHint').textContent='Token paste karo → start hone ke baad auto-hide 🔒';if(vInt)clearInterval(vInt);}
function showTokenReveal(){
  document.getElementById('tokVault').classList.remove('show');if(vInt)clearInterval(vInt);
  const t=document.getElementById('tokArea');t.style.display='block';t.style.filter='blur(4px)';
  setTimeout(()=>t.style.filter='none',200);
  document.getElementById('tokHint').textContent='👁 3 sec mein re-lock...';
  setTimeout(()=>{if(jobId)lockToken();},3000);
}

window.addEventListener('load',async()=>{
  try{const r=await fetch('/active');const d=await r.json();
    if(d.has_active){jobId=d.job_id;uid=d.uid||'';showBanner(d);document.getElementById('progCard').classList.add('show');lockToken();if(poll)clearInterval(poll);poll=setInterval(tick,800);}
  }catch(e){}
});

function showBanner(d){
  document.getElementById('ab').classList.add('show');
  document.getElementById('abInfo').textContent=`${ICONS[d.mode_key]||'💎'} ${d.reward} ${d.unit} · ${fmt(d.elapsed)} elapsed`;
  document.getElementById('abFill').style.width=(d.pct||0)+'%';
}
function hideBanner(){document.getElementById('ab').classList.remove('show');}

let cdTimer=null;
function startAutoClear(){
  const fill=document.getElementById('cdFill'),txt=document.getElementById('cdTxt');
  const S=20;fill.style.transition='none';fill.style.width='100%';let rem=S;
  setTimeout(()=>{fill.style.transition=`width ${S}s linear`;fill.style.width='0%';},100);
  cdTimer=setInterval(()=>{rem--;txt.textContent=`Auto-clear in ${rem}s...`;if(rem<=0){clearInterval(cdTimer);autoClear();}},1000);
}
function autoClear(){
  document.getElementById('doneCard').style.display='none';
  document.getElementById('progCard').classList.remove('show');
  ring(0,'gems');document.getElementById('bar').style.width='0%';
  document.getElementById('pR').textContent='0';document.getElementById('pClicks').textContent='0 / 0 steps';
  ['sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';document.getElementById('gBars').innerHTML='';
  setSt('Ready','');unlockToken();jobId='';
  document.getElementById('chainProgress').classList.remove('show');
}

function updateCalc(){
  const m=MCFG[curMode];if(!m.chain)return;
  const desired=parseInt(document.getElementById('desired').value)||0;
  const elite=desired*m.epc;
  document.getElementById('chainCalc').innerHTML=
    `Tujhe chahiye: <span>${desired}</span> ${curMode==='champion'?'Champion':'Legendary'} cards<br>
     Auto-farm: <span>${elite}</span> Elite cards → exchange: <span>${desired}</span> cards`;
}

function setMode(m){
  curMode=m;
  const mc=MCFG[m];
  Object.keys(MCFG).forEach(k=>{document.getElementById('m_'+k).className='mb '+k+(k===m?' on':'');});
  document.getElementById('dLabel').textContent=mc.lbl;
  document.getElementById('hTxt').textContent=mc.hint;
  document.getElementById('desired').value=m==='tickets'?'300':m==='legendary'||m==='champion'?'10':'5000';
  document.getElementById('desired').step=m==='tickets'?'30':m==='legendary'||m==='champion'?'1':'2';
  document.getElementById('btnS').textContent=mc.btn;
  document.getElementById('btnS').className='btn-start '+(mc.cls||'');
  const cb=document.getElementById('chainBox');
  if(mc.chain){
    cb.style.display='block';
    cb.className='show '+m;
    document.getElementById('chainTitle').textContent=`⚡ AUTO-CHAIN · ${m.toUpperCase()}`;
    document.getElementById('chainIcon2').textContent=mc.icon;
    document.getElementById('chainIcon3').textContent=mc.icon;
    updateCalc();
  } else {
    cb.style.display='none';
  }
}

function sw(v){document.getElementById('wrk').value=v;document.querySelectorAll('.pw').forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));}
function fmt(s){s=Math.max(0,Math.round(s));if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';}
function ring(p,m){
  document.getElementById('ring').style.strokeDashoffset=CIRC-(CIRC*p/100);
  document.getElementById('ring').className='ring-fg '+(MCFG[m]?.cls||'');
  document.getElementById('rpct').textContent=p.toFixed(1)+'%';
  document.getElementById('rpct').className='ring-pct '+(MCFG[m]?.cls||'');
}
function graph(h,m){const w=document.getElementById('gBars');if(!h.length)return;const mx=Math.max(...h,1);w.innerHTML=h.map(v=>`<div class="gb ${MCFG[m]?.cls||''}" style="height:${Math.max(2,(v/mx)*36)}px"></div>`).join('');}
function renderHist(list){
  const el=document.getElementById('hist');
  if(!list.length){el.innerHTML='<div class="empty">NO JOBS YET <span class="blink">_</span></div>';return;}
  el.innerHTML=list.map(s=>`<div class="si">
    <div><div class="si-r" style="color:${COLS[s.mode_key]||'var(--g1)'}">+${s.reward} ${s.label}</div>
    <div class="si-m">${s.success}/${s.total} · ${s.workers}w</div></div>
    <div class="si-tm">${s.time} ${s.date}<br/>${fmt(s.elapsed)}</div>
  </div>`).join('');
}
function setSt(m,c){const e=document.getElementById('stLine');e.textContent=m;e.className='st '+(c||'');}

function updateChainProgress(d){
  const cp=document.getElementById('chainProgress');
  if(!d.is_chain){cp.classList.remove('show');return;}
  cp.classList.add('show');
  cp.className='show '+d.mode_key;
  document.getElementById('cpTitle').textContent=`⚡ AUTO-CHAIN · ${d.mode_key.toUpperCase()}`;
  document.getElementById('p2Label').textContent=`PHASE 2 · ${d.mode_key.toUpperCase()}`;
  document.getElementById('p2Fill').className='cp-ph-fill '+(d.mode_key==='champion'?'p2c':'p2l');
  const p1t=d.phase1_total||0, p2t=d.phase2_total||0, pc=d.phase_completed||0;
  const p1s=d.phase1_success||0, p2s=d.phase2_success||0;
  if(d.phase===1){
    const p=p1t?Math.round(pc/p1t*100):0;
    document.getElementById('p1Fill').style.width=p+'%';
    document.getElementById('p1Val').textContent=`${pc} / ${p1t}`;
    document.getElementById('p2Fill').style.width='0%';
    document.getElementById('p2Val').textContent=`0 / ${p2t}`;
  } else {
    document.getElementById('p1Fill').style.width='100%';
    document.getElementById('p1Val').textContent=`${p1s} / ${p1t} ✓`;
    const p=p2t?Math.round(pc/p2t*100):0;
    document.getElementById('p2Fill').style.width=p+'%';
    document.getElementById('p2Val').textContent=`${pc} / ${p2t}`;
  }
}

async function go(){
  const tok=document.getElementById('tokArea').value.trim();
  const desired=parseInt(document.getElementById('desired').value);
  const wrk=parseInt(document.getElementById('wrk').value);
  if(!tok){alert('Token paste karo!');return;}
  if(desired<1){alert('Amount enter karo!');return;}
  if(cdTimer)clearInterval(cdTimer);
  document.getElementById('doneCard').style.display='none';
  setSt('Starting background job...','g');
  const res=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:tok,desired,workers:wrk,mode:curMode})});
  const data=await res.json();
  if(data.error){alert(data.error);setSt('','');return;}
  jobId=data.job_id;uid=data.uid||'';
  lockToken();
  document.getElementById('progCard').classList.add('show');
  document.getElementById('btnS').disabled=true;
  document.getElementById('btnX').style.display='block';
  const cls=MCFG[curMode].cls||'';
  ring(0,curMode);
  document.getElementById('bar').style.width='0%';
  document.getElementById('bar').className='bar-fill '+(cls||'');
  document.getElementById('pR').textContent='0';
  document.getElementById('pR').className='pval '+(cls||'');
  document.getElementById('rLabel').textContent=ICONS[curMode]+' ADDED';
  ['sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';
  document.getElementById('pClicks').textContent='0 / 0 steps';
  document.getElementById('gBars').innerHTML='';
  if(data.is_chain){
    setSt(`⚡ AUTO-CHAIN: farming ${data.elite_needed} elite → exchanging ${desired} cards`,'g');
  } else {
    setSt(`BG Job started · ${wrk} workers`,'g');
  }
  if(poll)clearInterval(poll);
  poll=setInterval(tick,800);
}

async function tick(){
  try{
    const r=await fetch(`/status?job_id=${jobId}&uid=${uid}`);
    if(r.status===401){clearInterval(poll);window.location.reload();return;}
    const d=await r.json();
    const mk=d.mode_key||'gems';
    const cls=MCFG[mk]?.cls||'';
    ring(d.pct,mk);
    document.getElementById('bar').style.width=d.pct+'%';
    document.getElementById('bar').className='bar-fill '+(cls||'');
    document.getElementById('pR').textContent=d.reward;
    document.getElementById('pR').className='pval '+(cls||'');
    document.getElementById('rLabel').textContent=(ICONS[mk]||'💎')+' ADDED';
    document.getElementById('pClicks').textContent=`${d.phase_completed||d.completed} / ${d.phase===2?d.phase2_total:d.phase1_total||d.total} steps`;
    document.getElementById('sSpd').textContent=d.speed;
    document.getElementById('sEta').textContent=fmt(d.eta);
    document.getElementById('sOk').textContent=d.success;
    document.getElementById('sFail').textContent=d.fail;
    graph(d.speed_history,mk);
    renderHist(d.history);
    updateChainProgress(d);
    if(d.has_active){
      showBanner(d);
      if(d.is_chain){
        const ph=d.phase===1?'Phase 1: Farming Elite cards...':'Phase 2: Exchanging cards...';
        setSt(`⚡ ${ph} · ${fmt(d.elapsed)} elapsed`,'g');
      } else {
        setSt(`${d.completed}/${d.total} · ${fmt(d.elapsed)} · server pe ✓`,'g');
      }
    }
    if(d.done){
      clearInterval(poll);resetUI();hideBanner();ring(100,mk);
      document.getElementById('bar').style.width='100%';
      document.getElementById('chainProgress').classList.remove('show');
      const dc=document.getElementById('doneCard');dc.style.display='block';
      document.getElementById('dIcon').textContent=ICONS[mk]||'💎';
      document.getElementById('dTitle').style.color=COLS[mk]||'var(--g1)';
      document.getElementById('dSub').innerHTML=
        `<strong style="color:${COLS[mk]||'var(--g1)'}">+${d.reward} ${d.unit}</strong> added!<br/>${d.success}/${d.total} success · ${fmt(d.elapsed)} total`;
      setSt('Job complete! ✅','g');
      startAutoClear();
    }
  }catch(e){setSt('Reconnecting...','');}
}

async function stopJob(){await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId})});clearInterval(poll);setSt('Stopped.','r');resetUI();hideBanner();unlockToken();jobId='';}
async function emergencyStop(){if(!confirm('Job stop karna hai?'))return;await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId})});clearInterval(poll);setSt('⛔ Emergency stop!','r');resetUI();hideBanner();unlockToken();jobId='';}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}
function resetUI(){document.getElementById('btnS').disabled=false;document.getElementById('btnX').style.display='none';}
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"\033[92m")
    print("╔══════════════════════════════════════════╗")
    print("║  DC25 ULTRA FARMER v5.1                  ║")
    print("║  ⚡ AUTO-CHAIN: Legendary + Champion      ║")
    print("║  💎 Gems · 🎫 Tickets · 🃏 Elite         ║")
    print(f"║  Email : {ADMIN_EMAIL:<32}║")
    print("║  Open  : http://localhost:5000           ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=5000, debug=False)
