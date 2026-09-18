# ⚡ SVM VPS v9.2 — LXC/LXD Discord Bot

<p align="center">
  <img src="https://img.shields.io/badge/Version-v9.2-blue?style=for-the-badge&logo=github" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%7C%20Debian-E95420?style=for-the-badge&logo=ubuntu&logoColor=white" alt="OS">
  <img src="https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord">
  <img src="https://img.shields.io/badge/LXD%2FLXC-Container-832561?style=for-the-badge&logo=canonical&logoColor=white" alt="LXD">
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status">
</p>

---

<p align="center">
  Fully automated Discord bot for managing LXC/LXD-based VPS containers — creation, resizing, suspension, port forwarding, multi-node support, and web control panel, all from Discord.
</p>

<p align="center">
  <b>Made with ❤️ by <a href="https://github.com/AnkitKing7">AnkitCoder</a></b><br>
  <b>Repository:</b> <a href="https://github.com/AnkitKing7/Svm-v9bot">AnkitKing7/Svm-v9bot</a>
</p>

---

## 💡 Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Discord.py-5865F2?style=flat-square&logo=discord&logoColor=white" />
  <img src="https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white" />
  <img src="https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/WebSockets-010101?style=flat-square&logo=socketdotio&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white" />
</p>

---

## ✨ Features

- 🎨 **Custom Emojis Auto-Sync:** Integrated `emoji.py` and `sync_emojis.py` automatic synchronization.
- 🚀 **Complete VPS Control:** Create, manage, reinstall, suspend, and share containers effortlessly.
- 🔑 **Per-User SSH Details:** Dedicated Public IPv4 with port-forwarding, local IP, and root password generation.
- 📌 **Static IP System:** Persistent `10.0.3.x` addresses for all LXC containers.
- 🌐 **Web Control Panel:**
  - Login via Discord ID + VPS ID + VPS Token.
  - Live status tracking and power operations (Start / Stop / Restart / Reinstall).
  - Add IPv4 Port Forwarding dynamically.
  - **Live Web Terminal:** Built-in WebSocket connection direct to `lxc exec`.
- 🤖 **Gemini AI Assistant:** Interactive technical assistance via the `!ai` command.
- 🌈 **Rainbow Console Banner:** Custom colorful startup interface.

---

## 📋 Requirements

- 🖥️ **Server:** Fresh Ubuntu or Debian server with **root access**.
- 🤖 **Discord:** Bot Token from [Discord Developer Portal](https://discord.com/developers/applications).
- 🆔 **Admin ID:** Your Discord User ID.
- 📦 **Dependencies:** `git` (`sudo apt install git -y`).

---

## 🚀 Quick Installation

Clone the repository and run the automated installer script as root:

```bash
git clone [https://github.com/AnkitKing7/Svm-v9.2-bot.git](https://github.com/AnkitKing7/Svm-v9.2-bot.git)
cd Svm-v9.2-bot
chmod +x install.sh
sudo ./install.sh
