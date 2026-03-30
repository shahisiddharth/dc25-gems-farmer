"""
Dream Cricket 25 - ULTRA Farmer v6.2 🌌 GALAXY EDITION
UPDATED: Gems = 4 per click | Elite = 2 per click | Tickets = 30 per click
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
    # ✅ NEW METHOD: 4 gems per click
    "gems": {
        "label":"💎 Gems", "unit":"Gems", "type":"reward_gems",
        "templateId":127900,
        "currencyTypeId":2, "amount":4,
    },
    # ✅ NEW METHOD: 30 tickets per click
    "tickets": {
        "label":"🎫 Tickets", "unit":"Tickets", "type":"reward_tickets",
        "templateId":124339,"currencyTypeId":23, "amount":30,
    },
    # ✅ NEW METHOD: 2 elite cards per click
    "elite": {
        "label":"🃏 Elite",  "unit":"Elite",   "type":"reward_elite",
        "templateId":127574,"currencyTypeId":14, "amount":2,
    },
    "legendary": {
        "label":"⭐ Legendary","unit":"Legendary","type":"chain",
        "elite_per_card":10,
        "reward_currencyTypeId":15,"reward_amount":1,
        "cost_currencyTypeId":14,"cost_amount":10,
        "attr_2770":"5.000000","amount":1,
    },
    "champion": {
        "label":"👑 Champion","unit":"Champion","type":"chain",
        "elite_per_card":10,
        "reward_currencyTypeId":16,"reward_amount":1,
        "cost_currencyTypeId":14,"cost_amount":10,
        "attr_2770":"49.000000","amount":1,
    },
}

_ts  = int(time.time())
_tsl = threading.Lock()
slots = {
    "A": {"job": None, "history": [], "lock": threading.Lock()},
    "B": {"job": None, "history": [], "lock": threading.Lock()},
}

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

# ── NEW GEMS MUTATION (4 per click) ──
def build_gems_mutation():
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 127900,
            "templateAttributes": [
                {"templateId": 0, "groupAttributeId": 3046, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3065, "attributeValue": "0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{
                "currencyTypeId": 2,
                "currencyAmount": 4,
                "giveAwayType": 7,
                "meta": "Reward"
            }]
        }]}
    }

# ── NEW ELITE MUTATION (2 per click) ──
def build_elite_mutation():
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 127574,
            "templateAttributes": [
                {"templateId": 0, "groupAttributeId": 3277, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3283, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3289, "attributeValue": uts()},
                {"templateId": 0, "groupAttributeId": 3290, "attributeValue": "0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{
                "currencyTypeId": 14,
                "currencyAmount": 2,
                "giveAwayType": 7,
                "meta": "Reward"
            }]
        }]}
    }

# ── NEW TICKETS MUTATION (30 per click) ──
def build_tickets_mutation():
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 124339,
            "templateAttributes": [
                {"templateId": 0, "groupAttributeId": 3277, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3283, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3289, "attributeValue": uts()},
                {"templateId": 0, "groupAttributeId": 3290, "attributeValue": "0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{
                "currencyTypeId": 23,
                "currencyAmount": 30,
                "giveAwayType": 11,
                "meta": "Reward"
            }]
        }]}
    }

def build_exchange_mutation(mode_key):
    m = MODES[mode_key]
    return {
        "query": """mutation assignStorePurchase ($input: ProductPurchaseAndAssignInput) {
            assignStorePurchase (input: $input) {
                purchaseState purchaseType acknowledgementState consumptionState
                orderId validPurchase kind rewardSuccess
            }
        }""",
        "variables": {"input": {
            "productPurchaseInput": {"packageName":"","productId":"","purchaseToken":"","platform":"","orderId":"","price":0,"currencyCode":"","priceText":""},
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
        p = token.split('.')[1]; p += '='*(4-len(p)%4)
        return json.loads(base64.b64decode(p)).get('user-info',{}).get('id','unknown')
    except: return 'unknown'

def make_headers(token):
    return {
        "Host":"api-prod.dreamgamestudios.in","Accept":"*/*",
        "Accept-Encoding":"gzip, deflate",
        "Authorization":f"Bearer {token}",
        "Content-Type":"application/json; charset=utf-8",
        "X-SpineSDK":"0.1","gameId":"1","studioId":"1",
        "userId":get_uid(token),"game-env":"BLUE","gameVersion":"1.5.55",
        "secretKey":"6b77f094-45e2-46d0-b6cc-827dcb5f6b85",
        "X-API-VERSION":"1",
        "User-Agent":"ProjectCricketUE4/++UE4+Release-4.27-CL-0 Android/15"
    }

def do_single(hdr, mode_key):
    m = MODES[mode_key]
    try:
        if m["type"] == "reward_gems":
            r = req.post(URL_USERDATA, headers=hdr, json=build_gems_mutation(), timeout=15)
            return r.status_code == 200
        elif m["type"] == "reward_tickets":
            r = req.post(URL_USERDATA, headers=hdr, json=build_tickets_mutation(), timeout=15)
            return r.status_code == 200
        elif m["type"] == "reward_elite" or m["type"] == "chain_elite":
            r = req.post(URL_USERDATA, headers=hdr, json=build_elite_mutation(), timeout=15)
            return r.status_code == 200
        else:
            r = req.post(URL_RECEIPT, headers=hdr, json=build_exchange_mutation(mode_key), timeout=15)
            if r.status_code == 200:
                return r.json().get("data",{}).get("assignStorePurchase",{}).get("rewardSuccess") == True
            return False
    except: return False

def run_phase(slot, hdr, total, workers, fn, phase_key):
    lk = slots[slot]["lock"]
    batches = math.ceil(total/workers)
    bt = []; phase_done = 0
    for b in range(batches):
        with lk:
            j = slots[slot]["job"]
            if not j or not j["running"]: return phase_done
        sz = min(workers, total - b*workers)
        if sz <= 0: break
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs = [ex.submit(fn) for _ in range(sz)]
            results = [f.result() for f in as_completed(fs)]
        t1 = time.time()
        ok = sum(1 for r in results if r); bad = sz - ok; phase_done += ok
        bt.append(t1-t0)
        if len(bt) > 10: bt.pop(0)
        avg = sum(bt)/len(bt); spd = round(workers/avg, 1); eta = (batches-b-1)*avg
        with lk:
            j = slots[slot]["job"]
            if j:
                j[phase_key] = phase_done; j["fail"] += bad
                j["phase_done"] = (b+1)*workers; j["eta"] = eta; j["speed"] = spd
                j["speed_history"].append(spd)
                if len(j["speed_history"]) > 30: j["speed_history"].pop(0)
    return phase_done

def run_job(slot):
    lk = slots[slot]["lock"]
    with lk:
        j = slots[slot]["job"]
        if not j: return
        token = j["token"]; total = j["total"]
        workers = j["workers"]; mode_key = j["mode_key"]
    hdr = make_headers(token)
    m = MODES[mode_key]

    if m["type"] == "chain":
        elite_needed = total * m["elite_per_card"]
        # Since elite mutation now gives 2, we need half the clicks
        clicks_needed = math.ceil(elite_needed / MODES["elite"]["amount"])
        with lk:
            j = slots[slot]["job"]
            if j:
                j["phase"] = 1; j["phase1_total"] = clicks_needed
                j["phase2_total"] = total; j["phase_done"] = 0
        p1ok_clicks = run_phase(slot, hdr, clicks_needed, workers,
                         lambda: do_single(hdr, "elite_internal"), "phase1_success")
        p1ok_elite = p1ok_clicks * MODES["elite"]["amount"]
        with lk:
            j = slots[slot]["job"]
            if not j or not j["running"]:
                _finish(slot, mode_key, total, workers); return
            j["phase"] = 2; j["phase_done"] = 0
        cards = p1ok_elite // m["elite_per_card"]
        run_phase(slot, hdr, cards, max(1, workers//5),
                  lambda: do_single(hdr, mode_key), "phase2_success")
    else:
        run_phase(slot, hdr, total, workers,
                  lambda: do_single(hdr, mode_key), "success")

    _finish(slot, mode_key, total, workers)

# Elite internal for chain
MODES["elite_internal"] = {
    "label":"🃏 Elite", "unit":"Elite", "type":"chain_elite",
    "templateId":127574,"currencyTypeId":14,"amount":2
}

def _finish(slot, mode_key, total, workers):
    lk = slots[slot]["lock"]
    with lk:
        j = slots[slot]["job"]
        if not j: return
        j["running"] = False; j["done"] = True; j["end_time"] = time.time()
        elapsed = j["end_time"] - j["start_time"]
        m = MODES[mode_key]
        success = j.get("phase2_success",0) if m["type"]=="chain" else j.get("success",0)
        entry = {
            "reward": success * m["amount"], "unit": m["unit"], "label": m["label"],
            "mode_key": mode_key, "success": success, "total": total, "workers": workers,
            "elapsed": round(elapsed,1), "time": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%d %b")
        }
        slots[slot]["history"].insert(0, entry)
        if len(slots[slot]["history"]) > 5:
            slots[slot]["history"] = slots[slot]["history"][:5]

def is_logged_in(): return session.get("logged_in") == True

def get_slot_status(slot):
    lk = slots[slot]["lock"]
    with lk:
        j = slots[slot]["job"]; hist = list(slots[slot]["history"])
    if not j:
        return {"running":False,"done":False,"slot":slot,"pct":0,"reward":0,"unit":"","success":0,"fail":0,"eta":0,"speed":0,"elapsed":0,"speed_history":[],"history":hist,"has_active":False,"phase":1,"phase1_total":0,"phase2_total":0,"phase_done":0,"phase1_success":0,"phase2_success":0,"is_chain":False,"mode_key":"gems","total":0}
    elapsed = (time.time() if j["running"] else j["end_time"]) - j["start_time"]
    mk = j["mode_key"]; m = MODES.get(mk, MODES["gems"]); is_chain = m["type"] == "chain"
    if is_chain:
        p1t = j.get("phase1_total",0); p2t = j.get("phase2_total",0)
        ph = j.get("phase",1); pd = j.get("phase_done",0)
        total_steps = p1t + p2t; done_steps = (p1t+pd) if ph==2 else pd
        pct = round(done_steps/total_steps*100,1) if total_steps else 0
        reward = j.get("phase2_success",0) * m["amount"]; success = j.get("phase2_success",0)
    else:
        pd = j.get("phase_done",0); tot = j["total"]
        pct = round(pd/tot*100,1) if tot else 0
        reward = j.get("success",0) * m["amount"]; success = j.get("success",0)
    return {
        "running":j["running"],"done":j["done"],"slot":slot,"pct":pct,
        "reward":reward,"unit":m["unit"],"label":m["label"],"success":success,
        "fail":j.get("fail",0),"eta":round(j.get("eta",0)),"speed":j.get("speed",0),
        "elapsed":round(elapsed),"speed_history":j.get("speed_history",[]),
        "history":hist,"has_active":j["running"],"mode_key":mk,"is_chain":is_chain,
        "total":j["total"],"phase":j.get("phase",1),"phase1_total":j.get("phase1_total",0),
        "phase2_total":j.get("phase2_total",0),"phase_done":j.get("phase_done",0),
        "phase1_success":j.get("phase1_success",0),"phase2_success":j.get("phase2_success",0),
    }

@app.route("/")
def index():
    if not is_logged_in(): return LOGIN_PAGE
    return MAIN_PAGE

@app.route("/login", methods=["POST"])
def login():
    d = request.json
    if d.get("email","").strip().lower()==ADMIN_EMAIL.lower() and d.get("password","").strip()==ADMIN_PASSWORD:
        session["logged_in"]=True; session.permanent=True; return jsonify({"ok":True})
    return jsonify({"error":"Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return jsonify({"ok":True})

@app.route("/start", methods=["POST"])
def start():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    d = request.json; slot = d.get("slot","A")
    if slot not in ["A","B"]: slot = "A"
    token = d.get("token","").strip(); desired = int(d.get("desired",100))
    workers = min(int(d.get("workers",20)), MAX_WORKERS)
    mode_key = d.get("mode","gems")
    if mode_key not in MODES or mode_key == "elite_internal": mode_key = "gems"
    if not token: return jsonify({"error":"Token required"}), 400
    lk = slots[slot]["lock"]
    with lk:
        j = slots[slot]["job"]
        if j and j["running"]: return jsonify({"error":f"Job {slot} already running!"}), 400
    m = MODES[mode_key]
    total = desired if m["type"]=="chain" else math.ceil(desired/m["amount"])
    with lk:
        slots[slot]["job"] = {
            "running":True,"done":False,"success":0,"fail":0,"total":total,
            "phase_done":0,"start_time":time.time(),"end_time":0,"eta":0,"speed":0,
            "speed_history":[],"token":token,"workers":workers,"mode_key":mode_key,
            "phase":1,"phase1_total":0,"phase2_total":0,"phase1_success":0,"phase2_success":0,
        }
    threading.Thread(target=run_job, args=(slot,), daemon=True).start()
    return jsonify({
        "ok":True,"slot":slot,"unit":m["unit"],"amount":m["amount"],
        "is_chain":m["type"]=="chain",
        "elite_needed": desired*m.get("elite_per_card",1) if m["type"]=="chain" else 0
    })

@app.route("/stop", methods=["POST"])
def stop():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    slot = request.json.get("slot","A"); lk = slots[slot]["lock"]
    with lk:
        j = slots.get(slot,{}).get("job")
        if j: j["running"] = False
    return jsonify({"ok":True})

@app.route("/status")
def status():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    return jsonify(get_slot_status(request.args.get("slot","A")))

@app.route("/status_all")
def status_all():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}), 401
    return jsonify({"A":get_slot_status("A"),"B":get_slot_status("B")})

@app.route("/ping")
def ping(): return "pong", 200

LOGIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 · GALAXY ACCESS</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#05000a;overflow:hidden;font-family:'Share Tech Mono',monospace;cursor:none;}
.cur{position:fixed;width:16px;height:16px;border:1px solid #c264fe;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:screen;}
.cur::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:3px;height:3px;background:#c264fe;border-radius:50%;}
#cv{position:fixed;inset:0;z-index:1;}
.nebula{position:fixed;border-radius:50%;filter:blur(80px);opacity:.15;z-index:1;animation:nebMove 8s ease-in-out infinite;}
@keyframes nebMove{0%,100%{transform:scale(1)}50%{transform:scale(1.2)}}
.star{position:fixed;border-radius:50%;background:#fff;animation:twinkle 3s infinite;z-index:2;}
@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}
#intro{position:fixed;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.gring{position:absolute;border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%) scale(0);animation:grp 5s ease-out infinite;border:1px solid rgba(194,100,254,.12);}
.gring:nth-child(1){width:160px;height:160px;}
.gring:nth-child(2){width:320px;height:320px;animation-delay:1s;}
.gring:nth-child(3){width:500px;height:500px;animation-delay:2s;}
.gring:nth-child(4){width:700px;height:700px;animation-delay:3s;}
.gring:nth-child(5){width:950px;height:950px;animation-delay:4s;}
@keyframes grp{0%{transform:translate(-50%,-50%) scale(0);opacity:.6}100%{transform:translate(-50%,-50%) scale(1);opacity:0}}
.co{position:absolute;width:60px;height:60px;opacity:0;}
.co.tl{top:16px;left:16px;border-top:2px solid #c264fe;border-left:2px solid #c264fe;animation:ci .3s ease .3s forwards;}
.co.tr{top:16px;right:16px;border-top:2px solid #c264fe;border-right:2px solid #c264fe;animation:ci .3s ease .45s forwards;}
.co.bl{bottom:16px;left:16px;border-bottom:2px solid #c264fe;border-left:2px solid #c264fe;animation:ci .3s ease .6s forwards;}
.co.br{bottom:16px;right:16px;border-bottom:2px solid #c264fe;border-right:2px solid #c264fe;animation:ci .3s ease .75s forwards;}
@keyframes ci{to{opacity:1}}
#ctr{position:relative;z-index:5;text-align:center;opacity:0;animation:cn .8s cubic-bezier(.16,1,.3,1) 1.5s forwards;}
@keyframes cn{0%{opacity:0;transform:scale(.85)}100%{opacity:1;transform:scale(1)}}
.orb-wrap{position:relative;display:inline-block;margin-bottom:14px;}
.galaxy-orb{width:90px;height:90px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#9933ff,#4400aa,#220055);box-shadow:0 0 50px rgba(194,100,254,.7);animation:orbPulse 3s ease-in-out infinite;}
@keyframes orbPulse{0%,100%{box-shadow:0 0 40px rgba(194,100,254,.5)}50%{box-shadow:0 0 80px rgba(194,100,254,1)}}
.orb-gem{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:32px;}
.spin-ring{position:absolute;border-radius:50%;border:1px solid rgba(194,100,254,.3);top:-14px;left:-14px;right:-14px;bottom:-14px;animation:spinR 4s linear infinite;}
@keyframes spinR{to{transform:rotate(360deg)}}
.spin-dot{width:7px;height:7px;background:#c264fe;border-radius:50%;position:absolute;top:-3px;left:50%;transform:translateX(-50%);box-shadow:0 0 10px #c264fe;}
.spin-ring2{position:absolute;border-radius:50%;border:1px dashed rgba(194,100,254,.15);top:-28px;left:-28px;right:-28px;bottom:-28px;animation:spinR 8s linear reverse infinite;}
.mt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(20px,6vw,44px);letter-spacing:8px;color:#c264fe;text-shadow:0 0 30px rgba(194,100,254,.8);position:relative;}
.mt::before{content:'GALAXY FARM';position:absolute;top:0;left:0;right:0;color:#ff44ff;opacity:0;animation:glitch1 6s infinite 3s;clip-path:polygon(0 20%,100% 20%,100% 40%,0 40%);}
.mt::after{content:'GALAXY FARM';position:absolute;top:0;left:0;right:0;color:#4400ff;opacity:0;animation:glitch2 6s infinite 3.1s;clip-path:polygon(0 60%,100% 60%,100% 80%,0 80%);}
@keyframes glitch1{0%,92%,100%{opacity:0}93%{opacity:.9;transform:translate(-3px,0)}94%{opacity:0}96%{opacity:.7;transform:translate(-2px,0)}97%{opacity:0}}
@keyframes glitch2{0%,92%,100%{opacity:0}93%{opacity:.9;transform:translate(3px,0)}94%{opacity:0}96%{opacity:.7;transform:translate(2px,0)}97%{opacity:0}}
.vt{display:inline-block;background:rgba(194,100,254,.08);border:1px solid rgba(194,100,254,.25);border-radius:2px;padding:3px 12px;font-size:9px;color:#9933ff;letter-spacing:5px;margin-top:8px;}
.new-badge{display:inline-block;background:rgba(0,255,100,.1);border:1px solid rgba(0,255,100,.3);border-radius:2px;padding:2px 8px;font-size:8px;color:#00ff88;letter-spacing:3px;margin-top:6px;animation:nblink 1.5s infinite;}
@keyframes nblink{0%,100%{opacity:1}50%{opacity:.4}}
#pw{margin-top:18px;width:min(320px,68vw);opacity:0;animation:fu .4s ease 2.2s forwards;}
@keyframes fu{to{opacity:1}}
.ph{display:flex;justify-content:space-between;font-size:9px;color:#4a2a6a;margin-bottom:5px;}
.pt2{background:rgba(194,100,254,.04);border:1px solid rgba(194,100,254,.1);border-radius:2px;height:7px;overflow:hidden;}
.pf{height:100%;width:0%;background:linear-gradient(90deg,#220055,#9933ff,#c264fe);}
.sps{margin-top:5px;display:flex;flex-direction:column;gap:3px;}
.sr{display:flex;align-items:center;gap:8px;font-size:7px;color:#4a2a6a;}
.sl2{width:80px;text-align:right;}.sts{flex:1;height:3px;background:rgba(194,100,254,.04);border-radius:1px;overflow:hidden;}
.sf{height:100%;width:0%;transition:width 1s;border-radius:1px;background:#9933ff;}
.sp{width:26px;color:#7722cc;font-size:7px;}
#bs{margin-top:8px;font-size:10px;color:#7722cc;letter-spacing:2px;text-align:center;min-height:14px;opacity:0;animation:fu .3s ease 2.6s forwards;}
#ag{position:fixed;inset:0;z-index:50;background:#05000a;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;}
.agb{border:2px solid #c264fe;padding:28px 50px;text-align:center;box-shadow:0 0 80px rgba(194,100,254,.5);}
.agi{font-size:44px;margin-bottom:10px;}
.agt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(14px,4vw,28px);letter-spacing:8px;color:#c264fe;}
.ags{font-size:10px;color:#7722cc;letter-spacing:4px;margin-top:6px;}
#sk{position:fixed;bottom:16px;right:16px;z-index:100;background:rgba(194,100,254,.04);border:1px solid rgba(194,100,254,.1);border-radius:3px;color:rgba(194,100,254,.25);font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;padding:4px 10px;cursor:pointer;}
#lw{position:fixed;inset:0;z-index:8;display:none;align-items:center;justify-content:center;background:rgba(5,0,10,.97);transition:opacity .5s;}
#lw.show{display:flex;}
.lc{background:#0d0018;border:1px solid rgba(194,100,254,.15);border-radius:6px;padding:24px;width:min(340px,85vw);position:relative;overflow:hidden;box-shadow:0 0 40px rgba(0,0,0,.5);}
.lc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#c264fe,transparent);}
.ll{text-align:center;margin-bottom:20px;}
.li{font-size:32px;margin-bottom:8px;}
.lh{font-family:'Orbitron',monospace;font-size:16px;letter-spacing:4px;color:#c264fe;}
.lp{font-size:8px;color:#4a2a6a;letter-spacing:2px;margin-top:4px;}
.lf{margin-bottom:14px;}
.lf label{display:block;font-size:8px;color:#7722cc;letter-spacing:2px;margin-bottom:5px;}
.lf input{width:100%;background:rgba(194,100,254,.03);border:1px solid rgba(194,100,254,.1);border-radius:2px;padding:9px 12px;color:#c264fe;font-family:'Share Tech Mono',monospace;font-size:12px;outline:none;transition:border .3s;}
.lf input:focus{border-color:rgba(194,100,254,.4);background:rgba(194,100,254,.06);}
.lb{width:100%;background:#c264fe;border:none;border-radius:2px;padding:11px;color:#05000a;font-family:'Orbitron',monospace;font-weight:900;font-size:11px;letter-spacing:3px;cursor:pointer;transition:all .3s;}
.lb:hover{background:#ff44ff;box-shadow:0 0 20px rgba(255,68,255,.4);}
.lb:disabled{background:#4a2a6a;cursor:not-allowed;box-shadow:none;}
.le{margin-top:12px;color:#ff2244;font-size:10px;text-align:center;opacity:0;transition:opacity .3s;}
.le.show{opacity:1;}
#cur{position:fixed;width:16px;height:16px;border:1px solid #c264fe;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:screen;}
#cur::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:3px;height:3px;background:#c264fe;border-radius:50%;}
.sr{display:flex;align-items:center;gap:8px;font-size:7px;color:#4a2a6a;}
.sl2{width:80px;text-align:right;}.sts{flex:1;height:3px;background:rgba(194,100,254,.04);border-radius:1px;overflow:hidden;}
.sf{height:100%;width:0%;transition:width 1s;border-radius:1px;background:#9933ff;}
.sp{width:26px;color:#7722cc;font-size:7px;}
</style>
</head>
<body>
<div id="cur"></div>
<canvas id="cv"></canvas>
<div id="intro">
  <div class="gring"></div><div class="gring"></div><div class="gring"></div><div class="gring"></div><div class="gring"></div>
  <div class="co tl"></div><div class="co tr"></div><div class="co bl"></div><div class="co br"></div>
  <div id="ctr">
    <div class="orb-wrap">
      <div class="galaxy-orb"></div><div class="orb-gem">🌌</div>
      <div class="spin-ring"><div class="spin-dot"></div></div>
      <div class="spin-ring2"></div>
    </div>
    <div class="mt">GALAXY FARM</div>
    <div class="vt">ULTRA v6.2</div>
    <div class="new-badge">NEW REWARDS UPDATED</div>
    <div id="pw">
      <div class="ph"><span>COSMIC SYNC</span><span id="pn">0%</span></div>
      <div class="pt2"><div class="pf" id="pfl"></div></div>
      <div class="sps">
        <div class="sr"><span class="sl2">GEMS CORE</span><div class="sts"><div class="sf" id="s1" style="background:#c264fe"></div></div><span class="sp" id="s1p">0%</span></div>
        <div class="sr"><span class="sl2">TICKET GATE</span><div class="sts"><div class="sf" id="s2" style="background:#ff8c00"></div></div><span class="sp" id="s2p">0%</span></div>
        <div class="sr"><span class="sl2">ELITE MATRIX</span><div class="sts"><div class="sf" id="s3" style="background:#aa88ff"></div></div><span class="sp" id="s3p">0%</span></div>
        <div class="sr"><span class="sl2">COSMIC PING</span><div class="sts"><div class="sf" id="s4" style="background:#4400ff"></div></div><span class="sp" id="s4p">0%</span></div>
      </div>
    </div>
    <div id="bs">▌</div>
  </div>
</div>
<div id="ag"><div class="agb"><div class="agi">🌌</div><div class="agt">GALAXY UNLOCKED</div><div class="ags">WELCOME · KING SHAHI</div></div></div>
<div id="lw">
  <div class="lc">
    <div class="ll"><div class="li">💎</div><div class="lh">GALAXY FARM</div><div class="lp">COSMIC ACCESS REQUIRED</div></div>
    <div class="lf"><label>EMAIL</label><input type="email" id="em" placeholder="your@email.com" autocomplete="email"/></div>
    <div class="lf"><label>PASSWORD</label><input type="password" id="pw2" placeholder="••••••••" autocomplete="current-password"/></div>
    <button class="lb" id="lb" onclick="doLogin()">🌌 ENTER GALAXY</button>
    <div class="le" id="le"></div>
  </div>
</div>
<button id="sk" onclick="skipAll()">SKIP ▶▶</button>
<script>
const cur=document.getElementById('cur');
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px';});
const cv=document.getElementById('cv'),cx=cv.getContext('2d');
cv.width=window.innerWidth;cv.height=window.innerHeight;
for(let i=0;i<150;i++){const s=document.createElement('div');s.className='star';const sz=Math.random()*2.5+0.5;s.style.cssText=`width:${sz}px;height:${sz}px;top:${Math.random()*100}%;left:${Math.random()*100}%;animation-delay:${Math.random()*3}s;animation-duration:${2+Math.random()*3}s;opacity:${Math.random()*.6+.1}`;document.body.appendChild(s);}
const cols=Math.floor(cv.width/16),drops=Array(cols).fill(1);
const CH='アイウカキクサシスタチナニハヒABCDEF0123456789★☆◆';
function drawM(){cx.fillStyle='rgba(5,0,10,0.06)';cx.fillRect(0,0,cv.width,cv.height);drops.forEach((y,i)=>{const c=CH[Math.floor(Math.random()*CH.length)];const r=Math.random();cx.fillStyle=r>.95?'#ff88ff':r>.8?'#c264fe':r>.5?'#6600aa44':'#33006622';cx.font='13px Share Tech Mono';cx.fillText(c,i*16,y*16);if(y*16>cv.height&&Math.random()>.975)drops[i]=0;drops[i]++;});}
const mI=setInterval(drawM,50);
let pct=0,li=0;
const lbls=['NEW METHOD 4x...','DUAL JOBS...','AUTO-CHAIN...','COSMIC PING...','READY!'];
const pfl=document.getElementById('pfl'),pn=document.getElementById('pn'),plbl=document.getElementById('pl'),bsEl=document.getElementById('bs');
setTimeout(()=>{const iv=setInterval(()=>{pct+=Math.random()*4+0.5;if(pct>=100){pct=100;clearInterval(iv);setTimeout(showAG,300);}pfl.style.width=pct+'%';pn.textContent=Math.floor(pct)+'%';const nl=Math.floor((pct/100)*lbls.length);if(nl!==li&&nl<lbls.length){li=nl;if(plbl)plbl.textContent=lbls[li];bsEl.textContent='> '+lbls[li];}[['s1','s1p'],['s2','s2p'],['s3','s3p'],['s4','s4p']].forEach(([id,pid],i)=>{const v=Math.min(100,Math.max(0,(pct-i*25)*4));document.getElementById(id).style.width=v+'%';document.getElementById(pid).textContent=Math.floor(v)+'%';});},55);},1800);
function showAG(){const ag=document.getElementById('ag');ag.style.opacity='1';ag.style.pointerEvents='auto';let f=0;const iv=setInterval(()=>{f++;ag.style.background=f%2===0?'#05000a':'rgba(194,100,254,.06)';if(f>=6){clearInterval(iv);setTimeout(showLogin,500);}},130);}
function showLogin(){[document.getElementById('intro'),document.getElementById('ag')].forEach(el=>{el.style.transition='opacity 0.7s';el.style.opacity='0';});document.getElementById('sk').style.display='none';clearInterval(mI);setTimeout(()=>{document.getElementById('intro').style.display='none';document.getElementById('ag').style.display='none';document.getElementById('lw').classList.add('show');document.getElementById('em').focus();},750);}
function skipAll(){showLogin();}
document.addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
async function doLogin(){
  const em=document.getElementById('em').value.trim(),pw=document.getElementById('pw2').value.trim();
  const btn=document.getElementById('lb');
  if(!em||!pw){showE('Email aur password chahiye!');return;}
  btn.disabled=true;btn.textContent='WARPING...';document.getElementById('le').classList.remove('show');
  try{const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em,password:pw})});const d=await r.json();if(d.ok){window.location.reload();}else{showE(d.error||'Access denied!');}}catch(e){showE('Connection error!');}
  btn.disabled=false;btn.textContent='🌌 ENTER GALAXY';
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
<title>GALAXY FARM · DC25 v6.2</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#05000a;--panel:#0d0018;--border:rgba(194,100,254,.15);--p1:#c264fe;--p2:#9933ff;--p3:#6600aa;--p4:#330055;--p1a:rgba(194,100,254,.08);--pink:#ff44ff;--cyan:#aa44ff;--red:#ff2244;--yellow:#ffd600;--gold:#ffd700;--orange:#ff8c00;--text:#d4a8ff;--dim:#4a2a6a;--cgems:#c264fe;--ctickets:#ff8c00;--celite:#aa88ff;--clegend:#ff44ff;--cchamp:#ffd700;}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 90% 60% at 20% 10%,rgba(102,0,170,.12) 0%,transparent 60%),radial-gradient(ellipse 70% 50% at 80% 90%,rgba(68,0,255,.08) 0%,transparent 60%);pointer-events:none;z-index:0;}
body::after{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.12) 3px,rgba(0,0,0,.12) 4px);pointer-events:none;z-index:1;}
.star-field{position:fixed;inset:0;z-index:0;pointer-events:none;}
.wrap{position:relative;z-index:2;}
.hdr{padding:14px 16px 12px;text-align:center;border-bottom:1px solid var(--border);position:relative;background:rgba(13,0,24,.8);}
.hdr::after{content:'';position:absolute;bottom:0;left:5%;right:5%;height:1px;background:linear-gradient(90deg,transparent,var(--p1),var(--pink),var(--p1),transparent);}
.hdr-badge{display:inline-block;background:rgba(194,100,254,.1);border:1px solid rgba(194,100,254,.3);border-radius:2px;padding:2px 10px;font-size:9px;letter-spacing:4px;color:var(--p2);margin-bottom:5px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(14px,4.5vw,26px);letter-spacing:6px;background:linear-gradient(135deg,var(--p1),var(--pink),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr p{color:var(--dim);font-size:8px;letter-spacing:2px;margin-top:3px;}
.new-method{display:inline-flex;align-items:center;gap:5px;background:rgba(0,255,100,.08);border:1px solid rgba(0,255,100,.25);border-radius:2px;padding:2px 8px;font-size:8px;color:#00ff88;letter-spacing:2px;margin-top:4px;animation:nblink 2s infinite;}
@keyframes nblink{0%,100%{opacity:1}50%{opacity:.5}}
.logout-btn{position:absolute;top:12px;right:12px;background:transparent;border:1px solid rgba(255,34,68,.3);border-radius:3px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:9px;padding:3px 8px;cursor:pointer;}
.ping-badge{position:absolute;top:14px;left:12px;display:flex;align-items:center;gap:4px;font-size:8px;color:var(--p2);}
.ping-dot{width:5px;height:5px;border-radius:50%;background:var(--p1);animation:pd 2s infinite;}
@keyframes pd{0%,100%{opacity:1;box-shadow:0 0 6px var(--p1);}50%{opacity:.4;}}
.dual-status{display:flex;gap:6px;padding:8px 10px;background:rgba(0,0,0,.4);border-bottom:1px solid var(--border);}
.ds-item{flex:1;background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:6px 8px;position:relative;overflow:hidden;}
.ds-item::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,rgba(194,100,254,.06) 0%,transparent 60%);pointer-events:none;}
.ds-item.sa{border-left:2px solid var(--p1);}.ds-item.sb{border-left:2px solid var(--pink);}
.ds-slot{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:3px;margin-bottom:2px;}
.ds-item.sa .ds-slot{color:var(--p1);}.ds-item.sb .ds-slot{color:var(--pink);}
.ds-reward{font-family:'Orbitron',monospace;font-size:13px;font-weight:700;}
.ds-item.sa .ds-reward{color:var(--p1);}.ds-item.sb .ds-reward{color:var(--pink);}
.ds-info{font-size:8px;color:var(--dim);}
.ds-bar{margin-top:3px;background:rgba(194,100,254,.05);border-radius:1px;height:3px;overflow:hidden;}
.dfa{height:100%;background:linear-gradient(90deg,var(--p4),var(--p1));transition:width .4s;}
.dfb{height:100%;background:linear-gradient(90deg,#2a0044,var(--pink));transition:width .4s;}
.ds-stop{position:absolute;top:3px;right:5px;background:transparent;border:none;color:rgba(255,34,68,.4);font-size:11px;cursor:pointer;padding:0;}
.ds-stop:hover{color:var(--red);}
.job-tabs{display:flex;border-bottom:1px solid var(--border);background:var(--panel);}
.job-tab{flex:1;padding:11px 8px;text-align:center;cursor:pointer;transition:all .2s;border-bottom:2px solid transparent;}
.job-tab.aa{border-bottom-color:var(--p1);background:rgba(194,100,254,.06);}
.job-tab.ab{border-bottom-color:var(--pink);background:rgba(255,68,255,.06);}
.jtl{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;}
.job-tab.aa .jtl{color:var(--p1);}.job-tab.ab .jtl{color:var(--pink);}
.job-tab:not(.aa):not(.ab) .jtl{color:var(--dim);}
.jts{font-size:7px;color:var(--dim);margin-top:2px;}
.jbadge{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:3px;vertical-align:middle;}
.jbadge.ra{background:var(--p1);box-shadow:0 0 6px var(--p1);animation:pd 1s infinite;}
.jbadge.rb{background:var(--pink);box-shadow:0 0 6px var(--pink);animation:pd 1s infinite;}
.jbadge.idle{background:var(--dim);}.jbadge.done{background:var(--yellow);}
.page{max-width:680px;margin:0 auto;padding:10px 11px 40px;display:flex;flex-direction:column;gap:9px;}
.job-panel{display:none;}.job-panel.show{display:flex;flex-direction:column;gap:9px;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:13px;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,rgba(194,100,254,.05) 0%,transparent 60%);pointer-events:none;}
.cg{position:absolute;top:0;left:0;width:100%;height:1px;background:linear-gradient(90deg,transparent,var(--p1),transparent);opacity:.4;}
.cl{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.ci{width:32px;height:32px;background:var(--p1a);border:1px solid var(--border);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:18px;}
.ct{flex:1;}.ct h2{font-family:'Orbitron',monospace;font-size:12px;letter-spacing:3px;color:var(--p1);}.ct p{font-size:8px;color:var(--dim);letter-spacing:1px;}
.fi{margin-bottom:10px;}.fi label{display:block;font-size:8px;color:var(--dim);letter-spacing:2px;margin-bottom:5px;text-transform:uppercase;}
.fi input,.fi select{width:100%;background:rgba(194,100,254,.03);border:1px solid var(--border);border-radius:3px;padding:9px 12px;color:var(--p1);font-family:'Share Tech Mono',monospace;font-size:12px;outline:none;transition:all .3s;}
.fi input:focus{border-color:var(--p1);background:rgba(194,100,254,.06);}
.modes{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px;margin-bottom:12px;}
.mode{background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:4px;padding:8px 5px;text-align:center;cursor:pointer;transition:all .2s;position:relative;}
.mode.active{border-color:var(--p1);background:var(--p1a);box-shadow:0 0 10px rgba(194,100,254,.15);}
.mode-icon{font-size:18px;margin-bottom:4px;}.mode-name{font-size:8px;font-weight:700;letter-spacing:1px;}
.mode.active .mode-name{color:var(--p1);}
.btn-start{width:100%;background:linear-gradient(135deg,var(--p1),var(--p2));border:none;border-radius:3px;padding:12px;color:#05000a;font-family:'Orbitron',monospace;font-weight:900;font-size:11px;letter-spacing:4px;cursor:pointer;transition:all .3s;text-transform:uppercase;}
.btn-start:hover{transform:translateY(-1px);box-shadow:0 5px 15px rgba(194,100,254,.3);}
.btn-start:active{transform:translateY(0);}
.btn-start:disabled{background:var(--dim);color:rgba(255,255,255,.2);cursor:not-allowed;box-shadow:none;}
.hist-list{display:flex;flex-direction:column;gap:6px;}.hist-item{background:rgba(0,0,0,.2);border:1px solid rgba(194,100,254,.08);border-radius:4px;padding:7px 10px;display:flex;align-items:center;justify-content:space-between;font-size:10px;}
.hi-left{display:flex;flex-direction:column;gap:2px;}.hi-label{font-weight:700;color:var(--p1);}.hi-time{font-size:7px;color:var(--dim);}
.hi-right{text-align:right;}.hi-val{font-family:'Orbitron',monospace;font-weight:700;color:var(--yellow);}.hi-unit{font-size:7px;color:var(--dim);margin-left:2px;}
#cur{position:fixed;width:16px;height:16px;border:1px solid #c264fe;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:screen;}
#cur::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:3px;height:3px;background:#c264fe;border-radius:50%;}
@media(max-width:480px){.page{padding:10px 8px 30px;}.modes{grid-template-columns:repeat(3,1fr);}}
</style>
</head>
<body>
<div id="cur"></div>
<div class="star-field" id="stars"></div>
<div class="wrap">
  <div class="hdr">
    <div class="ping-badge"><div class="ping-dot"></div><span>COSMIC LINK ACTIVE</span></div>
    <div class="hdr-badge">SYSTEM V6.2</div>
    <h1>GALAXY FARM</h1>
    <div class="new-method">✨ NEW REWARDS UPDATED (4 GEMS / 2 ELITE / 30 TICKETS)</div>
    <button class="logout-btn" onclick="doLogout()">DISCONNECT</button>
  </div>
  <div class="dual-status">
    <div class="ds-item sa" onclick="switchTab('A')">
      <div class="ds-slot">SLOT A</div>
      <div class="ds-reward" id="ra_val">0 <span style="font-size:8px">IDLE</span></div>
      <div class="ds-info" id="ra_info">Waiting for orders...</div>
      <div class="ds-bar"><div class="dfa" id="ra_bar" style="width:0%"></div></div>
      <button class="ds-stop" onclick="event.stopPropagation();stopJob('A')">⏻</button>
    </div>
    <div class="ds-item sb" onclick="switchTab('B')">
      <div class="ds-slot">SLOT B</div>
      <div class="ds-reward" id="rb_val">0 <span style="font-size:8px">IDLE</span></div>
      <div class="ds-info" id="rb_info">Waiting for orders...</div>
      <div class="ds-bar"><div class="dfb" id="rb_bar" style="width:0%"></div></div>
      <button class="ds-stop" onclick="event.stopPropagation();stopJob('B')">⏻</button>
    </div>
  </div>
  <div class="job-tabs">
    <div class="job-tab aa" id="tabA" onclick="switchTab('A')">
      <div class="jtl"><span class="jbadge idle" id="ba"></span>GALAXY A</div>
      <div class="jts" id="sa_ts">READY</div>
    </div>
    <div class="job-tab" id="tabB" onclick="switchTab('B')">
      <div class="jtl"><span class="jbadge idle" id="bb"></span>GALAXY B</div>
      <div class="jts" id="sb_ts">READY</div>
    </div>
  </div>
  <div class="page">
    <div id="panelA" class="job-panel show">
      <div class="card">
        <div class="cg"></div>
        <div class="cl"><div class="ci">🛸</div><div class="ct"><h2>COSMIC CONFIG</h2><p>Configure farming parameters for Slot A</p></div></div>
        <div class="fi"><label>AUTH TOKEN</label><input type="text" id="tkA" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."/></div>
        <div class="fi"><label>REWARD MODE</label>
          <div class="modes" id="modesA">
            <div class="mode active" onclick="setMode('A','gems')"><div class="mode-icon">💎</div><div class="mode-name">GEMS</div></div>
            <div class="mode" onclick="setMode('A','tickets')"><div class="mode-icon">🎫</div><div class="mode-name">TICKETS</div></div>
            <div class="mode" onclick="setMode('A','elite')"><div class="mode-icon">🃏</div><div class="mode-name">ELITE</div></div>
            <div class="mode" onclick="setMode('A','legendary')"><div class="mode-icon">⭐</div><div class="mode-name">LEGEND</div></div>
            <div class="mode" onclick="setMode('A','champion')"><div class="mode-icon">👑</div><div class="mode-name">CHAMP</div></div>
          </div>
        </div>
        <div style="display:flex;gap:10px;margin-bottom:15px;">
          <div class="fi" style="flex:1;"><label>DESIRED AMOUNT</label><input type="number" id="amA" value="1000" step="100"/></div>
          <div class="fi" style="flex:1;"><label>WARP SPEED</label><input type="number" id="wkA" value="50" max="200"/></div>
        </div>
        <button class="btn-start" id="btnA" onclick="startJob('A')">INITIATE WARP</button>
      </div>
      <div class="card">
        <div class="cg" style="background:var(--yellow)"></div>
        <div class="cl"><div class="ci">📜</div><div class="ct"><h2>MISSION LOG</h2><p>Recent successful transmissions</p></div></div>
        <div class="hist-list" id="histA"></div>
      </div>
    </div>
    <div id="panelB" class="job-panel">
      <div class="card">
        <div class="cg" style="background:var(--pink)"></div>
        <div class="cl"><div class="ci">🛸</div><div class="ct"><h2>COSMIC CONFIG</h2><p>Configure farming parameters for Slot B</p></div></div>
        <div class="fi"><label>AUTH TOKEN</label><input type="text" id="tkB" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."/></div>
        <div class="fi"><label>REWARD MODE</label>
          <div class="modes" id="modesB">
            <div class="mode active" onclick="setMode('B','gems')"><div class="mode-icon">💎</div><div class="mode-name">GEMS</div></div>
            <div class="mode" onclick="setMode('B','tickets')"><div class="mode-icon">🎫</div><div class="mode-name">TICKETS</div></div>
            <div class="mode" onclick="setMode('B','elite')"><div class="mode-icon">🃏</div><div class="mode-name">ELITE</div></div>
            <div class="mode" onclick="setMode('B','legendary')"><div class="mode-icon">⭐</div><div class="mode-name">LEGEND</div></div>
            <div class="mode" onclick="setMode('B','champion')"><div class="mode-icon">👑</div><div class="mode-name">CHAMP</div></div>
          </div>
        </div>
        <div style="display:flex;gap:10px;margin-bottom:15px;">
          <div class="fi" style="flex:1;"><label>DESIRED AMOUNT</label><input type="number" id="amB" value="1000" step="100"/></div>
          <div class="fi" style="flex:1;"><label>WARP SPEED</label><input type="number" id="wkB" value="50" max="200"/></div>
        </div>
        <button class="btn-start" id="btnB" onclick="startJob('B')" style="background:linear-gradient(135deg,var(--pink),var(--p2))">INITIATE WARP</button>
      </div>
      <div class="card">
        <div class="cg" style="background:var(--yellow)"></div>
        <div class="cl"><div class="ci">📜</div><div class="ct"><h2>MISSION LOG</h2><p>Recent successful transmissions</p></div></div>
        <div class="hist-list" id="histB"></div>
      </div>
    </div>
  </div>
</div>
<script>
let curSlot='A',activeModes={A:'gems',B:'gems'};
const cur=document.getElementById('cur');
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px';});
function switchTab(s){
  curSlot=s;
  document.getElementById('panelA').classList.toggle('show',s==='A');
  document.getElementById('panelB').classList.toggle('show',s==='B');
  document.getElementById('tabA').classList.toggle('aa',s==='A');
  document.getElementById('tabB').classList.toggle('ab',s==='B');
}
function setMode(s,m){
  activeModes[s]=m;
  const container=document.getElementById('modes'+s);
  [...container.children].forEach(el=>{
    el.classList.toggle('active',el.innerText.toLowerCase().includes(m.substring(0,4)));
  });
}
async function startJob(s){
  const tk=document.getElementById('tk'+s).value.trim(),am=document.getElementById('am'+s).value,wk=document.getElementById('wk'+s).value;
  if(!tk){alert('Token missing!');return;}
  const btn=document.getElementById('btn'+s);btn.disabled=true;btn.innerText='WARPING...';
  try{
    const r=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:s,token:tk,desired:am,workers:wk,mode:activeModes[s]})});
    const d=await r.json();if(!d.ok)alert(d.error);
  }catch(e){alert('Engine failure!');}
  btn.disabled=false;btn.innerText='INITIATE WARP';
}
async function stopJob(s){fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:s})});}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}
function updateUI(){
  fetch('/status_all').then(r=>r.json()).then(data=>{
    ['A','B'].forEach(s=>{
      const d=data[s],rv=document.getElementById('r'+s.toLowerCase()+'_val'),ri=document.getElementById('r'+s.toLowerCase()+'_info'),rb=document.getElementById('r'+s.toLowerCase()+'_bar'),bj=document.getElementById('b'+s.toLowerCase().substring(0,1)),ts=document.getElementById('s'+s.toLowerCase()+'_ts'),btn=document.getElementById('btn'+s),hl=document.getElementById('hist'+s);
      if(d.running){
        rv.innerHTML=`${d.reward} <span style="font-size:8px">${d.unit.toUpperCase()}</span>`;
        ri.innerText=`${d.pct}% · ${d.speed} c/s · ETA: ${d.eta}s`;
        rb.style.width=d.pct+'%';
        bj.className='jbadge r'+s.toLowerCase();
        ts.innerText='WARPING...';
        btn.disabled=true;btn.innerText='ACTIVE';
      }else{
        if(d.done){
          rv.innerHTML=`${d.reward} <span style="font-size:8px">DONE</span>`;
          ri.innerText='Mission accomplished.';
          rb.style.width='100%';
          bj.className='jbadge done';
          ts.innerText='COMPLETED';
        }else{
          rv.innerHTML=`0 <span style="font-size:8px">IDLE</span>`;
          ri.innerText='Waiting for orders...';
          rb.style.width='0%';
          bj.className='jbadge idle';
          ts.innerText='READY';
        }
        btn.disabled=false;btn.innerText='INITIATE WARP';
      }
      if(d.history&&d.history.length){
        hl.innerHTML=d.history.map(h=>`<div class="hist-item"><div class="hi-left"><div class="hi-label">${h.label}</div><div class="hi-time">${h.date} ${h.time}</div></div><div class="hi-right"><div class="hi-val">+${h.reward}</div><div class="hi-unit">${h.unit}</div></div></div>`).join('');
      }else{hl.innerHTML='<div style="text-align:center;padding:20px;color:var(--dim);font-size:10px;">No history yet</div>';}
    });
  });
}
setInterval(updateUI,1500);
for(let i=0;i<80;i++){const s=document.createElement('div');s.style.cssText=`position:absolute;width:${Math.random()*2}px;height:${Math.random()*2}px;background:white;top:${Math.random()*100}%;left:${Math.random()*100}%;opacity:${Math.random()*0.5};border-radius:50%;`;document.getElementById('stars').appendChild(s);}
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
