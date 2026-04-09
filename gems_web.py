"""
Dream Cricket 25 - ULTRA Farmer v6.2 🌌 GALAXY EDITION
FULLY RESTORED: All UI Features + New Reward Mutations
- Success Tracking ✓
- Worker Speed Display ✓
- Mission Logs ✓
- Progress Bars & Stats ✓
- New Rewards: 4 Gems | 30 Tickets | 2 Elite Cards
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
    # ✅ NEW METHOD: 100 coins per click
    "coins": {
        "label":"🪙 Coins", "unit":"Coins", "type":"reward_coins",
        "templateId":127573,"currencyTypeId":9, "amount":100,
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

## ── NEW TICKETS MUTATION (30 per click) ──
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

# ── NEW COINS MUTATION (100 per click) ──
def build_coins_mutation():
    return {
        "query": """mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }
        }""",
        "variables": {"input": [{
            "templateId": 127573,
            "templateAttributes": [
                {"templateId": 0, "groupAttributeId": 3277, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3283, "attributeValue": "0"},
                {"templateId": 0, "groupAttributeId": 3289, "attributeValue": uts()},
                {"templateId": 0, "groupAttributeId": 3290, "attributeValue": "0"}
            ],
            "gameItemRewards": [],
            "currencyRewards": [{
                "currencyTypeId": 9,
                "currencyAmount": 100,
                "giveAwayType": 7,
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
        elif m["type"] == "reward_coins":
            r = req.post(URL_USERDATA, headers=hdr, json=build_coins_mutation(), timeout=15)
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
.mt{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(20px,6vw,44px);letter-spacing:8px;color:#c264fe;text-shadow:0 0 30px rgba(194,100,254,.8);}
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
#lw{position:fixed;inset:0;z-index:8;display:none;align-items:center;justify-content:center;background:rgba(5,0,10,.97);}
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
    </div>
    <div class="mt">GALAXY FARM</div>
    <div class="vt">ULTRA v6.2</div>
    <div class="new-badge">✨ FULLY RESTORED</div>
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
<div id="ag"><div class="agb"><div class="agi">🌌</div><div class="agt">GALAXY UNLOCKED</div><div class="ags">WELCOME BACK</div></div></div>
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
const lbls=['RESTORING FEATURES...','DUAL JOBS...','AUTO-CHAIN...','COSMIC PING...','READY!'];
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
<title>GALAXY FARM · DC25 v6.2 RESTORED</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#05000a;--panel:#0d0018;--border:rgba(194,100,254,.15);--p1:#c264fe;--p2:#9933ff;--p3:#6600aa;--p4:#330055;--p1a:rgba(194,100,254,.08);--pink:#ff44ff;--cyan:#aa44ff;--red:#ff2244;--yellow:#ffd600;--gold:#ffd700;--orange:#ff8c00;--text:#d4a8ff;--dim:#4a2a6a;--cgems:#c264fe;--ctickets:#ff8c00;--ccoins:#ffb347;--celite:#aa88ff;--clegend:#ff44ff;--cchamp:#ffd700;}
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
.sec{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:4px;color:var(--dim);margin-bottom:7px;display:flex;align-items:center;gap:8px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}
.slot-badge{display:inline-block;font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;padding:3px 10px;border-radius:3px;margin-bottom:7px;}
.slot-badge.a{background:rgba(194,100,254,.1);border:1px solid var(--p1);color:var(--p1);}
.slot-badge.b{background:rgba(255,68,255,.08);border:1px solid var(--pink);color:var(--pink);}
.tok-area{width:100%;background:rgba(194,100,254,.03);border:1px solid var(--border);border-radius:4px;color:var(--p1);font-family:'Share Tech Mono',monospace;font-size:11px;padding:8px;outline:none;resize:none;height:66px;transition:border-color .2s;}
.tok-area:focus{border-color:var(--p1);}
.tok-area.bt{color:var(--pink);}.tok-area.bt:focus{border-color:var(--pink);}
.tok-vault{display:none;height:66px;background:rgba(194,100,254,.02);border:1px solid rgba(194,100,254,.2);border-radius:4px;position:relative;overflow:hidden;align-items:center;justify-content:center;flex-direction:column;gap:3px;cursor:pointer;}
.tok-vault.bv{border-color:rgba(255,68,255,.25);}
.tok-vault.show{display:flex;}
.vCv{position:absolute;inset:0;opacity:0.12;}
.vc{position:relative;z-index:2;text-align:center;}
.vi{font-size:17px;animation:vp 2s infinite;}
@keyframes vp{0%,100%{filter:drop-shadow(0 0 6px rgba(194,100,254,.6));}50%{filter:drop-shadow(0 0 20px rgba(194,100,254,1));}}
.vtt{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;color:var(--p1);}
.tok-vault.bv .vtt{color:var(--pink);}
.vsb{font-size:7px;color:var(--dim);letter-spacing:1px;margin-top:1px;}
.vdots{display:flex;gap:3px;justify-content:center;margin-top:3px;}
.vd{width:4px;height:4px;border-radius:50%;background:var(--p4);animation:vd 1.5s infinite;}
.vd:nth-child(2){animation-delay:.2s;}.vd:nth-child(3){animation-delay:.4s;}.vd:nth-child(4){animation-delay:.6s;}.vd:nth-child(5){animation-delay:.8s;}
@keyframes vd{0%,100%{background:var(--p4);}50%{background:var(--p1);box-shadow:0 0 6px var(--p1);}}
.vscan{position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--p1),transparent);animation:vscan 2s linear infinite;opacity:.2;}
@keyframes vscan{0%{top:0}100%{top:100%}}
.tok-hint{font-size:8px;color:var(--dim);margin-top:3px;}
.mode-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;}
.mb{padding:8px 2px;background:rgba(194,100,254,.03);border:1px solid var(--border);border-radius:4px;cursor:pointer;transition:all .2s;text-align:center;}
.mb:hover{border-color:rgba(194,100,254,.3);}
.mb.on.gems{border-color:var(--cgems);background:rgba(194,100,254,.1);box-shadow:0 0 12px rgba(194,100,254,.15);}
.mb.on.tickets{border-color:var(--ctickets);background:rgba(255,140,0,.08);}
.mb.on.elite{border-color:var(--celite);background:rgba(170,136,255,.08);}
.mb.on.legendary{border-color:var(--clegend);background:rgba(255,68,255,.08);}
.mb.on.champion{border-color:var(--cchamp);background:rgba(255,215,0,.08);}
.mbi{font-size:16px;margin-bottom:2px;}
.mbl{font-family:'Orbitron',monospace;font-size:6px;letter-spacing:1px;color:var(--dim);}
.mb.on.gems .mbl{color:var(--cgems);}.mb.on.tickets .mbl{color:var(--ctickets);}
.mb.on.elite .mbl{color:var(--celite);}.mb.on.legendary .mbl{color:var(--clegend);}
.mb.on.champion .mbl{color:var(--cchamp);}
.mbs{font-size:6px;color:var(--dim);margin-top:1px;}
.mb.on.gems .mbs{color:#00ff88;font-weight:bold;}
.chainBox{display:none;margin-top:6px;border-radius:4px;padding:7px 9px;}
.chainBox.show{display:block;}
.chainBox.legendary{background:rgba(255,68,255,.04);border:1px solid rgba(255,68,255,.2);}
.chainBox.champion{background:rgba(255,215,0,.04);border:1px solid rgba(255,215,0,.2);}
.chain-title{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:3px;margin-bottom:5px;}
.chainBox.legendary .chain-title{color:var(--clegend);}.chainBox.champion .chain-title{color:var(--cchamp);}
.chain-steps{display:flex;align-items:center;gap:4px;}
.cs{background:rgba(194,100,254,.05);border:1px solid var(--border);border-radius:3px;padding:4px 5px;text-align:center;}
.cs-icon{font-size:13px;}.cs-lbl{font-size:6px;color:var(--dim);}
.cs-arr{color:var(--dim);font-size:11px;}
.chain-calc{margin-top:5px;font-size:9px;color:var(--dim);}
.chain-calc span{font-family:'Orbitron',monospace;font-size:10px;}
.chainBox.legendary .chain-calc span{color:var(--clegend);}.chainBox.champion .chain-calc span{color:var(--cchamp);}
.cfg-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.cfg-item label{display:block;font-size:8px;letter-spacing:3px;color:var(--dim);margin-bottom:4px;}
input[type=number]{width:100%;background:rgba(194,100,254,.03);border:1px solid var(--border);border-radius:4px;color:var(--p1);font-family:'Share Tech Mono',monospace;font-size:14px;padding:8px 9px;outline:none;}
input[type=number]:focus{border-color:var(--p1);}
.hint{font-size:8px;color:var(--dim);margin-top:2px;}
.hint.new{color:#00ff88;font-weight:bold;}
.presets{display:flex;gap:4px;margin-top:5px;flex-wrap:wrap;}
.pw{flex:1;min-width:30px;background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:10px;padding:4px 2px;cursor:pointer;transition:all .15s;text-align:center;}
.pw:hover,.pw.on{border-color:var(--p1);color:var(--p1);background:rgba(194,100,254,.08);}
.pw.hot{border-color:var(--red)!important;color:var(--red)!important;background:rgba(255,34,68,.08)!important;}
.btn-start{width:100%;padding:13px;background:linear-gradient(135deg,#1a0028,#350050,#28003a);border:1px solid var(--p2);border-radius:6px;color:var(--p1);font-family:'Orbitron',monospace;font-weight:900;font-size:11px;letter-spacing:4px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;}
.btn-start.b{background:linear-gradient(135deg,#2a0030,#55005a,#3a0044);border-color:var(--pink);color:var(--pink);}
.btn-start.tickets{border-color:var(--orange);color:var(--orange);background:linear-gradient(135deg,#2a1400,#503000,#3a1c00);}
.btn-start.elite{border-color:var(--celite);color:var(--celite);background:linear-gradient(135deg,#1a1030,#332060,#281848);}
.btn-start.legendary{border-color:var(--clegend);color:var(--clegend);background:linear-gradient(135deg,#2a0030,#55005a,#3a0044);}
.btn-start.champion{border-color:var(--gold);color:var(--gold);background:linear-gradient(135deg,#2a2000,#504000,#3a3000);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(194,100,254,.15),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){transform:translateY(-1px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-stop{width:100%;padding:9px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:12px;letter-spacing:4px;cursor:pointer;display:none;}
.prog-card{display:none;}.prog-card.show{display:block;}
.prog-top{display:flex;align-items:center;gap:12px;margin-bottom:9px;}
.ring-wrap{position:relative;width:72px;height:72px;flex-shrink:0;}
.ring-wrap svg{width:72px;height:72px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:rgba(194,100,254,.1);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s;}
.ring-fg.tickets{stroke:url(#rgt);}.ring-fg.elite{stroke:url(#rge);}
.ring-fg.legendary{stroke:url(#rgl);}.ring-fg.champion{stroke:url(#rgc);}.ring-fg.bgems{stroke:url(#rgb);}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:11px;font-weight:900;color:var(--p1);}
.ring-pct.tickets{color:var(--orange);}.ring-pct.elite{color:var(--celite);}
.ring-pct.legendary{color:var(--clegend);}.ring-pct.champion{color:var(--gold);}.ring-pct.bgems{color:var(--pink);}
.plbl{font-size:8px;color:var(--dim);letter-spacing:2px;margin-bottom:2px;}
.pval{font-family:'Orbitron',monospace;font-size:18px;font-weight:700;color:var(--p1);}
.pval.tickets{color:var(--orange);}.pval.elite{color:var(--celite);}
.pval.legendary{color:var(--clegend);}.pval.champion{color:var(--gold);}.pval.bgems{color:var(--pink);}
.psub{font-size:9px;color:var(--dim);margin-top:1px;}
.bar-wrap{background:rgba(194,100,254,.04);border:1px solid var(--border);border-radius:3px;height:7px;overflow:hidden;margin-bottom:8px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--p4),var(--p2),var(--p1));width:0%;transition:width .4s;}
.bar-fill.tickets{background:linear-gradient(90deg,#3a1c00,#995500,#ff8c00);}
.bar-fill.elite{background:linear-gradient(90deg,#1a1030,#5540aa,#aa88ff);}
.bar-fill.legendary{background:linear-gradient(90deg,#2a0030,#880066,#ff44ff);}
.bar-fill.champion{background:linear-gradient(90deg,#3a3000,#aa8800,#ffd700);}
.bar-fill.bgems{background:linear-gradient(90deg,#2a0044,#880088,#ff44ff);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;}
.stat{background:rgba(194,100,254,.03);border:1px solid var(--border);border-radius:4px;padding:6px 4px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(10px,2.4vw,14px);font-weight:700;color:var(--p1);}
.sv.c{color:var(--cyan);}.sv.y{color:var(--yellow);}.sv.r{color:var(--red);}
.sl2{font-size:7px;color:var(--dim);letter-spacing:1px;margin-top:2px;}
.graph{background:rgba(194,100,254,.02);border:1px solid var(--border);border-radius:3px;height:34px;overflow:hidden;margin-top:7px;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:2px 2px 0;}
.gb{flex:1;min-width:2px;background:linear-gradient(to top,var(--p4),var(--p2));border-radius:1px 1px 0 0;}
.gb.tickets{background:linear-gradient(to top,#3a1c00,#ff8c00);}
.gb.elite{background:linear-gradient(to top,#1a1030,#aa88ff);}
.gb.legendary{background:linear-gradient(to top,#2a0030,#ff44ff);}
.gb.champion{background:linear-gradient(to top,#3a3000,#ffd700);}
.gb.bgems{background:linear-gradient(to top,#2a0044,#ff44ff);}
.st{text-align:center;font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:5px;min-height:12px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--p1);}.st.r{color:var(--red);}
.done-card{display:none;text-align:center;padding:14px;background:rgba(194,100,254,.05);border:1px solid rgba(194,100,254,.3);border-radius:6px;animation:galGlo 2s infinite;position:relative;overflow:hidden;}
@keyframes galGlo{0%,100%{box-shadow:0 0 15px rgba(194,100,254,.15);}50%{box-shadow:0 0 40px rgba(194,100,254,.35);}}
.done-icon{font-size:28px;margin-bottom:5px;}
.done-title{font-family:'Orbitron',monospace;font-size:12px;letter-spacing:5px;color:var(--p1);}
.done-sub{font-size:10px;color:var(--dim);margin-top:4px;line-height:1.7;}
.done-countdown{margin-top:8px;background:rgba(194,100,254,.05);border:1px solid var(--border);border-radius:2px;height:3px;overflow:hidden;}
.done-cd-fill{height:100%;background:var(--p1);width:100%;}
.done-cd-txt{font-size:7px;color:var(--dim);margin-top:3px;letter-spacing:2px;}
.sess-list{display:flex;flex-direction:column;gap:5px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(194,100,254,.02);border:1px solid var(--border);border-radius:4px;padding:7px 9px;}
.si-r{font-family:'Orbitron',monospace;font-size:12px;font-weight:700;color:var(--p1);}
.si-m{font-size:9px;color:var(--dim);}
.si-tm{font-size:8px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:11px;letter-spacing:2px;padding:8px;}
.blink{animation:bl 1s step-end infinite;}
@keyframes bl{0%,100%{opacity:1;}50%{opacity:0;}}
.bg-notice{background:rgba(194,100,254,.04);border:1px solid rgba(194,100,254,.12);border-radius:4px;padding:5px 9px;font-size:8px;color:var(--p2);letter-spacing:1px;text-align:center;margin-top:4px;}
</style>
</head>
<body>
<div class="star-field" id="starField"></div>
<div class="wrap">
<div class="hdr">
  <div class="ping-badge"><div class="ping-dot"></div>COSMIC PING</div>
  <div class="hdr-badge">🌌 GALAXY FARM</div>
  <h1>DC25 ULTRA FARMER</h1>
  <div class="new-method">✨ FULLY RESTORED: 4 GEMS · 30 TICKETS · 2 ELITE · v6.2</div>
  <button class="logout-btn" onclick="doLogout()">⏻ EXIT</button>
</div>

<div class="dual-status">
  <div class="ds-item sa"><div class="ds-slot">⚡ JOB A</div><div class="ds-reward" id="dsAR">—</div><div class="ds-info" id="dsAI">Idle</div><div class="ds-bar"><div class="dfa" id="dsAF" style="width:0%"></div></div><button class="ds-stop" id="dsAS" onclick="stopSlot('A')" style="display:none">⛔</button></div>
  <div class="ds-item sb"><div class="ds-slot">⚡ JOB B</div><div class="ds-reward" id="dsBR">—</div><div class="ds-info" id="dsBI">Idle</div><div class="ds-bar"><div class="dfb" id="dsBF" style="width:0%"></div></div><button class="ds-stop" id="dsBS" onclick="stopSlot('B')" style="display:none">⛔</button></div>
</div>

<div class="job-tabs">
  <div class="job-tab aa" id="tabA" onclick="switchTab('A')"><div class="jtl"><span class="jbadge idle" id="badgeA"></span>JOB A</div><div class="jts" id="subA">Ready</div></div>
  <div class="job-tab" id="tabB" onclick="switchTab('B')"><div class="jtl"><span class="jbadge idle" id="badgeB"></span>JOB B</div><div class="jts" id="subB">Ready</div></div>
</div>

<div class="page">

<!-- JOB A -->
<div class="job-panel show" id="panelA">
  <div class="card"><div class="cg"></div><div class="slot-badge a">🌌 JOB SLOT A</div><div class="sec">// TOKEN A</div>
    <textarea class="tok-area" id="tokA" placeholder="Paste Token A here..."></textarea>
    <div class="tok-vault" id="vaultA" onclick="revealToken('A')"><canvas class="vCv" id="vCvA"></canvas><div class="vscan"></div><div class="vc"><div class="vi">🔒</div><div class="vtt">TOKEN A SECURED</div><div class="vsb">Tap to reveal</div><div class="vdots"><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div></div></div></div>
    <div class="tok-hint" id="hintA">Token A paste karo → auto-hide hoga 🔒</div>
  </div>
  <div class="card"><div class="cg"></div><div class="sec">// MODE A</div><div class="mode-grid" id="mgA"></div><div class="chainBox" id="cbA"><div class="chain-title" id="ctA">⚡ AUTO-CHAIN</div><div class="chain-steps"><div class="cs"><div class="cs-icon">🃏</div><div class="cs-lbl">ELITE</div></div><div class="cs-arr">→</div><div class="cs"><div class="cs-icon" id="ciA">⭐</div><div class="cs-lbl">EXCHANGE</div></div><div class="cs-arr">→</div><div class="cs"><div class="cs-icon" id="ci2A">⭐</div><div class="cs-lbl">DONE!</div></div></div><div class="chain-calc" id="ccA">Enter amount</div></div></div>
  <div class="card"><div class="cg"></div><div class="sec">// CONFIG A</div>
    <div class="cfg-row">
      <div class="cfg-item"><label id="dlA">💎 DESIRED GEMS</label><input type="number" id="desA" value="5000" min="1" step="10" oninput="upCalc('A')"/><div class="hint new" id="htA">⚡ 1 click = 4 gems (NEW!)</div></div>
      <div class="cfg-item"><label>⚡ WORKERS</label><input type="number" id="wrkA" value="20" min="1" max="200"/><div class="presets" id="preA"></div></div>
    </div>
    <div class="bg-notice">🌌 Background mein chalta hai — phone band karo!</div>
  </div>
  <button class="btn-start" id="btnSA" onclick="go('A')">▶ LAUNCH JOB A</button>
  <button class="btn-stop" id="btnXA" onclick="stopSlot('A')">■ STOP JOB A</button>
  <div class="card prog-card" id="progA"><div class="cg"></div><div class="sec">// JOB A PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rg"  x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#6600aa"/><stop offset="100%" style="stop-color:#c264fe"/></linearGradient>
            <linearGradient id="rgt" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#995500"/><stop offset="100%" style="stop-color:#ff8c00"/></linearGradient>
            <linearGradient id="rge" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#5540aa"/><stop offset="100%" style="stop-color:#aa88ff"/></linearGradient>
            <linearGradient id="rgl" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#880066"/><stop offset="100%" style="stop-color:#ff44ff"/></linearGradient>
            <linearGradient id="rgc" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#aa8800"/><stop offset="100%" style="stop-color:#ffd700"/></linearGradient>
            <linearGradient id="rgb" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#880088"/><stop offset="100%" style="stop-color:#ff44ff"/></linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="rngA" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpA">0%</div>
      </div>
      <div><div class="plbl" id="rlA">ADDED</div><div class="pval" id="prA">0</div><div class="psub" id="pcA">0 / 0</div></div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="barA"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="spdA">0</div><div class="sl2">REQ/S</div></div>
      <div class="stat"><div class="sv y" id="etaA">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv"  id="okA">0</div><div class="sl2">OK</div></div>
      <div class="stat"><div class="sv r" id="flA">0</div><div class="sl2">FAIL</div></div>
    </div>
    <div class="graph"><div class="gbars" id="gbA"></div></div>
    <div class="st" id="stA"><span class="blink">_</span> Ready</div>
  </div>
  <div class="done-card" id="doneA"><div class="done-icon" id="diA">💎</div><div class="done-title" id="dtA">JOB A COMPLETE</div><div class="done-sub" id="dsA"></div><div class="done-countdown"><div class="done-cd-fill" id="cdfA"></div></div><div class="done-cd-txt" id="cdtA">Auto-clear in 20s...</div></div>
  <div class="card"><div class="cg"></div><div class="sec">// JOB A HISTORY</div><div class="sess-list" id="histA"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div></div>
</div>

<!-- JOB B -->
<div class="job-panel" id="panelB">
  <div class="card"><div class="cg"></div><div class="slot-badge b">🌌 JOB SLOT B</div><div class="sec">// TOKEN B</div>
    <textarea class="tok-area bt" id="tokB" placeholder="Paste Token B here..."></textarea>
    <div class="tok-vault bv" id="vaultB" onclick="revealToken('B')"><canvas class="vCv" id="vCvB"></canvas><div class="vscan"></div><div class="vc"><div class="vi">🔒</div><div class="vtt" style="color:var(--pink)">TOKEN B SECURED</div><div class="vsb">Tap to reveal</div><div class="vdots"><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div></div></div></div>
    <div class="tok-hint" id="hintB">Token B paste karo → auto-hide hoga 🔒</div>
  </div>
  <div class="card"><div class="cg"></div><div class="sec">// MODE B</div><div class="mode-grid" id="mgB"></div><div class="chainBox" id="cbB"><div class="chain-title" id="ctB">⚡ AUTO-CHAIN</div><div class="chain-steps"><div class="cs"><div class="cs-icon">🃏</div><div class="cs-lbl">ELITE</div></div><div class="cs-arr">→</div><div class="cs"><div class="cs-icon" id="ciB">⭐</div><div class="cs-lbl">EXCHANGE</div></div><div class="cs-arr">→</div><div class="cs"><div class="cs-icon" id="ci2B">⭐</div><div class="cs-lbl">DONE!</div></div></div><div class="chain-calc" id="ccB">Enter amount</div></div></div>
  <div class="card"><div class="cg"></div><div class="sec">// CONFIG B</div>
    <div class="cfg-row">
      <div class="cfg-item"><label id="dlB">💎 DESIRED GEMS</label><input type="number" id="desB" value="5000" min="1" step="10" oninput="upCalc('B')"/><div class="hint new" id="htB">⚡ 1 click = 4 gems (NEW!)</div></div>
      <div class="cfg-item"><label>⚡ WORKERS</label><input type="number" id="wrkB" value="20" min="1" max="200"/><div class="presets" id="preB"></div></div>
    </div>
    <div class="bg-notice">🌌 Background mein chalta hai — phone band karo!</div>
  </div>
  <button class="btn-start b" id="btnSB" onclick="go('B')">▶ LAUNCH JOB B</button>
  <button class="btn-stop" id="btnXB" onclick="stopSlot('B')">■ STOP JOB B</button>
  <div class="card prog-card" id="progB"><div class="cg"></div><div class="sec">// JOB B PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs><linearGradient id="rgb2" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#880088"/><stop offset="100%" style="stop-color:#ff44ff"/></linearGradient></defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg bgems" id="rngB" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct bgems" id="rpB">0%</div>
      </div>
      <div><div class="plbl" id="rlB">ADDED</div><div class="pval bgems" id="prB">0</div><div class="psub" id="pcB">0 / 0</div></div>
    </div>
    <div class="bar-wrap"><div class="bar-fill bgems" id="barB"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="spdB">0</div><div class="sl2">REQ/S</div></div>
      <div class="stat"><div class="sv y" id="etaB">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv"  id="okB">0</div><div class="sl2">OK</div></div>
      <div class="stat"><div class="sv r" id="flB">0</div><div class="sl2">FAIL</div></div>
    </div>
    <div class="graph"><div class="gbars" id="gbB"></div></div>
    <div class="st" id="stB"><span class="blink">_</span> Ready</div>
  </div>
  <div class="done-card" id="doneB"><div class="done-icon" id="diB">💎</div><div class="done-title" id="dtB" style="color:var(--pink)">JOB B COMPLETE</div><div class="done-sub" id="dsB"></div><div class="done-countdown"><div class="done-cd-fill" id="cdfB" style="background:var(--pink)"></div></div><div class="done-cd-txt" id="cdtB">Auto-clear in 20s...</div></div>
  <div class="card"><div class="cg"></div><div class="sec">// JOB B HISTORY</div><div class="sess-list" id="histB"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div></div>
</div>

</div></div>

<script>
const CIRC=245;
const MCFG={
  gems:     {lbl:'💎 DESIRED GEMS',   hint:'⚡ 1 click = 4 gems (NEW!)', hintNew:true, btn:'LAUNCH', cls:'',        chain:false,icon:'💎',epc:0},
  tickets:  {lbl:'🎫 DESIRED TICKETS',hint:'1 click = 30 tickets',        hintNew:false,btn:'LAUNCH', cls:'tickets', chain:false,icon:'🎫',epc:0},
  coins:    {lbl:'🪙 DESIRED COINS',  hint:'1 click = 100 coins',         hintNew:false,btn:'LAUNCH', cls:'coins',   chain:false,icon:'🪙',epc:0},
  elite:    {lbl:'🃏 DESIRED ELITE',   hint:'1 click = 2 cards',            hintNew:false,btn:'LAUNCH', cls:'elite',   chain:false,icon:'🃏',epc:0},
  legendary:{lbl:'⭐ DESIRED LEGEND',  hint:'AUTO: 10 elite→1',            hintNew:false,btn:'AUTO-CHAIN',cls:'legendary',chain:true,icon:'⭐',epc:10},
  champion: {lbl:'👑 DESIRED CHAMPION',hint:'AUTO: 10 elite→1',            hintNew:false,btn:'AUTO-CHAIN',cls:'champion', chain:true,icon:'👑',epc:10},
};
const COLS={gems:'var(--cgems)',tickets:'var(--ctickets)',coins:'var(--ccoins)',elite:'var(--celite)',legendary:'var(--clegend)',champion:'var(--cchamp)'};
const ICONS={gems:'💎',tickets:'🎫',coins:'🪙',elite:'🃏',legendary:'⭐',champion:'👑'};
  const MK=['gems','tickets','coins','elite','legendary','champion'];
  const MI=['💎','🎫','🪙','🃏','⭐','👑'];
  const ML=['GEMS','TICKETS','COINS','ELITE','LEGEND','CHAMP'];
  const MS=['4/click⚡','+30/click','+100/click','+2/click','AUTO⚡','AUTO⚡'];

let curMode={A:'gems',B:'gems'};
let polls={A:null,B:null};
let cdTimers={A:null,B:null};
let vInts={A:null,B:null};

// Stars
const sf=document.getElementById('starField');
for(let i=0;i<120;i++){
  const s=document.createElement('div');const sz=Math.random()*2+.5;
  s.style.cssText=`position:absolute;width:${sz}px;height:${sz}px;border-radius:50%;background:#fff;top:${Math.random()*100}%;left:${Math.random()*100}%;opacity:${Math.random()*.5+.1};animation:t4blink ${2+Math.random()*4}s ${Math.random()*3}s infinite;`;
  sf.appendChild(s);
}
const styleEl=document.createElement('style');
styleEl.textContent='@keyframes t4blink{0%,100%{opacity:.15}50%{opacity:.8}}';
document.head.appendChild(styleEl);

// Build grids
['A','B'].forEach(s=>{
  const g=document.getElementById('mg'+s);
  MK.forEach((mk,i)=>{
    const d=document.createElement('div');
    d.className='mb'+(mk==='gems'?' on gems':' '+mk);
    d.id=`m${mk}${s}`;
    d.innerHTML=`<div class="mbi">${MI[i]}</div><div class="mbl">${ML[i]}</div><div class="mbs">${MS[i]}</div>`;
    d.onclick=()=>setMode(s,mk);g.appendChild(d);
  });
  const p=document.getElementById('pre'+s);
  [10,20,50,100,200].forEach(v=>{
    const b=document.createElement('button');
    b.className='pw'+(v===20?' on':'')+(v===200?' hot':'');
    b.textContent=v===200?'200🔥':String(v);
    b.onclick=()=>swW(s,v);p.appendChild(b);
  });
});

function switchTab(t){
  document.getElementById('tabA').className='job-tab'+(t==='A'?' aa':'');
  document.getElementById('tabB').className='job-tab'+(t==='B'?' ab':'');
  document.getElementById('panelA').className='job-panel'+(t==='A'?' show':'');
  document.getElementById('panelB').className='job-panel'+(t==='B'?' show':'');
}

function setMode(s,m){
  curMode[s]=m;const mc=MCFG[m];
  MK.forEach(k=>document.getElementById(`m${k}${s}`).className='mb '+k+(k===m?' on':''));
  document.getElementById('dl'+s).textContent=mc.lbl;
  const htEl=document.getElementById('ht'+s);
  htEl.textContent=mc.hint;
  htEl.className=mc.hintNew?'hint new':'hint';
  document.getElementById('des'+s).value=m==='tickets'?'300':m==='legendary'||m==='champion'?'10':'5000';
  document.getElementById('des'+s).step=m==='tickets'?'30':m==='legendary'||m==='champion'?'1':m==='gems'?'10':'2';
  const isB=s==='B'; const btnCls=isB&&m==='gems'?'b':mc.cls||'';
  document.getElementById('btnS'+s).textContent=`▶ ${mc.btn} JOB ${s}`;
  document.getElementById('btnS'+s).className='btn-start '+(btnCls||'');
  const cb=document.getElementById('cb'+s);
  if(mc.chain){cb.style.display='block';cb.className='chainBox show '+m;document.getElementById('ct'+s).textContent=`⚡ AUTO-CHAIN · ${m.toUpperCase()}`;document.getElementById('ci'+s).textContent=mc.icon;document.getElementById('ci2'+s).textContent=mc.icon;upCalc(s);}
  else cb.style.display='none';
}

function upCalc(s){const mc=MCFG[curMode[s]];if(!mc.chain)return;const d=parseInt(document.getElementById('des'+s).value)||0;document.getElementById('cc'+s).innerHTML=`Farm: <span>${d*mc.epc}</span> Elite → <span>${d}</span> cards`;}
function swW(s,v){document.getElementById('wrk'+s).value=v;document.querySelectorAll(`#pre${s} .pw`).forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));}
function fmt(s){s=Math.max(0,Math.round(s));if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';}

function ringUpd(rng,rpc,p,mk,isB){
  document.getElementById(rng).style.strokeDashoffset=CIRC-(CIRC*p/100);
  let cls=MCFG[mk]?.cls||'';if(isB)cls='bgems';
  document.getElementById(rng).className='ring-fg '+cls;
  document.getElementById(rpc).textContent=p.toFixed(1)+'%';
  document.getElementById(rpc).className='ring-pct '+cls;
}

function grUpd(gb,h,mk,isB){
  const w=document.getElementById(gb);if(!h.length)return;
  let cls=MCFG[mk]?.cls||'';if(isB)cls='bgems';
  const mx=Math.max(...h,1);
  w.innerHTML=h.map(v=>`<div class="gb ${cls}" style="height:${Math.max(2,(v/mx)*30)}px"></div>`).join('');
}

function histUpd(id,list){
  const el=document.getElementById(id);
  if(!list.length){el.innerHTML='<div class="empty">NO JOBS YET <span class="blink">_</span></div>';return;}
  el.innerHTML=list.map(s=>`<div class="si"><div><div class="si-r" style="color:${COLS[s.mode_key]||'var(--p1)'}">+${s.reward} ${s.label}</div><div class="si-m">${s.success}/${s.total} · ${s.workers}w</div></div><div class="si-tm">${s.time} ${s.date}<br/>${fmt(s.elapsed)}</div></div>`).join('');
}

function setSt(s,m,c){const e=document.getElementById('st'+s);e.textContent=m;e.className='st '+(c||'');}

function initVault(s){
  const cv=document.getElementById('vCv'+s);const w=document.getElementById('vault'+s);
  cv.width=w.offsetWidth;cv.height=w.offsetHeight;
  const ctx=cv.getContext('2d');const cols=Math.floor(cv.width/10),drops=Array(cols).fill(1);
  const CH='アイウABCDEF★◆01<>{};';
  function draw(){ctx.fillStyle='rgba(5,0,10,0.08)';ctx.fillRect(0,0,cv.width,cv.height);drops.forEach((y,i)=>{const c=CH[Math.floor(Math.random()*CH.length)];ctx.fillStyle=Math.random()>.9?'#c264fe':'#33006688';ctx.font='9px Share Tech Mono';ctx.fillText(c,i*10,y*10);if(y*10>cv.height&&Math.random()>.97)drops[i]=0;drops[i]++;});}
  vInts[s]=setInterval(draw,60);
}
function lockToken(s){document.getElementById('tok'+s).style.display='none';document.getElementById('vault'+s).classList.add('show');document.getElementById('hint'+s).textContent=`🔒 Token ${s} secured — tap to reveal`;initVault(s);}
function unlockToken(s){document.getElementById('tok'+s).style.display='block';document.getElementById('vault'+s).classList.remove('show');document.getElementById('hint'+s).textContent=`Token ${s} paste karo → auto-hide hoga 🔒`;if(vInts[s])clearInterval(vInts[s]);}
function revealToken(s){
  document.getElementById('vault'+s).classList.remove('show');if(vInts[s])clearInterval(vInts[s]);
  const t=document.getElementById('tok'+s);t.style.display='block';t.style.filter='blur(4px)';
  setTimeout(()=>t.style.filter='none',200);
  document.getElementById('hint'+s).textContent=`👁 3 sec mein re-lock...`;
  setTimeout(()=>{if(document.getElementById('btnX'+s).style.display!='none')lockToken(s);},3000);
}

function updateDS(d,s){
  const isB=s==='B';
  const R=document.getElementById('ds'+s+'R'),I=document.getElementById('ds'+s+'I');
  const F=document.getElementById('ds'+s+'F'),Stp=document.getElementById('ds'+s+'S');
  const badge=document.getElementById('badge'+s),tab=document.getElementById('tab'+s),sub=document.getElementById('sub'+s);
  if(d.has_active){
    R.textContent=`+${d.reward} ${d.unit}`;I.textContent=`${d.pct}% · ${fmt(d.elapsed)}`;
    F.style.width=d.pct+'%';Stp.style.display='block';
    badge.className=isB?'jbadge rb':'jbadge ra';
    tab.className='job-tab '+(isB?'ab':'aa');sub.textContent=`${d.pct}% running`;
  } else if(d.done){
    R.textContent=`+${d.reward} ${d.unit} ✓`;I.textContent='Complete!';F.style.width='100%';
    Stp.style.display='none';badge.className='jbadge done';sub.textContent='Done ✓';
  } else {
    R.textContent='—';I.textContent='Idle';F.style.width='0%';
    Stp.style.display='none';badge.className='jbadge idle';sub.textContent='Ready';
  }
}

async function go(s){
  const tok=document.getElementById('tok'+s).value.trim();
  const desired=parseInt(document.getElementById('des'+s).value);
  const wrk=parseInt(document.getElementById('wrk'+s).value);
  if(!tok){alert(`Token ${s} paste karo!`);return;}
  if(desired<1){alert('Amount enter karo!');return;}
  if(cdTimers[s])clearInterval(cdTimers[s]);
  document.getElementById('done'+s).style.display='none';
  setSt(s,'Starting...','g');
  const res=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:tok,desired,workers:wrk,mode:curMode[s],slot:s})});
  const data=await res.json();
  if(data.error){alert(data.error);setSt(s,'','');return;}
  lockToken(s);
  const mk=curMode[s];const isB=s==='B';
  document.getElementById('prog'+s).classList.add('show');
  document.getElementById('btnS'+s).disabled=true;
  document.getElementById('btnX'+s).style.display='block';
  let barCls=MCFG[mk]?.cls||'';if(isB)barCls='bgems';
  document.getElementById('bar'+s).style.width='0%';
  document.getElementById('bar'+s).className='bar-fill '+(barCls||'');
  document.getElementById('pr'+s).textContent='0';
  document.getElementById('pr'+s).className='pval '+(isB?'bgems':MCFG[mk]?.cls||'');
  ringUpd('rng'+s,'rp'+s,0,mk,isB);
  ['spd','eta','ok','fl'].forEach(k=>document.getElementById(k+s).textContent=k==='eta'?'--':'0');
  document.getElementById('gb'+s).innerHTML='';
  setSt(s,data.is_chain?`🌌 AUTO-CHAIN: ${data.elite_needed} elite → ${desired} cards`:`🌌 Job ${s} started — 4 gems/click ⚡`,'g');
  if(polls[s])clearInterval(polls[s]);
  polls[s]=setInterval(()=>tick(s),800);
}

async function tick(s){
  try{
    const r=await fetch('/status?slot='+s);
    if(r.status===401){clearInterval(polls[s]);window.location.reload();return;}
    const d=await r.json();
    const mk=d.mode_key||'gems';const isB=s==='B';
    let barCls=MCFG[mk]?.cls||'';if(isB)barCls='bgems';
    ringUpd('rng'+s,'rp'+s,d.pct,mk,isB);
    document.getElementById('bar'+s).style.width=d.pct+'%';
    document.getElementById('bar'+s).className='bar-fill '+barCls;
    document.getElementById('pr'+s).textContent=d.reward;
    document.getElementById('rl'+s).textContent=(ICONS[mk]||'💎')+' ADDED';
    document.getElementById('pc'+s).textContent=`${d.phase_done||0} steps · ${fmt(d.elapsed)}`;
    document.getElementById('spd'+s).textContent=d.speed;
    document.getElementById('eta'+s).textContent=fmt(d.eta);
    document.getElementById('ok'+s).textContent=d.success;
    document.getElementById('fl'+s).textContent=d.fail;
    grUpd('gb'+s,d.speed_history,mk,isB);
    histUpd('hist'+s,d.history);
    updateDS(d,s);
    if(d.has_active)setSt(s,`${fmt(d.elapsed)} elapsed · cosmic server pe chal raha hai 🌌`,'g');
    if(d.done){
      clearInterval(polls[s]);resetUI(s);ringUpd('rng'+s,'rp'+s,100,mk,isB);
      document.getElementById('bar'+s).style.width='100%';
      const dc=document.getElementById('done'+s);dc.style.display='block';
      dc.style.borderColor=COLS[mk]||'var(--p1)';
      document.getElementById('di'+s).textContent=ICONS[mk]||'💎';
      document.getElementById('dt'+s).style.color=COLS[mk]||'var(--p1)';
      document.getElementById('ds'+s).innerHTML=`<strong style="color:${COLS[mk]||'var(--p1)'}">+${d.reward} ${d.unit}</strong> added!<br/>${d.success}/${d.total} success · ${fmt(d.elapsed)} total`;
      setSt(s,'🌌 Job '+s+' complete! ✅','g');
      startAC(s);
    }
  }catch(e){setSt(s,'Reconnecting...','');}
}

function startAC(s){
  const fill=document.getElementById('cdf'+s),txt=document.getElementById('cdt'+s);
  const S=20;fill.style.transition='none';fill.style.width='100%';let rem=S;
  setTimeout(()=>{fill.style.transition=`width ${S}s linear`;fill.style.width='0%';},100);
  cdTimers[s]=setInterval(()=>{rem--;txt.textContent=`Auto-clear in ${rem}s...`;if(rem<=0){clearInterval(cdTimers[s]);autoClear(s);}},1000);
}
function autoClear(s){
  document.getElementById('done'+s).style.display='none';
  document.getElementById('prog'+s).classList.remove('show');
  ringUpd('rng'+s,'rp'+s,0,'gems',s==='B');
  document.getElementById('bar'+s).style.width='0%';
  document.getElementById('pr'+s).textContent='0';
  ['spd','ok','fl'].forEach(k=>document.getElementById(k+s).textContent='0');
  document.getElementById('eta'+s).textContent='--';
  document.getElementById('gb'+s).innerHTML='';
  setSt(s,'Ready','');unlockToken(s);
}
async function stopSlot(s){await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:s})});clearInterval(polls[s]);setSt(s,'⛔ Stopped.','r');resetUI(s);unlockToken(s);}
function resetUI(s){document.getElementById('btnS'+s).disabled=false;document.getElementById('btnX'+s).style.display='none';}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}

setInterval(async()=>{
  try{const r=await fetch('/status_all');if(r.status!==200)return;const d=await r.json();updateDS(d.A,'A');updateDS(d.B,'B');}catch(e){}
},2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("\033[35m")
    print("╔══════════════════════════════════════════╗")
    print("║  🌌 DC25 GALAXY FARM v6.2 RESTORED      ║")
    print("║  ✨ FULLY RESTORED: All Features Back!  ║")
    print("║  4 GEMS · 30 TICKETS · 2 ELITE CARDS    ║")
    print("║  Dual Jobs · Auto-Chain · Token Vault    ║")
    print(f"║  Email : {ADMIN_EMAIL:<32}║")
    print("║  Open  : http://localhost:5000           ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=5000, debug=False)
