"""
Dream Cricket 25 - ULTRA Farmer v6.0
DUAL JOB SYSTEM - Job A + Job B simultaneously!
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
    "gems":     {"label":"💎 Gems",     "unit":"Gems",     "type":"reward", "templateId":125968,"currencyTypeId":2,  "amount":2},
    "tickets":  {"label":"🎫 Tickets",  "unit":"Tickets",  "type":"reward", "templateId":124339,"currencyTypeId":23, "amount":30},
    "elite":    {"label":"🃏 Elite",    "unit":"Elite",    "type":"reward", "templateId":122012,"currencyTypeId":14, "amount":1},
    "legendary":{"label":"⭐ Legendary","unit":"Legendary","type":"chain",  "elite_per_card":10,
        "reward_currencyTypeId":15,"reward_amount":1,"cost_currencyTypeId":14,"cost_amount":10,"attr_2770":"5.000000","amount":1},
    "champion": {"label":"👑 Champion", "unit":"Champion", "type":"chain",  "elite_per_card":10,
        "reward_currencyTypeId":16,"reward_amount":1,"cost_currencyTypeId":14,"cost_amount":10,"attr_2770":"49.000000","amount":1},
}

_ts  = int(time.time())
_tsl = threading.Lock()

# TWO independent job slots
slots = {
    "A": {"job": None, "history": []},
    "B": {"job": None, "history": []},
}
slots_lock = threading.Lock()

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
    return {"query":"""mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }}""",
        "variables":{"input":[{"templateId":122012,
            "templateAttributes":[
                {"templateId":0,"groupAttributeId":3277,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3283,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3289,"attributeValue":uts()},
                {"templateId":0,"groupAttributeId":3290,"attributeValue":"0"}],
            "gameItemRewards":[],"currencyRewards":[{"currencyTypeId":14,"currencyAmount":1,"giveAwayType":11,"meta":"Reward"}]}]}}

def build_reward_mutation(mode_key):
    m=MODES[mode_key]
    return {"query":"""mutation assignUserRewardBulk ($input: [UserRewardInput]) {
            assignUserRewardBulk (input: $input) { responseStatus }}""",
        "variables":{"input":[{"templateId":m["templateId"],
            "templateAttributes":[
                {"templateId":0,"groupAttributeId":3277,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3283,"attributeValue":"1"},
                {"templateId":0,"groupAttributeId":3289,"attributeValue":uts()},
                {"templateId":0,"groupAttributeId":3290,"attributeValue":"0"}],
            "gameItemRewards":[],"currencyRewards":[{"currencyTypeId":m["currencyTypeId"],"currencyAmount":m["amount"],"giveAwayType":11,"meta":"Reward"}]}]}}

def build_exchange_mutation(mode_key):
    m=MODES[mode_key]
    return {"query":"""mutation assignStorePurchase ($input: ProductPurchaseAndAssignInput) {
            assignStorePurchase (input: $input) {
                purchaseState purchaseType acknowledgementState consumptionState
                orderId validPurchase kind rewardSuccess}}""",
        "variables":{"input":{
            "productPurchaseInput":{"packageName":"","productId":"","purchaseToken":"","platform":"","orderId":"","price":0,"currencyCode":"","priceText":""},
            "productInfoInput":{"templateAttributeInputs":[
                {"templateId":104716,"groupAttributeId":2758,"attributeValue":"1"},
                {"templateId":104716,"groupAttributeId":2764,"attributeValue":"0.000000"},
                {"templateId":104716,"groupAttributeId":2770,"attributeValue":m["attr_2770"]},
                {"templateId":104716,"groupAttributeId":2775,"attributeValue":"0.000000"},
                {"templateId":104716,"groupAttributeId":2780,"attributeValue":"0.000000"},
                {"templateId":104716,"groupAttributeId":2795,"attributeValue":"946645200000"},
                {"templateId":104716,"groupAttributeId":2804,"attributeValue":"0"}],
                "gameItemInputs":[],"userOwnedItemInputs":[],
                "currencyInputs":[{"currencyTypeId":m["reward_currencyTypeId"],"currencyAmount":m["reward_amount"]}],
                "storeListingInput":{"storeId":945961900,"storeItemListingId":104716,"bundleId":563354144}},
            "currencyDebit":[{"currencyTypeId":m["cost_currencyTypeId"],"currencyAmount":m["cost_amount"]}]}}}

def get_uid(token):
    try:
        p=token.split('.')[1]; p+='='*(4-len(p)%4)
        return json.loads(base64.b64decode(p)).get('user-info',{}).get('id','unknown')
    except: return 'unknown'

def make_headers(token):
    return {"Host":"api-prod.dreamgamestudios.in","Accept":"*/*","Accept-Encoding":"gzip, deflate",
        "Authorization":f"Bearer {token}","Content-Type":"application/json; charset=utf-8",
        "X-SpineSDK":"0.1","gameId":"1","studioId":"1","userId":get_uid(token),"game-env":"BLUE",
        "gameVersion":"1.5.55","secretKey":"6b77f094-45e2-46d0-b6cc-827dcb5f6b85",
        "X-API-VERSION":"1","User-Agent":"ProjectCricketUE4/++UE4+Release-4.27-CL-0 Android/15"}

def do_reward(hdr, mode_key):
    try:
        r=req.post(URL_USERDATA,headers=hdr,json=build_reward_mutation(mode_key),timeout=15)
        return r.status_code==200
    except: return False

def do_elite(hdr):
    try:
        r=req.post(URL_USERDATA,headers=hdr,json=build_elite_mutation(),timeout=15)
        return r.status_code==200
    except: return False

def do_exchange(hdr, mode_key):
    try:
        r=req.post(URL_RECEIPT,headers=hdr,json=build_exchange_mutation(mode_key),timeout=15)
        if r.status_code==200:
            return r.json().get("data",{}).get("assignStorePurchase",{}).get("rewardSuccess")==True
        return False
    except: return False

def run_batch(slot, hdr, total, workers, fn):
    batches=math.ceil(total/workers); bt=[]
    success=0; fail=0
    for b in range(batches):
        with slots_lock:
            j=slots[slot]["job"]
            if not j or not j["running"]: break
        sz=min(workers, total-b*workers)
        if sz<=0: break
        t0=time.time()
        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs=[ex.submit(fn) for _ in range(sz)]
            results=[f.result() for f in as_completed(fs)]
        t1=time.time()
        ok=sum(1 for r in results if r)
        bad=sz-ok
        success+=ok; fail+=bad
        bt.append(t1-t0)
        if len(bt)>10: bt.pop(0)
        avg=sum(bt)/len(bt)
        with slots_lock:
            j=slots[slot]["job"]
            if j:
                j["phase_done"]=(b+1)*workers
                j["eta"]=(batches-b-1)*avg
                j["speed"]=round(workers/avg,1)
                j["speed_history"].append(round(workers/avg,1))
                if len(j["speed_history"])>30: j["speed_history"].pop(0)
    return success, fail

def run_job(slot):
    with slots_lock:
        j=slots[slot]["job"]
        if not j: return
        token=j["token"]; total=j["total"]; workers=j["workers"]
        mode_key=j["mode_key"]
    hdr=make_headers(token)
    m=MODES[mode_key]

    if m["type"]=="chain":
        elite_needed=total*m["elite_per_card"]
        with slots_lock:
            j=slots[slot]["job"]
            if j:
                j["phase"]=1
                j["phase1_total"]=elite_needed
                j["phase2_total"]=total
                j["phase_done"]=0
        p1ok,p1fail=run_batch(slot,hdr,elite_needed,workers,lambda:do_elite(hdr))
        with slots_lock:
            j=slots[slot]["job"]
            if j:
                j["phase1_success"]=p1ok
                j["phase"]=2
                j["phase_done"]=0
                if not j["running"]:
                    _finish(slot,mode_key,total,workers,0,0)
                    return
        cards=p1ok//m["elite_per_card"]
        p2ok,p2fail=run_batch(slot,hdr,cards,max(1,workers//5),lambda:do_exchange(hdr,mode_key))
        with slots_lock:
            j=slots[slot]["job"]
            if j:
                j["success"]=p2ok; j["fail"]=p2fail
                j["phase2_success"]=p2ok
        _finish(slot,mode_key,total,workers,p2ok,p2fail)
    else:
        s,f=run_batch(slot,hdr,total,workers,lambda:do_reward(hdr,mode_key))
        with slots_lock:
            j=slots[slot]["job"]
            if j: j["success"]=s; j["fail"]=f
        _finish(slot,mode_key,total,workers,s,f)

def _finish(slot,mode_key,total,workers,success,fail):
    with slots_lock:
        j=slots[slot]["job"]
        if not j: return
        j["running"]=False; j["done"]=True
        j["end_time"]=time.time()
        elapsed=j["end_time"]-j["start_time"]
        m=MODES[mode_key]
        entry={"reward":success*m["amount"],"unit":m["unit"],"label":m["label"],
            "mode_key":mode_key,"success":success,"total":total,"workers":workers,
            "elapsed":round(elapsed,1),"time":datetime.now().strftime("%H:%M:%S"),
            "date":datetime.now().strftime("%d %b")}
        slots[slot]["history"].insert(0,entry)
        if len(slots[slot]["history"])>5:
            slots[slot]["history"]=slots[slot]["history"][:5]

def is_logged_in(): return session.get("logged_in")==True

def get_slot_status(slot):
    with slots_lock:
        j=slots[slot]["job"]
        hist=list(slots[slot]["history"])
    if not j:
        return {"running":False,"done":False,"slot":slot,"pct":0,"reward":0,"unit":"",
            "success":0,"fail":0,"eta":0,"speed":0,"elapsed":0,
            "speed_history":[],"history":hist,"has_active":False,
            "phase":1,"phase1_total":0,"phase2_total":0,"phase_done":0,
            "phase1_success":0,"phase2_success":0,"is_chain":False,"mode_key":"gems"}
    elapsed=(time.time() if j["running"] else j["end_time"])-j["start_time"]
    mk=j["mode_key"]; m=MODES.get(mk,MODES["gems"])
    is_chain=m["type"]=="chain"
    if is_chain:
        p1t=j.get("phase1_total",0); p2t=j.get("phase2_total",0)
        pd=j.get("phase_done",0); ph=j.get("phase",1)
        total_steps=p1t+p2t
        done_steps=(p1t if ph==2 else pd)+(pd if ph==2 else 0)
        pct=round(done_steps/total_steps*100,1) if total_steps else 0
        reward=j.get("phase2_success",0)*m["amount"]
    else:
        total=j["total"]; pd=j.get("phase_done",0)
        pct=round(pd/total*100,1) if total else 0
        reward=j["success"]*m["amount"]
    return {"running":j["running"],"done":j["done"],"slot":slot,
        "pct":pct,"reward":reward,"unit":m["unit"],"label":m["label"],
        "success":j["success"],"fail":j["fail"],
        "eta":round(j.get("eta",0)),"speed":j.get("speed",0),
        "elapsed":round(elapsed),"speed_history":j.get("speed_history",[]),
        "history":hist,"has_active":j["running"],"mode_key":mk,"is_chain":is_chain,
        "phase":j.get("phase",1),"phase1_total":j.get("phase1_total",0),
        "phase2_total":j.get("phase2_total",0),"phase_done":j.get("phase_done",0),
        "phase1_success":j.get("phase1_success",0),"phase2_success":j.get("phase2_success",0)}

@app.route("/")
def index():
    if not is_logged_in(): return LOGIN_PAGE
    return MAIN_PAGE

@app.route("/login",methods=["POST"])
def login():
    d=request.json
    if d.get("email","").strip().lower()==ADMIN_EMAIL.lower() and d.get("password","").strip()==ADMIN_PASSWORD:
        session["logged_in"]=True; session.permanent=True
        return jsonify({"ok":True})
    return jsonify({"error":"Invalid email or password"}),401

@app.route("/logout",methods=["POST"])
def logout():
    session.clear(); return jsonify({"ok":True})

@app.route("/start",methods=["POST"])
def start():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}),401
    d=request.json
    slot=d.get("slot","A")
    if slot not in ["A","B"]: slot="A"
    token=d.get("token","").strip()
    desired=int(d.get("desired",100))
    workers=min(int(d.get("workers",20)),MAX_WORKERS)
    mode_key=d.get("mode","gems")
    if mode_key not in MODES: mode_key="gems"
    if not token: return jsonify({"error":"Token required"}),400
    with slots_lock:
        j=slots[slot]["job"]
        if j and j["running"]: return jsonify({"error":f"Job {slot} already running!"}),400
    m=MODES[mode_key]
    total=desired if m["type"]=="chain" else math.ceil(desired/m["amount"])
    with slots_lock:
        slots[slot]["job"]={
            "running":True,"done":False,"success":0,"fail":0,
            "total":total,"phase_done":0,"start_time":time.time(),"end_time":0,
            "eta":0,"speed":0,"speed_history":[],"token":token,
            "workers":workers,"mode_key":mode_key,
            "phase":1,"phase1_total":0,"phase2_total":0,
            "phase1_success":0,"phase2_success":0,
        }
    threading.Thread(target=run_job,args=(slot,),daemon=True).start()
    return jsonify({"ok":True,"slot":slot,"unit":m["unit"],"amount":m["amount"],
        "is_chain":m["type"]=="chain","elite_needed":desired*m.get("elite_per_card",1) if m["type"]=="chain" else 0})

@app.route("/stop",methods=["POST"])
def stop():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}),401
    slot=request.json.get("slot","A")
    with slots_lock:
        j=slots.get(slot,{}).get("job")
        if j: j["running"]=False
    return jsonify({"ok":True})

@app.route("/status")
def status():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}),401
    slot=request.args.get("slot","A")
    return jsonify(get_slot_status(slot))

@app.route("/status_all")
def status_all():
    if not is_logged_in(): return jsonify({"error":"Unauthorized"}),401
    return jsonify({"A":get_slot_status("A"),"B":get_slot_status("B")})

@app.route("/ping")
def ping(): return "pong",200

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
.ring:nth-child(1){width:200px;height:200px;}.ring:nth-child(2){width:400px;height:400px;animation-delay:.8s;}
.ring:nth-child(3){width:650px;height:650px;animation-delay:1.6s;}.ring:nth-child(4){width:950px;height:950px;animation-delay:2.4s;}
@keyframes rp{0%{transform:translate(-50%,-50%) scale(0);opacity:.5}100%{transform:translate(-50%,-50%) scale(1);opacity:0}}
.co{position:absolute;width:80px;height:80px;opacity:0;}
.co.tl{top:16px;left:16px;border-top:2px solid #00ff88;border-left:2px solid #00ff88;animation:ci .3s ease .2s forwards;}
.co.tr{top:16px;right:16px;border-top:2px solid #00ff88;border-right:2px solid #00ff88;animation:ci .3s ease .35s forwards;}
.co.bl{bottom:16px;left:16px;border-bottom:2px solid #00ff88;border-left:2px solid #00ff88;animation:ci .3s ease .5s forwards;}
.co.br{bottom:16px;right:16px;border-bottom:2px solid #00ff88;border-right:2px solid #00ff88;animation:ci .3s ease .65s forwards;}
@keyframes ci{to{opacity:1}}
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
@keyframes fu{to{opacity:1}}
.ph{display:flex;justify-content:space-between;font-size:9px;color:#1a4a2a;margin-bottom:5px;}
.pt2{background:rgba(0,255,100,.04);border:1px solid #0a2015;border-radius:2px;height:7px;overflow:hidden;}
.pf{height:100%;width:0%;background:linear-gradient(90deg,#002a14,#00aa55,#00ffaa);}
.sps{margin-top:5px;display:flex;flex-direction:column;gap:3px;}
.sr{display:flex;align-items:center;gap:8px;font-size:7px;color:#1a3a2a;}
.sl2{width:80px;text-align:right;}.sts{flex:1;height:3px;background:rgba(0,255,100,.04);border-radius:1px;overflow:hidden;}
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
  <div id="ctr">
    <div class="gw"><div class="orb orb1"><div class="od"></div></div><div class="orb orb2"><div class="od"></div></div><span class="gi">💎</span></div>
    <div class="mt">DC25 FARMER</div>
    <div class="vt">DUAL JOB · v6.0</div>
    <div id="pw">
      <div class="ph"><span id="pl">INITIALIZING...</span><span id="pn">0%</span></div>
      <div class="pt2"><div class="pf" id="pfl"></div></div>
      <div class="sps">
        <div class="sr"><span class="sl2">JOB SLOT A</span><div class="sts"><div class="sf g" id="s1"></div></div><span class="sp" id="s1p">0%</span></div>
        <div class="sr"><span class="sl2">JOB SLOT B</span><div class="sts"><div class="sf c" id="s2"></div></div><span class="sp" id="s2p">0%</span></div>
        <div class="sr"><span class="sl2">AUTO-CHAIN</span><div class="sts"><div class="sf y" id="s3"></div></div><span class="sp" id="s3p">0%</span></div>
        <div class="sr"><span class="sl2">AUTO-PING</span><div class="sts"><div class="sf p" id="s4"></div></div><span class="sp" id="s4p">0%</span></div>
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
const lbls=['LOADING...','JOB SLOT A...','JOB SLOT B...','AUTO-CHAIN...','DUAL READY!'];
const pfl=document.getElementById('pfl'),pn=document.getElementById('pn'),plbl=document.getElementById('pl'),bsEl=document.getElementById('bs');
setTimeout(()=>{const iv=setInterval(()=>{pct+=Math.random()*4+0.5;if(pct>=100){pct=100;clearInterval(iv);setTimeout(showAG,300);}pfl.style.width=pct+'%';pn.textContent=Math.floor(pct)+'%';const nl=Math.floor((pct/100)*lbls.length);if(nl!==li&&nl<lbls.length){li=nl;plbl.textContent=lbls[li];bsEl.textContent='> '+lbls[li];}[['s1','s1p'],['s2','s2p'],['s3','s3p'],['s4','s4p']].forEach(([id,pid],i)=>{const v=Math.min(100,Math.max(0,(pct-i*25)*4));document.getElementById(id).style.width=v+'%';document.getElementById(pid).textContent=Math.floor(v)+'%';});},55);},2200);
function showAG(){const ag=document.getElementById('ag');ag.style.opacity='1';ag.style.pointerEvents='auto';let f=0;const iv=setInterval(()=>{f++;ag.style.background=f%2===0?'#000':'rgba(0,255,100,.04)';if(f>=6){clearInterval(iv);setTimeout(showLogin,500);}},130);}
function showLogin(){[document.getElementById('intro'),document.getElementById('ag')].forEach(el=>{el.style.transition='opacity 0.7s';el.style.opacity='0';});document.getElementById('sk').style.display='none';clearInterval(mI);setTimeout(()=>{document.getElementById('intro').style.display='none';document.getElementById('ag').style.display='none';document.getElementById('lw').classList.add('show');document.getElementById('em').focus();},750);}
function skipAll(){showLogin();}
document.addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
async function doLogin(){
  const em=document.getElementById('em').value.trim(),pw=document.getElementById('pw2').value.trim();
  const btn=document.getElementById('lb');
  if(!em||!pw){showE('Email aur password required!');return;}
  btn.disabled=true;btn.textContent='VERIFYING...';document.getElementById('le').classList.remove('show');
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
<title>DC25 ULTRA FARMER v6</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#03050a;--panel:#0a1520;--border:#0d2a1a;--g1:#00ffaa;--g2:#00cc77;--g3:#004422;--cyan:#00e5ff;--red:#ff2244;--yellow:#ffd600;--purple:#c264fe;--orange:#ff8c00;--gold:#ffd700;--blue:#4488ff;--text:#a8ffd0;--dim:#2a4a35;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 20% 0%,rgba(0,255,100,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(0,200,255,.03) 0%,transparent 60%),repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,255,100,.012) 40px,rgba(0,255,100,.012) 41px);pointer-events:none;z-index:0;}
body::after{content:'';position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.15) 3px,rgba(0,0,0,.15) 4px);pointer-events:none;z-index:1;}
.wrap{position:relative;z-index:2;}

/* HEADER */
.hdr{padding:14px 16px 12px;text-align:center;border-bottom:1px solid var(--border);position:relative;}
.hdr::after{content:'';position:absolute;bottom:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--g1),var(--cyan),var(--g1),transparent);}
.hdr-badge{display:inline-block;background:rgba(0,255,100,.08);border:1px solid var(--g3);border-radius:2px;padding:2px 8px;font-size:9px;letter-spacing:3px;color:var(--g2);margin-bottom:4px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(13px,4vw,24px);letter-spacing:5px;background:linear-gradient(135deg,var(--g1),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr p{color:var(--dim);font-size:8px;letter-spacing:2px;margin-top:2px;}
.logout-btn{position:absolute;top:12px;right:12px;background:transparent;border:1px solid rgba(255,34,68,.3);border-radius:3px;color:var(--red);font-family:'Share Tech Mono',monospace;font-size:9px;padding:3px 8px;cursor:pointer;}
.ping-badge{position:absolute;top:14px;left:12px;display:flex;align-items:center;gap:4px;font-size:8px;color:var(--g2);}
.ping-dot{width:5px;height:5px;border-radius:50%;background:var(--g1);animation:pd 2s infinite;}
@keyframes pd{0%,100%{opacity:1;box-shadow:0 0 4px var(--g1);}50%{opacity:.4;}}

/* DUAL JOB TABS */
.job-tabs{display:flex;border-bottom:1px solid var(--border);background:var(--panel);}
.job-tab{flex:1;padding:12px 8px;text-align:center;cursor:pointer;transition:all .2s;position:relative;border-bottom:2px solid transparent;}
.job-tab.active-a{border-bottom-color:var(--g1);background:rgba(0,255,100,.05);}
.job-tab.active-b{border-bottom-color:var(--blue);background:rgba(68,136,255,.05);}
.job-tab-label{font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;}
.job-tab.active-a .job-tab-label{color:var(--g1);}
.job-tab.active-b .job-tab-label{color:var(--blue);}
.job-tab:not(.active-a):not(.active-b) .job-tab-label{color:var(--dim);}
.job-tab-sub{font-size:8px;color:var(--dim);margin-top:2px;letter-spacing:1px;}
.job-badge{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px;vertical-align:middle;}
.job-badge.running{background:var(--g1);box-shadow:0 0 6px var(--g1);animation:pd 1s infinite;}
.job-badge.running-b{background:var(--blue);box-shadow:0 0 6px var(--blue);animation:pd 1s infinite;}
.job-badge.idle{background:var(--dim);}
.job-badge.done{background:var(--yellow);}

/* DUAL STATUS BAR (mini) */
.dual-status{display:flex;gap:6px;padding:8px 12px;background:rgba(0,0,0,.3);border-bottom:1px solid var(--border);}
.ds-item{flex:1;background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:6px 8px;position:relative;overflow:hidden;}
.ds-item.slot-a{border-left:2px solid var(--g1);}
.ds-item.slot-b{border-left:2px solid var(--blue);}
.ds-slot{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:3px;color:var(--dim);margin-bottom:3px;}
.ds-item.slot-a .ds-slot{color:var(--g1);}
.ds-item.slot-b .ds-slot{color:var(--blue);}
.ds-reward{font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:var(--g1);}
.ds-item.slot-b .ds-reward{color:var(--blue);}
.ds-info{font-size:9px;color:var(--dim);}
.ds-bar{margin-top:4px;background:rgba(0,255,100,.05);border-radius:1px;height:3px;overflow:hidden;}
.ds-fill-a{height:100%;background:linear-gradient(90deg,var(--g3),var(--g1));transition:width .4s;}
.ds-fill-b{height:100%;background:linear-gradient(90deg,#112244,var(--blue));transition:width .4s;}
.ds-stop{position:absolute;top:4px;right:6px;background:transparent;border:none;color:rgba(255,34,68,.5);font-size:12px;cursor:pointer;padding:0;}
.ds-stop:hover{color:var(--red);}

.page{max-width:680px;margin:0 auto;padding:10px 12px 40px;display:flex;flex-direction:column;gap:10px;}

/* JOB PANELS */
.job-panel{display:none;}
.job-panel.show{display:flex;flex-direction:column;gap:10px;}

.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:14px;position:relative;overflow:hidden;}
.cg{position:absolute;top:0;left:0;right:0;height:1px;}
.cg.green{background:linear-gradient(90deg,transparent,var(--g2),transparent);}
.cg.blue{background:linear-gradient(90deg,transparent,var(--blue),transparent);}
.cg.cyan{background:linear-gradient(90deg,transparent,var(--cyan),transparent);}
.cg.gold{background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.cg.purple{background:linear-gradient(90deg,transparent,var(--purple),transparent);}
.sec{font-family:'Orbitron',monospace;font-size:8px;letter-spacing:4px;color:var(--dim);margin-bottom:8px;display:flex;align-items:center;gap:8px;}
.sec::after{content:'';flex:1;height:1px;background:var(--border);}

/* Slot label badge */
.slot-badge{display:inline-block;font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;padding:3px 10px;border-radius:3px;margin-bottom:8px;}
.slot-badge.a{background:rgba(0,255,100,.08);border:1px solid var(--g1);color:var(--g1);}
.slot-badge.b{background:rgba(68,136,255,.08);border:1px solid var(--blue);color:var(--blue);}

/* Token vault */
.tok-area{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:11px;padding:9px;outline:none;resize:none;height:68px;transition:border-color .2s;}
.tok-area:focus{border-color:var(--g2);}
.tok-area.b-tok{color:var(--blue);}
.tok-area.b-tok:focus{border-color:var(--blue);}
.tok-vault{display:none;height:68px;background:rgba(0,255,100,.02);border:1px solid rgba(0,255,100,.18);border-radius:4px;position:relative;overflow:hidden;align-items:center;justify-content:center;flex-direction:column;gap:3px;cursor:pointer;}
.tok-vault.b-vault{border-color:rgba(68,136,255,.3);background:rgba(68,136,255,.02);}
.tok-vault.show{display:flex;}
.vCv{position:absolute;inset:0;opacity:0.13;}
.vc{position:relative;z-index:2;text-align:center;}
.vi{font-size:18px;animation:vp 2s infinite;}
@keyframes vp{0%,100%{filter:drop-shadow(0 0 6px rgba(0,255,136,.6));}50%{filter:drop-shadow(0 0 16px rgba(0,255,136,1));}}
.vtt{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;color:var(--g1);}
.tok-vault.b-vault .vtt{color:var(--blue);}
.vsb{font-size:8px;color:var(--dim);letter-spacing:1px;margin-top:1px;}
.vdots{display:flex;gap:3px;justify-content:center;margin-top:3px;}
.vd{width:4px;height:4px;border-radius:50%;background:var(--g3);animation:vd 1.5s infinite;}
.vd:nth-child(2){animation-delay:.2s;}.vd:nth-child(3){animation-delay:.4s;}.vd:nth-child(4){animation-delay:.6s;}.vd:nth-child(5){animation-delay:.8s;}
@keyframes vd{0%,100%{background:var(--g3);}50%{background:var(--g1);box-shadow:0 0 5px var(--g1);}}
.vscan{position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--g1),transparent);animation:vscan 2s linear infinite;opacity:.25;}
@keyframes vscan{0%{top:0}100%{top:100%}}
.tok-hint{font-size:8px;color:var(--dim);margin-top:3px;letter-spacing:1px;}

/* Mode grid */
.mode-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;}
.mb{padding:8px 2px;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;cursor:pointer;transition:all .2s;text-align:center;}
.mb.on.gems{border-color:var(--g1);background:rgba(0,255,100,.08);}
.mb.on.tickets{border-color:var(--orange);background:rgba(255,140,0,.08);}
.mb.on.elite{border-color:var(--cyan);background:rgba(0,229,255,.08);}
.mb.on.legendary{border-color:var(--purple);background:rgba(194,100,254,.08);}
.mb.on.champion{border-color:var(--gold);background:rgba(255,215,0,.08);}
.mbi{font-size:17px;margin-bottom:2px;}
.mbl{font-family:'Orbitron',monospace;font-size:6px;letter-spacing:1px;color:var(--dim);}
.mb.on.gems .mbl{color:var(--g1);}
.mb.on.tickets .mbl{color:var(--orange);}
.mb.on.elite .mbl{color:var(--cyan);}
.mb.on.legendary .mbl{color:var(--purple);}
.mb.on.champion .mbl{color:var(--gold);}
.mbs{font-size:7px;color:var(--dim);margin-top:1px;}

/* Chain box */
.chainBox{display:none;margin-top:7px;border-radius:4px;padding:8px 10px;}
.chainBox.show{display:block;}
.chainBox.legendary{background:rgba(194,100,254,.05);border:1px solid rgba(194,100,254,.2);}
.chainBox.champion{background:rgba(255,215,0,.05);border:1px solid rgba(255,215,0,.2);}
.chain-title{font-family:'Orbitron',monospace;font-size:7px;letter-spacing:3px;margin-bottom:6px;}
.chainBox.legendary .chain-title{color:var(--purple);}
.chainBox.champion .chain-title{color:var(--gold);}
.chain-steps{display:flex;align-items:center;gap:5px;}
.cs{background:rgba(0,0,0,.3);border-radius:3px;padding:4px 6px;font-size:9px;text-align:center;}
.cs-icon{font-size:14px;}
.cs-lbl{font-size:7px;color:var(--dim);}
.cs-arr{color:var(--dim);font-size:12px;}
.chain-calc{margin-top:6px;font-size:9px;color:var(--dim);}
.chain-calc span{font-family:'Orbitron',monospace;font-size:10px;}
.chainBox.legendary .chain-calc span{color:var(--purple);}
.chainBox.champion .chain-calc span{color:var(--gold);}

/* Config */
.cfg-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.cfg-item label{display:block;font-size:8px;letter-spacing:3px;color:var(--dim);margin-bottom:4px;}
input[type=number]{width:100%;background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;color:var(--g1);font-family:'Share Tech Mono',monospace;font-size:14px;padding:8px 10px;outline:none;}
.hint{font-size:8px;color:var(--dim);margin-top:2px;}
.presets{display:flex;gap:4px;margin-top:5px;flex-wrap:wrap;}
.pw{flex:1;min-width:32px;background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--dim);font-family:'Share Tech Mono',monospace;font-size:10px;padding:4px 2px;cursor:pointer;transition:all .15s;text-align:center;}
.pw:hover,.pw.on{border-color:var(--g1);color:var(--g1);background:rgba(0,255,100,.08);}
.pw.hot{border-color:var(--red)!important;color:var(--red)!important;background:rgba(255,34,68,.08)!important;}

/* Buttons */
.btn-start{width:100%;padding:14px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid var(--g2);border-radius:6px;color:var(--g1);font-family:'Orbitron',monospace;font-weight:900;font-size:11px;letter-spacing:4px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;}
.btn-start.b{background:linear-gradient(135deg,#001128,#002255,#001a44);border-color:var(--blue);color:var(--blue);}
.btn-start.tickets{border-color:var(--orange);color:var(--orange);background:linear-gradient(135deg,#2a1400,#503000,#3a1c00);}
.btn-start.elite{border-color:var(--cyan);color:var(--cyan);background:linear-gradient(135deg,#002a2a,#005050,#003a3a);}
.btn-start.legendary{border-color:var(--purple);color:var(--purple);background:linear-gradient(135deg,#1a0028,#350050,#28003a);}
.btn-start.champion{border-color:var(--gold);color:var(--gold);background:linear-gradient(135deg,#2a2000,#504000,#3a3000);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){transform:translateY(-1px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-stop{width:100%;padding:10px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:12px;letter-spacing:4px;cursor:pointer;display:none;}

/* Progress */
.prog-card{display:none;}.prog-card.show{display:block;}
.prog-top{display:flex;align-items:center;gap:14px;margin-bottom:10px;}
.ring-wrap{position:relative;width:72px;height:72px;flex-shrink:0;}
.ring-wrap svg{width:72px;height:72px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:var(--border);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s;}
.ring-fg.tickets{stroke:url(#rgt);}.ring-fg.elite{stroke:url(#rge);}
.ring-fg.legendary{stroke:url(#rgl);}.ring-fg.champion{stroke:url(#rgc);}
.ring-fg.b-gems{stroke:url(#rgb);}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:12px;font-weight:900;color:var(--g1);}
.ring-pct.tickets{color:var(--orange);}.ring-pct.elite{color:var(--cyan);}
.ring-pct.legendary{color:var(--purple);}.ring-pct.champion{color:var(--gold);}
.ring-pct.b-gems{color:var(--blue);}
.plbl{font-size:9px;color:var(--dim);letter-spacing:2px;margin-bottom:2px;}
.pval{font-family:'Orbitron',monospace;font-size:19px;font-weight:700;color:var(--g1);}
.pval.tickets{color:var(--orange);}.pval.elite{color:var(--cyan);}
.pval.legendary{color:var(--purple);}.pval.champion{color:var(--gold);}.pval.b-gems{color:var(--blue);}
.psub{font-size:9px;color:var(--dim);margin-top:1px;}
.bar-wrap{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:3px;height:8px;overflow:hidden;margin-bottom:9px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));width:0%;transition:width .4s;}
.bar-fill.tickets{background:linear-gradient(90deg,#3a1c00,#995500,#ff8c00);}
.bar-fill.elite{background:linear-gradient(90deg,#003a3a,#009999,#00e5ff);}
.bar-fill.legendary{background:linear-gradient(90deg,#280038,#6600aa,#c264fe);}
.bar-fill.champion{background:linear-gradient(90deg,#3a3000,#aa8800,#ffd700);}
.bar-fill.b-gems{background:linear-gradient(90deg,#112244,#224488,#4488ff);}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;}
.stat{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;padding:7px 4px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(10px,2.5vw,14px);font-weight:700;color:var(--g1);}
.sv.c{color:var(--cyan);}.sv.y{color:var(--yellow);}.sv.r{color:var(--red);}
.sl2{font-size:7px;color:var(--dim);letter-spacing:1px;margin-top:2px;}
.graph{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:3px;height:36px;overflow:hidden;margin-top:8px;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:2px 2px 0;}
.gb{flex:1;min-width:2px;background:linear-gradient(to top,var(--g3),var(--g2));border-radius:1px 1px 0 0;}
.gb.tickets{background:linear-gradient(to top,#3a1c00,#ff8c00);}
.gb.elite{background:linear-gradient(to top,#003a3a,#00e5ff);}
.gb.legendary{background:linear-gradient(to top,#280038,#c264fe);}
.gb.champion{background:linear-gradient(to top,#3a3000,#ffd700);}
.gb.b-gems{background:linear-gradient(to top,#112244,#4488ff);}
.st{text-align:center;font-size:9px;color:var(--dim);letter-spacing:1px;margin-top:6px;min-height:13px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--g1);}.st.r{color:var(--red);}.st.b{color:var(--blue);}

/* Done */
.done-card{display:none;text-align:center;padding:14px;background:rgba(0,255,100,.04);border:1px solid var(--g2);border-radius:6px;animation:glo 2s infinite;}
@keyframes glo{0%,100%{box-shadow:0 0 12px rgba(0,255,100,.1);}50%{box-shadow:0 0 30px rgba(0,255,100,.22);}}
.done-icon{font-size:26px;margin-bottom:5px;}
.done-title{font-family:'Orbitron',monospace;font-size:12px;letter-spacing:5px;color:var(--g1);}
.done-sub{font-size:10px;color:var(--dim);margin-top:4px;line-height:1.7;}
.done-countdown{margin-top:8px;background:rgba(0,255,100,.05);border:1px solid var(--border);border-radius:2px;height:3px;overflow:hidden;}
.done-cd-fill{height:100%;background:var(--g2);width:100%;}
.done-cd-txt{font-size:7px;color:var(--dim);margin-top:3px;letter-spacing:2px;}

/* History */
.sess-list{display:flex;flex-direction:column;gap:5px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(0,255,100,.02);border:1px solid var(--border);border-radius:4px;padding:7px 9px;}
.si-r{font-family:'Orbitron',monospace;font-size:12px;font-weight:700;color:var(--g1);}
.si-m{font-size:9px;color:var(--dim);}
.si-tm{font-size:8px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:11px;letter-spacing:2px;padding:8px;}
.blink{animation:bl 1s step-end infinite;}
@keyframes bl{0%,100%{opacity:1;}50%{opacity:0;}}
.bg-notice{background:rgba(0,229,255,.04);border:1px solid rgba(0,229,255,.12);border-radius:4px;padding:6px 9px;font-size:8px;color:#00e5ff;letter-spacing:1px;text-align:center;margin-top:4px;}
</style>
</head>
<body>
<div class="wrap">

<!-- HEADER -->
<div class="hdr">
  <div class="ping-badge"><div class="ping-dot"></div>AUTO-PING</div>
  <div class="hdr-badge">DC25</div>
  <h1>ULTRA FARMER v6.0</h1>
  <p>DUAL JOB SYSTEM · 2 ORDERS SIMULTANEOUSLY</p>
  <button class="logout-btn" onclick="doLogout()">⏻ OUT</button>
</div>

<!-- DUAL STATUS BAR (always visible) -->
<div class="dual-status">
  <div class="ds-item slot-a" id="dsA">
    <div class="ds-slot">⚡ JOB SLOT A</div>
    <div class="ds-reward" id="dsAReward">—</div>
    <div class="ds-info" id="dsAInfo">Idle</div>
    <div class="ds-bar"><div class="ds-fill-a" id="dsAFill" style="width:0%"></div></div>
    <button class="ds-stop" id="dsAStop" onclick="stopSlot('A')" style="display:none">⛔</button>
  </div>
  <div class="ds-item slot-b" id="dsB">
    <div class="ds-slot" style="color:var(--blue)">⚡ JOB SLOT B</div>
    <div class="ds-reward" style="color:var(--blue)" id="dsBReward">—</div>
    <div class="ds-info" id="dsBInfo">Idle</div>
    <div class="ds-bar"><div class="ds-fill-b" id="dsBFill" style="width:0%"></div></div>
    <button class="ds-stop" id="dsBStop" onclick="stopSlot('B')" style="display:none">⛔</button>
  </div>
</div>

<!-- JOB TABS -->
<div class="job-tabs">
  <div class="job-tab active-a" id="tabA" onclick="switchTab('A')">
    <div class="job-tab-label"><span class="job-badge idle" id="badgeA"></span>JOB A</div>
    <div class="job-tab-sub" id="tabASub">Ready</div>
  </div>
  <div class="job-tab" id="tabB" onclick="switchTab('B')">
    <div class="job-tab-label"><span class="job-badge idle" id="badgeB"></span>JOB B</div>
    <div class="job-tab-sub" id="tabBSub">Ready</div>
  </div>
</div>

<div class="page">

<!-- ═══ JOB PANEL A ═══ -->
<div class="job-panel show" id="panelA">
  <div class="card">
    <div class="cg green"></div>
    <div class="slot-badge a">⚡ JOB SLOT A</div>
    <div class="sec">// BEARER TOKEN</div>
    <textarea class="tok-area" id="tokA" placeholder="Paste Token A here..."></textarea>
    <div class="tok-vault" id="vaultA" onclick="revealToken('A')">
      <canvas class="vCv" id="vCvA"></canvas><div class="vscan"></div>
      <div class="vc"><div class="vi">🔒</div><div class="vtt">TOKEN A SECURED</div><div class="vsb">Tap to reveal</div>
        <div class="vdots"><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div></div>
      </div>
    </div>
    <div class="tok-hint" id="hintA">Token A paste karo → auto-hide hoga 🔒</div>
  </div>
  <div class="card">
    <div class="cg gold"></div><div class="sec">// SELECT MODE</div>
    <div class="mode-grid" id="modeGridA"></div>
    <div class="chainBox" id="chainBoxA">
      <div class="chain-title" id="chainTitleA">⚡ AUTO-CHAIN</div>
      <div class="chain-steps">
        <div class="cs"><div class="cs-icon">🃏</div><div class="cs-lbl">ELITE</div></div>
        <div class="cs-arr">→</div>
        <div class="cs"><div class="cs-icon" id="chainIconA">⭐</div><div class="cs-lbl">EXCHANGE</div></div>
        <div class="cs-arr">→</div>
        <div class="cs"><div class="cs-icon" id="chainIconA2">⭐</div><div class="cs-lbl">DONE!</div></div>
      </div>
      <div class="chain-calc" id="chainCalcA">Enter amount</div>
    </div>
  </div>
  <div class="card">
    <div class="cg cyan"></div><div class="sec">// CONFIG</div>
    <div class="cfg-row">
      <div class="cfg-item"><label id="dLabelA">💎 DESIRED</label><input type="number" id="desiredA" value="5000" min="1" step="2" oninput="updateCalc('A')"/><div class="hint" id="hTxtA">1 click = 2 gems</div></div>
      <div class="cfg-item"><label>⚡ WORKERS</label><input type="number" id="wrkA" value="20" min="1" max="200"/>
        <div class="presets" id="presetsA"></div>
      </div>
    </div>
    <div class="bg-notice">🔁 Background mein chalta hai — phone band karo!</div>
  </div>
  <button class="btn-start" id="btnSA" onclick="go('A')">▶ LAUNCH JOB A</button>
  <button class="btn-stop" id="btnXA" onclick="stopSlot('A')">■ STOP JOB A</button>
  <div class="card prog-card" id="progA">
    <div class="cg green"></div><div class="sec">// JOB A PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rg"  x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#00cc77"/><stop offset="100%" style="stop-color:#00ffaa"/></linearGradient>
            <linearGradient id="rgt" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#995500"/><stop offset="100%" style="stop-color:#ff8c00"/></linearGradient>
            <linearGradient id="rge" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#009999"/><stop offset="100%" style="stop-color:#00e5ff"/></linearGradient>
            <linearGradient id="rgl" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#6600aa"/><stop offset="100%" style="stop-color:#c264fe"/></linearGradient>
            <linearGradient id="rgc" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#aa8800"/><stop offset="100%" style="stop-color:#ffd700"/></linearGradient>
            <linearGradient id="rgb" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#224488"/><stop offset="100%" style="stop-color:#4488ff"/></linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="ringA" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpctA">0%</div>
      </div>
      <div><div class="plbl" id="rLabelA">ADDED</div><div class="pval" id="pRA">0</div><div class="psub" id="pClicksA">0 / 0</div></div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="barA"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpdA">0</div><div class="sl2">REQ/S</div></div>
      <div class="stat"><div class="sv y" id="sEtaA">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv"  id="sOkA">0</div><div class="sl2">OK</div></div>
      <div class="stat"><div class="sv r" id="sFailA">0</div><div class="sl2">FAIL</div></div>
    </div>
    <div class="graph"><div class="gbars" id="gBarsA"></div></div>
    <div class="st" id="stA"><span class="blink">_</span> Ready</div>
  </div>
  <div class="done-card" id="doneA">
    <div class="done-icon" id="dIconA">💎</div>
    <div class="done-title" id="dTitleA">JOB A COMPLETE</div>
    <div class="done-sub" id="dSubA"></div>
    <div class="done-countdown"><div class="done-cd-fill" id="cdFillA"></div></div>
    <div class="done-cd-txt" id="cdTxtA">Auto-clear in 20s...</div>
  </div>
  <div class="card">
    <div class="cg purple"></div><div class="sec">// JOB A HISTORY</div>
    <div class="sess-list" id="histA"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div>
  </div>
</div>

<!-- ═══ JOB PANEL B ═══ -->
<div class="job-panel" id="panelB">
  <div class="card">
    <div class="cg blue"></div>
    <div class="slot-badge b">⚡ JOB SLOT B</div>
    <div class="sec">// BEARER TOKEN</div>
    <textarea class="tok-area b-tok" id="tokB" placeholder="Paste Token B here..."></textarea>
    <div class="tok-vault b-vault" id="vaultB" onclick="revealToken('B')">
      <canvas class="vCv" id="vCvB"></canvas><div class="vscan"></div>
      <div class="vc"><div class="vi">🔒</div><div class="vtt" style="color:var(--blue)">TOKEN B SECURED</div><div class="vsb">Tap to reveal</div>
        <div class="vdots"><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div><div class="vd"></div></div>
      </div>
    </div>
    <div class="tok-hint" id="hintB">Token B paste karo → auto-hide hoga 🔒</div>
  </div>
  <div class="card">
    <div class="cg gold"></div><div class="sec">// SELECT MODE</div>
    <div class="mode-grid" id="modeGridB"></div>
    <div class="chainBox" id="chainBoxB">
      <div class="chain-title" id="chainTitleB">⚡ AUTO-CHAIN</div>
      <div class="chain-steps">
        <div class="cs"><div class="cs-icon">🃏</div><div class="cs-lbl">ELITE</div></div>
        <div class="cs-arr">→</div>
        <div class="cs"><div class="cs-icon" id="chainIconB">⭐</div><div class="cs-lbl">EXCHANGE</div></div>
        <div class="cs-arr">→</div>
        <div class="cs"><div class="cs-icon" id="chainIconB2">⭐</div><div class="cs-lbl">DONE!</div></div>
      </div>
      <div class="chain-calc" id="chainCalcB">Enter amount</div>
    </div>
  </div>
  <div class="card">
    <div class="cg cyan"></div><div class="sec">// CONFIG</div>
    <div class="cfg-row">
      <div class="cfg-item"><label id="dLabelB">💎 DESIRED</label><input type="number" id="desiredB" value="5000" min="1" step="2" oninput="updateCalc('B')"/><div class="hint" id="hTxtB">1 click = 2 gems</div></div>
      <div class="cfg-item"><label>⚡ WORKERS</label><input type="number" id="wrkB" value="20" min="1" max="200"/>
        <div class="presets" id="presetsB"></div>
      </div>
    </div>
    <div class="bg-notice">🔁 Background mein chalta hai — phone band karo!</div>
  </div>
  <button class="btn-start b" id="btnSB" onclick="go('B')">▶ LAUNCH JOB B</button>
  <button class="btn-stop" id="btnXB" onclick="stopSlot('B')">■ STOP JOB B</button>
  <div class="card prog-card" id="progB">
    <div class="cg blue"></div><div class="sec">// JOB B PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rgb2" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" style="stop-color:#224488"/><stop offset="100%" style="stop-color:#4488ff"/></linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg b-gems" id="ringB" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct b-gems" id="rpctB">0%</div>
      </div>
      <div><div class="plbl" id="rLabelB">ADDED</div><div class="pval b-gems" id="pRB">0</div><div class="psub" id="pClicksB">0 / 0</div></div>
    </div>
    <div class="bar-wrap"><div class="bar-fill b-gems" id="barB"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpdB">0</div><div class="sl2">REQ/S</div></div>
      <div class="stat"><div class="sv y" id="sEtaB">--</div><div class="sl2">ETA</div></div>
      <div class="stat"><div class="sv"  id="sOkB">0</div><div class="sl2">OK</div></div>
      <div class="stat"><div class="sv r" id="sFailB">0</div><div class="sl2">FAIL</div></div>
    </div>
    <div class="graph"><div class="gbars" id="gBarsB"></div></div>
    <div class="st" id="stB"><span class="blink">_</span> Ready</div>
  </div>
  <div class="done-card" id="doneB">
    <div class="done-icon" id="dIconB">💎</div>
    <div class="done-title" id="dTitleB" style="color:var(--blue)">JOB B COMPLETE</div>
    <div class="done-sub" id="dSubB"></div>
    <div class="done-countdown"><div class="done-cd-fill" id="cdFillB" style="background:var(--blue)"></div></div>
    <div class="done-cd-txt" id="cdTxtB">Auto-clear in 20s...</div>
  </div>
  <div class="card">
    <div class="cg blue"></div><div class="sec">// JOB B HISTORY</div>
    <div class="sess-list" id="histB"><div class="empty">NO JOBS YET <span class="blink">_</span></div></div>
  </div>
</div>

</div>
</div>

<script>
const CIRC=245;
const MCFG={
  gems:     {lbl:'💎 DESIRED GEMS',   hint:'1 click = 2 gems',    btn:'▶ LAUNCH',  cls:'',        chain:false,icon:'💎',epc:0},
  tickets:  {lbl:'🎫 DESIRED TICKETS',hint:'1 click = 30 tickets',btn:'▶ LAUNCH',  cls:'tickets', chain:false,icon:'🎫',epc:0},
  elite:    {lbl:'🃏 DESIRED ELITE',   hint:'1 click = 1 card',   btn:'▶ LAUNCH',  cls:'elite',   chain:false,icon:'🃏',epc:0},
  legendary:{lbl:'⭐ DESIRED LEGEND',  hint:'AUTO: 10 elite→1',   btn:'⚡ AUTO-CHAIN',cls:'legendary',chain:true,icon:'⭐',epc:10},
  champion: {lbl:'👑 DESIRED CHAMPION',hint:'AUTO: 10 elite→1',   btn:'⚡ AUTO-CHAIN',cls:'champion', chain:true,icon:'👑',epc:10},
};
const COLS={gems:'var(--g1)',tickets:'var(--orange)',elite:'var(--cyan)',legendary:'var(--purple)',champion:'var(--gold)'};
const ICONS={gems:'💎',tickets:'🎫',elite:'🃏',legendary:'⭐',champion:'👑'};
const MODES_LIST=['gems','tickets','elite','legendary','champion'];
const MODEICONS=['💎','🎫','🃏','⭐','👑'];
const MODELABELS=['GEMS','TICKETS','ELITE','LEGEND','CHAMP'];
const MODESUBS=['+2/click','+30/click','+1/click','AUTO⚡','AUTO⚡'];

let activeTab='A';
let curMode={A:'gems',B:'gems'};
let polls={A:null,B:null};
let cdTimers={A:null,B:null};
let vCanvases={A:null,B:null};
let vIntervals={A:null,B:null};

// Build mode grids
['A','B'].forEach(s=>{
  const grid=document.getElementById('modeGrid'+s);
  MODES_LIST.forEach((mk,i)=>{
    const div=document.createElement('div');
    div.className='mb'+(mk==='gems'?' on gems':' '+mk);
    div.id=`m_${mk}_${s}`;
    div.innerHTML=`<div class="mbi">${MODEICONS[i]}</div><div class="mbl">${MODELABELS[i]}</div><div class="mbs">${MODESUBS[i]}</div>`;
    div.onclick=()=>setMode(s,mk);
    grid.appendChild(div);
  });
  // Presets
  const pre=document.getElementById('presets'+s);
  [10,20,50,100,200].forEach(v=>{
    const btn=document.createElement('button');
    btn.className='pw'+(v===20?' on':'')+(v===200?' hot':'');
    btn.textContent=v===200?'200🔥':String(v);
    btn.onclick=()=>swW(s,v);
    pre.appendChild(btn);
  });
});

function switchTab(t){
  activeTab=t;
  document.getElementById('tabA').className='job-tab'+(t==='A'?' active-a':'');
  document.getElementById('tabB').className='job-tab'+(t==='B'?' active-b':'');
  document.getElementById('panelA').className='job-panel'+(t==='A'?' show':'');
  document.getElementById('panelB').className='job-panel'+(t==='B'?' show':'');
}

function setMode(s,m){
  curMode[s]=m;
  const mc=MCFG[m];
  MODES_LIST.forEach(k=>{document.getElementById(`m_${k}_${s}`).className='mb '+k+(k===m?' on':'');});
  document.getElementById('dLabel'+s).textContent=mc.lbl;
  document.getElementById('hTxt'+s).textContent=mc.hint;
  document.getElementById('desired'+s).value=m==='tickets'?'300':m==='legendary'||m==='champion'?'10':'5000';
  document.getElementById('desired'+s).step=m==='tickets'?'30':m==='legendary'||m==='champion'?'1':'2';
  const btn=document.getElementById('btnS'+s);
  btn.textContent=`▶ ${mc.btn.replace('▶ ','')} JOB ${s}`;
  btn.className='btn-start '+(s==='B'&&m==='gems'?'b':mc.cls||'');
  const cb=document.getElementById('chainBox'+s);
  if(mc.chain){
    cb.style.display='block';cb.className='chainBox show '+m;
    document.getElementById('chainTitle'+s).textContent=`⚡ AUTO-CHAIN · ${m.toUpperCase()}`;
    document.getElementById('chainIcon'+s).textContent=mc.icon;
    document.getElementById('chainIcon'+s+'2').textContent=mc.icon;
    updateCalc(s);
  } else {cb.style.display='none';}
}

function updateCalc(s){
  const m=MCFG[curMode[s]];if(!m.chain)return;
  const d=parseInt(document.getElementById('desired'+s).value)||0;
  document.getElementById('chainCalc'+s).innerHTML=`Farm: <span>${d*m.epc}</span> Elite → Exchange: <span>${d}</span> cards`;
}

function swW(s,v){
  document.getElementById('wrk'+s).value=v;
  document.querySelectorAll(`#presets${s} .pw`).forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));
}

function fmt(s){s=Math.max(0,Math.round(s));if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';}

function ringUpd(id,pctId,p,mk,isB){
  document.getElementById(id).style.strokeDashoffset=CIRC-(CIRC*p/100);
  let cls=MCFG[mk]?.cls||'';if(isB&&mk==='gems')cls='b-gems';
  document.getElementById(id).className='ring-fg '+cls;
  document.getElementById(pctId).textContent=p.toFixed(1)+'%';
  document.getElementById(pctId).className='ring-pct '+cls;
}

function graphUpd(id,h,mk,isB){
  const w=document.getElementById(id);if(!h.length)return;
  let cls=MCFG[mk]?.cls||'';if(isB&&mk==='gems')cls='b-gems';
  const mx=Math.max(...h,1);
  w.innerHTML=h.map(v=>`<div class="gb ${cls}" style="height:${Math.max(2,(v/mx)*32)}px"></div>`).join('');
}

function histUpd(id,list){
  const el=document.getElementById(id);
  if(!list.length){el.innerHTML='<div class="empty">NO JOBS YET <span class="blink">_</span></div>';return;}
  el.innerHTML=list.map(s=>`<div class="si">
    <div><div class="si-r" style="color:${COLS[s.mode_key]||'var(--g1)'}">+${s.reward} ${s.label}</div>
    <div class="si-m">${s.success}/${s.total} · ${s.workers}w</div></div>
    <div class="si-tm">${s.time} ${s.date}<br/>${fmt(s.elapsed)}</div>
  </div>`).join('');
}

function setSt(s,m,c){const e=document.getElementById('st'+s);e.textContent=m;e.className='st '+(c||'');}

// Vault
function initVault(s){
  const cv=document.getElementById('vCv'+s);
  const w=document.getElementById('vault'+s);
  cv.width=w.offsetWidth;cv.height=w.offsetHeight;
  const ctx=cv.getContext('2d');
  const cols=Math.floor(cv.width/10),drops=Array(cols).fill(1);
  const CH='01アイウABCDEF<>{};';
  function draw(){ctx.fillStyle='rgba(0,0,0,0.08)';ctx.fillRect(0,0,cv.width,cv.height);drops.forEach((y,i)=>{const c=CH[Math.floor(Math.random()*CH.length)];ctx.fillStyle=Math.random()>.9?'#00ffaa':'#00441a';ctx.font='9px Share Tech Mono';ctx.fillText(c,i*10,y*10);if(y*10>cv.height&&Math.random()>.97)drops[i]=0;drops[i]++;});}
  vIntervals[s]=setInterval(draw,60);
}
function lockToken(s){
  document.getElementById('tok'+s).style.display='none';
  document.getElementById('vault'+s).classList.add('show');
  document.getElementById('hint'+s).textContent=`🔒 Token ${s} secured — tap to reveal`;
  initVault(s);
}
function unlockToken(s){
  document.getElementById('tok'+s).style.display='block';
  document.getElementById('vault'+s).classList.remove('show');
  document.getElementById('hint'+s).textContent=`Token ${s} paste karo → auto-hide hoga 🔒`;
  if(vIntervals[s])clearInterval(vIntervals[s]);
}
function revealToken(s){
  document.getElementById('vault'+s).classList.remove('show');
  if(vIntervals[s])clearInterval(vIntervals[s]);
  const t=document.getElementById('tok'+s);t.style.display='block';t.style.filter='blur(4px)';
  setTimeout(()=>t.style.filter='none',200);
  document.getElementById('hint'+s).textContent=`👁 3 sec mein re-lock...`;
  setTimeout(()=>{if(document.getElementById('btnX'+s).style.display!='none')lockToken(s);},3000);
}

// Dual status bar update
function updateDualStatus(d,s){
  const isB=s==='B';
  const rEl=document.getElementById('ds'+s+'Reward');
  const iEl=document.getElementById('ds'+s+'Info');
  const fEl=document.getElementById('ds'+s+'Fill');
  const stpEl=document.getElementById('ds'+s+'Stop');
  const badge=document.getElementById('badge'+s);
  const tab=document.getElementById('tab'+s);
  const tabSub=document.getElementById('tab'+s+'Sub');
  if(d.has_active){
    rEl.textContent=`+${d.reward} ${d.unit}`;
    iEl.textContent=`${d.pct}% · ${fmt(d.elapsed)}`;
    fEl.style.width=d.pct+'%';
    stpEl.style.display='block';
    badge.className=isB?'job-badge running-b':'job-badge running';
    tab.className='job-tab '+(isB?'active-b':'active-a');
    tabSub.textContent=`${d.pct}% running`;
  } else if(d.done){
    rEl.textContent=`+${d.reward} ${d.unit} ✓`;
    iEl.textContent='Complete!';
    fEl.style.width='100%';
    stpEl.style.display='none';
    badge.className='job-badge done';
    tabSub.textContent='Done ✓';
  } else {
    rEl.textContent='—';iEl.textContent='Idle';fEl.style.width='0%';
    stpEl.style.display='none';badge.className='job-badge idle';tabSub.textContent='Ready';
  }
}

async function go(s){
  const tok=document.getElementById('tok'+s).value.trim();
  const desired=parseInt(document.getElementById('desired'+s).value);
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
  document.getElementById('prog'+s).classList.add('show');
  document.getElementById('btnS'+s).disabled=true;
  document.getElementById('btnX'+s).style.display='block';
  const mk=curMode[s];const isB=s==='B';
  let barCls=MCFG[mk]?.cls||'';if(isB&&mk==='gems')barCls='b-gems';
  document.getElementById('bar'+s).style.width='0%';
  document.getElementById('bar'+s).className='bar-fill '+(barCls||'');
  document.getElementById('pR'+s).textContent='0';
  document.getElementById('pR'+s).className='pval '+(isB&&mk==='gems'?'b-gems':MCFG[mk]?.cls||'');
  ringUpd('ring'+s,'rpct'+s,0,mk,isB);
  ['Spd','Eta','Ok','Fail'].forEach(k=>{const el=document.getElementById('s'+k+s);el.textContent=k==='Eta'?'--':'0';});
  document.getElementById('gBars'+s).innerHTML='';
  setSt(s,data.is_chain?`⚡ AUTO-CHAIN: ${data.elite_needed} elite → ${desired} cards`:`Job ${s} started`,'g');
  if(polls[s])clearInterval(polls[s]);
  polls[s]=setInterval(()=>tick(s),800);
}

async function tick(s){
  try{
    const r=await fetch('/status?slot='+s);
    if(r.status===401){clearInterval(polls[s]);window.location.reload();return;}
    const d=await r.json();
    const mk=d.mode_key||'gems';const isB=s==='B';
    let barCls=MCFG[mk]?.cls||'';if(isB&&mk==='gems')barCls='b-gems';
    ringUpd('ring'+s,'rpct'+s,d.pct,mk,isB);
    document.getElementById('bar'+s).style.width=d.pct+'%';
    document.getElementById('bar'+s).className='bar-fill '+(barCls||'');
    document.getElementById('pR'+s).textContent=d.reward;
    document.getElementById('rLabel'+s).textContent=(ICONS[mk]||'💎')+' ADDED';
    document.getElementById('pClicks'+s).textContent=`${d.phase_done||0} steps`;
    document.getElementById('sSpd'+s).textContent=d.speed;
    document.getElementById('sEta'+s).textContent=fmt(d.eta);
    document.getElementById('sOk'+s).textContent=d.success;
    document.getElementById('sFail'+s).textContent=d.fail;
    graphUpd('gBars'+s,d.speed_history,mk,isB);
    histUpd('hist'+s,d.history);
    updateDualStatus(d,s);
    if(d.has_active)setSt(s,`${fmt(d.elapsed)} elapsed · server pe chal raha hai ✓`,'g');
    if(d.done){
      clearInterval(polls[s]);resetUI(s);ringUpd('ring'+s,'rpct'+s,100,mk,isB);
      document.getElementById('bar'+s).style.width='100%';
      const dc=document.getElementById('done'+s);dc.style.display='block';
      document.getElementById('dIcon'+s).textContent=ICONS[mk]||'💎';
      document.getElementById('dTitle'+s).style.color=COLS[mk]||'var(--g1)';
      document.getElementById('dSub'+s).innerHTML=`<strong style="color:${COLS[mk]||'var(--g1)'}">+${d.reward} ${d.unit}</strong> added!<br/>${d.success}/${d.total} success · ${fmt(d.elapsed)} total`;
      setSt(s,'Job '+s+' complete! ✅','g');
      startAutoClear(s);
    }
  }catch(e){setSt(s,'Reconnecting...','');}
}

function startAutoClear(s){
  const fill=document.getElementById('cdFill'+s),txt=document.getElementById('cdTxt'+s);
  const S=20;fill.style.transition='none';fill.style.width='100%';let rem=S;
  setTimeout(()=>{fill.style.transition=`width ${S}s linear`;fill.style.width='0%';},100);
  cdTimers[s]=setInterval(()=>{rem--;txt.textContent=`Auto-clear in ${rem}s...`;if(rem<=0){clearInterval(cdTimers[s]);autoClear(s);}},1000);
}
function autoClear(s){
  document.getElementById('done'+s).style.display='none';
  document.getElementById('prog'+s).classList.remove('show');
  ringUpd('ring'+s,'rpct'+s,0,'gems',s==='B');
  document.getElementById('bar'+s).style.width='0%';
  document.getElementById('pR'+s).textContent='0';
  ['sSpd','sOk','sFail'].forEach(id=>document.getElementById(id+s).textContent='0');
  document.getElementById('sEta'+s).textContent='--';
  document.getElementById('gBars'+s).innerHTML='';
  setSt(s,'Ready','');unlockToken(s);
}

async function stopSlot(s){
  await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:s})});
  clearInterval(polls[s]);setSt(s,'⛔ Stopped.','r');resetUI(s);unlockToken(s);
}
function resetUI(s){document.getElementById('btnS'+s).disabled=false;document.getElementById('btnX'+s).style.display='none';}
async function doLogout(){await fetch('/logout',{method:'POST'});window.location.reload();}

// Poll dual status every 2s for the status bar
setInterval(async()=>{
  try{
    const r=await fetch('/status_all');
    if(r.status!==200)return;
    const d=await r.json();
    updateDualStatus(d.A,'A');
    updateDualStatus(d.B,'B');
  }catch(e){}
},2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"\033[92m")
    print("╔══════════════════════════════════════════╗")
    print("║  DC25 ULTRA FARMER v6.0 - DUAL JOBS      ║")
    print("║  Job A + Job B simultaneously!           ║")
    print(f"║  Email : {ADMIN_EMAIL:<32}║")
    print("║  Open  : http://localhost:5000           ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")
    app.run(host="0.0.0.0", port=5000, debug=False)
