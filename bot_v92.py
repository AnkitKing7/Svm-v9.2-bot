# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║     ███████╗██╗   ██╗███╗   ███╗    ██╗   ██╗ █████╗ ██████╗     ║
# ║     ██╔════╝██║   ██║████╗ ████║    ██║   ██║██╔══██╗╚════██╗    ║
# ║     ███████╗██║   ██║██╔████╔██║    ██║   ██║╚██████║ █████╔╝    ║
# ║     ╚════██║╚██╗ ██╔╝██║╚██╔╝██║    ╚██╗ ██╔╝ ╚═══██║██╔═══╝     ║
# ║     ███████║ ╚████╔╝ ██║ ╚═╝ ██║     ╚████╔╝ █████╔╝ ███████╗    ║
# ║     ╚══════╝  ╚═══╝  ╚═╝     ╚═╝      ╚═══╝  ╚════╝  ╚══════╝    ║
# ║                                                                  ║
# ║                 SVM VPS v9.2 — Made by AnkitCoder                ║
# ╚══════════════════════════════════════════════════════════════════╝
"""
SVM VPS v9.2 — Advanced LXC/LXD VPS Discord Bot
Features:
  • Custom application emojis (emoji.py + sync_emojis.py auto-sync)
  • VPS create / manage / reinstall / suspend / share
  • Per-user SSH details: Public IPv4 + port-forward, local IP, root password
  • Static IP system for LXC containers (persistent 10.0.3.x addresses)
  • Web Control Panel (login with Discord ID + VPS ID + VPS Token)
      - Live status, Start / Stop / Restart / Reinstall
      - Add Port (IPv4 port forwarding)
      - Live web terminal (websocket → lxc exec)
  • Gemini AI assistant (!ai command)
  • Rainbow console banner
Made by AnkitCoder
"""

import discord
from discord.ext import commands
import asyncio
import subprocess
import json
from datetime import datetime
import shlex
import logging
import shutil
import os
from typing import Optional, List, Dict, Any
import threading
import time
import sqlite3
import random
import requests
import secrets
import string
import re
import sys

# ---- Custom emoji module (synced via sync_emojis.py) ----
try:
    import emoji as E  # emoji.py in the same folder
    HAS_EMOJI_MODULE = True
except Exception:
    E = None
    HAS_EMOJI_MODULE = False

# ---- Web panel deps ----
try:
    from aiohttp import web
    HAS_AIOHTTP = True
except Exception:
    HAS_AIOHTTP = False

# ============================================================================
# CONFIG
# ============================================================================
DISCORD_TOKEN  = os.getenv('DISCORD_TOKEN', '')
BOT_NAME       = os.getenv('BOT_NAME', 'Svm-v9.2')
SERVER_NAME    = os.getenv('SERVER_NAME', 'Svm v9.2')
PREFIX         = os.getenv('PREFIX', '!')
YOUR_SERVER_IP = os.getenv('YOUR_SERVER_IP', '127.0.0.1')
BOT_VERSION    = os.getenv('BOT_VERSION', '9.2-PRO')
BOT_DEVELOPER  = os.getenv('BOT_DEVELOPER', 'AnkitCoder')
PANEL_PORT     = int(os.getenv('PANEL_PORT', '8080'))
PANEL_ENABLED  = os.getenv('PANEL_ENABLED', 'true').lower() == 'true'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AQ.Ab8RN6LubPeK8vHmtoyz8cq_EyBE9fB-RS5S_7ToVhohA3u0fw')
GEMINI_MODEL   = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
STATIC_IP_BASE = os.getenv('STATIC_IP_BASE', '10.0.3')     # lxdbr0 subnet
STATIC_IP_START = int(os.getenv('STATIC_IP_START', '100')) # first assignable host

_cached_public_ip = None

def get_public_ip() -> str:
    """Fetch the server's public IPv4 via ifconfig.me, caching the result."""
    global _cached_public_ip
    if _cached_public_ip:
        return _cached_public_ip
    for url in ("https://ifconfig.me/ip", "https://api.ipify.org", "https://ipv4.icanhazip.com"):
        try:
            resp = requests.get(url, timeout=5)
            ip = resp.text.strip()
            if ip and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                _cached_public_ip = ip
                return ip
        except Exception:
            continue
    return YOUR_SERVER_IP

_raw_main_admin_ids = os.getenv('MAIN_ADMIN_ID', '1405866008127864852')
MAIN_ADMIN_IDS_ENV = [uid.strip() for uid in _raw_main_admin_ids.split(',') if uid.strip()]
MAIN_ADMIN_ID = int(MAIN_ADMIN_IDS_ENV[0])
VPS_USER_ROLE_ID = int(os.getenv('VPS_USER_ROLE_ID', '1210291131301101618'))
DEFAULT_STORAGE_POOL = os.getenv('DEFAULT_STORAGE_POOL', 'default')

OS_OPTIONS = [
    {"label": "Ubuntu 20.04 LTS", "value": "ubuntu:20.04"},
    {"label": "Ubuntu 22.04 LTS", "value": "ubuntu:22.04"},
    {"label": "Ubuntu 24.04 LTS", "value": "ubuntu:24.04"},
    {"label": "Debian 10 (Buster)", "value": "images:debian/10"},
    {"label": "Debian 11 (Bullseye)", "value": "images:debian/11"},
    {"label": "Debian 12 (Bookworm)", "value": "images:debian/12"},
    {"label": "Debian 13 (Trixie)", "value": "images:debian/13"},
]

# ============================================================================
# LOGGING + RAINBOW BANNER
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger('svm_v92_bot')

def _rainbow(text: str) -> str:
    colors = [31, 33, 32, 36, 34, 35]  # red yellow green cyan blue magenta
    out, i = [], 0
    for ch in text:
        if ch.strip():
            out.append(f"\033[1;{colors[i % 6]}m{ch}\033[0m")
            i += 1
        else:
            out.append(ch)
    return ''.join(out)

def print_banner():
    art = [
        r"  ███████╗██╗   ██╗███╗   ███╗    ██╗   ██╗ █████╗       ██████╗ ",
        r"  ██╔════╝██║   ██║████╗ ████║    ██║   ██║██╔══██╗      ╚════██╗",
        r"  ███████╗██║   ██║██╔████╔██║    ██║   ██║╚██████║      █████╔╝",
        r"  ╚════██║╚██╗ ██╔╝██║╚██╔╝██║    ╚██╗ ██╔╝ ╚═══██║      ██╔═══╝ ",
        r"  ███████║ ╚████╔╝ ██║ ╚═╝ ██║     ╚████╔╝ █████╔╝ ██╗  ███████╗",
        r"  ╚══════╝  ╚═══╝  ╚═╝     ╚═╝      ╚═══╝  ╚════╝  ╚═╝  ╚══════╝",
    ]
    print()
    for line in art:
        print(_rainbow(line))
    print(_rainbow(f"\n        >>> {SERVER_NAME} — Advanced VPS Manager v{BOT_VERSION} <<<"))
    print(_rainbow(f"        >>> Made by {BOT_DEVELOPER} <<<\n"))

# ============================================================================
# DATABASE
# ============================================================================
def get_db():
    conn = sqlite3.connect('vps.db')
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_vps_token() -> str:
    """Secure token for the web control panel."""
    return "SVM-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(20))

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)')
    cur.execute('CREATE TABLE IF NOT EXISTS main_admins (user_id TEXT PRIMARY KEY)')
    for uid in MAIN_ADMIN_IDS_ENV:
        cur.execute('INSERT OR IGNORE INTO main_admins (user_id) VALUES (?)', (uid,))
    cur.execute('''CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        location TEXT, total_vps INTEGER, tags TEXT DEFAULT '[]',
        api_key TEXT, url TEXT, is_local INTEGER DEFAULT 0)''')
    cur.execute('SELECT COUNT(*) FROM nodes WHERE is_local = 1')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO nodes (name, location, total_vps, tags, api_key, url, is_local) VALUES (?,?,?,?,?,?,?)',
                    ('Local Node', 'Local', 100, '[]', None, None, 1))
    cur.execute('''CREATE TABLE IF NOT EXISTS vps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, node_id INTEGER NOT NULL DEFAULT 1,
        container_name TEXT UNIQUE NOT NULL, ram TEXT NOT NULL, cpu TEXT NOT NULL,
        storage TEXT NOT NULL, config TEXT NOT NULL,
        os_version TEXT DEFAULT 'ubuntu:22.04', status TEXT DEFAULT 'stopped',
        suspended INTEGER DEFAULT 0, whitelisted INTEGER DEFAULT 0,
        created_at TEXT NOT NULL, shared_with TEXT DEFAULT '[]',
        suspension_history TEXT DEFAULT '[]', root_password TEXT DEFAULT '',
        pinggy_address TEXT, vps_token TEXT DEFAULT '', static_ip TEXT DEFAULT '')''')
    # --- Migrations ---
    cur.execute('PRAGMA table_info(vps)')
    columns = [col[1] for col in cur.fetchall()]
    if 'os_version' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN os_version TEXT DEFAULT 'ubuntu:22.04'")
    if 'node_id' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN node_id INTEGER DEFAULT 1")
    if 'root_password' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN root_password TEXT DEFAULT ''")
    if 'pinggy_address' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN pinggy_address TEXT")
    if 'vps_token' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN vps_token TEXT DEFAULT ''")
    if 'static_ip' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN static_ip TEXT DEFAULT ''")
    # Backfill tokens for existing VPS
    cur.execute("SELECT id FROM vps WHERE vps_token IS NULL OR vps_token = ''")
    for row in cur.fetchall():
        cur.execute("UPDATE vps SET vps_token = ? WHERE id = ?", (generate_vps_token(), row[0]))
    cur.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    for key, value in [('cpu_threshold', '90'), ('ram_threshold', '90')]:
        cur.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
    cur.execute('CREATE TABLE IF NOT EXISTS port_allocations (user_id TEXT PRIMARY KEY, allocated_ports INTEGER DEFAULT 0)')
    cur.execute('''CREATE TABLE IF NOT EXISTS port_forwards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
        vps_container TEXT NOT NULL, vps_port INTEGER NOT NULL,
        host_port INTEGER NOT NULL, created_at TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def get_setting(key: str, default: Any = None):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cur.fetchone(); conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit(); conn.close()

def get_nodes() -> List[Dict]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM nodes'); rows = cur.fetchall(); conn.close()
    nodes = [dict(row) for row in rows]
    for node in nodes:
        node['tags'] = json.loads(node['tags'])
    return nodes

def get_node(node_id: int) -> Optional[Dict]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM nodes WHERE id = ?', (node_id,))
    row = cur.fetchone(); conn.close()
    if row:
        node = dict(row); node['tags'] = json.loads(node['tags']); return node
    return None

def get_current_vps_count(node_id: int) -> int:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM vps WHERE node_id = ?', (node_id,))
    count = cur.fetchone()[0]; conn.close()
    return count

def get_vps_data() -> Dict[str, List[Dict[str, Any]]]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM vps'); rows = cur.fetchall(); conn.close()
    data = {}
    for row in rows:
        user_id = row['user_id']
        data.setdefault(user_id, [])
        vps = dict(row)
        vps['shared_with'] = json.loads(vps['shared_with'])
        vps['suspension_history'] = json.loads(vps['suspension_history'])
        vps['suspended'] = bool(vps['suspended'])
        vps['whitelisted'] = bool(vps['whitelisted'])
        vps['os_version'] = vps.get('os_version', 'ubuntu:22.04')
        data[user_id].append(vps)
    return data

def get_admins() -> List[str]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT user_id FROM admins'); rows = cur.fetchall(); conn.close()
    return [row['user_id'] for row in rows]

def get_main_admins() -> List[str]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT user_id FROM main_admins'); rows = cur.fetchall(); conn.close()
    ids = [row['user_id'] for row in rows]
    return ids if ids else [str(MAIN_ADMIN_ID)]

def save_main_admins():
    conn = get_db(); cur = conn.cursor()
    cur.execute('DELETE FROM main_admins')
    for uid in main_admin_ids:
        cur.execute('INSERT INTO main_admins (user_id) VALUES (?)', (uid,))
    conn.commit(); conn.close()

def save_vps_data():
    conn = get_db(); cur = conn.cursor()
    for user_id, vps_list in vps_data.items():
        for vps in vps_list:
            shared_json = json.dumps(vps['shared_with'])
            history_json = json.dumps(vps['suspension_history'])
            suspended_int = 1 if vps['suspended'] else 0
            whitelisted_int = 1 if vps.get('whitelisted', False) else 0
            os_ver = vps.get('os_version', 'ubuntu:22.04')
            created_at = vps.get('created_at', datetime.now().isoformat())
            node_id = vps.get('node_id', 1)
            root_password = vps.get('root_password', '')
            pinggy = vps.get('pinggy_address')
            token = vps.get('vps_token') or generate_vps_token()
            vps['vps_token'] = token
            static_ip = vps.get('static_ip', '')
            if 'id' not in vps or vps['id'] is None:
                cur.execute('''INSERT INTO vps (user_id, node_id, container_name, ram, cpu, storage, config,
                    os_version, status, suspended, whitelisted, created_at, shared_with, suspension_history,
                    root_password, pinggy_address, vps_token, static_ip)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (user_id, node_id, vps['container_name'], vps['ram'], vps['cpu'], vps['storage'], vps['config'],
                     os_ver, vps['status'], suspended_int, whitelisted_int, created_at, shared_json,
                     history_json, root_password, pinggy, token, static_ip))
                vps['id'] = cur.lastrowid
            else:
                cur.execute('''UPDATE vps SET user_id=?, node_id=?, container_name=?, ram=?, cpu=?, storage=?, config=?,
                    os_version=?, status=?, suspended=?, whitelisted=?, shared_with=?, suspension_history=?,
                    root_password=?, pinggy_address=?, vps_token=?, static_ip=? WHERE id=?''',
                    (user_id, node_id, vps['container_name'], vps['ram'], vps['cpu'], vps['storage'], vps['config'],
                     os_ver, vps['status'], suspended_int, whitelisted_int, shared_json, history_json,
                     root_password, pinggy, token, static_ip, vps['id']))
    conn.commit(); conn.close()

def save_admin_data():
    conn = get_db(); cur = conn.cursor()
    cur.execute('DELETE FROM admins')
    for admin_id in admin_data['admins']:
        cur.execute('INSERT INTO admins (user_id) VALUES (?)', (admin_id,))
    conn.commit(); conn.close()

def find_vps_by_id(vps_id: int) -> Optional[tuple]:
    """Return (owner_user_id, vps_dict) for a numeric VPS DB id."""
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM vps WHERE id = ?', (vps_id,))
    row = cur.fetchone(); conn.close()
    if not row:
        return None
    vps = dict(row)
    vps['shared_with'] = json.loads(vps['shared_with'])
    vps['suspension_history'] = json.loads(vps['suspension_history'])
    vps['suspended'] = bool(vps['suspended']); vps['whitelisted'] = bool(vps['whitelisted'])
    return vps['user_id'], vps

# ============================================================================
# PORT FORWARDING (IPv4)
# ============================================================================
def get_user_allocation(user_id: str) -> int:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT allocated_ports FROM port_allocations WHERE user_id = ?', (user_id,))
    row = cur.fetchone(); conn.close()
    return row[0] if row else 0

def get_user_used_ports(user_id: str) -> int:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM port_forwards WHERE user_id = ?', (user_id,))
    row = cur.fetchone(); conn.close()
    return row[0]

def allocate_ports(user_id: str, amount: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO port_allocations (user_id, allocated_ports) VALUES (?, COALESCE((SELECT allocated_ports FROM port_allocations WHERE user_id = ?), 0) + ?)', (user_id, user_id, amount))
    conn.commit(); conn.close()

def deallocate_ports(user_id: str, amount: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute('UPDATE port_allocations SET allocated_ports = MAX(0, allocated_ports - ?) WHERE user_id = ?', (amount, user_id))
    conn.commit(); conn.close()

def get_available_host_port(node_id: int) -> Optional[int]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT host_port FROM port_forwards WHERE vps_container IN (SELECT container_name FROM vps WHERE node_id = ?)', (node_id,))
    used_ports = set(row[0] for row in cur.fetchall()); conn.close()
    for _ in range(100):
        port = random.randint(20000, 50000)
        if port not in used_ports:
            return port
    return None

async def create_port_forward(user_id: str, container: str, vps_port: int, node_id: int) -> Optional[int]:
    """Forward a VPS port to a random host port on the public IPv4 (TCP+UDP)."""
    host_port = get_available_host_port(node_id)
    if not host_port:
        return None
    try:
        await execute_lxc(container, f"config device add {container} tcp_proxy_{host_port} proxy listen=tcp:0.0.0.0:{host_port} connect=tcp:127.0.0.1:{vps_port}", node_id=node_id)
        await execute_lxc(container, f"config device add {container} udp_proxy_{host_port} proxy listen=udp:0.0.0.0:{host_port} connect=udp:127.0.0.1:{vps_port}", node_id=node_id)
        conn = get_db(); cur = conn.cursor()
        cur.execute('INSERT INTO port_forwards (user_id, vps_container, vps_port, host_port, created_at) VALUES (?,?,?,?,?)',
                    (user_id, container, vps_port, host_port, datetime.now().isoformat()))
        conn.commit(); conn.close()
        return host_port
    except Exception as e:
        logger.error(f"Failed to create port forward: {e}")
        return None

async def remove_port_forward(forward_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT user_id, vps_container, host_port FROM port_forwards WHERE id = ?', (forward_id,))
    row = cur.fetchone()
    if not row:
        conn.close(); return False, None
    user_id, container, host_port = row
    node_id = find_node_id_for_container(container)
    try:
        await execute_lxc(container, f"config device remove {container} tcp_proxy_{host_port}", node_id=node_id)
        await execute_lxc(container, f"config device remove {container} udp_proxy_{host_port}", node_id=node_id)
        cur.execute('DELETE FROM port_forwards WHERE id = ?', (forward_id,))
        conn.commit(); conn.close()
        return True, user_id
    except Exception as e:
        logger.error(f"Failed to remove port forward {forward_id}: {e}")
        conn.close(); return False, None

def get_user_forwards(user_id: str) -> List[Dict]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM port_forwards WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    rows = cur.fetchall(); conn.close()
    return [dict(row) for row in rows]

def get_vps_forwards(container: str) -> List[Dict]:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM port_forwards WHERE vps_container = ? ORDER BY created_at DESC', (container,))
    rows = cur.fetchall(); conn.close()
    return [dict(row) for row in rows]

async def recreate_port_forwards(container_name: str) -> int:
    node_id = find_node_id_for_container(container_name)
    readded = 0
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT vps_port, host_port FROM port_forwards WHERE vps_container = ?', (container_name,))
    rows = cur.fetchall()
    for row in rows:
        try:
            await execute_lxc(container_name, f"config device add {container_name} tcp_proxy_{row['host_port']} proxy listen=tcp:0.0.0.0:{row['host_port']} connect=tcp:127.0.0.1:{row['vps_port']}", node_id=node_id)
            await execute_lxc(container_name, f"config device add {container_name} udp_proxy_{row['host_port']} proxy listen=udp:0.0.0.0:{row['host_port']} connect=udp:127.0.0.1:{row['vps_port']}", node_id=node_id)
            readded += 1
        except Exception as e:
            logger.error(f"Re-add port forward failed for {container_name}: {e}")
    conn.close()
    return readded

def find_node_id_for_container(container_name: str) -> int:
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT node_id FROM vps WHERE container_name = ?', (container_name,))
    row = cur.fetchone(); conn.close()
    return row[0] if row else 1

# ============================================================================
# STATIC IP SYSTEM (LXC bridged networking)
# ============================================================================
def allocate_static_ip() -> str:
    """Pick the next free static IP inside the lxdbr0 subnet."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT static_ip FROM vps WHERE static_ip != ''")
    used = set(r[0] for r in cur.fetchall()); conn.close()
    host = STATIC_IP_START
    while host < 250:
        ip = f"{STATIC_IP_BASE}.{host}"
        if ip not in used:
            return ip
        host += 1
    return f"{STATIC_IP_BASE}.{random.randint(100, 250)}"

async def apply_static_ip(container_name: str, static_ip: str, node_id: int):
    """Pin a static IPv4 on the container's eth0 (works on lxdbr0 managed bridge)."""
    try:
        await execute_lxc(container_name, f"config device override {container_name} eth0 ipv4.address={static_ip}", node_id=node_id)
        logger.info(f"Static IP {static_ip} pinned to {container_name}")
    except Exception as e:
        logger.warning(f"Static IP override failed ({container_name}): {e} — container will use DHCP")

async def get_container_ip(container_name: str, node_id: int) -> str:
    """Read the live local IPv4 of a container."""
    try:
        out = await execute_lxc(container_name, f"list {container_name} -c4 --format csv", node_id=node_id)
        if isinstance(out, str):
            m = re.search(r'(\d+\.\d+\.\d+\.\d+)', out)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "N/A"

# Initialize database + load state
init_db()
vps_data = get_vps_data()
admin_data = {'admins': get_admins()}
main_admin_ids = set(get_main_admins())
CPU_THRESHOLD = int(get_setting('cpu_threshold', 90))
RAM_THRESHOLD = int(get_setting('ram_threshold', 90))

# ============================================================================
# BOT SETUP
# ============================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
resource_monitor_active = True

# ---- Emoji helpers (custom emojis with graceful unicode fallback) ----
def em(name: str, fallback: str = "") -> str:
    if HAS_EMOJI_MODULE:
        return getattr(E, name, fallback) or fallback
    return fallback

E_TICK    = em('TICK', '✅')
E_CROSS   = em('CROSS', '❌')
E_WARN    = em('WARNING', '⚠️')
E_LOAD    = em('LOADING', '⏳')
E_PC      = em('PC', '🖥️')
E_LOCK    = em('LOCK', '🔒')
E_UNLOCK  = em('UNLOCK', '🔓')
E_ROCKET  = em('ZROCKET', '🚀')
E_GEAR    = em('ZSETTINGS', '⚙️')
E_WIFI    = em('WIFI', '📶')
E_LINK    = em('ZYROXLINKS', '🔗')
E_TIME    = em('TIME', '⏱️')
E_UPTIME  = em('UPTIME', '⏱️')
E_STAR    = em('STAR', '⭐')
E_CROWN   = em('BLACKCROWN', '👑')
E_SYSTEM  = em('SYSTEM', '🖥️')
E_CLOUD   = em('ZCLOUD', '☁️')
E_PEOPLE  = em('ZPEOPLE', '👥')
E_ONLINE  = em('ONLINE', '🟢')
E_OFFLINE = em('OFFLINE', '🔴')
E_PLUS    = em('ZPLUS', '➕')
E_WRENCH  = em('ZWRENCH', '🔧')
E_TADA    = em('TADAA', '🎉')
E_KEY     = em('LOCK', '🔑')
E_TERMINAL= em('CODEBASE', '💻')

def truncate_text(text, max_length=1024):
    if not text:
        return text
    return text if len(text) <= max_length else text[:max_length-3] + "..."

THUMB_URL = "https://cdn.discordapp.com/attachments/1472508478789648446/1538220451363422208/1779656037142_0.png"

def create_embed(title, description="", color=0x1a1a1a):
    embed = discord.Embed(title=truncate_text(f"{E_STAR} {BOT_NAME} • {title}", 256),
                          description=truncate_text(description, 4096), color=color)
    embed.set_thumbnail(url=THUMB_URL)
    embed.set_footer(text=f"{BOT_NAME} VPS Manager v{BOT_VERSION} • Made by {BOT_DEVELOPER} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                     icon_url=THUMB_URL)
    return embed

def add_field(embed, name, value, inline=False):
    embed.add_field(name=truncate_text(f"▸ {name}", 256), value=truncate_text(value, 1024), inline=inline)
    return embed

def create_success_embed(title, description=""):
    return create_embed(f"{E_TICK} {title}", description, color=0x00ff88)

def create_error_embed(title, description=""):
    return create_embed(f"{E_CROSS} {title}", description, color=0xff3366)

def create_info_embed(title, description=""):
    return create_embed(f"{E_SYSTEM} {title}", description, color=0x00ccff)

def create_warning_embed(title, description=""):
    return create_embed(f"{E_WARN} {title}", description, color=0xffaa00)

# ============================================================================
# ADMIN CHECKS
# ============================================================================
def is_admin():
    async def predicate(ctx):
        user_id = str(ctx.author.id)
        if user_id in main_admin_ids or user_id in admin_data.get("admins", []):
            return True
        raise commands.CheckFailure("You need admin permissions to use this command. Contact support.")
    return commands.check(predicate)

def is_main_admin():
    async def predicate(ctx):
        if str(ctx.author.id) in main_admin_ids:
            return True
        raise commands.CheckFailure("Only the main admin can use this command.")
    return commands.check(predicate)
# ============================================================================
# LXC EXECUTION (multi-node)
# ============================================================================
async def execute_lxc(container_name: str, command: str, timeout=120, node_id: Optional[int] = None):
    if node_id is None:
        node_id = find_node_id_for_container(container_name)
    node = get_node(node_id)
    if not node:
        raise Exception(f"Node {node_id} not found")
    full_command = f"lxc {command}"
    if node['is_local']:
        try:
            cmd = shlex.split(full_command)
            proc = await asyncio.create_subprocess_exec(*cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill(); await proc.wait()
                raise asyncio.TimeoutError(f"Command timed out after {timeout}s")
            if proc.returncode != 0:
                error = stderr.decode().strip() if stderr else "Command failed"
                raise Exception(f"LXC failed: {error}\nCommand: {full_command}")
            return stdout.decode().strip() if stdout else True
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"LXC Error: {full_command} - {e}")
            raise
    else:
        url = f"{node['url']}/api/execute"
        try:
            response = requests.post(url, json={"command": full_command},
                                     params={"api_key": node["api_key"]}, timeout=timeout)
            response.raise_for_status()
            res = response.json()
            if res.get("returncode", 1) != 0:
                raise Exception(f"Remote LXC failed on {node['name']}: {res.get('stderr', 'failed')}")
            return res.get("stdout", True)
        except requests.exceptions.RequestException as e:
            raise Exception(f"Remote execution failed on {node['name']}: {e}")

async def safe_start_container(container_name: str, node_id: int):
    try:
        await execute_lxc(container_name, f"start {container_name}", node_id=node_id)
    except Exception as e:
        if "already running" in str(e).lower() or "is running" in str(e).lower():
            logger.info(f"{container_name} already running; ok.")
        else:
            raise

async def apply_lxc_config(container_name: str, node_id: int):
    try:
        await execute_lxc(container_name, f"config set {container_name} security.nesting true", node_id=node_id)
        await execute_lxc(container_name, f"config set {container_name} security.privileged true", node_id=node_id)
        await execute_lxc(container_name, f"config set {container_name} security.syscalls.intercept.mknod true", node_id=node_id)
        await execute_lxc(container_name, f"config set {container_name} security.syscalls.intercept.setxattr true", node_id=node_id)
        await execute_lxc(container_name, f"config set {container_name} linux.kernel_modules overlay,loop,nf_nat,ip_tables,ip6_tables,netlink_diag,br_netfilter", node_id=node_id)
        try:
            await execute_lxc(container_name, f"config device add {container_name} fuse unix-char path=/dev/fuse", node_id=node_id)
        except Exception:
            pass
        raw = ("lxc.apparmor.profile = unconfined\nlxc.apparmor.allow_nesting = 1\n"
               "lxc.apparmor.allow_incomplete = 1\nlxc.cap.drop =\n"
               "lxc.cgroup.devices.allow = a\nlxc.cgroup2.devices.allow = a\n"
               "lxc.mount.auto = proc:rw sys:rw cgroup:rw shmounts:rw\n"
               "lxc.mount.entry = /dev/fuse dev/fuse none bind,create=file 0 0\n")
        await execute_lxc(container_name, f"config set {container_name} raw.lxc '{raw}'", node_id=node_id)
    except Exception as e:
        logger.error(f"apply_lxc_config failed for {container_name}: {e}")

async def apply_internal_permissions(container_name: str, node_id: int):
    try:
        await asyncio.sleep(8)
        cmds = ["mkdir -p /etc/sysctl.d/",
                "echo 'net.ipv4.ip_unprivileged_port_start=0' > /etc/sysctl.d/99-custom.conf",
                "echo 'net.ipv4.ping_group_range=0 2147483647' >> /etc/sysctl.d/99-custom.conf",
                "echo 'fs.inotify.max_user_watches=524288' >> /etc/sysctl.d/99-custom.conf",
                "echo 'kernel.unprivileged_userns_clone=1' >> /etc/sysctl.d/99-custom.conf",
                "sysctl -p /etc/sysctl.d/99-custom.conf || true"]
        for cmd in cmds:
            try:
                await execute_lxc(container_name, f'exec {container_name} -- bash -c "{cmd}"', node_id=node_id)
            except Exception as ce:
                logger.warning(f"cmd failed in {container_name}: {cmd} - {ce}")
    except Exception as e:
        logger.error(f"apply_internal_permissions failed: {e}")

async def setup_ssh_access(container_name: str, node_id: int) -> str:
    """Install openssh-server, set root password, enable password root login."""
    password = generate_password()
    cmds = ["DEBIAN_FRONTEND=noninteractive apt-get update -y",
            "DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server",
            f"echo 'root:{password}' | chpasswd",
            "printf 'PermitRootLogin yes\\nPasswordAuthentication yes\\n' >> /etc/ssh/sshd_config",
            "mkdir -p /run/sshd",
            "systemctl enable ssh 2>/dev/null || systemctl enable sshd 2>/dev/null || true",
            "systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || service ssh restart 2>/dev/null || true"]
    for cmd in cmds:
        try:
            await execute_lxc(container_name, f'exec {container_name} -- bash -c "{cmd}"', node_id=node_id, timeout=180)
        except Exception as ce:
            logger.warning(f"SSH setup cmd failed in {container_name}: {ce}")
    return password

# ============================================================================
# PINGGY TUNNEL (backup SSH access)
# ============================================================================
PINGGY_LOG_PATH = "/root/.pinggy_tunnel.log"

def parse_pinggy_address(log_text: str) -> Optional[str]:
    if not log_text:
        return None
    m = re.search(r'tcp://([\w\.\-]+):(\d+)', log_text, re.IGNORECASE)
    return f"{m.group(1)}:{m.group(2)}" if m else None

async def establish_pinggy_tunnel(container_name: str, node_id: int, retries: int = 4, wait_seconds: int = 5) -> Optional[str]:
    try:
        await execute_lxc(container_name,
            f'exec {container_name} -- bash -c "command -v ssh >/dev/null || (DEBIAN_FRONTEND=noninteractive apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-client)"',
            node_id=node_id, timeout=180)
    except Exception as e:
        logger.warning(f"Pinggy ssh client check failed: {e}")
    try:
        await execute_lxc(container_name,
            f"exec {container_name} -- bash -c \"pkill -f 'free.pinggy.io' >/dev/null 2>&1; rm -f {PINGGY_LOG_PATH}\"",
            node_id=node_id)
    except Exception:
        pass
    tunnel_cmd = ("setsid nohup ssh -p 443 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                  f"-o ServerAliveInterval=30 -R0:localhost:22 qr+tcp@free.pinggy.io > {PINGGY_LOG_PATH} 2>&1 < /dev/null & disown")
    try:
        await execute_lxc(container_name, f'exec {container_name} -- bash -c "{tunnel_cmd}"', node_id=node_id)
    except Exception as e:
        logger.error(f"Pinggy start failed in {container_name}: {e}")
        return None
    for _ in range(retries):
        await asyncio.sleep(wait_seconds)
        try:
            log_output = await execute_lxc(container_name, f"exec {container_name} -- cat {PINGGY_LOG_PATH}", node_id=node_id)
        except Exception:
            log_output = ""
        address = parse_pinggy_address(log_output if isinstance(log_output, str) else "")
        if address:
            return address
    return None

# ============================================================================
# ROLE / HOST STATS / MONITOR
# ============================================================================
async def get_or_create_vps_role(guild):
    global VPS_USER_ROLE_ID
    me = guild.me
    if not me or not me.guild_permissions.manage_roles:
        return None
    role_name = f"{BOT_NAME} VPS User"
    if VPS_USER_ROLE_ID:
        role = guild.get_role(VPS_USER_ROLE_ID)
        if role and role < me.top_role:
            return role
        VPS_USER_ROLE_ID = None
    role = discord.utils.get(guild.roles, name=role_name)
    if role and role < me.top_role:
        VPS_USER_ROLE_ID = role.id
        return role
    try:
        role = await guild.create_role(name=role_name, color=discord.Color.dark_purple(),
                                       permissions=discord.Permissions.none(), reason=f"{BOT_NAME} VPS User role")
        await role.edit(position=me.top_role.position - 1)
        VPS_USER_ROLE_ID = role.id
        return role
    except Exception as e:
        logger.error(f"Failed to create VPS role: {e}")
        return None

def get_host_cpu_usage():
    try:
        result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if '%Cpu(s):' in line:
                p = line.split()
                return float(p[1]) + float(p[3]) + float(p[5]) + float(p[9]) + float(p[11]) + float(p[13])
        return 0.0
    except Exception:
        return 0.0

def get_host_ram_usage():
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        if len(lines) > 1:
            mem = lines[1].split()
            return (int(mem[2]) / int(mem[1]) * 100) if int(mem[1]) > 0 else 0.0
        return 0.0
    except Exception:
        return 0.0

def get_host_disk_usage():
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        if len(lines) > 1:
            p = lines[1].split()
            return f"{p[2]}/{p[1]} ({p[4]})"
        return "Unknown"
    except Exception:
        return "Unknown"

async def get_host_stats(node_id: int) -> Dict:
    node = get_node(node_id)
    if node['is_local']:
        return {"cpu": get_host_cpu_usage(), "ram": get_host_ram_usage(), "disk": get_host_disk_usage()}
    try:
        r = requests.get(f"{node['url']}/api/get_host_stats", params={"api_key": node["api_key"]}, timeout=10)
        r.raise_for_status()
        stats = r.json(); stats['disk'] = stats.get('disk', 'Unknown')
        return stats
    except Exception:
        return {"cpu": 0.0, "ram": 0.0, "disk": "Unknown"}

def resource_monitor():
    global resource_monitor_active
    last_backup = time.time()
    while resource_monitor_active:
        try:
            for node in get_nodes():
                stats = asyncio.run(get_host_stats(node['id']))
                logger.info(f"Node {node['name']}: CPU {stats['cpu']:.1f}%, RAM {stats['ram']:.1f}%")
                if stats['cpu'] > CPU_THRESHOLD or stats['ram'] > RAM_THRESHOLD:
                    logger.warning(f"Node {node['name']} exceeded thresholds!")
            if time.time() - last_backup > 3600:
                backup = f"vps_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                try:
                    shutil.copy('vps.db', backup)
                    last_backup = time.time()
                except Exception as e:
                    logger.error(f"DB backup failed: {e}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(60)

threading.Thread(target=resource_monitor, daemon=True).start()

# ============================================================================
# CONTAINER STATS
# ============================================================================
async def get_container_stats(container_name: str, node_id: Optional[int] = None) -> Dict:
    if node_id is None:
        node_id = find_node_id_for_container(container_name)
    node = get_node(node_id)
    if node['is_local']:
        return {"status": await _c_status(container_name), "cpu": await _c_cpu(container_name),
                "ram": await _c_ram(container_name), "disk": await _c_disk(container_name),
                "uptime": await _c_uptime(container_name)}
    try:
        r = requests.post(f"{node['url']}/api/get_container_stats", json={"container": container_name},
                          params={"api_key": node["api_key"]}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"status": "unknown", "cpu": 0.0, "ram": {"used": 0, "total": 0, "pct": 0.0},
                "disk": "Unknown", "uptime": "Unknown"}

async def _run_local(*args):
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    return stdout.decode()

async def _c_status(c):
    try:
        out = await _run_local("lxc", "info", c)
        for line in out.splitlines():
            if line.startswith("Status: "):
                return line.split(": ", 1)[1].strip().lower()
        return "unknown"
    except Exception:
        return "unknown"

async def _c_cpu(c):
    try:
        out = await _run_local("lxc", "exec", c, "--", "top", "-bn1")
        for line in out.splitlines():
            if '%Cpu(s):' in line:
                p = line.split()
                return float(p[1]) + float(p[3]) + float(p[5]) + float(p[9]) + float(p[11]) + float(p[13])
        return 0.0
    except Exception:
        return 0.0

async def _c_ram(c):
    try:
        out = await _run_local("lxc", "exec", c, "--", "free", "-m")
        lines = out.splitlines()
        if len(lines) > 1:
            p = lines[1].split()
            total, used = int(p[1]), int(p[2])
            return {'used': used, 'total': total, 'pct': (used / total * 100) if total else 0.0}
        return {'used': 0, 'total': 0, 'pct': 0.0}
    except Exception:
        return {'used': 0, 'total': 0, 'pct': 0.0}

async def _c_disk(c):
    try:
        out = await _run_local("lxc", "exec", c, "--", "df", "-h", "/")
        for line in out.splitlines():
            if '/dev/' in line and ' /' in line:
                p = line.split()
                if len(p) >= 5:
                    return f"{p[2]}/{p[1]} ({p[4]})"
        return "Unknown"
    except Exception:
        return "Unknown"

async def _c_uptime(c):
    try:
        out = await _run_local("lxc", "exec", c, "--", "uptime")
        return out.strip() if out else "Unknown"
    except Exception:
        return "Unknown"

def get_default_storage_pool():
    try:
        result = subprocess.run(['lxc', 'storage', 'list', '--format', 'csv'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if lines and lines[0]:
            return lines[0].split(',')[0]
    except Exception:
        pass
    return "default"

DEFAULT_STORAGE_POOL = os.getenv('DEFAULT_STORAGE_POOL', get_default_storage_pool())

def get_uptime():
    try:
        return subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "Unknown"

def progress_bar(pct: float, length: int = 12) -> str:
    filled = max(0, min(length, int(pct / 100 * length)))
    return '█' * filled + '░' * (length - filled)

# ============================================================================
# SHARED VPS DEPLOY ROUTINE (used by create + reinstall)
# ============================================================================
async def deploy_container(container_name: str, os_version: str, ram_gb: int, cpu: int,
                           disk_gb: int, node_id: int) -> tuple:
    """Create container, apply config, static IP, SSH. Returns (root_password, pinggy_address, static_ip)."""
    ram_mb = ram_gb * 1024
    await execute_lxc(container_name, f"init {os_version} {container_name} -s {DEFAULT_STORAGE_POOL}", node_id=node_id)
    await execute_lxc(container_name, f"config set {container_name} limits.memory {ram_mb}MB", node_id=node_id)
    await execute_lxc(container_name, f"config set {container_name} limits.cpu {cpu}", node_id=node_id)
    await execute_lxc(container_name, f"config device set {container_name} root size={disk_gb}GB", node_id=node_id)
    await apply_lxc_config(container_name, node_id)
    static_ip = allocate_static_ip()
    await apply_static_ip(container_name, static_ip, node_id)
    await safe_start_container(container_name, node_id)
    await apply_internal_permissions(container_name, node_id)
    root_password = await setup_ssh_access(container_name, node_id)
    pinggy_address = await establish_pinggy_tunnel(container_name, node_id)
    return root_password, pinggy_address, static_ip

def build_ssh_dm_fields(embed, vps: dict, vps_id: int):
    """Standard SSH/panel detail fields used in DM notifications."""
    public_ip = get_public_ip()
    static_ip = vps.get('static_ip') or 'DHCP'
    pinggy = vps.get('pinggy_address')
    add_field(embed, f"{E_PC} VPS Details",
              f"**VPS ID:** `#{vps_id}`\n**Container:** `{vps['container_name']}`\n"
              f"**Config:** {vps.get('config', 'Custom')}\n**OS:** {vps.get('os_version', 'ubuntu:22.04')}\n"
              f"**Status:** {E_ONLINE} Running", False)
    if pinggy:
        host, port = pinggy.split(":")
        add_field(embed, f"{E_KEY} SSH Login (Public)",
                  f"**Host:** `{host}`\n**Port:** `{port}`\n**User:** `root`\n"
                  f"**Password:** `{vps.get('root_password', '')}`\n```ssh root@{host} -p {port}```", False)
    else:
        add_field(embed, f"{E_KEY} SSH Login",
                  f"**Local IP:** `{static_ip}`\n**User:** `root`\n**Password:** `{vps.get('root_password', '')}`\n"
                  f"```ssh root@{static_ip}```\n⚠️ Public tunnel failed — use `{PREFIX}manage` → Reconnect Tunnel.", False)
    add_field(embed, f"{E_WIFI} Network",
              f"**Server IPv4:** `{public_ip}`\n**Local IP (static):** `{static_ip}`\n"
              f"Use **Add Port** to forward ports on the public IPv4.", False)
    add_field(embed, f"{E_LINK} Web Control Panel",
              f"**Panel:** `http://{public_ip}:{PANEL_PORT}`\n"
              f"**VPS ID:** `#{vps_id}`\n**VPS Token:** `{vps.get('vps_token', '')}`\n"
              f"Login with your **Discord ID + VPS ID + Token** for live status, "
              f"Start/Stop/Restart/Reinstall, ports & live terminal.", False)
# ============================================================================
# DISCORD UI — VIEWS
# ============================================================================
class NodeSelectView(discord.ui.View):
    def __init__(self, ram: int, cpu: int, disk: int, user: discord.Member, ctx):
        super().__init__(timeout=300)
        self.ram, self.cpu, self.disk, self.user, self.ctx = ram, cpu, disk, user, ctx
        options = []
        for n in get_nodes():
            current = get_current_vps_count(n['id'])
            if current < n['total_vps']:
                options.append(discord.SelectOption(label=n['name'], value=str(n['id']),
                               description=f"{n['location']} - Available: {n['total_vps'] - current}"))
        if not options:
            self.add_item(discord.ui.Select(placeholder="No available nodes", disabled=True))
        else:
            self.select = discord.ui.Select(placeholder=f"{E_CLOUD} Select a Node", options=options)
            self.select.callback = self.select_node
            self.add_item(self.select)

    async def select_node(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.ctx.author.id):
            await interaction.response.send_message(embed=create_error_embed("Access Denied", "Only the command author can select."), ephemeral=True)
            return
        node_id = int(self.select.values[0])
        self.select.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=create_info_embed("Select OS", "Choose the OS for the VPS."),
                                        view=OSSelectView(self.ram, self.cpu, self.disk, self.user, self.ctx, node_id))

class OSSelectView(discord.ui.View):
    def __init__(self, ram, cpu, disk, user, ctx, node_id):
        super().__init__(timeout=300)
        self.ram, self.cpu, self.disk, self.user, self.ctx, self.node_id = ram, cpu, disk, user, ctx, node_id
        self.select = discord.ui.Select(placeholder="Select an OS",
            options=[discord.SelectOption(label=o["label"], value=o["value"]) for o in OS_OPTIONS])
        self.select.callback = self.select_os
        self.add_item(self.select)

    async def select_os(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.ctx.author.id):
            await interaction.response.send_message(embed=create_error_embed("Access Denied", "Only the command author can select."), ephemeral=True)
            return
        os_version = self.select.values[0]
        self.select.disabled = True
        await interaction.response.edit_message(
            embed=create_info_embed(f"{E_LOAD} Creating VPS", f"Deploying {os_version} for {self.user.mention} on node {self.node_id}..."), view=self)
        user_id = str(self.user.id)
        vps_data.setdefault(user_id, [])
        vps_count = len(vps_data[user_id]) + 1
        container_name = f"{BOT_NAME.lower().replace('.', '')}-vps-{user_id}-{vps_count}"
        try:
            root_password, pinggy_address, static_ip = await deploy_container(
                container_name, os_version, self.ram, self.cpu, self.disk, self.node_id)
            config_str = f"{self.ram}GB RAM / {self.cpu} CPU / {self.disk}GB Disk"
            vps_info = {"container_name": container_name, "node_id": self.node_id,
                        "ram": f"{self.ram}GB", "cpu": str(self.cpu), "storage": f"{self.disk}GB",
                        "config": config_str, "os_version": os_version, "status": "running",
                        "suspended": False, "whitelisted": False, "suspension_history": [],
                        "created_at": datetime.now().isoformat(), "shared_with": [],
                        "root_password": root_password, "pinggy_address": pinggy_address,
                        "vps_token": generate_vps_token(), "static_ip": static_ip, "id": None}
            vps_data[user_id].append(vps_info)
            save_vps_data()
            vps_id = vps_info['id']
            if self.ctx.guild:
                role = await get_or_create_vps_role(self.ctx.guild)
                if role:
                    try:
                        await self.user.add_roles(role, reason=f"{BOT_NAME} VPS ownership")
                    except discord.Forbidden:
                        pass
            success_embed = create_success_embed(f"{E_TADA} VPS Created Successfully")
            add_field(success_embed, "Owner", self.user.mention, True)
            add_field(success_embed, "VPS ID", f"`#{vps_id}`", True)
            add_field(success_embed, "Container", f"`{container_name}`", True)
            add_field(success_embed, "Node", get_node(self.node_id)['name'], True)
            add_field(success_embed, "Resources", f"**RAM:** {self.ram}GB\n**CPU:** {self.cpu} Cores\n**Storage:** {self.disk}GB", False)
            add_field(success_embed, "OS", os_version, True)
            add_field(success_embed, "Static IP", f"`{static_ip}`", True)
            add_field(success_embed, "Features", "Nesting • Privileged • FUSE • Docker Ready • Static IP • Web Panel", False)
            await interaction.followup.send(embed=success_embed)
            dm_embed = create_success_embed(f"{E_TADA} Your VPS is Ready!",
                f"Your **{SERVER_NAME}** VPS has been deployed!\nSave your **VPS ID** and **VPS Token** — you need them for the Web Panel.")
            build_ssh_dm_fields(dm_embed, vps_info, vps_id)
            add_field(dm_embed, f"{E_GEAR} Management",
                      f"• `{PREFIX}manage` — start/stop/reinstall from Discord\n"
                      f"• Web Panel — full browser control with live terminal\n"
                      f"• Contact admin for upgrades", False)
            try:
                await self.user.send(embed=dm_embed)
            except discord.Forbidden:
                await self.ctx.send(embed=create_info_embed("Notification Failed",
                    f"Couldn't DM {self.user.mention}. Please enable DMs — VPS token was sent there."))
        except Exception as e:
            await interaction.followup.send(embed=create_error_embed("Creation Failed", f"Error: {str(e)}"))

class ReinstallOSSelectView(discord.ui.View):
    def __init__(self, parent_view, container_name, owner_id, actual_idx, ram_gb, cpu, storage_gb, node_id):
        super().__init__(timeout=300)
        self.parent_view, self.container_name, self.owner_id, self.actual_idx = parent_view, container_name, owner_id, actual_idx
        self.ram_gb, self.cpu, self.storage_gb, self.node_id = ram_gb, cpu, storage_gb, node_id
        self.select = discord.ui.Select(placeholder="Select the new OS",
            options=[discord.SelectOption(label=o["label"], value=o["value"]) for o in OS_OPTIONS])
        self.select.callback = self.select_os
        self.add_item(self.select)

    async def select_os(self, interaction: discord.Interaction):
        os_version = self.select.values[0]
        self.select.disabled = True
        await interaction.response.edit_message(
            embed=create_info_embed(f"{E_LOAD} Reinstalling VPS", f"Deploying {os_version} on `{self.container_name}`..."), view=self)
        try:
            root_password, pinggy_address, static_ip = await deploy_container(
                self.container_name, os_version, self.ram_gb, self.cpu, self.storage_gb, self.node_id)
            target = vps_data[self.owner_id][self.actual_idx]
            target.update({"os_version": os_version, "status": "running", "suspended": False,
                           "created_at": datetime.now().isoformat(), "root_password": root_password,
                           "pinggy_address": pinggy_address, "static_ip": static_ip,
                           "config": f"{self.ram_gb}GB RAM / {self.cpu} CPU / {self.storage_gb}GB Disk"})
            save_vps_data()
            success_embed = create_success_embed("Reinstall Complete", f"VPS `{self.container_name}` reinstalled with **{os_version}**!")
            add_field(success_embed, "Resources", f"**RAM:** {self.ram_gb}GB\n**CPU:** {self.cpu} Cores\n**Storage:** {self.storage_gb}GB", False)
            add_field(success_embed, "New Static IP", f"`{static_ip}`", True)
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            try:
                owner_user = await bot.fetch_user(int(self.owner_id))
                dm_embed = create_success_embed("VPS Reinstalled!",
                    f"Your VPS `{self.container_name}` was reinstalled. SSH password has changed.\nYour VPS ID & Token stay the same.")
                build_ssh_dm_fields(dm_embed, target, target.get('id') or 0)
                await owner_user.send(embed=dm_embed)
            except Exception:
                pass
            self.stop()
        except Exception as e:
            await interaction.followup.send(embed=create_error_embed("Reinstall Failed", f"Error: {str(e)}"), ephemeral=True)
            self.stop()

class ManageView(discord.ui.View):
    def __init__(self, user_id, vps_list, is_shared=False, owner_id=None, is_admin=False, actual_index: Optional[int] = None):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.vps_list = vps_list[:]
        self.selected_index = None
        self.is_shared = is_shared
        self.owner_id = owner_id or user_id
        self.is_admin = is_admin
        self.actual_index = actual_index
        self.indices = list(range(len(vps_list)))
        if len(vps_list) > 1:
            options = [discord.SelectOption(label=f"VPS #{v.get('id', i+1)} ({v.get('config', 'Custom')})",
                        description=f"Status: {v.get('status', 'unknown')}", value=str(i))
                       for i, v in enumerate(vps_list)]
            self.select = discord.ui.Select(placeholder="Select a VPS to manage", options=options)
            self.select.callback = self.select_vps
            self.add_item(self.select)
            self.initial_embed = create_embed(f"{E_GEAR} VPS Management", "Select a VPS from the dropdown below.", 0x1a1a1a)
            add_field(self.initial_embed, "Available VPS",
                      "\n".join([f"**VPS #{v.get('id','?')}:** `{v['container_name']}` — `{v.get('status','?').upper()}`" for v in vps_list]), False)
        else:
            self.selected_index = 0
            self.initial_embed = None
            self.add_action_buttons()

    async def get_initial_embed(self):
        if self.initial_embed is None:
            self.initial_embed = await self.create_vps_embed(self.selected_index)
        return self.initial_embed

    async def create_vps_embed(self, index):
        vps = self.vps_list[index]
        node = get_node(vps['node_id'])
        node_name = node['name'] if node else "Unknown"
        status = vps.get('status', 'unknown')
        suspended = vps.get('suspended', False)
        color = 0x00ff88 if status == 'running' and not suspended else (0xffaa00 if suspended else 0xff3366)
        container_name = vps['container_name']
        stats = await get_container_stats(container_name)
        status_text = stats['status'].upper()
        if suspended:
            status_text += " (SUSPENDED)"
        embed = create_embed(f"{E_GEAR} VPS Management — #{vps.get('id', index+1)}",
                             f"Container `{container_name}` on node **{node_name}**", color)
        add_field(embed, f"{E_PC} Resources",
                  f"**Config:** {vps.get('config', 'Custom')}\n**Status:** `{status_text}`\n"
                  f"**OS:** {vps.get('os_version', 'ubuntu:22.04')}\n**Static IP:** `{vps.get('static_ip') or 'DHCP'}`\n"
                  f"**Uptime:** {stats['uptime']}", False)
        add_field(embed, "📈 Live Usage",
                  f"**CPU:** {progress_bar(stats['cpu'])} {stats['cpu']:.1f}%\n"
                  f"**RAM:** {progress_bar(stats['ram']['pct'])} {stats['ram']['used']}/{stats['ram']['total']} MB\n"
                  f"**Disk:** {stats['disk']}", False)
        pinggy = vps.get('pinggy_address')
        if pinggy:
            host, port = pinggy.split(":")
            add_field(embed, f"{E_KEY} SSH", f"```ssh root@{host} -p {port}```", True)
        else:
            add_field(embed, f"{E_KEY} SSH", f"Local: `ssh root@{vps.get('static_ip','N/A')}`", True)
        add_field(embed, f"{E_LINK} Web Panel", f"`http://{get_public_ip()}:{PANEL_PORT}`\nVPS ID: `#{vps.get('id')}`", True)
        add_field(embed, "🎮 Controls", "Use the buttons below to manage your VPS", False)
        return embed

    def add_action_buttons(self):
        if not self.is_shared and not self.is_admin:
            b = discord.ui.Button(label="Reinstall", style=discord.ButtonStyle.danger, emoji="🔄")
            b.callback = lambda i: self.action_callback(i, 'reinstall'); self.add_item(b)
        for label, style, emoji_, action in [
            ("Start", discord.ButtonStyle.success, "▶️", 'start'),
            ("Stop", discord.ButtonStyle.secondary, "⏸️", 'stop'),
            ("SSH", discord.ButtonStyle.primary, "🔑", 'tmate'),
            ("Stats", discord.ButtonStyle.secondary, "📊", 'stats')]:
            b = discord.ui.Button(label=label, style=style, emoji=emoji_)
            b.callback = (lambda a: (lambda i: self.action_callback(i, a)))(action)
            self.add_item(b)
        if not self.is_shared:
            for label, style, emoji_, action in [
                ("Add Port", discord.ButtonStyle.primary, "➕", 'addport'),
                ("Password", discord.ButtonStyle.danger, "🔐", 'changepass'),
                ("Tunnel", discord.ButtonStyle.primary, "🔌", 'reconnect_tunnel'),
                ("Panel Info", discord.ButtonStyle.secondary, "🌐", 'panel')]:
                b = discord.ui.Button(label=label, style=style, emoji=emoji_)
                b.callback = (lambda a: (lambda i: self.action_callback(i, a)))(action)
                self.add_item(b)

    async def select_vps(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id and not self.is_admin:
            await interaction.response.send_message(embed=create_error_embed("Access Denied", "This is not your VPS!"), ephemeral=True)
            return
        self.selected_index = int(self.select.values[0])
        await interaction.response.defer()
        new_embed = await self.create_vps_embed(self.selected_index)
        self.clear_items(); self.add_action_buttons()
        await interaction.edit_original_response(embed=new_embed, view=self)

    async def action_callback(self, interaction: discord.Interaction, action: str):
        if str(interaction.user.id) != self.user_id and not self.is_admin:
            await interaction.response.send_message(embed=create_error_embed("Access Denied", "This is not your VPS!"), ephemeral=True)
            return
        if self.selected_index is None:
            await interaction.response.send_message(embed=create_error_embed("No VPS Selected", "Select a VPS first."), ephemeral=True)
            return
        actual_idx = self.actual_index if self.is_shared else self.indices[self.selected_index]
        target_vps = vps_data[self.owner_id][actual_idx]
        suspended = target_vps.get('suspended', False)
        if suspended and not self.is_admin and action != 'stats':
            await interaction.response.send_message(embed=create_error_embed("Suspended", "This VPS is suspended. Contact an admin."), ephemeral=True)
            return
        container_name, node_id = target_vps["container_name"], target_vps['node_id']

        if action == 'stats':
            stats = await get_container_stats(container_name, node_id)
            e = create_info_embed("📈 Live Statistics", f"Real-time stats for `{container_name}`")
            add_field(e, "Status", f"`{stats['status'].upper()}`", True)
            add_field(e, "CPU", f"{progress_bar(stats['cpu'])} {stats['cpu']:.1f}%", True)
            add_field(e, "Memory", f"{stats['ram']['used']}/{stats['ram']['total']} MB ({stats['ram']['pct']:.1f}%)", True)
            add_field(e, "Disk", stats['disk'], True)
            add_field(e, "Uptime", stats['uptime'], True)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        if action == 'panel':
            e = create_info_embed(f"{E_LINK} Web Panel Access", f"Control `{container_name}` from your browser.")
            add_field(e, "Panel URL", f"`http://{get_public_ip()}:{PANEL_PORT}`", False)
            add_field(e, "Login", f"**Discord ID:** `{self.owner_id}`\n**VPS ID:** `#{target_vps.get('id')}`\n**Token:** ||{target_vps.get('vps_token','')}||", False)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        if action == 'reinstall':
            if self.is_shared or self.is_admin:
                await interaction.response.send_message(embed=create_error_embed("Access Denied", "Only the VPS owner can reinstall!"), ephemeral=True)
                return
            ram_gb = int(target_vps['ram'].replace('GB', ''))
            cpu = int(target_vps['cpu'])
            storage_gb = int(target_vps['storage'].replace('GB', ''))
            confirm_embed = create_warning_embed("Reinstall Warning",
                f"**WARNING:** This erases ALL data on `{container_name}` and installs a fresh OS.\nThis cannot be undone. Continue?")
            view = ConfirmReinstallView(self, container_name, self.owner_id, actual_idx, ram_gb, cpu, storage_gb, node_id)
            await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
            return

        if action == 'addport':
            owner_id = self.owner_id
            class AddPortModal(discord.ui.Modal, title="Add IPv4 Port Forward"):
                vps_port_input = discord.ui.TextInput(label="VPS Port (1-65535)", placeholder="e.g. 8080", max_length=5)
                async def on_submit(self, mi: discord.Interaction):
                    await mi.response.defer(ephemeral=True)
                    try:
                        vps_port = int(self.vps_port_input.value)
                        if not 1 <= vps_port <= 65535:
                            raise ValueError
                    except ValueError:
                        await mi.followup.send(embed=create_error_embed("Invalid Port", "Port must be 1-65535."), ephemeral=True)
                        return
                    allocated, used = get_user_allocation(owner_id), get_user_used_ports(owner_id)
                    if used >= allocated:
                        await mi.followup.send(embed=create_error_embed("Quota Exceeded", f"Allocated: {allocated}, Used: {used}. Contact admin for more."), ephemeral=True)
                        return
                    host_port = await create_port_forward(owner_id, container_name, vps_port, node_id)
                    if host_port:
                        public_ip = get_public_ip()
                        e = create_success_embed("Port Forward Created", f"VPS port `{vps_port}` → host port `{host_port}` (TCP & UDP)")
                        add_field(e, "Public Access", f"`{public_ip}:{host_port}` → VPS:`{vps_port}`", False)
                        await mi.followup.send(embed=e, ephemeral=True)
                        try:
                            dm = await bot.fetch_user(int(owner_id))
                            de = create_success_embed("🔌 Port Forward Created", f"VPS `{container_name}`: `{public_ip}:{host_port}` → `{vps_port}` (TCP & UDP)")
                            await dm.send(embed=de)
                        except discord.Forbidden:
                            pass
                    else:
                        await mi.followup.send(embed=create_error_embed("Failed", "Could not assign a host port."), ephemeral=True)
            await interaction.response.send_modal(AddPortModal())
            return

        await interaction.response.defer(ephemeral=True)
        if suspended:
            target_vps['suspended'] = False
            save_vps_data()

        if action == 'start':
            try:
                await safe_start_container(container_name, node_id)
                target_vps["status"] = "running"; save_vps_data()
                await apply_internal_permissions(container_name, node_id)
                readded = await recreate_port_forwards(container_name)
                await interaction.followup.send(embed=create_success_embed("VPS Started", f"`{container_name}` is running! Re-added {readded} port forwards."), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=create_error_embed("Start Failed", str(e)), ephemeral=True)
        elif action == 'stop':
            try:
                await execute_lxc(container_name, f"stop {container_name}", timeout=120, node_id=node_id)
                target_vps["status"] = "stopped"; save_vps_data()
                await interaction.followup.send(embed=create_success_embed("VPS Stopped", f"`{container_name}` stopped."), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=create_error_embed("Stop Failed", str(e)), ephemeral=True)
        elif action == 'tmate':
            await interaction.followup.send(embed=create_info_embed(f"{E_LOAD} SSH Access", "Generating SSH session..."), ephemeral=True)
            try:
                try:
                    await execute_lxc(container_name, f"exec {container_name} -- which tmate", node_id=node_id)
                except Exception:
                    await execute_lxc(container_name, f"exec {container_name} -- apt-get update -y", node_id=node_id)
                    await execute_lxc(container_name, f"exec {container_name} -- apt-get install tmate -y", node_id=node_id)
                sess = f"svm-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                await execute_lxc(container_name, f"exec {container_name} -- tmate -S /tmp/{sess}.sock new-session -d", node_id=node_id)
                await asyncio.sleep(3)
                ssh_url = (await execute_lxc(container_name, f"exec {container_name} -- tmate -S /tmp/{sess}.sock display -p '#{{tmate_ssh}}'", node_id=node_id)).strip()
                if ssh_url:
                    e = create_embed(f"{E_KEY} SSH Access", f"SSH for `{container_name}`:", 0x00ff88)
                    add_field(e, "Command", f"```{ssh_url}```", False)
                    add_field(e, f"{E_WARN} Security", "Temporary link. Do not share.", False)
                    try:
                        await interaction.user.send(embed=e)
                        await interaction.followup.send(embed=create_success_embed("SSH Sent", "Check your DMs!"), ephemeral=True)
                    except discord.Forbidden:
                        await interaction.followup.send(embed=create_error_embed("DM Failed", "Enable DMs to receive the SSH link!"), ephemeral=True)
                else:
                    await interaction.followup.send(embed=create_error_embed("SSH Failed", "No SSH URL generated."), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=create_error_embed("SSH Error", str(e)), ephemeral=True)
        elif action == 'changepass':
            try:
                new_password = generate_password()
                await execute_lxc(container_name, f"exec {container_name} -- bash -c \"echo 'root:{new_password}' | chpasswd\"", node_id=node_id, timeout=60)
                target_vps['root_password'] = new_password; save_vps_data()
                try:
                    dm = await bot.fetch_user(int(self.owner_id))
                    e = create_success_embed("🔐 Root Password Changed", f"New password for `{container_name}`:")
                    add_field(e, "New Password", f"`{new_password}`", False)
                    await dm.send(embed=e)
                    await interaction.followup.send(embed=create_success_embed("Password Changed", "Check your DMs!"), ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send(embed=create_success_embed("Password Changed", f"New password: `{new_password}`"), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=create_error_embed("Failed", str(e)), ephemeral=True)
        elif action == 'reconnect_tunnel':
            await interaction.followup.send(embed=create_info_embed(f"{E_LOAD} Reconnecting", "Setting up a fresh SSH tunnel (~30s)..."), ephemeral=True)
            try:
                new_address = await establish_pinggy_tunnel(container_name, node_id)
                target_vps['pinggy_address'] = new_address; save_vps_data()
                if new_address:
                    host, port = new_address.split(":")
                    await interaction.followup.send(embed=create_success_embed("Tunnel Reconnected",
                        f"```ssh root@{host} -p {port}```"), ephemeral=True)
                else:
                    await interaction.followup.send(embed=create_error_embed("Failed", "Could not establish tunnel. Is the VPS running?"), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(embed=create_error_embed("Failed", str(e)), ephemeral=True)
        new_embed = await self.create_vps_embed(self.selected_index)
        await interaction.edit_original_response(embed=new_embed, view=self)

class ConfirmReinstallView(discord.ui.View):
    def __init__(self, parent_view, container_name, owner_id, actual_idx, ram_gb, cpu, storage_gb, node_id):
        super().__init__(timeout=60)
        self.parent_view, self.container_name, self.owner_id, self.actual_idx = parent_view, container_name, owner_id, actual_idx
        self.ram_gb, self.cpu, self.storage_gb, self.node_id = ram_gb, cpu, storage_gb, node_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, inter: discord.Interaction, item: discord.ui.Button):
        await inter.response.defer(ephemeral=True)
        try:
            await inter.followup.send(embed=create_info_embed("Deleting Container", f"Removing `{self.container_name}`..."), ephemeral=True)
            await execute_lxc(self.container_name, f"delete {self.container_name} --force", node_id=self.node_id)
            await inter.followup.send(embed=create_info_embed("Select OS", "Choose the new OS."),
                view=ReinstallOSSelectView(self.parent_view, self.container_name, self.owner_id,
                                           self.actual_idx, self.ram_gb, self.cpu, self.storage_gb, self.node_id),
                ephemeral=True)
        except Exception as e:
            await inter.followup.send(embed=create_error_embed("Delete Failed", str(e)), ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, inter: discord.Interaction, item: discord.ui.Button):
        new_embed = await self.parent_view.create_vps_embed(self.parent_view.selected_index)
        await inter.response.edit_message(embed=new_embed, view=self.parent_view)
# ============================================================================
# DISCORD COMMANDS
# ============================================================================
@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(embed=create_success_embed("Pong!", f"{E_TIME} Latency: **{round(bot.latency * 1000)}ms**"))

@bot.command(name='uptime')
async def uptime(ctx):
    await ctx.send(embed=create_info_embed(f"{E_UPTIME} Host Uptime", get_uptime()))

@bot.command(name='thresholds')
@is_admin()
async def thresholds(ctx):
    await ctx.send(embed=create_info_embed("Resource Thresholds", f"**CPU:** {CPU_THRESHOLD}%\n**RAM:** {RAM_THRESHOLD}%"))

@bot.command(name='set-threshold')
@is_admin()
async def set_threshold(ctx, cpu: int, ram: int):
    global CPU_THRESHOLD, RAM_THRESHOLD
    if cpu < 0 or ram < 0:
        await ctx.send(embed=create_error_embed("Invalid", "Thresholds must be non-negative.")); return
    CPU_THRESHOLD, RAM_THRESHOLD = cpu, ram
    set_setting('cpu_threshold', str(cpu)); set_setting('ram_threshold', str(ram))
    await ctx.send(embed=create_success_embed("Thresholds Updated", f"**CPU:** {cpu}%\n**RAM:** {ram}%"))

@bot.command(name='set-status')
@is_admin()
async def set_status(ctx, activity_type: str, *, name: str):
    types = {'playing': discord.ActivityType.playing, 'watching': discord.ActivityType.watching,
             'listening': discord.ActivityType.listening, 'streaming': discord.ActivityType.streaming}
    if activity_type.lower() not in types:
        await ctx.send(embed=create_error_embed("Invalid Type", "Valid: playing, watching, listening, streaming")); return
    await bot.change_presence(activity=discord.Activity(type=types[activity_type.lower()], name=name))
    await ctx.send(embed=create_success_embed("Status Updated", f"Set to {activity_type}: {name}"))

@bot.command(name="myvps")
async def my_vps(ctx):
    user_id = str(ctx.author.id)
    vps_list = vps_data.get(user_id, [])
    if not vps_list:
        embed = create_error_embed("No VPS Found", f"You don't have any **{BOT_NAME} VPS** yet.")
        add_field(embed, f"{E_ROCKET} Quick Actions", f"• `{PREFIX}manage` — Manage VPS\n• Contact an admin to request a VPS", False)
        await ctx.send(embed=embed); return
    embed = create_info_embed(f"{E_PC} My VPS Dashboard", "Your personal VPS overview")
    running = suspended = whitelisted = 0
    cards = []
    for vps in vps_list:
        node = get_node(vps.get("node_id"))
        node_name = node["name"] if node else "Unknown"
        if vps.get("suspended"):
            status = f"{E_CROSS} SUSPENDED"; suspended += 1
        elif vps.get("status") == "running":
            status = f"{E_ONLINE} RUNNING"; running += 1
        else:
            status = f"{E_OFFLINE} STOPPED"
        if vps.get("whitelisted"):
            whitelisted += 1
        cards.append(f"**VPS #{vps.get('id','?')}** — `{vps['container_name']}`\n"
                     f"{status} • `{vps.get('config','Custom')}`\n"
                     f"{E_WIFI} `{vps.get('static_ip') or 'DHCP'}` • 📍 `{node_name}`")
    embed.add_field(name="📊 Summary",
        value=f"{E_PC} `{len(vps_list)}` VPS\n{E_ONLINE} `{running}` Running\n⛔ `{suspended}` Suspended\n✅ `{whitelisted}` Whitelisted", inline=True)
    embed.add_field(name="⚡ Quick Actions", value=f"`{PREFIX}manage`\n`{PREFIX}panel`\n`{PREFIX}ai`", inline=True)
    embed.add_field(name=f"{E_LINK} Web Panel", value=f"`http://{get_public_ip()}:{PANEL_PORT}`", inline=True)
    text = "\n\n".join(cards)
    for i in range(0, len(text), 1024):
        embed.add_field(name=f"{E_PC} Your VPS", value=text[i:i+1024], inline=False)
    embed.timestamp = ctx.message.created_at
    await ctx.send(embed=embed)

@bot.command(name='panel')
async def panel_cmd(ctx):
    """Show your web panel URL + login details."""
    user_id = str(ctx.author.id)
    vps_list = vps_data.get(user_id, [])
    if not vps_list:
        await ctx.send(embed=create_error_embed("No VPS", "You need a VPS first. Contact an admin.")); return
    embed = create_info_embed(f"{E_LINK} Web Control Panel", "Control your VPS from any browser.")
    add_field(embed, "Panel URL", f"`http://{get_public_ip()}:{PANEL_PORT}`", False)
    lines = []
    for v in vps_list:
        lines.append(f"**VPS #{v.get('id')}** `{v['container_name']}`\nToken: ||{v.get('vps_token','')}||")
    add_field(embed, f"{E_KEY} Your Logins (Discord ID: {user_id})", "\n\n".join(lines), False)
    try:
        await ctx.author.send(embed=embed)
        await ctx.send(embed=create_success_embed("Panel Info Sent", "Check your DMs for login details!"))
    except discord.Forbidden:
        await ctx.send(embed=embed)

@bot.command(name='create')
@is_admin()
async def create_vps(ctx, ram: int, cpu: int, disk: int, user: discord.Member):
    if ram <= 0 or cpu <= 0 or disk <= 0:
        await ctx.send(embed=create_error_embed("Invalid Specs", "RAM, CPU, Disk must be positive integers.")); return
    await ctx.send(embed=create_info_embed(f"{E_ROCKET} VPS Creation",
        f"Creating VPS for {user.mention}: **{ram}GB RAM / {cpu} CPU / {disk}GB Disk**\nSelect node below."),
        view=NodeSelectView(ram, cpu, disk, user, ctx))

@bot.command(name='manage')
async def manage_vps(ctx, user: discord.Member = None):
    if user:
        if str(ctx.author.id) not in main_admin_ids and str(ctx.author.id) not in admin_data.get("admins", []):
            await ctx.send(embed=create_error_embed("Access Denied", "Only admins can manage other users' VPS.")); return
        user_id = str(user.id)
        vps_list = vps_data.get(user_id, [])
        if not vps_list:
            await ctx.send(embed=create_error_embed("No VPS", f"{user.mention} has no VPS.")); return
        view = ManageView(str(ctx.author.id), vps_list, is_admin=True, owner_id=user_id)
        await ctx.send(embed=create_info_embed(f"Managing {user.name}'s VPS", f"Admin control for {user.mention}"), view=view)
    else:
        user_id = str(ctx.author.id)
        vps_list = vps_data.get(user_id, [])
        if not vps_list:
            await ctx.send(embed=create_error_embed("No VPS Found", f"You don't have any {BOT_NAME} VPS. Contact an admin.")); return
        view = ManageView(user_id, vps_list)
        await ctx.send(embed=await view.get_initial_embed(), view=view)

@bot.command(name='lxc-list')
@is_admin()
async def lxc_list(ctx, node_id: int = 1):
    try:
        result = await execute_lxc("", "list", node_id=node_id)
        node = get_node(node_id)
        await ctx.send(embed=create_info_embed(f"LXC Containers — {node['name']}", f"```\n{result}\n```"))
    except Exception as e:
        await ctx.send(embed=create_error_embed("Error", str(e)))

@bot.command(name='give-ports')
@is_admin()
async def give_ports(ctx, user: discord.Member, amount: int):
    allocate_ports(str(user.id), amount)
    await ctx.send(embed=create_success_embed("Ports Allocated",
        f"{user.mention} now has **{get_user_allocation(str(user.id))}** port slots (added {amount})."))

@bot.command(name='ports')
async def my_ports(ctx):
    user_id = str(ctx.author.id)
    allocated, used = get_user_allocation(user_id), get_user_used_ports(user_id)
    forwards = get_user_forwards(user_id)
    embed = create_info_embed(f"{E_WIFI} Your Port Forwards", f"**Quota:** {used}/{allocated} used")
    public_ip = get_public_ip()
    if forwards:
        lines = [f"`{public_ip}:{f['host_port']}` → VPS `{f['vps_container']}` port `{f['vps_port']}`" for f in forwards[:15]]
        add_field(embed, "Active Forwards", "\n".join(lines), False)
    else:
        add_field(embed, "Active Forwards", "None. Use `!manage` → Add Port.", False)
    await ctx.send(embed=embed)

@bot.command(name='remove-port')
async def remove_port(ctx, forward_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT user_id FROM port_forwards WHERE id = ?', (forward_id,))
    row = cur.fetchone(); conn.close()
    if not row or (row[0] != str(ctx.author.id) and str(ctx.author.id) not in main_admin_ids):
        await ctx.send(embed=create_error_embed("Not Found", "Forward not found or not yours.")); return
    ok, _ = await remove_port_forward(forward_id)
    if ok:
        await ctx.send(embed=create_success_embed("Removed", f"Forward #{forward_id} removed."))
    else:
        await ctx.send(embed=create_error_embed("Failed", "Could not remove forward."))

@bot.command(name='suspend')
@is_admin()
async def suspend_vps(ctx, container_name: str):
    for uid, lst in vps_data.items():
        for v in lst:
            if v['container_name'] == container_name:
                v['suspended'] = True
                try:
                    await execute_lxc(container_name, f"stop {container_name} --force", node_id=v['node_id'])
                    v['status'] = 'stopped'
                except Exception:
                    pass
                save_vps_data()
                await ctx.send(embed=create_success_embed("Suspended", f"`{container_name}` suspended & stopped.")); return
    await ctx.send(embed=create_error_embed("Not Found", f"No VPS named `{container_name}`."))

@bot.command(name='unsuspend')
@is_admin()
async def unsuspend_vps(ctx, container_name: str):
    for uid, lst in vps_data.items():
        for v in lst:
            if v['container_name'] == container_name:
                v['suspended'] = False; save_vps_data()
                await ctx.send(embed=create_success_embed("Unsuspended", f"`{container_name}` is active again.")); return
    await ctx.send(embed=create_error_embed("Not Found", f"No VPS named `{container_name}`."))

@bot.command(name='delete-vps')
@is_admin()
async def delete_vps(ctx, container_name: str):
    for uid, lst in list(vps_data.items()):
        for i, v in enumerate(lst):
            if v['container_name'] == container_name:
                try:
                    await execute_lxc(container_name, f"delete {container_name} --force", node_id=v['node_id'])
                except Exception as e:
                    logger.warning(f"delete: {e}")
                conn = get_db(); cur = conn.cursor()
                cur.execute('DELETE FROM port_forwards WHERE vps_container = ?', (container_name,))
                cur.execute('DELETE FROM vps WHERE container_name = ?', (container_name,))
                conn.commit(); conn.close()
                lst.pop(i)
                if not lst:
                    vps_data.pop(uid, None)
                await ctx.send(embed=create_success_embed("Deleted", f"`{container_name}` fully removed.")); return
    await ctx.send(embed=create_error_embed("Not Found", f"No VPS named `{container_name}`."))

@bot.command(name='regen-token')
async def regen_token(ctx):
    """Regenerate web-panel token for your VPS (first one)."""
    user_id = str(ctx.author.id)
    vps_list = vps_data.get(user_id, [])
    if not vps_list:
        await ctx.send(embed=create_error_embed("No VPS", "You have no VPS.")); return
    v = vps_list[0]
    v['vps_token'] = generate_vps_token(); save_vps_data()
    try:
        await ctx.author.send(embed=create_success_embed(f"{E_KEY} Token Regenerated",
            f"New token for VPS #{v.get('id')}:\n||{v['vps_token']}||"))
        await ctx.send(embed=create_success_embed("Token Regenerated", "New token sent to your DMs!"))
    except discord.Forbidden:
        await ctx.send(embed=create_error_embed("DM Failed", "Enable DMs to receive the token."))

# ---------- Admin management ----------
@bot.command(name='admin-add')
@is_main_admin()
async def admin_add(ctx, user: discord.Member):
    uid = str(user.id)
    if uid in main_admin_ids or uid in admin_data.get("admins", []):
        await ctx.send(embed=create_error_embed("Already Admin", f"{user.mention} is already an admin!")); return
    admin_data["admins"].append(uid); save_admin_data()
    await ctx.send(embed=create_success_embed("Admin Added", f"{user.mention} is now an admin!"))

@bot.command(name='admin-remove')
@is_main_admin()
async def admin_remove(ctx, user: discord.Member):
    uid = str(user.id)
    if uid in main_admin_ids:
        await ctx.send(embed=create_error_embed("Cannot Remove", "You cannot remove the main admin!")); return
    if uid not in admin_data.get("admins", []):
        await ctx.send(embed=create_error_embed("Not Admin", f"{user.mention} is not an admin!")); return
    admin_data["admins"].remove(uid); save_admin_data()
    await ctx.send(embed=create_success_embed("Admin Removed", f"{user.mention} is no longer an admin!"))

@bot.command(name='add-admin')
@is_main_admin()
async def add_admin_id(ctx, user_id: str):
    if not user_id.isdigit():
        await ctx.send(embed=create_error_embed("Invalid ID", "Provide a numeric Discord user ID.")); return
    if user_id in main_admin_ids:
        await ctx.send(embed=create_error_embed("Already Admin", "Already a main admin!")); return
    main_admin_ids.add(user_id); save_main_admins()
    await ctx.send(embed=create_success_embed("Main Admin Added", f"`{user_id}` is now a main admin!"))

@bot.command(name='rm-admin')
@is_main_admin()
async def rm_admin_id(ctx, user_id: str):
    if user_id not in main_admin_ids:
        await ctx.send(embed=create_error_embed("Not Admin", "Not a main admin!")); return
    if len(main_admin_ids) <= 1:
        await ctx.send(embed=create_error_embed("Cannot Remove", "At least one main admin must remain.")); return
    main_admin_ids.discard(user_id); save_main_admins()
    await ctx.send(embed=create_success_embed("Main Admin Removed", f"`{user_id}` removed."))

@bot.command(name='admin-list')
@is_main_admin()
async def admin_list(ctx):
    embed = create_embed(f"{E_CROWN} Admin Team", "Current administrators:", 0x1a1a1a)
    mains, subs = [], []
    for mid in main_admin_ids:
        try:
            u = await bot.fetch_user(int(mid)); mains.append(f"• {u.mention} (`{mid}`)")
        except Exception:
            mains.append(f"• `{mid}`")
    for aid in admin_data.get("admins", []):
        try:
            u = await bot.fetch_user(int(aid)); subs.append(f"• {u.mention} (`{aid}`)")
        except Exception:
            subs.append(f"• `{aid}`")
    add_field(embed, f"{E_CROWN} Main Admin(s)", "\n".join(mains) or "None", False)
    add_field(embed, "🛡️ Admins", "\n".join(subs) or "No additional admins", False)
    await ctx.send(embed=embed)

@bot.command(name="userinfo")
@is_admin()
async def user_info(ctx, user: discord.Member):
    user_id = str(user.id)
    vps_list = vps_data.get(user_id, [])
    embed = create_embed("👤 User Dashboard", f"Stats for {user.mention}", 0x1A1A1A)
    is_admin_user = user_id in main_admin_ids or user_id in admin_data.get("admins", [])
    embed.add_field(name="👤 User", value=f"**Name:** `{user.name}`\n**ID:** `{user.id}`", inline=True)
    embed.add_field(name="🛡️ Admin", value="✅ Yes" if is_admin_user else "❌ No", inline=True)
    embed.add_field(name=f"{E_PC} VPS", value=f"`{len(vps_list)}`", inline=True)
    if vps_list:
        lines = []
        for v in vps_list:
            status = "⛔" if v.get("suspended") else ("🟢" if v.get("status") == "running" else "🔴")
            lines.append(f"{status} **#{v.get('id')}** `{v['container_name']}` — `{v.get('config','')}`")
        embed.add_field(name="📋 VPS List", value="\n".join(lines)[:1024], inline=False)
        embed.add_field(name="🌐 Ports", value=f"`{get_user_used_ports(user_id)}/{get_user_allocation(user_id)}` used", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='status')
@is_admin()
async def system_status(ctx):
    start = time.time()
    nodes = get_nodes()
    total_vps = sum(len(l) for l in vps_data.values())
    running_vps = stopped_vps = suspended_vps = 0
    for lst in vps_data.values():
        for v in lst:
            if v.get('suspended'): suspended_vps += 1
            elif v.get('status') == 'running': running_vps += 1
            else: stopped_vps += 1
    embed = create_embed(f"📊 {SERVER_NAME} — System Dashboard",
                         f"*Generated in {(time.time()-start)*1000:.0f}ms*", 0x1a1a1a)
    add_field(embed, "🤖 Bot",
        f"**Uptime:** {get_uptime()}\n**Latency:** {round(bot.latency*1000)}ms\n"
        f"**Version:** {BOT_VERSION}\n**Developer:** {BOT_DEVELOPER}", True)
    add_field(embed, f"{E_PEOPLE} Users & VPS",
        f"**Users:** {len(vps_data)}\n**VPS:** {total_vps}\n🟢 {running_vps} • 🔴 {stopped_vps} • 🟡 {suspended_vps}", True)
    node_lines = []
    for n in nodes:
        st = "🟢 Online" if n['is_local'] else "🌐 Remote"
        node_lines.append(f"**{n['name']}** ({st}) — {get_current_vps_count(n['id'])}/{n['total_vps']} VPS")
    add_field(embed, f"{E_CLOUD} Nodes", "\n".join(node_lines) or "None", False)
    stats = await get_host_stats(1)
    add_field(embed, "💾 Host Resources",
        f"**CPU:** {progress_bar(stats['cpu'])} {stats['cpu']:.0f}%\n"
        f"**RAM:** {progress_bar(stats['ram'])} {stats['ram']:.0f}%\n**Disk:** {stats['disk']}", True)
    add_field(embed, f"{E_LINK} Web Panel", f"`http://{get_public_ip()}:{PANEL_PORT}`", True)
    await ctx.send(embed=embed)

@bot.command(name='serverstats')
@is_admin()
async def server_stats(ctx):
    total_vps = sum(len(l) for l in vps_data.values())
    total_ram = total_cpu = total_storage = 0
    for lst in vps_data.values():
        for v in lst:
            try: total_ram += int(v.get("ram", "0GB").replace("GB", ""))
            except Exception: pass
            try: total_cpu += int(v.get("cpu", 0))
            except Exception: pass
            try: total_storage += int(v.get("storage", "0GB").replace("GB", ""))
            except Exception: pass
    embed = create_embed("📊 Server Statistics", "**Live Infrastructure Dashboard**", 0x1A1A1A)
    embed.add_field(name=f"{E_PEOPLE} Users", value=f"`{len(vps_data)}`", inline=True)
    embed.add_field(name=f"{E_PC} VPS", value=f"`{total_vps}`", inline=True)
    embed.add_field(name="📈 Allocated", value=f"RAM `{total_ram}GB`\nCPU `{total_cpu}`\nDisk `{total_storage}GB`", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='vpsinfo')
@is_admin()
async def vps_info(ctx, container_name: str = None):
    if not container_name:
        all_lines = []
        for user_id, lst in vps_data.items():
            for v in lst:
                all_lines.append(f"`{v['container_name']}` — <@{user_id}> — {v.get('status','?').upper()}")
        text = "\n".join(all_lines) or "No VPS deployed."
        for i in range(0, len(text), 1800):
            await ctx.send(embed=create_embed(f"{E_PC} All VPS", text[i:i+1800], 0x1a1a1a))
        return
    for uid, lst in vps_data.items():
        for v in lst:
            if v['container_name'] == container_name:
                embed = create_embed(f"{E_PC} {container_name}", f"Owner: <@{uid}>", 0x1a1a1a)
                add_field(embed, "Specs", f"**RAM:** {v['ram']}\n**CPU:** {v['cpu']}\n**Disk:** {v['storage']}\n**OS:** {v.get('os_version')}", True)
                add_field(embed, "Network", f"**Static IP:** `{v.get('static_ip') or 'DHCP'}`\n**Tunnel:** `{v.get('pinggy_address') or 'none'}`", True)
                add_field(embed, "Panel", f"**VPS ID:** `#{v.get('id')}`\n**Token:** ||{v.get('vps_token','')}||", False)
                await ctx.send(embed=embed); return
    await ctx.send(embed=create_error_embed("Not Found", f"No VPS named `{container_name}`."))

@bot.command(name='help')
async def help_cmd(ctx):
    user_id = str(ctx.author.id)
    is_adm = user_id in main_admin_ids or user_id in admin_data.get("admins", [])
    embed = create_embed(f"{E_STAR} {BOT_NAME} — Help Center",
                         f"**{SERVER_NAME}** • Advanced VPS Manager • Made by **{BOT_DEVELOPER}**", 0x1a1a1a)
    add_field(embed, f"{E_PC} User Commands",
        f"`{PREFIX}myvps` — Your VPS dashboard\n`{PREFIX}manage` — Control panel (buttons)\n"
        f"`{PREFIX}panel` — Web panel login info\n`{PREFIX}ports` — Your port forwards\n"
        f"`{PREFIX}remove-port <id>` — Remove a forward\n`{PREFIX}regen-token` — New panel token\n"
        f"`{PREFIX}ai <question>` — Gemini AI assistant\n`{PREFIX}ping` / `{PREFIX}uptime`", False)
    if is_adm:
        add_field(embed, f"{E_CROWN} Admin Commands",
            f"`{PREFIX}create <ram> <cpu> <disk> @user`\n`{PREFIX}manage @user` — Manage any VPS\n"
            f"`{PREFIX}give-ports @user <n>`\n`{PREFIX}suspend / unsuspend <container>`\n"
            f"`{PREFIX}delete-vps <container>`\n`{PREFIX}vpsinfo [container]`\n"
            f"`{PREFIX}status` / `{PREFIX}serverstats`\n`{PREFIX}lxc-list`\n"
            f"`{PREFIX}set-threshold <cpu> <ram>`\n`{PREFIX}set-status <type> <text>`", False)
    if user_id in main_admin_ids:
        add_field(embed, "👑 Main Admin",
            f"`{PREFIX}admin-add @user` / `{PREFIX}admin-remove @user`\n"
            f"`{PREFIX}add-admin <id>` / `{PREFIX}rm-admin <id>`\n`{PREFIX}admin-list`", False)
    add_field(embed, f"{E_LINK} Web Panel", f"`http://{get_public_ip()}:{PANEL_PORT}` — live status, controls, ports & terminal", False)
    await ctx.send(embed=embed)
# ============================================================================
# GEMINI AI ASSISTANT
# ============================================================================
def gemini_sync(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text":
            f"You are {BOT_NAME} AI, a helpful assistant inside a Discord VPS hosting bot. "
            "You help with Linux, VPS, SSH, Docker, networking and general questions. "
            "Keep answers concise (under 1500 characters) and use plain text with simple markdown."}]},
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
    }
    try:
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Gemini HTTP error: {e} - {getattr(e.response, 'text', '')[:200]}")
        return "⚠️ AI service returned an error. Check the API key/model name."
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "⚠️ AI service is unavailable right now. Try again later."

@bot.command(name='ai')
async def ai_cmd(ctx, *, question: str = None):
    if not question:
        await ctx.send(embed=create_info_embed(f"{em('ZAI','🤖')} AI Assistant", f"Usage: `{PREFIX}ai <your question>`")); return
    thinking = await ctx.send(embed=create_info_embed(f"{E_LOAD} Thinking...", "Gemini AI is generating a response..."))
    try:
        answer = await asyncio.to_thread(gemini_sync, question)
    except Exception:
        answer = "⚠️ AI request failed."
    embed = create_embed(f"{em('ZAI','🤖')} {BOT_NAME} AI", truncate_text(answer, 3900), 0x9b59b6)
    add_field(embed, "Question", truncate_text(question, 200), False)
    await thinking.edit(embed=embed)

# ============================================================================
# WEB CONTROL PANEL (aiohttp)
# ============================================================================
PANEL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__SERVER_NAME__ — VPS Control Panel</title>
<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
<style>
:root{--bg:#0a0e17;--card:#111827;--card2:#1a2234;--acc:#6c5ce7;--acc2:#00d4ff;--ok:#00e68a;--bad:#ff4d6d;--warn:#ffb020;--txt:#e6edf7;--mut:#8b98b0}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif}
body{background:radial-gradient(1200px 600px at 80% -10%,#1b2450 0%,var(--bg) 55%);color:var(--txt);min-height:100vh}
a{color:var(--acc2)}
.container{max-width:1080px;margin:0 auto;padding:24px}
.banner{text-align:center;padding:34px 0 18px}
.brand{font-size:52px;font-weight:900;letter-spacing:2px;background:linear-gradient(90deg,#ff004c,#ff8a00,#ffee00,#00e68a,#00d4ff,#6c5ce7,#ff00c8,#ff004c);background-size:400% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:rb 6s linear infinite}
@keyframes rb{to{background-position:400% 0}}
.sub{color:var(--mut);margin-top:6px}
.card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid #232d44;border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.kv{background:#0d1424;border:1px solid #20293f;border-radius:12px;padding:14px}
.kv .k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:1px}
.kv .v{font-size:18px;font-weight:700;margin-top:4px;word-break:break-all}
input{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #26314c;background:#0c1220;color:var(--txt);margin:6px 0;font-size:15px}
input:focus{outline:none;border-color:var(--acc)}
.btn{border:none;border-radius:10px;padding:11px 18px;font-weight:700;font-size:14px;cursor:pointer;color:#fff;transition:.15s;margin:4px}
.btn:hover{transform:translateY(-2px);filter:brightness(1.15)}
.b-acc{background:linear-gradient(135deg,var(--acc),#4834d4)}
.b-ok{background:linear-gradient(135deg,#00b46e,#007a4d)}
.b-bad{background:linear-gradient(135deg,#e0355f,#a1123a)}
.b-warn{background:linear-gradient(135deg,#e09a00,#9c6a00)}
.b-info{background:linear-gradient(135deg,#0aa5c2,#066a80)}
.row{display:flex;flex-wrap:wrap;align-items:center}
.pill{padding:5px 14px;border-radius:999px;font-size:12px;font-weight:800}
.pill.on{background:rgba(0,230,138,.15);color:var(--ok);border:1px solid #0b5}
.pill.off{background:rgba(255,77,109,.15);color:var(--bad);border:1px solid #b04}
.bar{height:8px;background:#0c1220;border-radius:99px;overflow:hidden;margin-top:6px}
.bar>div{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--acc2),var(--acc))}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px;border-bottom:1px solid #20293f}
th{color:var(--mut);font-size:12px;text-transform:uppercase}
#terminal{height:360px;border-radius:12px;overflow:hidden;background:#000;border:1px solid #20293f}
.hidden{display:none}
.foot{text-align:center;color:var(--mut);padding:26px;font-size:13px}
.err{color:var(--bad);font-weight:700;margin-top:8px}
h3{margin-bottom:12px;color:var(--acc2)}
</style>
</head>
<body>
<div class="container">
  <div class="banner">
    <div class="brand">__SERVER_NAME__</div>
    <div class="sub">Advanced VPS Control Panel • v__VERSION__ • Made by __DEV__</div>
  </div>

  <div id="loginCard" class="card" style="max-width:460px;margin:20px auto">
    <h3>🔐 Login</h3>
    <input id="discordId" placeholder="Discord User ID">
    <input id="vpsId" placeholder="VPS ID (e.g. 3)">
    <input id="token" placeholder="VPS Token (SVM-XXXX...)">
    <button class="btn b-acc" style="width:100%" onclick="login()">Connect</button>
    <div id="loginErr" class="err"></div>
  </div>

  <div id="panel" class="hidden">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div><h3 id="vpsName">VPS</h3><span id="vpsStatus" class="pill off">…</span></div>
        <div class="row">
          <button class="btn b-ok" onclick="action('start')">▶ Start</button>
          <button class="btn b-warn" onclick="action('stop')">⏸ Stop</button>
          <button class="btn b-info" onclick="action('restart')">🔁 Restart</button>
          <button class="btn b-bad" onclick="if(confirm('Reinstall ERASES all data. Continue?')) action('reinstall')">🔄 Reinstall</button>
          <button class="btn b-acc" onclick="logout()">Logout</button>
        </div>
      </div>
      <div class="grid" style="margin-top:16px">
        <div class="kv"><div class="k">CPU</div><div class="v" id="cpu">–</div><div class="bar"><div id="cpuBar" style="width:0%"></div></div></div>
        <div class="kv"><div class="k">RAM</div><div class="v" id="ram">–</div><div class="bar"><div id="ramBar" style="width:0%"></div></div></div>
        <div class="kv"><div class="k">Disk</div><div class="v" id="disk">–</div></div>
        <div class="kv"><div class="k">Uptime</div><div class="v" id="uptime" style="font-size:13px">–</div></div>
        <div class="kv"><div class="k">Local IP (Static)</div><div class="v" id="lip">–</div></div>
        <div class="kv"><div class="k">Server IPv4</div><div class="v" id="pip">–</div></div>
        <div class="kv"><div class="k">SSH (Public)</div><div class="v" id="ssh" style="font-size:13px">–</div></div>
        <div class="kv"><div class="k">Config / OS</div><div class="v" id="cfg" style="font-size:13px">–</div></div>
      </div>
    </div>

    <div class="card">
      <h3>🌐 Port Forwarding (IPv4)</h3>
      <div class="row"><input id="newPort" placeholder="VPS port (e.g. 8080)" style="max-width:220px">
      <button class="btn b-acc" onclick="addPort()">➕ Add Port</button></div>
      <table id="portsTable"><thead><tr><th>Public</th><th>→ VPS Port</th><th>Created</th><th></th></tr></thead><tbody></tbody></table>
    </div>

    <div class="card">
      <h3>💻 Live Terminal <span style="color:var(--mut);font-size:12px">(auto-connects to your VPS)</span></h3>
      <div class="row" style="margin-bottom:8px">
        <button class="btn b-ok" onclick="connectTerm()">Connect</button>
        <button class="btn b-bad" onclick="disconnectTerm()">Disconnect</button>
      </div>
      <div id="terminal"></div>
    </div>
  </div>
  <div class="foot">__SERVER_NAME__ • Made by <b>__DEV__</b></div>
</div>
<script>
let auth=null, term=null, ws=null, statTimer=null;
async function api(path, method='GET', body=null){
  const r = await fetch(path,{method,headers:{'Content-Type':'application/json','X-Discord-Id':auth.d,'X-Vps-Id':auth.v,'X-Token':auth.t},body:body?JSON.stringify(body):null});
  const j = await r.json().catch(()=>({ok:false,error:'bad response'}));
  if(!r.ok) throw new Error(j.error||('HTTP '+r.status));
  return j;
}
async function login(){
  const d=document.getElementById('discordId').value.trim(), v=document.getElementById('vpsId').value.trim(), t=document.getElementById('token').value.trim();
  auth={d,v,t};
  try{
    const j=await api('/api/status');
    localStorage.setItem('svm_auth',JSON.stringify(auth));
    document.getElementById('loginCard').classList.add('hidden');
    document.getElementById('panel').classList.remove('hidden');
    render(j); statTimer=setInterval(refresh,5000); connectTerm();
  }catch(e){document.getElementById('loginErr').textContent='Login failed: '+e.message; auth=null;}
}
function logout(){clearInterval(statTimer);disconnectTerm();localStorage.removeItem('svm_auth');location.reload();}
function render(j){
  document.getElementById('vpsName').textContent='🖥 '+j.container_name+' (#'+j.id+')';
  const st=document.getElementById('vpsStatus');
  st.textContent=j.suspended?'SUSPENDED':j.status.toUpperCase();
  st.className='pill '+(j.status==='running'&&!j.suspended?'on':'off');
  document.getElementById('cpu').textContent=(j.cpu||0).toFixed(1)+'%';
  document.getElementById('cpuBar').style.width=(j.cpu||0)+'%';
  document.getElementById('ram').textContent=j.ram.used+'/'+j.ram.total+' MB ('+(j.ram.pct||0).toFixed(1)+'%)';
  document.getElementById('ramBar').style.width=(j.ram.pct||0)+'%';
  document.getElementById('disk').textContent=j.disk; document.getElementById('uptime').textContent=j.uptime;
  document.getElementById('lip').textContent=j.static_ip||'DHCP'; document.getElementById('pip').textContent=j.public_ip;
  document.getElementById('ssh').textContent=j.ssh||'—';
  document.getElementById('cfg').textContent=j.config+' • '+j.os_version;
  const tb=document.querySelector('#portsTable tbody'); tb.innerHTML='';
  (j.ports||[]).forEach(p=>{const tr=document.createElement('tr');
    tr.innerHTML='<td><b>'+j.public_ip+':'+p.host_port+'</b></td><td>'+p.vps_port+'</td><td>'+p.created_at.slice(0,10)+'</td><td><button class="btn b-bad" style="padding:5px 10px" onclick="delPort('+p.id+')">✖</button></td>';
    tb.appendChild(tr);});
}
async function refresh(){try{render(await api('/api/status'));}catch(e){}}
async function action(a){
  try{const j=await api('/api/action','POST',{action:a}); alert(j.message||'Done'); setTimeout(refresh,3000);}
  catch(e){alert('Action failed: '+e.message);}
}
async function addPort(){
  const p=parseInt(document.getElementById('newPort').value);
  if(!p||p<1||p>65535){alert('Invalid port');return;}
  try{const j=await api('/api/ports','POST',{vps_port:p}); alert('Forwarded: '+j.public_ip+':'+j.host_port+' → '+p); refresh();}
  catch(e){alert('Failed: '+e.message);}
}
async function delPort(id){try{await api('/api/ports/'+id,'DELETE');refresh();}catch(e){alert(e.message);}}
function connectTerm(){
  if(!term){term=new Terminal({cursorBlink:true,fontSize:14,theme:{background:'#05070d'}});term.open(document.getElementById('terminal'));}
  disconnectTerm();
  const proto=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(proto+'://'+location.host+'/ws/terminal?d='+auth.d+'&v='+auth.v+'&t='+encodeURIComponent(auth.t));
  ws.onopen=()=>term.writeln('\x1b[32m● Connected to VPS terminal\x1b[0m');
  ws.onmessage=e=>term.write(e.data);
  ws.onclose=()=>term.writeln('\r\n\x1b[31m● Disconnected\x1b[0m');
  ws.onerror=()=>term.writeln('\r\n\x1b[31m● Connection error (is the VPS running?)\x1b[0m');
  term.onData(d=>{if(ws&&ws.readyState===1)ws.send(d);});
}
function disconnectTerm(){if(ws){try{ws.close();}catch(e){} ws=null;}}
(function(){const s=localStorage.getItem('svm_auth');if(s){try{auth=JSON.parse(s);document.getElementById('discordId').value=auth.d;document.getElementById('vpsId').value=auth.v;document.getElementById('token').value=auth.t;login();}catch(e){}}})();
</script>
</body>
</html>"""

def panel_html() -> str:
    return (PANEL_HTML.replace("__SERVER_NAME__", SERVER_NAME)
                      .replace("__VERSION__", BOT_VERSION)
                      .replace("__DEV__", BOT_DEVELOPER))

def _panel_auth(request) -> Optional[tuple]:
    d = request.headers.get('X-Discord-Id') or request.query.get('d')
    v = request.headers.get('X-Vps-Id') or request.query.get('v')
    t = request.headers.get('X-Token') or request.query.get('t')
    if not (d and v and t):
        return None
    found = find_vps_by_id(int(v)) if str(v).isdigit() else None
    if not found:
        return None
    owner, vps = found
    if str(owner) != str(d) or vps.get('vps_token') != t:
        return None
    return owner, vps

async def panel_index(request):
    return web.Response(text=panel_html(), content_type='text/html')

async def panel_status(request):
    auth = _panel_auth(request)
    if not auth:
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    owner, vps = auth
    stats = await get_container_stats(vps['container_name'], vps['node_id'])
    public_ip = get_public_ip()
    ssh = None
    if vps.get('pinggy_address'):
        h, p = vps['pinggy_address'].split(':')
        ssh = f"ssh root@{h} -p {p}"
    elif vps.get('static_ip'):
        ssh = f"ssh root@{vps['static_ip']}"
    return web.json_response({
        "ok": True, "id": vps['id'], "container_name": vps['container_name'],
        "status": stats['status'] if not vps.get('suspended') else 'suspended',
        "suspended": vps.get('suspended', False),
        "cpu": stats['cpu'], "ram": stats['ram'], "disk": stats['disk'], "uptime": stats['uptime'],
        "static_ip": vps.get('static_ip') or '', "public_ip": public_ip, "ssh": ssh,
        "config": vps.get('config', 'Custom'), "os_version": vps.get('os_version', ''),
        "ports": get_vps_forwards(vps['container_name']),
    })

async def panel_action(request):
    auth = _panel_auth(request)
    if not auth:
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    owner, vps = auth
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get('action', '')
    container, node_id = vps['container_name'], vps['node_id']
    if vps.get('suspended'):
        return web.json_response({"ok": False, "error": "VPS is suspended"}, status=403)
    try:
        if action == 'start':
            await safe_start_container(container, node_id)
            await recreate_port_forwards(container)
            msg = "VPS started"
        elif action == 'stop':
            await execute_lxc(container, f"stop {container}", timeout=120, node_id=node_id)
            msg = "VPS stopped"
        elif action == 'restart':
            await execute_lxc(container, f"restart {container}", timeout=180, node_id=node_id)
            await recreate_port_forwards(container)
            msg = "VPS restarted"
        elif action == 'reinstall':
            asyncio.create_task(_panel_reinstall(owner, vps))
            msg = "Reinstall started in background — check Discord DM for new password"
        else:
            return web.json_response({"ok": False, "error": "Unknown action"}, status=400)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    # Update status in DB
    for uid, lst in vps_data.items():
        for v in lst:
            if v['container_name'] == container:
                if action == 'start': v['status'] = 'running'
                elif action == 'stop': v['status'] = 'stopped'
                save_vps_data()
    return web.json_response({"ok": True, "message": msg})

async def _panel_reinstall(owner, vps):
    """Background reinstall triggered from web panel (keeps same OS, new password)."""
    container, node_id = vps['container_name'], vps['node_id']
    try:
        ram_gb = int(vps['ram'].replace('GB', '')); cpu = int(vps['cpu']); disk_gb = int(vps['storage'].replace('GB', ''))
        await execute_lxc(container, f"delete {container} --force", node_id=node_id)
        root_password, pinggy, static_ip = await deploy_container(container, vps.get('os_version', 'ubuntu:22.04'), ram_gb, cpu, disk_gb, node_id)
        vps.update({"status": "running", "root_password": root_password, "pinggy_address": pinggy,
                    "static_ip": static_ip, "created_at": datetime.now().isoformat()})
        save_vps_data()
        try:
            user = await bot.fetch_user(int(owner))
            dm = create_success_embed("VPS Reinstalled (Web Panel)", f"`{container}` was reinstalled from the web panel.")
            build_ssh_dm_fields(dm, vps, vps.get('id') or 0)
            await user.send(embed=dm)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Panel reinstall failed for {container}: {e}")

async def panel_add_port(request):
    auth = _panel_auth(request)
    if not auth:
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    owner, vps = auth
    try:
        body = await request.json()
        vps_port = int(body.get('vps_port'))
        if not 1 <= vps_port <= 65535:
            raise ValueError
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid port"}, status=400)
    if get_user_used_ports(owner) >= get_user_allocation(owner):
        return web.json_response({"ok": False, "error": "Port quota exceeded — ask an admin for more"}, status=403)
    host_port = await create_port_forward(owner, vps['container_name'], vps_port, vps['node_id'])
    if not host_port:
        return web.json_response({"ok": False, "error": "Could not assign host port"}, status=500)
    return web.json_response({"ok": True, "host_port": host_port, "public_ip": get_public_ip()})

async def panel_del_port(request):
    auth = _panel_auth(request)
    if not auth:
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    owner, vps = auth
    fid = int(request.match_info['id'])
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT user_id FROM port_forwards WHERE id = ?', (fid,))
    row = cur.fetchone(); conn.close()
    if not row or row[0] != owner:
        return web.json_response({"ok": False, "error": "Not found"}, status=404)
    ok, _ = await remove_port_forward(fid)
    return web.json_response({"ok": ok})

async def panel_terminal_ws(request):
    """WebSocket live terminal: proxies keystrokes to `lxc exec <container> -- bash`."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    auth = _panel_auth(request)
    if not auth:
        await ws.close(message=b'Unauthorized')
        return ws
    owner, vps = auth
    if vps.get('suspended'):
        await ws.close(message=b'VPS suspended')
        return ws
    node = get_node(vps['node_id'])
    if not node or not node['is_local']:
        await ws.send_str("Terminal is only available on the local node.\r\n")
        await ws.close()
        return ws
    container = vps['container_name']
    try:
        proc = await asyncio.create_subprocess_exec(
            "lxc", "exec", container, "--", "bash", "-l",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except Exception as e:
        await ws.send_str(f"Failed to attach: {e}\r\n")
        await ws.close()
        return ws

    async def pump_out():
        try:
            while True:
                chunk = await proc.stdout.read(1024)
                if not chunk:
                    break
                await ws.send_str(chunk.decode('utf-8', errors='replace'))
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

    pump = asyncio.create_task(pump_out())
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT and proc.stdin:
                proc.stdin.write(msg.data.encode('utf-8', errors='replace'))
                await proc.stdin.drain()
            elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.CLOSED, web.WSMsgType.ERROR):
                break
    finally:
        pump.cancel()
        try:
            proc.kill()
        except Exception:
            pass
    return ws

def start_web_panel(loop):
    if not (PANEL_ENABLED and HAS_AIOHTTP):
        logger.info("Web panel disabled or aiohttp missing.")
        return
    app = web.Application()
    app.router.add_get('/', panel_index)
    app.router.add_get('/api/status', panel_status)
    app.router.add_post('/api/action', panel_action)
    app.router.add_post('/api/ports', panel_add_port)
    app.router.add_delete('/api/ports/{id}', panel_del_port)
    app.router.add_get('/ws/terminal', panel_terminal_ws)
    runner = web.AppRunner(app)
    async def _start():
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PANEL_PORT)
        await site.start()
        logger.info(f"Web panel running on 0.0.0.0:{PANEL_PORT}")
    loop.create_task(_start())

# ============================================================================
# EVENTS + STARTUP
# ============================================================================
@bot.event
async def on_ready():
    print_banner()
    logger.info(f'{bot.user} connected! | {BOT_NAME} v{BOT_VERSION}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,
                                                        name=f"{BOT_NAME} VPS Manager"))
    # Application emoji sync (auto-upload + ID fix from emoji.py)
    try:
        import sync_emojis
        await sync_emojis.run_sync(DISCORD_TOKEN)
    except ImportError:
        logger.warning("sync_emojis.py not found — skipping emoji sync.")
    except Exception as e:
        logger.error(f"Emoji sync failed: {e}")
    # Web control panel
    start_web_panel(asyncio.get_running_loop())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=create_error_embed("Missing Argument", f"Check usage with `{PREFIX}help`."))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=create_error_embed("Invalid Argument", "Please check your input and try again."))
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(embed=create_error_embed("Access Denied", str(error) or "You need admin permissions."))
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(embed=create_error_embed("System Error", "An unexpected error occurred."))

if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN env var is not set!")
        sys.exit(1)
    bot.run(DISCORD_TOKEN)
