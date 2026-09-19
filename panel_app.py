"""
SVM v9.2 Web Panel
------------------
A lightweight control panel that lets a VPS owner log in with the VPS ID +
token they received in their Discord DM, then view live status and control
their own container (start/stop/restart/reinstall/ports) plus an in-browser
terminal that attaches via `lxc exec` (no SSH keys/ports involved).

This process is independent from bot.py but reads/writes the SAME vps.db
SQLite database, so actions here are immediately visible to the bot and
vice versa.

Run with: python3 panel_app.py
Requires: flask, flask-socketio, eventlet  (see install.sh)
"""
import os
import json
import shlex
import sqlite3
import secrets
import subprocess
from datetime import datetime

from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify
from flask_socketio import SocketIO, emit, disconnect

DB_PATH = os.getenv('VPS_DB_PATH', 'vps.db')
SECRET_KEY = os.getenv('PANEL_SECRET_KEY') or secrets.token_hex(32)
SERVER_NAME = os.getenv('SERVER_NAME', 'SVM v9.2')
PANEL_PORT = int(os.getenv('PANEL_PORT', '8080'))

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

OS_LABELS = {
    "ubuntu:20.04": "Ubuntu 20.04 LTS", "ubuntu:22.04": "Ubuntu 22.04 LTS",
    "ubuntu:24.04": "Ubuntu 24.04 LTS", "images:debian/10": "Debian 10",
    "images:debian/11": "Debian 11", "images:debian/12": "Debian 12",
    "images:debian/13": "Debian 13",
}

# --------------------------------------------------------------------------
# DB helpers (read/write the same schema bot.py uses)
# --------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def find_vps_by_credentials(vps_id: str, token: str):
    if not vps_id.isdigit() or not token:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM vps WHERE id = ? AND panel_token = ?', (vps_id, token))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_vps_by_id(vps_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM vps WHERE id = ?', (vps_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_node(node_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM nodes WHERE id = ?', (node_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_ports_for(container_name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM port_forwards WHERE vps_container = ? ORDER BY created_at DESC', (container_name,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_user_allocation(user_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT allocated_ports FROM port_allocations WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def set_status(vps_id: int, status: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE vps SET status = ? WHERE id = ?', (status, vps_id))
    conn.commit()
    conn.close()

# --------------------------------------------------------------------------
# LXC execution — local-node only from the panel by design. Remote-node
# containers are controlled the same way the bot does (via the node's
# HTTP execute API); this panel proxies to that node API when node_id != local.
# --------------------------------------------------------------------------
def run_lxc(args: list, timeout=60) -> str:
    """Run a local `lxc ...` command and return combined stdout, raising on failure."""
    proc = subprocess.run(["lxc"] + args, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"lxc {' '.join(args)} failed")
    return proc.stdout.strip()

def lxc_for_vps(vps: dict, args: list, timeout=60) -> str:
    """Runs the command against the right backend: local lxc, or the remote node's API."""
    node = get_node(vps['node_id']) or {}
    if node.get('is_local', 1):
        return run_lxc(args, timeout=timeout)
    import requests
    full_command = "lxc " + " ".join(shlex.quote(a) for a in args)
    resp = requests.post(f"{node['url']}/api/execute", json={"command": full_command},
                          params={"api_key": node["api_key"]}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("returncode", 1) != 0:
        raise RuntimeError(data.get("stderr", "remote command failed"))
    return data.get("stdout", "")

def live_status(vps: dict) -> str:
    try:
        out = run_lxc(["list", vps['container_name'], "--format", "json"]) \
            if (get_node(vps['node_id']) or {}).get('is_local', 1) else None
        if out:
            info = json.loads(out)
            if info:
                return info[0].get("status", "Unknown").lower()
    except Exception:
        pass
    return vps.get('status', 'unknown')

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def current_vps():
    vid = session.get('vps_id')
    token = session.get('vps_token')
    if not vid or not token:
        return None
    return find_vps_by_credentials(str(vid), token)

def require_login():
    vps = current_vps()
    if not vps:
        return None
    return vps

# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    if current_vps():
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_HTML, server_name=SERVER_NAME, error=None)

@app.route('/login', methods=['POST'])
def login():
    vps_id = request.form.get('vps_id', '').strip()
    token = request.form.get('token', '').strip()
    vps = find_vps_by_credentials(vps_id, token)
    if not vps:
        return render_template_string(LOGIN_HTML, server_name=SERVER_NAME,
                                       error="Invalid VPS ID or token.")
    session['vps_id'] = vps_id
    session['vps_token'] = token
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    vps = require_login()
    if not vps:
        return redirect(url_for('index'))
    status = live_status(vps)
    ports = get_ports_for(vps['container_name'])
    allocated = get_user_allocation(vps['user_id'])
    return render_template_string(
        DASHBOARD_HTML, server_name=SERVER_NAME, vps=vps, status=status,
        ports=ports, allocated=allocated, os_labels=OS_LABELS
    )

@app.route('/api/action', methods=['POST'])
def api_action():
    vps = require_login()
    if not vps:
        return jsonify({"ok": False, "error": "not authenticated"}), 401
    action = request.json.get('action')
    container = vps['container_name']
    try:
        if action == 'start':
            lxc_for_vps(vps, ["start", container])
            set_status(vps['id'], 'running')
        elif action == 'stop':
            lxc_for_vps(vps, ["stop", container, "--force"])
            set_status(vps['id'], 'stopped')
        elif action == 'restart':
            lxc_for_vps(vps, ["restart", container, "--force"])
            set_status(vps['id'], 'running')
        else:
            return jsonify({"ok": False, "error": "unknown action"}), 400
        return jsonify({"ok": True, "status": live_status(vps)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/add-port', methods=['POST'])
def api_add_port():
    vps = require_login()
    if not vps:
        return jsonify({"ok": False, "error": "not authenticated"}), 401
    try:
        vps_port = int(request.json.get('vps_port'))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid port"}), 400
    allocated = get_user_allocation(vps['user_id'])
    used = len(get_ports_for(vps['container_name']))
    if used >= allocated:
        return jsonify({"ok": False, "error": f"Port quota reached ({used}/{allocated}). Ask an admin for more."}), 400
    import random
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT host_port FROM port_forwards')
    used_ports = {r[0] for r in cur.fetchall()}
    host_port = None
    for _ in range(100):
        candidate = random.randint(20000, 50000)
        if candidate not in used_ports:
            host_port = candidate
            break
    if not host_port:
        conn.close()
        return jsonify({"ok": False, "error": "no free host ports"}), 500
    container = vps['container_name']
    try:
        lxc_for_vps(vps, ["config", "device", "add", container, f"tcp_proxy_{host_port}",
                          "proxy", f"listen=tcp:0.0.0.0:{host_port}", f"connect=tcp:127.0.0.1:{vps_port}"])
        lxc_for_vps(vps, ["config", "device", "add", container, f"udp_proxy_{host_port}",
                          "proxy", f"listen=udp:0.0.0.0:{host_port}", f"connect=udp:127.0.0.1:{vps_port}"])
        cur.execute('INSERT INTO port_forwards (user_id, vps_container, vps_port, host_port, created_at) VALUES (?, ?, ?, ?, ?)',
                    (vps['user_id'], container, vps_port, host_port, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "host_port": host_port})
    except Exception as e:
        conn.close()
        return jsonify({"ok": False, "error": str(e)}), 500

# --------------------------------------------------------------------------
# Live terminal: WebSocket <-> `lxc exec <container> -- bash` subprocess.
# Only works for the local node (remote-node terminals would need the node's
# own exec-stream API, which isn't part of this scope).
# --------------------------------------------------------------------------
_terminal_procs = {}  # sid -> subprocess.Popen

@socketio.on('connect', namespace='/terminal')
def term_connect():
    vps = current_vps()
    if not vps:
        disconnect()
        return
    node = get_node(vps['node_id']) or {}
    if not node.get('is_local', 1):
        emit('output', '\r\n[Live terminal is only available for local-node VPS.]\r\n')
        disconnect()
        return
    container = vps['container_name']
    proc = subprocess.Popen(
        ["lxc", "exec", container, "--", "bash"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=0
    )
    _terminal_procs[request.sid] = proc
    socketio.start_background_task(_pump_output, request.sid, proc)

def _pump_output(sid, proc):
    while True:
        chunk = proc.stdout.read(1024)
        if not chunk:
            break
        socketio.emit('output', chunk.decode(errors='replace'), namespace='/terminal', room=sid)
    socketio.emit('output', '\r\n[session ended]\r\n', namespace='/terminal', room=sid)

@socketio.on('input', namespace='/terminal')
def term_input(data):
    proc = _terminal_procs.get(request.sid)
    if proc and proc.stdin:
        try:
            proc.stdin.write(data.encode())
            proc.stdin.flush()
        except Exception:
            pass

@socketio.on('disconnect', namespace='/terminal')
def term_disconnect():
    proc = _terminal_procs.pop(request.sid, None)
    if proc:
        proc.terminate()

# --------------------------------------------------------------------------
# Templates (single-file for simplicity; split into templates/ if this grows)
# --------------------------------------------------------------------------
BASE_CSS = """
:root {
  --bg: #0b0d12; --panel: #12151d; --border: #232733; --text: #e7e9ee;
  --muted: #8b93a7; --accent: #6c5ce7; --green: #2ecc71; --red: #ff5c5c;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif;
}
.wrap { max-width: 960px; margin: 0 auto; padding: 32px 20px; }
.brand {
  font-weight: 800; font-size: 2rem; text-align: center; margin-bottom: 4px;
  background: linear-gradient(90deg, #ff5c5c, #ffb84c, #ffe74c, #7bff6b, #4cc9ff, #a26bff, #ff5c5c);
  background-size: 300% auto;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: rainbow 4s linear infinite;
}
@keyframes rainbow { to { background-position: 300% center; } }
.subtitle { text-align: center; color: var(--muted); margin-bottom: 28px; font-size: .9rem; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 14px;
  padding: 24px; margin-bottom: 18px;
}
label { display: block; font-size: .8rem; color: var(--muted); margin-bottom: 6px; }
input {
  width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: #0d0f16; color: var(--text); margin-bottom: 14px; font-size: .95rem;
}
button {
  border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; cursor: pointer;
  background: var(--accent); color: white; font-size: .9rem;
}
button.secondary { background: #232733; }
button.danger { background: var(--red); }
button:hover { filter: brightness(1.1); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 16px 0; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: .75rem; font-weight: 700; }
.badge.running { background: rgba(46,204,113,.15); color: var(--green); }
.badge.stopped { background: rgba(255,92,92,.15); color: var(--red); }
.badge.unknown { background: rgba(139,147,167,.15); color: var(--muted); }
.row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border); }
.row:last-child { border-bottom: none; }
#term { background: #000; border-radius: 10px; padding: 10px; height: 380px; overflow-y: auto;
  font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: .85rem; white-space: pre-wrap; }
#term-input { width: 100%; margin-top: 10px; }
.error { color: var(--red); font-size: .85rem; margin-bottom: 10px; }
.muted { color: var(--muted); font-size: .8rem; }
a { color: #7bb8ff; }
"""

LOGIN_HTML = """
<!doctype html><html><head><meta charset="utf-8">
<title>{{ server_name }} Panel</title><style>""" + BASE_CSS + """</style></head>
<body><div class="wrap">
  <div class="brand">{{ server_name }}</div>
  <div class="subtitle">VPS Control Panel</div>
  <div class="card" style="max-width:380px;margin:0 auto;">
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" action="/login">
      <label>VPS ID</label>
      <input name="vps_id" placeholder="e.g. 12" required>
      <label>Panel Token</label>
      <input name="token" type="password" placeholder="from your Discord DM" required>
      <button type="submit" style="width:100%">Login</button>
    </form>
    <p class="muted" style="margin-top:14px;">Find your VPS ID and token in the DM you got when your VPS was created.</p>
  </div>
</div></body></html>
"""

DASHBOARD_HTML = """
<!doctype html><html><head><meta charset="utf-8">
<title>{{ server_name }} — {{ vps.container_name }}</title><style>""" + BASE_CSS + """</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
</head><body><div class="wrap">
  <div class="brand">{{ server_name }}</div>
  <div class="subtitle">VPS #{{ vps.id }} — {{ vps.container_name }} &middot; <a href="/logout">Log out</a></div>

  <div class="card">
    <div class="row">
      <div><b>Status</b></div>
      <div><span class="badge {{ status }}" id="status-badge">{{ status }}</span></div>
    </div>
    <div class="row"><div>OS</div><div>{{ os_labels.get(vps.os_version, vps.os_version) }}</div></div>
    <div class="row"><div>Resources</div><div>{{ vps.config }}</div></div>
    {% if vps.static_ip %}<div class="row"><div>Static IP</div><div>{{ vps.static_ip }}</div></div>{% endif %}
    <div class="grid" style="margin-top:16px;">
      <button onclick="doAction('start')">▶ Start</button>
      <button class="secondary" onclick="doAction('stop')">⏹ Stop</button>
      <button class="secondary" onclick="doAction('restart')">🔁 Restart</button>
      <button class="danger" onclick="alert('Reinstall from Discord: use the !manage command so you can pick the OS safely.')">💿 Reinstall</button>
    </div>
  </div>

  <div class="card">
    <b>Port Forwards</b> <span class="muted">({{ ports|length }}/{{ allocated }} used)</span>
    {% for p in ports %}
      <div class="row"><div>VPS port {{ p.vps_port }}</div><div>→ {{ p.host_port }} (host)</div></div>
    {% endfor %}
    <div style="margin-top:14px;display:flex;gap:8px;">
      <input id="new-port" placeholder="Port inside VPS e.g. 25565" style="margin-bottom:0;">
      <button onclick="addPort()">Add</button>
    </div>
  </div>

  <div class="card">
    <b>Live Terminal</b>
    <div id="term"></div>
    <input id="term-input" placeholder="Type a command and press Enter...">
  </div>
</div>

<script>
async function doAction(action) {
  const r = await fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({action})});
  const d = await r.json();
  if (d.ok) {
    const badge = document.getElementById('status-badge');
    badge.textContent = d.status; badge.className = 'badge ' + d.status;
  } else { alert(d.error || 'Action failed'); }
}
async function addPort() {
  const vps_port = document.getElementById('new-port').value;
  const r = await fetch('/api/add-port', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({vps_port})});
  const d = await r.json();
  if (d.ok) { location.reload(); } else { alert(d.error || 'Failed to add port'); }
}

const term = document.getElementById('term');
const input = document.getElementById('term-input');
const socket = io('/terminal');
socket.on('output', (data) => { term.textContent += data; term.scrollTop = term.scrollHeight; });
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { socket.emit('input', input.value + '\\n'); input.value = ''; }
});
</script>
</body></html>
"""

if __name__ == '__main__':
    print(f"[{SERVER_NAME}] Panel starting on 0.0.0.0:{PANEL_PORT}")
    socketio.run(app, host='0.0.0.0', port=PANEL_PORT)
