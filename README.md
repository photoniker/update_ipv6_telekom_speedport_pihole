

# Speedport IPv6 DNS Auto-Update

Automatically updates the IPv6 DNS server entry on a **Telekom Speedport Smart 4 Plus** router using Selenium.
This script runs on a **Raspberry Pi** and periodically checks the Pi’s IPv6 GUA.
If the IPv6 changes, the value is automatically updated in the router’s web interface. 

This is a workaround to get pihole running with the Speedport Router.

---

## ⭐ Features

* Reads current IPv6 GUA of the Raspberry Pi
* Detects IPv6 changes
* Logs into Speedport Smart 4 Plus via Chromium + Selenium
* Updates *Primary IPv6 DNS Server* field
* Saves settings automatically
* Runs as background systemd service
* Full logging
* Optional command-line progress bar
* Written with typing hints + Google-style docstrings

---

## 📌 Why is this needed?

Telekom Speedport routers often **change the IPv6 prefix daily**.
This means a Raspberry Pi running **Pi-hole** or any DNS service will receive a new IPv6 GUA.

Unfortunately, Speedport routers **do not support DNS hostnames → only raw IPv6**.

This script fully automates the update process.

---

# 1. Installation

Below are the recommended installation steps for a **fresh Raspberry Pi OS (Debian)**.

---

## 1.1 Update system

```bash
sudo apt update
sudo apt upgrade -y
```

---

## 1.2 Install Pi-hole (optional)

```bash
curl -sSL https://install.pi-hole.net | bash
```

---

## 1.3 Install Python + pip

```bash
sudo apt install -y python3 python3-pip python3-venv
```

---

## 1.4 Install Chromium + Chromedriver

### Chromium

```bash
sudo apt install -y chromium-browser
```

### Check architecture

```bash
uname -m
```

### Download Chromedriver for ARM64 (Raspberry Pi 4/5)

```bash
sudo apt install -y chromium-chromedriver
```

Verify:

```bash
chromedriver --version
```

---

## 1.5 Install project dependencies

Create project folder:

```bash
mkdir speedport-updater
cd speedport-updater
```

Create *virtual environment* (recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

---

# 2. Configuration

Edit the script:

```python
routerIP = "http://192.168.2.1"
routerPassword = "YOUR_ROUTER_PASSWORD"
interface = "eth0"
interval = 3600   # seconds
```

---

# 3. Running the Script

Run manually:

```bash
python3 speedport_updater.py
```

Run continuously (with progress bar):

```bash
python3 speedport_updater.py --progress
```

Logs appear under:

```
/var/log/speedport-updater.log
```

---

# 4. Using a systemd background service

A **systemd service** keeps your script running forever — even after reboots.
This is the Linux-native method for long-running background processes.

### Create service file:

```bash
sudo nano /etc/systemd/system/speedport-updater.service
```

Paste:

```ini
[Unit]
Description=Speedport IPv6 DNS Auto-Updater
After=network-online.target

[Service]
Type=simple
ExecStart=/home/pi/speedport-updater/venv/bin/python /home/pi/speedport-updater/speedport_updater.py
Restart=always
User=pi
WorkingDirectory=/home/pi/speedport-updater
StandardOutput=append:/var/log/speedport-updater.log
StandardError=append:/var/log/speedport-updater.log

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable speedport-updater
sudo systemctl start speedport-updater
```

Check status:

```bash
systemctl status speedport-updater
```

---

# 5. requirements.txt

```
selenium
typing_extensions
```

(On Raspberry Pi, `chromedriver` and `chromium` are installed via apt.)

---

# 6. Script Architecture Notes

* Uses **Selenium WebDriver** to control the router’s UI
* Uses **WebDriverWait** instead of raw sleeps
* Uses **logging**, not print()
* Modular structure:

  * `get_ipv6_gua()`
  * `update_dns_ipv6()`
  * `main()` event loop
* Graceful Chromium cleanup via `driver.quit()`

---

# 7. Troubleshooting

### Login button stays disabled

Script uses JavaScript injection:

```python
driver.execute_script("arguments[0].removeAttribute('disabled')", login_button)
```

### IPv6 not detected

Check:

```bash
ip -6 addr show eth0
```

Look for **global dynamic**.

---

# 8. License

MIT – free to use and modify.

---

# 9. Contributing

Pull requests welcome!

---

If you want, I can also:

✅ Generate the full ZIP upload layout
✅ Provide an example folder structure
✅ Add badges (code style, Python version)
✅ Add screenshots for GitHub
✅ Write a German translation

##### Just tell me!
