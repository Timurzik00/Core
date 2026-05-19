import json
import os
import shlex
import socket
import subprocess
import time
from pathlib import Path

import requests

try:
    import docker
except ImportError:
    docker = None

CORE_URL = os.environ.get("CORE_URL", "http://127.0.0.1:8000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
STATE_FILE = Path(os.environ.get("AGENT_STATE_FILE", "./agent_state.json"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"
AGENT_FAMILY = os.environ.get("AGENT_FAMILY", "coroot")
AGENT_VERSION = os.environ.get("AGENT_VERSION", "v1.0.0")
AGENT_HOSTNAME = os.environ.get("AGENT_HOSTNAME", socket.gethostname())
COROOT_AGENT_CONTAINER = os.environ.get("COROOT_AGENT_CONTAINER")
HOST_FS_ROOT = os.environ.get("HOST_FS_ROOT")

session = requests.Session()
session.trust_env = False

if COROOT_AGENT_CONTAINER and docker is None:
    raise RuntimeError("Python docker SDK is required when COROOT_AGENT_CONTAINER is set")

if COROOT_AGENT_CONTAINER:
    docker_client = docker.from_env()
else:
    docker_client = None


def build_agent_info():
    return {
        "agent": {
            "family": AGENT_FAMILY,
            "hostname": AGENT_HOSTNAME,
            "version": AGENT_VERSION,
        }
    }


def register_agent():
    url = f"{CORE_URL}/api/v1/agent/register"
    response = session.post(url, json=build_agent_info(), timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload["uuid"]


def load_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def write_file_spec(file_spec):
    if HOST_FS_ROOT:
        path = Path(HOST_FS_ROOT) / file_spec["path"].lstrip("/")
    else:
        path = Path(file_spec["path"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(file_spec["content"])
    try:
        path.chmod(0o644)
    except OSError:
        pass
    print(f"[agent] wrote file {path}")
    return path


def read_file_content(file_path: str) -> str | None:
    """Прочитать содержимое файла"""
    try:
        if HOST_FS_ROOT:
            path = Path(HOST_FS_ROOT) / file_path.lstrip("/")
        else:
            path = Path(file_path)
        
        if path.exists() and path.is_file():
            return path.read_text()
    except Exception as e:
        print(f"[agent] failed to read file {file_path}: {e}")
    return None


def execute_cli(cli):
    binary = cli.get("binary")
    args = cli.get("args", "")

    if not binary:
        raise ValueError("cli.binary is required")

    if DRY_RUN:
        print(f"[agent] dry-run execute: {binary} {args}")
        return None

    argv = [binary] + shlex.split(args)

    if COROOT_AGENT_CONTAINER:
        if docker_client is None:
            raise RuntimeError("Docker client is not available")

        container = docker_client.containers.get(COROOT_AGENT_CONTAINER)
        print(f"[agent] exec in container {COROOT_AGENT_CONTAINER}: {argv}")
        result = container.exec_run(argv, stdout=True, stderr=True, demux=True)
        exit_code, output = result.exit_code, result.output
        stdout, stderr = output if isinstance(output, tuple) else (output, None)
        stdout = stdout.decode().strip() if stdout else ""
        stderr = stderr.decode().strip() if stderr else ""
        if exit_code != 0:
            raise RuntimeError(
                f"CLI inside container failed with {exit_code}: {stderr or stdout}"
            )
        print(f"[agent] executed CLI in container {COROOT_AGENT_CONTAINER} successfully")
        if stdout:
            print(stdout)
        return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

    if not Path(binary).exists():
        raise FileNotFoundError(f"CLI binary not found: {binary}")

    result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"CLI failed with {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
        )
    print(f"[agent] executed CLI {binary} successfully")
    if result.stdout:
        print(result.stdout.strip())
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def apply_config(config):
    cli_result = None
    applied_files = {}

    if not config:
        raise ValueError("Empty config")

    if config.get("file"):
        file_spec = config["file"]
        path = write_file_spec(file_spec)
        applied_files[file_spec["path"]] = {
            "content": file_spec["content"],
            "is_in_sync": True,
        }

    if config.get("cli"):
        cli_result = execute_cli(config["cli"])

    if not config.get("file") and not config.get("cli"):
        raise ValueError("Config contains no file or cli section")

    return applied_files, cli_result


def capture_current_snapshot(applied_files=None, cli_result=None):
    """
    Захватить расширенный снимок конфига с информацией о файлах и CLI результатах
    """
    snapshot = {
        "hostname": AGENT_HOSTNAME,
        "family": AGENT_FAMILY,
        "timestamp": time.time(),
    }
    
    # Информация о Docker контейнере если есть
    if COROOT_AGENT_CONTAINER and docker_client:
        try:
            container = docker_client.containers.get(COROOT_AGENT_CONTAINER)
            snapshot["container_status"] = container.status
            snapshot["container_image"] = container.image.tags if container.image else []
        except Exception as e:
            snapshot["container_error"] = str(e)
    
    # Информация о файлах
    if applied_files:
        snapshot["files"] = applied_files
    
    # Результаты CLI команд
    if cli_result:
        snapshot["cli_results"] = cli_result
    
    return snapshot


def report_status(agent_uuid, last_applied_version=None, last_error=None, current_snapshot=None):
    url = f"{CORE_URL}/api/v1/agent/{agent_uuid}/status"
    payload = {
        "last_applied_version": last_applied_version,
        "last_error": last_error,
        "current_snapshot": current_snapshot,
    }
    response = session.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def sync_loop(agent_uuid):
    state = load_state()
    last_applied_version = state.get("last_applied_version")
    last_config = state.get("last_config")

    while True:
        try:
            url = f"{CORE_URL}/api/v1/agent/{agent_uuid}/config"
            response = session.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            config = payload.get("config", {})
            version = payload.get("version")

            if version is None:
                print("[agent] config response has no version, skipping")
            elif version != last_applied_version:
                print(f"[agent] detected new desired config version {version}, applying")
                try:
                    applied_files, cli_result = apply_config(config)
                    last_applied_version = version
                    state["agent_uuid"] = agent_uuid
                    state["last_applied_version"] = version
                    state["last_config"] = config
                    state["last_error"] = None
                    save_state(state)
                    
                    # Захватить расширенный снимок с файлами и результатами
                    snapshot = capture_current_snapshot(applied_files, cli_result)
                    report_status(agent_uuid, last_applied_version, None, snapshot)
                except Exception as exc:
                    error_text = str(exc)
                    print(f"[agent] failed to apply config: {error_text}")
                    state["last_error"] = error_text
                    save_state(state)
                    
                    snapshot = capture_current_snapshot()
                    report_status(agent_uuid, last_applied_version, error_text, snapshot)
            else:
                print("[agent] no changes")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                print("[agent] no desired config yet, waiting")
            else:
                print(f"[agent] poll error: {exc}")
                try:
                    snapshot = capture_current_snapshot()
                    report_status(agent_uuid, last_applied_version, str(exc), snapshot)
                except Exception:
                    pass
        except Exception as exc:
            print(f"[agent] poll error: {exc}")
            try:
                snapshot = capture_current_snapshot()
                report_status(agent_uuid, last_applied_version, str(exc), snapshot)
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    uuid_file = Path("./agent_uuid.txt")
    if uuid_file.exists():
        agent_uuid = uuid_file.read_text().strip()
    else:
        agent_uuid = register_agent()
        uuid_file.write_text(agent_uuid)
        print(f"[agent] registered uuid={agent_uuid}")

    sync_loop(agent_uuid)