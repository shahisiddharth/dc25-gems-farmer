"""
Dream Cricket 25 - ULTRA Gems Farmer
Render.com deployment - Public version
"""

from flask import Flask, jsonify, request
import requests as req
import json, time, base64, math, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

app = Flask(__name__)

URL      = "https://api-prod.dreamgamestudios.in/userdata/graphql"
GEMS_PER = 2
MAX_WORKERS = 200

_ts  = int(time.time())
_tsl = threading.Lock()

# Per-session storage (keyed by session_id)
sessions = {}
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
    except:
        return '28788969'

def make_headers(token):
    return {
        "Host": "api-prod.dreamgamestudios.in",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "X-SpineSDK": "0.1",
        "gameId": "1", "studioId": "1",
        "userId": get_uid(token),
        "game-env": "BLUE",
        "gameVersion": "1.5.55",
        "secretKey": "6b77f094-45e2-46d0-b6cc-827dcb5f6b85",
        "X-API-VERSION": "1",
        "User-Agent": "ProjectCricketUE4/++UE4+Release-4.27-CL-0 Android/15"
    }

def one_req(hdr, sid):
    try:
        r = req.post(URL, headers=hdr, json=mutation(), timeout=15)
        ok = r.status_code == 200
    except:
        ok = False
    with sessions_lock:
        if sid in sessions:
            if ok: sessions[sid]["success"] += 1
            else:  sessions[sid]["fail"]    += 1
    return ok

def run_job(sid, token, total, workers):
    hdr = make_headers(token)
    batches = math.ceil(total / workers)
    bt = []

    for b in range(batches):
        with sessions_lock:
            if sid not in sessions or not sessions[sid]["running"]:
                break

        sz = min(workers, total - sessions[sid]["completed"])
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=sz) as ex:
            fs = [ex.submit(one_req, hdr, sid) for _ in range(sz)]
            for f in as_completed(fs): pass

        t1 = time.time()
        with sessions_lock:
            if sid not in sessions: break
            sessions[sid]["completed"] += sz

        bt.append(t1 - t0)
        if len(bt) > 10: bt.pop(0)
        avg = sum(bt) / len(bt)
        spd = round(workers / avg, 1)
        eta = (batches - b - 1) * avg

        with sessions_lock:
            if sid in sessions:
                sessions[sid]["eta"]   = eta
                sessions[sid]["speed"] = spd
                sessions[sid]["speed_history"].append(spd)
                if len(sessions[sid]["speed_history"]) > 30:
                    sessions[sid]["speed_history"].pop(0)

    with sessions_lock:
        if sid in sessions:
            sessions[sid]["running"] = False
            sessions[sid]["done"]    = True
            elapsed = time.time() - sessions[sid]["start_time"]
            sessions[sid]["history"].insert(0, {
                "gems":    sessions[sid]["success"] * GEMS_PER,
                "success": sessions[sid]["success"],
                "total":   total,
                "workers": workers,
                "elapsed": round(elapsed, 1),
                "time":    datetime.now().strftime("%H:%M:%S")
            })
            if len(sessions[sid]["history"]) > 5:
                sessions[sid]["history"] = sessions[sid]["history"][:5]

@app.route("/")
def index():
    return PAGE

@app.route("/start", methods=["POST"])
def start():
    d       = request.json
    token   = d.get("token","").strip()
    gems    = int(d.get("gems", 100))
    workers = int(d.get("workers", 20))
    sid     = d.get("sid", "default")

    if not token: return jsonify({"error":"Token required"}), 400
    if gems < 2:  return jsonify({"error":"Min 2 gems"}), 400
    workers = min(workers, MAX_WORKERS)

    with sessions_lock:
        if sid in sessions and sessions[sid]["running"]:
            return jsonify({"error":"Already running"}), 400

        prev_history = sessions[sid]["history"] if sid in sessions else []
        clicks = math.ceil(gems / GEMS_PER)
        sessions[sid] = {
            "running": True, "done": False,
            "success": 0, "fail": 0,
            "total": clicks, "completed": 0,
            "start_time": time.time(),
            "eta": 0, "speed": 0,
            "speed_history": [],
            "history": prev_history,
        }

    threading.Thread(target=run_job, args=(sid,token,clicks,workers), daemon=True).start()
    return jsonify({"ok": True, "clicks": clicks})

@app.route("/stop", methods=["POST"])
def stop():
    sid = request.json.get("sid","default")
    with sessions_lock:
        if sid in sessions:
            sessions[sid]["running"] = False
    return jsonify({"ok": True})

@app.route("/status")
def status():
    sid = request.args.get("sid","default")
    with sessions_lock:
        j = dict(sessions.get(sid, {
            "running":False,"done":False,"success":0,"fail":0,
            "total":0,"completed":0,"start_time":0,
            "eta":0,"speed":0,"speed_history":[],"history":[]
        }))
    elapsed = time.time() - j["start_time"] if j["start_time"] else 0
    pct = round(j["completed"]/j["total"]*100, 1) if j["total"] else 0
    return jsonify({
        "running":  j["running"], "done":j["done"],
        "completed":j["completed"], "total":j["total"],
        "pct": pct,
        "gems":     j["success"] * GEMS_PER,
        "success":  j["success"], "fail":j["fail"],
        "eta":      round(j.get("eta",0)),
        "speed":    j.get("speed",0),
        "elapsed":  round(elapsed),
        "speed_history": j.get("speed_history",[]),
        "history":       j.get("history",[]),
    })

@app.route("/ping")
def ping():
    return "pong", 200

# ─── HTML ─────────────────────────────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DC25 ULTRA FARMER</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#03050a;--bg2:#070d14;--panel:#0a1520;--border:#0d2a1a;
  --g1:#00ffaa;--g2:#00cc77;--g3:#004422;
  --cyan:#00e5ff;--red:#ff2244;--yellow:#ffd600;
  --purple:#c264fe;--text:#a8ffd0;--dim:#2a4a35;--dim2:#1a3025;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;}
body::before{
  content:'';position:fixed;inset:0;
  background:
    radial-gradient(ellipse 80% 50% at 20% 0%,rgba(0,255,100,.04) 0%,transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 100%,rgba(0,200,255,.03) 0%,transparent 60%),
    repeating-linear-gradient(0deg,transparent,transparent 40px,rgba(0,255,100,.012) 40px,rgba(0,255,100,.012) 41px),
    repeating-linear-gradient(90deg,transparent,transparent 40px,rgba(0,255,100,.008) 40px,rgba(0,255,100,.008) 41px);
  pointer-events:none;z-index:0;
}
body::after{
  content:'';position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.15) 3px,rgba(0,0,0,.15) 4px);
  pointer-events:none;z-index:1;
}
.wrap{position:relative;z-index:2}

.hdr{padding:28px 20px 22px;text-align:center;border-bottom:1px solid var(--border);position:relative;}
.hdr::after{content:'';position:absolute;bottom:0;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--g1),var(--cyan),var(--g1),transparent);}
.hdr-badge{display:inline-block;background:rgba(0,255,100,.08);border:1px solid var(--g3);border-radius:2px;padding:2px 10px;font-size:10px;letter-spacing:4px;color:var(--g2);margin-bottom:10px;}
.hdr h1{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(20px,6vw,38px);letter-spacing:6px;background:linear-gradient(135deg,var(--g1),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;filter:drop-shadow(0 0 20px rgba(0,255,150,.4));}
.hdr p{color:var(--dim);font-size:11px;letter-spacing:3px;margin-top:6px;}

.page{max-width:680px;margin:0 auto;padding:20px 14px 40px;display:flex;flex-direction:column;gap:14px;}

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
.pw:hover,.pw.on{border-color:var(--g1);color:var(--g1);background:rgba(0,255,100,.08);text-shadow:0 0 8px rgba(0,255,100,.5);}
.pw.hot{border-color:var(--red) !important;color:var(--red) !important;background:rgba(255,34,68,.08) !important;}

.btn-start{width:100%;padding:18px;background:linear-gradient(135deg,#002a14,#005028,#003a1c);border:1px solid var(--g2);border-radius:6px;color:var(--g1);font-family:'Orbitron',monospace;font-weight:900;font-size:14px;letter-spacing:6px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;text-shadow:0 0 15px rgba(0,255,100,.6);box-shadow:0 0 30px rgba(0,255,100,.08),inset 0 1px 0 rgba(0,255,100,.1);}
.btn-start::before{content:'';position:absolute;top:-50%;left:-60%;width:30%;height:200%;background:linear-gradient(90deg,transparent,rgba(0,255,100,.12),transparent);transform:skewX(-20deg);animation:shine 3s infinite;}
@keyframes shine{0%{left:-60%}100%{left:160%}}
.btn-start:hover:not(:disabled){background:linear-gradient(135deg,#003a1c,#006633,#004422);box-shadow:0 0 50px rgba(0,255,100,.2);transform:translateY(-2px);}
.btn-start:disabled{opacity:.35;cursor:not-allowed;}
.btn-start:disabled::before{animation:none;}

.btn-stop{width:100%;padding:12px;background:rgba(255,34,68,.06);border:1px solid var(--red);border-radius:6px;color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;font-size:14px;letter-spacing:4px;cursor:pointer;transition:all .2s;display:none;}
.btn-stop:hover{background:rgba(255,34,68,.15);}

.prog-card{display:none;}
.prog-card.show{display:block;}

.prog-top{display:flex;align-items:center;gap:20px;margin-bottom:16px;}
.ring-wrap{position:relative;width:90px;height:90px;flex-shrink:0;}
.ring-wrap svg{width:90px;height:90px;transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:var(--border);stroke-width:6;}
.ring-fg{fill:none;stroke:url(#rg);stroke-width:6;stroke-linecap:round;stroke-dasharray:245;stroke-dashoffset:245;transition:stroke-dashoffset .5s ease;}
.ring-pct{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:var(--g1);text-shadow:0 0 10px rgba(0,255,100,.5);}
.prog-info{flex:1;}
.plbl{font-size:10px;color:var(--dim);letter-spacing:2px;margin-bottom:4px;}
.pval{font-family:'Orbitron',monospace;font-size:24px;font-weight:700;color:var(--g1);text-shadow:0 0 15px rgba(0,255,100,.4);}
.psub{font-size:11px;color:var(--dim);margin-top:2px;}

.bar-wrap{background:rgba(0,255,100,.04);border:1px solid var(--border);border-radius:3px;height:12px;overflow:hidden;margin-bottom:14px;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--g3),var(--g2),var(--g1));width:0%;transition:width .4s ease;box-shadow:0 0 10px rgba(0,255,100,.4);}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.stat{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:4px;padding:10px 8px;text-align:center;}
.sv{font-family:'Orbitron',monospace;font-size:clamp(13px,3.5vw,19px);font-weight:700;color:var(--g1);}
.sv.c{color:var(--cyan);}
.sv.y{color:var(--yellow);}
.sv.r{color:var(--red);}
.sl{font-size:8px;color:var(--dim);letter-spacing:2px;margin-top:3px;}

.graph-wrap{margin-top:12px;}
.glbl{font-size:9px;color:var(--dim);letter-spacing:3px;margin-bottom:6px;}
.graph{background:rgba(0,255,100,.03);border:1px solid var(--border);border-radius:3px;height:52px;position:relative;overflow:hidden;}
.gbars{display:flex;align-items:flex-end;gap:2px;height:100%;padding:4px 4px 0;}
.gb{flex:1;min-width:3px;background:linear-gradient(to top,var(--g3),var(--g2));border-radius:1px 1px 0 0;transition:height .3s ease;}

.st{text-align:center;font-size:11px;color:var(--dim);letter-spacing:1px;margin-top:10px;min-height:16px;font-family:'Share Tech Mono',monospace;}
.st.g{color:var(--g1);}
.st.r{color:var(--red);}

.done-card{display:none;text-align:center;padding:24px 20px;background:rgba(0,255,100,.04);border:1px solid var(--g2);border-radius:6px;animation:glo 2s infinite;}
@keyframes glo{0%,100%{box-shadow:0 0 15px rgba(0,255,100,.1);}50%{box-shadow:0 0 40px rgba(0,255,100,.25),0 0 80px rgba(0,255,100,.1);}}
.done-icon{font-size:36px;margin-bottom:10px;}
.done-title{font-family:'Orbitron',monospace;font-size:20px;letter-spacing:6px;color:var(--g1);text-shadow:0 0 20px rgba(0,255,100,.6);}
.done-sub{font-size:13px;color:var(--dim);margin-top:8px;line-height:1.8;}

.sess-list{display:flex;flex-direction:column;gap:8px;}
.si{display:flex;align-items:center;justify-content:space-between;background:rgba(0,255,100,.02);border:1px solid var(--border);border-radius:4px;padding:10px 14px;}
.si-gems{font-family:'Orbitron',monospace;font-size:16px;font-weight:700;color:var(--g1);}
.si-meta{font-size:11px;color:var(--dim);}
.si-time{font-size:10px;color:var(--dim);text-align:right;}
.empty{text-align:center;color:var(--dim);font-size:12px;letter-spacing:2px;padding:10px;}

.cur{animation:blink 1s step-end infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div class="hdr-badge">DREAM CRICKET 25</div>
  <h1>ULTRA GEMS FARMER</h1>
  <p>PUBLIC EDITION · MAX 200 WORKERS · ZERO FAILED</p>
</div>

<div class="page">

  <div class="card">
    <div class="cg"></div>
    <div class="sec">// BEARER TOKEN</div>
    <textarea id="tok" placeholder="Paste your Bearer token here..."></textarea>
  </div>

  <div class="card">
    <div class="cg c"></div>
    <div class="sec">// CONFIGURATION</div>
    <div class="cfg-row">
      <div class="cfg-item">
        <label>💎 DESIRED GEMS</label>
        <input type="number" id="gems" value="5000" min="2" step="2"/>
        <div class="hint">1 click = 2 gems</div>
      </div>
      <div class="cfg-item">
        <label>⚡ PARALLEL WORKERS</label>
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
  </div>

  <button class="btn-start" id="btnS" onclick="go()">▶ LAUNCH FARMING</button>
  <button class="btn-stop"  id="btnX" onclick="halt()">■ STOP FARMING</button>

  <div class="card prog-card" id="progCard">
    <div class="cg"></div>
    <div class="sec">// LIVE PROGRESS</div>
    <div class="prog-top">
      <div class="ring-wrap">
        <svg viewBox="0 0 90 90">
          <defs>
            <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" style="stop-color:#00cc77"/>
              <stop offset="100%" style="stop-color:#00ffaa"/>
            </linearGradient>
          </defs>
          <circle class="ring-bg" cx="45" cy="45" r="39"/>
          <circle class="ring-fg" id="ring" cx="45" cy="45" r="39"/>
        </svg>
        <div class="ring-pct" id="rpct">0%</div>
      </div>
      <div class="prog-info">
        <div class="plbl">GEMS ADDED</div>
        <div class="pval" id="pGems">0</div>
        <div class="psub" id="pClicks">0 / 0 clicks</div>
      </div>
    </div>
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
    <div class="stats">
      <div class="stat"><div class="sv c" id="sSpd">0</div><div class="sl">REQ/SEC</div></div>
      <div class="stat"><div class="sv y" id="sEta">--</div><div class="sl">ETA</div></div>
      <div class="stat"><div class="sv"   id="sOk">0</div><div class="sl">SUCCESS</div></div>
      <div class="stat"><div class="sv r" id="sFail">0</div><div class="sl">FAILED</div></div>
    </div>
    <div class="graph-wrap">
      <div class="glbl">// SPEED GRAPH (req/s)</div>
      <div class="graph"><div class="gbars" id="gBars"></div></div>
    </div>
    <div class="st" id="stLine"><span class="cur">_</span> Ready</div>
  </div>

  <div class="done-card" id="doneCard">
    <div class="done-icon">💎</div>
    <div class="done-title">FARMING COMPLETE</div>
    <div class="done-sub" id="doneSub"></div>
  </div>

  <div class="card">
    <div class="cg p"></div>
    <div class="sec">// SESSION HISTORY</div>
    <div class="sess-list" id="sessList">
      <div class="empty">NO SESSIONS YET <span class="cur">_</span></div>
    </div>
  </div>

</div>
</div>

<script>
const CIRC = 245;
// Unique session ID per browser tab
const SID = Math.random().toString(36).slice(2,10);
let poll = null;

function sw(v){
  document.getElementById('wrk').value=v;
  document.querySelectorAll('.pw').forEach(b=>b.classList.toggle('on',b.textContent.replace('🔥','')==v));
}
function fmt(s){
  s=Math.max(0,Math.round(s));
  if(s<60)return s+'s';
  if(s<3600)return Math.floor(s/60)+'m '+(s%60)+'s';
  return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';
}
function ring(pct){
  document.getElementById('ring').style.strokeDashoffset=CIRC-(CIRC*pct/100);
  document.getElementById('rpct').textContent=pct.toFixed(1)+'%';
}
function graph(history){
  const w=document.getElementById('gBars');
  if(!history.length)return;
  const mx=Math.max(...history,1);
  w.innerHTML=history.map(v=>`<div class="gb" style="height:${Math.max(4,(v/mx)*44)}px"></div>`).join('');
}
function sessions(list){
  const el=document.getElementById('sessList');
  if(!list.length){el.innerHTML='<div class="empty">NO SESSIONS YET <span class="cur">_</span></div>';return;}
  el.innerHTML=list.map(s=>`
    <div class="si">
      <div>
        <div class="si-gems">+${s.gems} 💎</div>
        <div class="si-meta">${s.success}/${s.total} clicks · ${s.workers} workers</div>
      </div>
      <div class="si-time">${s.time}<br/>${fmt(s.elapsed)}</div>
    </div>`).join('');
}
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
  ring(0);
  document.getElementById('bar').style.width='0%';
  ['pGems','sSpd','sOk','sFail'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('sEta').textContent='--';
  document.getElementById('pClicks').textContent='0 / 0 clicks';
  document.getElementById('gBars').innerHTML='';
  setSt('Launching...','g');

  const res=await fetch('/start',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:tok,gems,workers:wrk,sid:SID})
  });
  const data=await res.json();
  if(data.error){alert(data.error);resetUI();return;}
  setSt(`Running ${data.clicks} clicks · ${wrk} workers`,'g');
  poll=setInterval(tick,700);
}

async function tick(){
  try{
    const r=await fetch('/status?sid='+SID);
    const d=await r.json();
    ring(d.pct);
    document.getElementById('bar').style.width=d.pct+'%';
    document.getElementById('pGems').textContent=d.gems;
    document.getElementById('pClicks').textContent=`${d.completed} / ${d.total} clicks`;
    document.getElementById('sSpd').textContent=d.speed;
    document.getElementById('sEta').textContent=fmt(d.eta);
    document.getElementById('sOk').textContent=d.success;
    document.getElementById('sFail').textContent=d.fail;
    graph(d.speed_history);
    sessions(d.history);
    if(d.running) setSt(`${d.completed}/${d.total} · elapsed ${fmt(d.elapsed)}`,'g');
    if(d.done){
      clearInterval(poll);resetUI();ring(100);
      document.getElementById('bar').style.width='100%';
      document.getElementById('doneCard').style.display='block';
      document.getElementById('doneSub').innerHTML=
        `<strong style="color:var(--g1)">+${d.gems} GEMS</strong> added successfully<br/>
         ${d.success}/${d.total} success · ${fmt(d.elapsed)} total time`;
      setSt('Complete!','g');
    }
  }catch(e){setSt('Connection error...','r');}
}

async function halt(){
  await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:SID})});
  clearInterval(poll);setSt('Stopped.','r');resetUI();
}
function resetUI(){
  document.getElementById('btnS').disabled=false;
  document.getElementById('btnX').style.display='none';
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
