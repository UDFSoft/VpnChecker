
#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import requests


VPN_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 15
API_TIMEOUT = 10

API_BASE_URL = "https://vpn.udfsoft.com/api/v1/checker/servers"
API_TOKEN = os.environ.get("API_KEY")

# Директивы, запрещённые в непроверенных OpenVPN-конфигах.
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
    """Загружает список серверов и тип проверки из корня JSON."""
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    servers = data.get("servers")
    server_type = data.get("type")

    if not isinstance(servers, list):
        raise ValueError("JSON must contain a 'servers' array")

    if not isinstance(server_type, str) or not server_type.strip():
        raise ValueError("JSON must contain a non-empty root 'type'")

    return servers, server_type


def api_headers():
    """Формирует заголовки API с ключом авторизации."""
    if not API_TOKEN:
        raise ValueError("API_KEY environment variable is not set")

    return {
        "X-Api-Key": API_TOKEN,
        "X-APP-VERSION": "-125",
    }


def server_url(server_id):
    """Возвращает URL API конкретного сервера."""
    if server_id is None or not str(server_id).strip():
        raise ValueError("Server ID is missing")

    return f"{API_BASE_URL}/{quote(str(server_id), safe='')}"


def download_config(url):
    """Загружает OpenVPN-конфигурацию по vpnConfigUrl."""
    if not isinstance(url, str) or not (
        url.startswith("https://") or url.startswith("http://")
    ):
        raise ValueError("Only HTTP/HTTPS config URLs are allowed")

    response = requests.get(
        url,
        headers=api_headers(),
        timeout=DOWNLOAD_TIMEOUT,
        allow_redirects=False,
    )
    response.raise_for_status()

    if len(response.content) > 1024 * 1024:
        raise ValueError("Config file is too large")

    return response.text


def validate_config(config):
    """
    Отклоняет конфиги с директивами, которые могут запускать
    команды или подключать дополнительные конфигурационные файлы.
    """
    for line in config.splitlines():
        line = line.strip()

        if not line or line.startswith("#") or line.startswith(";"):
            continue

        directive = line.split(None, 1)[0].lower()

        if directive in BLOCKED_DIRECTIVES:
            raise ValueError(f"Unsafe OpenVPN directive: {directive}")

    if "<connection>" in config.lower():
        raise ValueError("Connection blocks are not supported")


def report_result(server_id, success, server_type):
    """
    Отправляет результат проверки на API.

    success=1 — подключение установлено.
    success=0 — подключение не удалось.
    type — значение из корня servers.json.
    """
    try:
        response = requests.get(
            f"{server_url(server_id)}/results",
            params={
                "success": 1 if success else 0,
                "type": server_type,
            },
            headers=api_headers(),
            timeout=API_TIMEOUT,
            allow_redirects=False,
        )
        response.raise_for_status()

        print(
            f"  Result reported: server_id={server_id}, "
            f"success={1 if success else 0}, type={server_type}"
        )

    except (requests.RequestException, ValueError) as error:
        print(f"  Failed to report server result: {error}")


def check_server(server, server_type):
    """Проверяет VPN-сервер и отправляет результат проверки."""
    country = server.get("country", "Unknown")
    server_id = server.get("id")
    url = server.get("vpnConfigUrl")
    username = server.get("userName")
    password = server.get("userPassword")

    print(f"\nChecking: {country} — {url}")

    success = False

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

            if username and password:
                auth_path.write_text(
                    f"{username}\n{password}\n",
                    encoding="utf-8",
                )
                auth_path.chmod(0o600)

                openvpn_args.extend([
                    "--auth-user-pass", str(auth_path),
                ])

            with open(log_path, "w", encoding="utf-8") as log_file:
                process = subprocess.Popen(
                    openvpn_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

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
                        success = True
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
                if process.poll() is None:
                    process.terminate()

                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            log_text = log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if success:
                print(f"WORKING: {country}")
            else:
                print(f"FAILED: {country}")

                for line in log_text.splitlines()[-10:]:
                    print(f"  {line}")

        # Отправляем результат после фактической проверки VPN.
        report_result(server_id, success, server_type)

    except Exception as error:
        print(f"ERROR: {country}: {error}")

    return success


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: vpn_checker.py INPUT.json OUTPUT.json",
            file=sys.stderr,
        )
        return 2

    if not API_TOKEN:
        print(
            "ERROR: API_KEY environment variable is not set",
            file=sys.stderr,
        )
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    try:
        servers, server_type = load_servers(input_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: Failed to load input: {error}", file=sys.stderr)
        return 2

    if not servers:
        print("Input server list is empty; refusing to overwrite output.")
        return 1

    working_servers = []

    for server in servers:
        if not isinstance(server, dict):
            print("Skipping invalid server entry")
            continue

        if check_server(server, server_type):
            working_servers.append(server)

    if not working_servers:
        print(
            "No working servers found. "
            "Preserving the previous output file."
        )
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "type": server_type,
                    "servers": working_servers,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")

    except OSError as error:
        print(f"ERROR: Failed to write output: {error}", file=sys.stderr)
        return 2

    print(
        f"\nFinished: {len(working_servers)} of "
        f"{len(servers)} servers are working."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
