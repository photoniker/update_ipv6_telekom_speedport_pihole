"""Continuously monitors the IPv6 GUA of a Raspberry Pi and, when it changes,
updates the "Primary DNSv6 Server" field in a Speedport Smart 4 Plus router
via the router web UI.

This script:
- finds the current IPv6 GUA on a given interface,
- logs in to the router web UI,
- writes the IPv6 as the primary IPv6 DNS,
- saves and closes the browser,
- repeats every `interval` seconds (default 3600 s).

Notes:
- Keep router password secret; consider using environment variables or a secrets store.
- On Raspberry Pi, install Chromium and chromedriver (see README).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from threading import Event
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Optional: if chrome driver manager is available, it can download a matching driver.
# It is included in requirements.txt as a fallback. On Raspberry Pi it's often
# better to install chromium-chromedriver via apt and reference /usr/bin/chromedriver.
try:
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
    WEBDRIVER_MANAGER_AVAILABLE = True
except Exception:
    WEBDRIVER_MANAGER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------
@dataclass
class Config:
    """Configuration for IPv6 DNS updater."""
    router_url: str = "http://192.168.2.1"
    router_password: str = ""  # please override (or set env var)
    interface: str = "eth0"
    check_interval: int = 60  # seconds; default: 1 hour
    chromium_paths: tuple[str, ...] = ("/usr/bin/chromium", "/usr/bin/chromium-browser")
    chromedriver_paths: tuple[str, ...] = ("/usr/bin/chromedriver", "/usr/bin/chromium-driver")
    headless: bool = False  # set True if you don't want UI to appear


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ipv6-dns-updater")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def get_ipv6_gua(interface: str = "eth0") -> Optional[str]:
    """Return the first global dynamic IPv6 address (GUA) for `interface`.

    Args:
        interface: Linux network interface name (e.g., "eth0").

    Returns:
        IPv6 address string (without prefix) if found, otherwise None.
    """
    try:
        output = subprocess.check_output(["ip", "-6", "addr", "show", interface], text=True)
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to run `ip` command: %s", exc)
        return None

    for line in output.splitlines():
        line = line.strip()
        # typical line: "inet6 2003:.../64 scope global dynamic"
        if line.startswith("inet6") and "global" in line and "dynamic" in line:
            # second token is address with prefix
            parts = line.split()
            if len(parts) >= 2:
                addr_with_prefix = parts[1]  # e.g. "2003:.../64"
                addr = addr_with_prefix.split("/")[0]
                return addr
    return None


def simple_progress_bar(seconds: int):
    for i in range(seconds):
        percent = (i + 1) / seconds * 100
        bar = "#" * int(percent / 4)
        sys.stdout.write(f"\rWaiting: [{bar:<25}] {percent:5.1f}%")
        sys.stdout.flush()
        time.sleep(1)
    print()


def find_executable(paths: tuple[str, ...]) -> Optional[str]:
    """Return first existing executable path from `paths` or None."""
    for p in paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


def create_chrome_driver(config: Config) -> webdriver.Chrome:
    """Create and return a Selenium Chrome webdriver.

    This function tries (in order):
    1. Use chromedriver binary installed at common system paths (recommended on Pi).
    2. If not found and webdriver-manager is available, download a matching driver.
    3. Raise RuntimeError if no driver can be used.

    Args:
        config: Config dataclass.

    Returns:
        An instance of selenium.webdriver.Chrome.
    """
    # prepare options
    chrome_opts = Options()
    # select a chromium/chrome binary if available
    chromium_bin = find_executable(config.chromium_paths)
    if chromium_bin:
        chrome_opts.binary_location = chromium_bin
        logger.debug("Using Chromium binary at %s", chromium_bin)
    else:
        logger.debug("No system chromium binary found in %s", config.chromium_paths)

    if config.headless:
        # note: you may need to tweak headless flags on older Chromium versions
        chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1200,900")

    # Try system chromedriver paths first
    chromedriver = find_executable(config.chromedriver_paths)
    service = None
    if chromedriver:
        logger.debug("Found chromedriver at %s", chromedriver)
        service = Service(chromedriver)
    else:
        if WEBDRIVER_MANAGER_AVAILABLE:
            # webdriver-manager will download a driver matching installed chrome/chromium
            logger.info("chromedriver not found on system; attempting to install via webdriver-manager")
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            logger.debug("webdriver-manager installed chromedriver at %s", driver_path)
        else:
            raise RuntimeError(
                "No chromedriver found and webdriver-manager unavailable. "
                "Install chromedriver (apt) or install webdriver-manager package."
            )

    # create driver
    try:
        driver = webdriver.Chrome(service=service, options=chrome_opts)
    except Exception as exc:
        logger.exception("Failed to start Chrome webdriver: %s", exc)
        raise
    return driver


def update_dns_ipv6_once(router_url: str, router_password: str, ipv6: str, config: Config) -> None:
    """Open the router web UI, login and set the Primary DNSv6 server to `ipv6`.

    The function will create and quit its own webdriver instance to ensure
    a fresh browser session every update.

    Args:
        router_url: Base URL of router (e.g., "http://192.168.2.1").
        router_password: Router admin password.
        ipv6: IPv6 address to write into the DNS field.
        config: Config dataclass.

    Raises:
        RuntimeError: on failures to update via web UI.
    """
    if not ipv6:
        raise ValueError("ipv6 must be provided")

    logger.info("Updating router with IPv6: %s", ipv6)

    driver = create_chrome_driver(config)
    wait = WebDriverWait(driver, 12)

    try:
        # open router page
        driver.get(router_url)
        logger.debug("Opened router URL: %s", router_url)

        # The Speedport first page may show a "Jump to Login" button
        try:
            start_btn = wait.until(EC.element_to_be_clickable((By.ID, "startbutton")))
            start_btn.click()
            logger.debug("Clicked 'Jump to Login' button")
        except TimeoutException:
            logger.debug("'Jump to Login' not present or not clickable; continuing")

        # fill password
        try:
            pw_field = wait.until(EC.element_to_be_clickable((By.ID, "router_password")))
            # router has a readonly trick - clicking/focusing should make it editable
            pw_field.click()
            pw_field.clear()
            pw_field.send_keys(router_password)
        except TimeoutException as exc:
            logger.exception("Password field not found or not interactable")
            raise RuntimeError("Login password field not found") from exc

        # enable login button (sometimes disabled via attribute)
        try:
            login_button = driver.find_element(By.ID, "loginbutton")
            driver.execute_script("arguments[0].removeAttribute('disabled')", login_button)
            time.sleep(0.2)
            login_button.click()
        except NoSuchElementException:
            logger.exception("Login button not found")
            raise RuntimeError("Login button not found")

        logger.info("Login successful (assumed). Waiting for navigation...")
        time.sleep(1.5)

        # navigate directly to connection page (page path observed on Speedport Smart 4 Plus)
        dns_url = router_url.rstrip("/") + "/html/content/internet/connection.html"
        driver.get(dns_url)

        # find DNS field and set value
        try:
            dns_field = wait.until(EC.element_to_be_clickable((By.NAME, "other_dns6_prim")))
            dns_field.clear()
            dns_field.send_keys(ipv6)
        except TimeoutException as exc:
            logger.exception("DNSv6 input field not found")
            raise RuntimeError("DNSv6 field not found") from exc

        # click save
        try:
            save_button = driver.find_element(By.ID, "savebutton")
            save_button.click()
        except NoSuchElementException:
            logger.exception("Save button not found")
            raise RuntimeError("Save button not found")

        logger.info("DNSv6 successfully set to %s", ipv6)

        # small wait to let router apply/save
        time.sleep(1.5)

    finally:
        # ensure chromium is closed after update — user requested that explicitly
        try:
            driver.quit()
            logger.debug("Chromium closed")
        except Exception:
            logger.exception("Error quitting driver; continuing")


def main_loop(router_url: str, router_password: str, config: Config) -> None:
    """Main monitoring loop. Checks IPv6 GUA every config.check_interval seconds.

    Args:
        router_url: Router base url.
        router_password: Router admin password.
        config: Config dataclass.
    """
    logger.info("Starting IPv6 DNS updater loop with interval %s seconds", config.check_interval)
    last_ipv6: Optional[str] = None
    stop_event = Event()

    try:
        while not stop_event.wait(0):  # immediate evaluation, then break to timed wait below
            current_ipv6 = get_ipv6_gua(config.interface)
            logger.info("Current Raspberry Pi IPv6: %s", current_ipv6)

            if current_ipv6 is None:
                logger.warning("No IPv6 address found on interface '%s'.", config.interface)
            else:
                if current_ipv6 != last_ipv6:
                    logger.info("IPv6 changed: %s -> %s", last_ipv6, current_ipv6)
                    try:
                        update_dns_ipv6_once(router_url, router_password, current_ipv6, config)
                        last_ipv6 = current_ipv6
                    except Exception as exc:
                        logger.exception("Failed updating router: %s", exc)
                else:
                    logger.debug("IPv6 unchanged.")

            # interruptible sleep
            logger.info("Waiting %s seconds until next check...", config.check_interval)
            # wait returns True if event set, False if timeout elapsed
            stopped = stop_event.wait(config.check_interval)
            if stopped:
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user (KeyboardInterrupt). Exiting.")
    except Exception:
        logger.exception("Unexpected error in main loop")
    finally:
        logger.info("Updater stopped.")


# ---------------------------------------------------------------------------
# CLI bootstrap
# ---------------------------------------------------------------------------
def _get_router_password_from_env() -> Optional[str]:
    return os.getenv("SPEEDPORT_PASSWORD")


def _cli_main() -> int:
    """Entry point if run as script."""
    # default config; override via env or CLI if you implement it later
    cfg = Config()
    cfg.router_password = _get_router_password_from_env() or cfg.router_password
    if not cfg.router_password:
        logger.error("Router password not set. Set SPEEDPORT_PASSWORD env var or edit script.")
        return 2

    # On Raspberry Pi you probably want interface "eth0" if using wired
    logger.info("Using interface: %s", cfg.interface)

    try:
        main_loop(cfg.router_url, cfg.router_password, cfg)
        return 0
    except Exception:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    sys.exit(_cli_main())
