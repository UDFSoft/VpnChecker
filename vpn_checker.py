#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


VPN_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 15

# Директивы, которые не должны присутствовать в непроверенных конфигах.
BLOCKED_DIRECTIVES = {
    "up",
    "down",
    "route-up",
    "ipchange",
    "client-connect",
    "client-disconnect",
    "learn-address",
    "plugin",
    "script-security",
    "config",
    "include",
}


def load_servers(path):
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    servers = data.get("servers")

    if not isinstance(servers, list):
        raise ValueError("JSON must contain a 'servers' array")

    return servers


def download_config(url):
    if not isinstance(url, str) or not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("Only HTTP/HTTPS config URLs are allowed")

    headers = {
        "X-APP-VERSION": "-125"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=DOWNLOAD_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    if len(response.content) > 1024 * 1024:
        raise ValueError("Config file is too large")

    return response.text


def validate_config(config):
    """
    Отклоняем конфиги с директивами, которые могут запускать команды
    или подключать дополнительные конфигурационные файлы.
    """
    for line in config.splitlines():
        line = line.strip()

        if not line or line.startswith("#") or line.startswith(";"):
            continue

        directive = line.split(None, 1)[0].lower()

        if directive in BLOCKED_DIRECTIVES:
            raise ValueError(
                f"Unsafe OpenVPN directive: {directive}"
            )

    if "<connection>" in config.lower():
        raise ValueError("Connection blocks are not supported")


def check_server(server):
    country = server.get("country", "Unknown")
    url = server.get("vpnConfigUrl")
    username = server.get("userName")
    password = server.get("userPassword")

    print(f"\nChecking: {country} — {url}")

    try:
        config = download_config(url)
        validate_config(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "server.ovpn"
            log_path = Path(temp_dir) / "openvpn.log"
            auth_path = Path(temp_dir) / "credentials.txt"

            config_path.write_text(config, encoding="utf-8")

            openvpn_args = [
                "openvpn",
                "--config", str(config_path),
                "--verb", "3",
            ]

            # Если заданы имя пользователя и пароль, передаем их безопасно через файл авторизации
            if username and password:
                auth_path.write_text(f"{username}\n{password}\n", encoding="utf-8")
                openvpn_args.extend(["--auth-user-pass", str(auth_path)])

            # Не используем sudo. OpenVPN запускается с правами пользователя GitHub Actions.
            with open(log_path, "w", encoding="utf-8") as log_file:
                process = subprocess.Popen(
                    openvpn_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            connected = False
            start_time = time.monotonic()

            try:
                while time.monotonic() - start_time < VPN_TIMEOUT:
                    if process.poll() is not None:
                        break

                    log_text = log_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )

                    if "Initialization Sequence Completed" in log_text:
                        connected = True
                        break

                    if any(error in log_text for error in (
                        "AUTH_FAILED",
                        "Options error:",
                        "Cannot open TUN/TAP",
                        "Exiting due to fatal error",
                    )):
                        break

                    time.sleep(1)

            finally:
                process.terminate()

                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            if connected:
                print(f"WORKING: {country}")
                return True

            print(f"FAILED: {country}")

            # Выводим последние строки журнала для диагностики.
            log_text = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            for line in log_text.splitlines()[-10:]:
                print(f"  {line}")

            return False

    except Exception as error:
        print(f"ERROR: {country}: {error}")
        return False


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: vpn_checker.py INPUT.json OUTPUT.json",
            file=sys.stderr,
        )
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    servers = load_servers(input_path)

    if not servers:
        print("Input server list is empty; refusing to overwrite output.")
        return 1

    working_servers = []

    for server in servers:
        if not isinstance(server, dict):
            print("Skipping invalid server entry")
            continue

        if check_server(server):
            working_servers.append(server)

    if not working_servers:
        print(
            "No working servers found. "
            "Preserving the previous output file."
        )
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            {"servers": working_servers},
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

    print(
        f"\nFinished: {len(working_servers)} of "
        f"{len(servers)} servers are working."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
