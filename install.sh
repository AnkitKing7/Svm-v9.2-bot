#!/bin/bash
# ============================================================
#  SVM VPS v9.2 — Installer
#  LXD/LXC + Python deps + Web Panel + Gemini AI + systemd
#  Made by AnkitCoder
# ============================================================

set -e

# ---------- Colors ----------
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; BLU='\033[0;34m'
MAG='\033[0;35m'; CYN='\033[0;36m'; WHT='\033[1;37m'; NC='\033[0m'

rainbow_line() {
    local text="$1"
    local colors=("$RED" "$YEL" "$GRN" "$CYN" "$BLU" "$MAG")
    local i=0
    for (( j=0; j<${#text}; j++ )); do
        c=${colors[$((i % 6))]}
        printf '%b%s%b' "$c" "${text:$j:1}" "$NC"
        i=$((i+1))
    done
    echo ""
}

ascii_banner() {
    rainbow_line ' ███████╗██╗   ██╗███╗   ███╗    ██╗   ██╗ █████╗      ██████╗ '
    rainbow_line ' ██╔════╝██║   ██║████╗ ████║    ██║   ██║██╔══██╗     ╚════██╗'
    rainbow_line ' ███████╗██║   ██║██╔████╔██║    ██║   ██║╚██████║      █████╔╝'
    rainbow_line ' ╚════██║╚██╗ ██╔╝██║╚██╔╝██║    ╚██╗ ██╔╝ ╚═══██║     ██╔═══╝ '
    rainbow_line ' ███████║ ╚████╔╝ ██║ ╚═╝ ██║     ╚████╔╝ █████╔╝ ██╗ ███████╗'
    rainbow_line ' ╚══════╝  ╚═══╝  ╚═╝     ╚═╝      ╚═══╝  ╚════╝  ╚═╝ ╚══════╝'
    echo ""
    rainbow_line '              ~ Made by AnkitCoder ~'
    echo ""
}

banner() {
    clear
    ascii_banner
    echo -e "${WHT}  ─────────────────────────────────────────────────────────────${NC}"
    echo -e "  ${CYN}SVM VPS v9.2 — LXC/LXD Discord Bot + Web Panel + AI Installer${NC}"
    echo -e "  ${CYN}Ubuntu & Debian supported | Static IPs | IPv4 Port Forwarding${NC}"
    echo -e "  ${MAG}Made by AnkitCoder${NC}"
    echo -e "${WHT}  ─────────────────────────────────────────────────────────────${NC}\n"
}

step()  { echo -e "${GRN}[+]${NC} $1"; }
warn()  { echo -e "${YEL}[!]${NC} $1"; }
err()   { echo -e "${RED}[x]${NC} $1"; }

need_root() {
    if [ "$EUID" -ne 0 ]; then
        err "Please run this script as root (sudo ./install.sh)"
        exit 1
    fi
}

# ---------- OS selection ----------
choose_os() {
    echo -e "${WHT}Select your OS:${NC}"
    echo -e "  ${YEL}1)${NC} Ubuntu"
    echo -e "  ${YEL}2)${NC} Debian"
    read -rp "$(echo -e "${CYN}Enter choice [1-2]: ${NC}")" OS_CHOICE
}

install_lxd_ubuntu() {
    step "Updating system (Ubuntu)..."
    apt update && apt upgrade -y
    step "Installing LXC utilities..."
    apt install lxc lxc-utils -y
    step "Installing snapd..."
    apt install snapd -y
    systemctl enable --now snapd.socket
    step "Installing LXD via snap..."
    snap install lxd
    step "Adding ${SUDO_USER:-root} to lxd group..."
    usermod -aG lxd "${SUDO_USER:-root}" || true
    step "Initializing LXD (auto/minimal config)..."
    lxd init --auto
    step "Installing bridge/uidmap utilities..."
    apt update
    apt install lxc lxc-utils bridge-utils uidmap -y
}

install_lxd_debian() {
    step "Updating system (Debian)..."
    apt update && apt upgrade -y
    step "Installing snapd..."
    apt install snapd -y
    systemctl enable --now snapd.socket
    step "Linking snap directory..."
    ln -sf /var/lib/snapd/snap /snap
    step "Installing LXD via snap..."
    snap install lxd
    step "Adding ${SUDO_USER:-root} to lxd group..."
    usermod -aG lxd "${SUDO_USER:-root}" || true
    step "Initializing LXD (auto/minimal config)..."
    lxd init --auto
}

install_python_stack() {
    step "Installing Python 3 / pip..."
    apt install python3-pip python3-venv -y
    step "Allowing pip to break system packages (PEP 668 override)..."
    mkdir -p ~/.config/pip
    echo -e "[global]\nbreak-system-packages = true" > ~/.config/pip/pip.conf
    step "Installing Python dependencies (discord.py, aiohttp, requests, colorama)..."
    pip3 install -U discord.py aiohttp requests colorama
}

deploy_bot() {
    step "Deploying bot files to /root ..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local missing=0
    for f in bot.py emoji.py sync_emojis.py; do
        if [ -f "$SCRIPT_DIR/$f" ]; then
            cp "$SCRIPT_DIR/$f" /root/$f
            step "Deployed $f"
        else
            if [ "$f" = "bot.py" ]; then
                err "bot.py not found next to install.sh. Place it in the same folder and re-run."
                exit 1
            else
                warn "$f not found (optional, skipping)"
                missing=1
            fi
        fi
    done
}

configure_env() {
    echo -e "\n${WHT}────────── Bot Configuration ──────────${NC}"
    read -rp "$(echo -e "${CYN}Enter your Discord Bot Token: ${NC}")" DISCORD_TOKEN
    read -rp "$(echo -e "${CYN}Enter your Main Admin Discord ID: ${NC}")" MAIN_ADMIN_ID
    read -rp "$(echo -e "${CYN}Enter Gemini API Key (leave empty to skip AI): ${NC}")" GEMINI_API_KEY
    read -rp "$(echo -e "${CYN}Web Panel Port [8080]: ${NC}")" PANEL_PORT
    PANEL_PORT=${PANEL_PORT:-8080}
    read -rp "$(echo -e "${CYN}Enable Application Emoji Sync on startup? [Y/n]: ${NC}")" EMOJI_SYNC_ANS
    EMOJI_SYNC="true"
    [ "$EMOJI_SYNC_ANS" = "n" ] || [ "$EMOJI_SYNC_ANS" = "N" ] && EMOJI_SYNC="false"

    if [ -z "$DISCORD_TOKEN" ] || [ -z "$MAIN_ADMIN_ID" ]; then
        err "Token and Admin ID cannot be empty."
        exit 1
    fi
}

open_firewall() {
    step "Opening web panel port ${PANEL_PORT} (ufw, if installed)..."
    if command -v ufw >/dev/null 2>&1; then
        ufw allow "${PANEL_PORT}/tcp" >/dev/null 2>&1 || true
    fi
}

create_service() {
    step "Creating systemd service..."
    cat > /etc/systemd/system/bot.service <<EOF
[Unit]
Description=SVM VPS v9.2 Bot (AnkitCoder)
After=network.target

[Service]
User=root
WorkingDirectory=/root
ExecStart=/usr/bin/python3 /root/bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=DISCORD_TOKEN=${DISCORD_TOKEN}
Environment=MAIN_ADMIN_ID=${MAIN_ADMIN_ID}
Environment=BOT_NAME=Svm-v9.2
Environment=SERVER_NAME=Svm v9.2
Environment=BOT_VERSION=9.2-PRO
Environment=BOT_DEVELOPER=AnkitCoder
Environment=PANEL_PORT=${PANEL_PORT}
Environment=PANEL_ENABLED=true
Environment=GEMINI_API_KEY=${GEMINI_API_KEY}
Environment=EMOJI_SYNC=${EMOJI_SYNC}

[Install]
WantedBy=multi-user.target
EOF
    step "Reloading systemd daemon..."
    systemctl daemon-reload
    step "Starting bot service..."
    systemctl restart bot
    step "Enabling bot service on boot..."
    systemctl enable bot
}

final_message() {
    local PUB_IP
    PUB_IP=$(curl -s --max-time 5 https://ifconfig.me/ip || echo "YOUR_SERVER_IP")
    echo ""
    ascii_banner
    echo -e "${WHT}────────────────────────────────────────${NC}"
    echo -e "${GRN}  SVM VPS v9.2 — Installation complete!${NC}"
    echo -e "${WHT}────────────────────────────────────────${NC}"
    echo -e "  ${CYN}Service:${NC}      bot.service"
    echo -e "  ${CYN}Status:${NC}       systemctl status bot"
    echo -e "  ${CYN}Logs:${NC}         journalctl -u bot -f"
    echo -e "  ${CYN}Restart:${NC}      systemctl restart bot"
    echo -e "  ${CYN}Web Panel:${NC}    http://${PUB_IP}:${PANEL_PORT}"
    echo -e "  ${MAG}Made by AnkitCoder${NC}"
    echo -e "${WHT}────────────────────────────────────────${NC}\n"
}

main() {
    banner
    need_root
    choose_os
    case "$OS_CHOICE" in
        1) install_lxd_ubuntu ;;
        2) install_lxd_debian ;;
        *) err "Invalid choice. Exiting."; exit 1 ;;
    esac
    install_python_stack
    deploy_bot
    configure_env
    open_firewall
    create_service
    final_message
}

main "$@"
