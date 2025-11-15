# IPv6 DNS Updater for Speedport Smart 4 Plus

Automatically keeps the "Primary DNSv6 Server" in a Telekom Speedport Smart 4 Plus updated to match the Global Unicast IPv6 (GUA) assigned to a Raspberry Pi.

The script periodically checks the Raspberry Pi's IPv6 on a specified interface and, when changed, logs into the router web UI and updates the IPv6 DNS field.

---

## Features

- Detects Raspberry Pi IPv6 GUA on a given interface (default `eth0`).
- Logs into Speedport Smart 4 Plus web UI and updates *Primary DNSv6 Server*.
- Runs continuously with a configurable check interval (default: 1 hour).
- Uses Selenium (Chromium) to automate the browser.
- Closes Chromium after each update (no leftover windows).
- Logging output instead of prints.

---

## Warning & Security

- **Do not** expose your router admin interface to the public internet.
- Keep your router admin password secret. Use environment variables or a secret store.
- Test the script locally first.
- Update router firmware and Raspberry Pi packages.

---

## Requirements

- Raspberry Pi (or any Linux) with Python 3.8+
- Chromium browser and matching chromedriver (strongly recommended to install via apt)
- `pip` and virtualenv (recommended)
- Network access: the Pi must reach the router UI (typically `http://192.168.2.1`)

---

## Installing on Raspberry Pi (recommended steps)

1. Update and install system dependencies (Chromium + chromedriver):
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y chromium chromium-driver python3 python3-venv python3-pip
