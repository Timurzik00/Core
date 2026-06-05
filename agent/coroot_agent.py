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
AGENT_FAMILY = os.environ.get("AGENT_FAMILY") or "default"
AGENT_VERSION = os.environ.get("AGENT_VERSION", "v1.0.0")

def _get_host_hostname() -> str:
    for path in ["/host/proc/sys/kernel/hostname", "/hostfs/proc/sys/kernel/hostname"]:
        try:
            return Path(path).read_text().strip()
        except OSError:
            pass
    return os.environ.get("AGENT_HOSTNAME", socket.gethostname())

AGENT_HOSTNAME = _get_host_hostname()
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
    return response.json()["uuid"]


def load_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _resolve_host_path(path: str) -> Path:
    """Преобразовать абсолютный путь хоста в путь внутри контейнера с учётом HOST_FS_ROOT."""
    if HOST_FS_ROOT:
        return Path(HOST_FS_ROOT) / path.lstrip("/")
    return Path(path)


def write_file_spec(file_spec):
    path = _resolve_host_path(file_spec["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(file_spec["content"])
    try:
        path.chmod(0o644)
    except OSError:
        pass
    print(f"[agent] wrote file {path}")
    return path


def read_file_content(file_path: str) -> str | None:
    try:
        path = _resolve_host_path(file_path)
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
            raise RuntimeError(f"CLI inside container failed with {exit_code}: {stderr or stdout}")
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


def apply_config(config: dict) -> tuple[dict, dict | None]:
    """
    Применить один конфиг (file + cli).
    Возвращает (applied_files, cli_result).
    """
    if not config:
        raise ValueError("Empty config")

    if not config.get("file") and not config.get("cli"):
        raise ValueError("Config contains no file or cli section")

    applied_files = {}
    cli_result = None

    if config.get("file"):
        file_spec = config["file"]
        write_file_spec(file_spec)
        applied_files[file_spec["path"]] = {
            "content": file_spec["content"],
            "is_in_sync": True,
        }

    if config.get("cli"):
        cli_result = execute_cli(config["cli"])

    return applied_files, cli_result


def _config_key(config: dict) -> str:
    """Уникальный ключ конфига для сравнения — service, legacy family, или file.path."""
    return config.get("service") or config.get("family") or (config.get("file") or {}).get("path") or "default"


def _configs_changed(prev: list[dict], curr: list[dict]) -> list[dict]:
    """
    Вернуть только те конфиги из curr, которые изменились по сравнению с prev.
    Сравниваем по ключу (service / file.path) и содержимому целиком.
    """
    prev_map = {_config_key(c): c for c in prev}
    changed = []
    for cfg in curr:
        key = _config_key(cfg)
        if prev_map.get(key) != cfg:
            changed.append(cfg)
    return changed


def apply_configs(configs: list[dict], prev_configs: list[dict] | None = None) -> tuple[dict, list, list[str]]:
    """
    Применить список конфигов, пропуская неизменившиеся.

    prev_configs — конфиги из предыдущей применённой версии (из state).
    Возвращает (applied_files, cli_results, skipped_families).
    """
    all_files: dict = {}
    all_cli: list = []
    skipped: list[str] = []

    to_apply = _configs_changed(prev_configs, configs) if prev_configs is not None else configs

    if prev_configs is not None and len(to_apply) < len(configs):
        skipped_keys = {_config_key(c) for c in configs} - {_config_key(c) for c in to_apply}
        skipped = list(skipped_keys)
        print(f"[agent] skipping unchanged configs: {skipped}")

    if not to_apply:
        print("[agent] all configs unchanged, nothing to apply")
        return all_files, all_cli, skipped

    for i, config in enumerate(to_apply):
        service_tag = _config_key(config)
        print(f"[agent] applying config {i + 1}/{len(to_apply)} (service={service_tag})")
        applied_files, cli_result = apply_config(config)
        all_files.update(applied_files)
        if cli_result:
            all_cli.append(cli_result)

    return all_files, all_cli, skipped


def collect_all_files_state(configs: list[dict]) -> dict:
    """
    Прочитать с диска фактическое состояние ВСЕХ файлов из desired configs.
    Используется для построения снапшота: чтобы он отражал состояние всех
    управляемых файлов, а не только тех, что только что применились.
    """
    result: dict = {}
    for config in configs:
        if not isinstance(config, dict):
            continue
        file_spec = config.get("file")
        if not file_spec or not file_spec.get("path"):
            continue
        path = file_spec["path"]
        expected = file_spec.get("content", "")

        try:
            full_path = _resolve_host_path(path)
            if full_path.exists() and full_path.is_file():
                current = full_path.read_text(errors="replace")
                result[path] = {
                    "content": current,
                    "is_in_sync": current == expected,
                }
            else:
                result[path] = {
                    "content": None,
                    "is_in_sync": False,
                }
        except Exception as exc:
            print(f"[agent] failed to read {path} for snapshot: {exc}")
            result[path] = {
                "content": None,
                "is_in_sync": False,
            }
    return result


def capture_current_snapshot(applied_files=None, cli_results=None):
    snapshot = {
        "hostname": AGENT_HOSTNAME,
        "family": AGENT_FAMILY,
        "timestamp": time.time(),
    }

    if COROOT_AGENT_CONTAINER and docker_client:
        try:
            container = docker_client.containers.get(COROOT_AGENT_CONTAINER)
            snapshot["container_status"] = container.status
            snapshot["container_image"] = container.image.tags if container.image else []
        except Exception as e:
            snapshot["container_error"] = str(e)

    if applied_files:
        snapshot["files"] = applied_files

    if cli_results:
        snapshot["cli_results"] = cli_results

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


def extract_configs(payload: dict) -> list[dict]:
    """
    Поддерживает оба формата ответа от Core:
      - новый:  {"version": N, "config": {"configs": [...]}}
      - старый: {"version": N, "config": {...}}  (один конфиг)
    """
    config = payload.get("config", {})

    # Если Core вернул обёртку с массивом внутри config.configs
    if isinstance(config, dict) and "configs" in config:
        return config["configs"]

    # Иначе — один конфиг (обратная совместимость)
    if config:
        return [config]

    return []


# ========== AD-HOC COMMANDS ==========

def cmd_read_file(params: dict) -> dict:
    """Прочитать файл с хоста."""
    path = params.get("path")
    if not path:
        raise ValueError("path is required")

    full_path = _resolve_host_path(path)

    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not full_path.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    content = full_path.read_text(errors="replace")
    return {"content": content, "size": len(content)}


def cmd_list_dir(params: dict) -> dict:
    """
    Получить список файлов/папок в директории.
    Параметры: path (обязательно).
    Возвращает: {entries: [{name, type, size, modified}], path}
    """
    path = params.get("path") or "/"

    full_path = _resolve_host_path(path)

    if not full_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not full_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    try:
        for entry in sorted(full_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                    "modified": stat.st_mtime,
                })
            except (PermissionError, OSError) as e:
                entries.append({
                    "name": entry.name,
                    "type": "error",
                    "error": str(e),
                })
    except PermissionError as e:
        raise PermissionError(f"Cannot list directory: {e}")

    return {"path": path, "entries": entries, "total": len(entries)}


COMMAND_HANDLERS = {
    "read_file": cmd_read_file,
    "list_dir": cmd_list_dir,
}


def fetch_pending_commands(agent_uuid: str) -> list[dict]:
    url = f"{CORE_URL}/api/v1/agent/{agent_uuid}/commands/pending/list"
    try:
        response = session.get(url, timeout=5)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[agent] failed to fetch commands: {exc}")
        return []


def submit_command_result(agent_uuid: str, command_id: int, result: dict | None = None, error: str | None = None):
    url = f"{CORE_URL}/api/v1/agent/{agent_uuid}/commands/{command_id}/result"
    payload = {"result": result, "error": error}
    try:
        session.post(url, json=payload, timeout=10).raise_for_status()
    except Exception as exc:
        print(f"[agent] failed to submit result for cmd {command_id}: {exc}")


def process_commands(agent_uuid: str):
    """Забрать pending-команды и выполнить их."""
    cmds = fetch_pending_commands(agent_uuid)
    for cmd in cmds:
        cmd_id = cmd["id"]
        cmd_type = cmd["command_type"]
        params = cmd.get("params", {})

        print(f"[agent] processing command {cmd_id} ({cmd_type})")
        handler = COMMAND_HANDLERS.get(cmd_type)
        if not handler:
            submit_command_result(agent_uuid, cmd_id, error=f"unknown command type: {cmd_type}")
            continue

        try:
            result = handler(params)
            submit_command_result(agent_uuid, cmd_id, result=result)
        except Exception as exc:
            print(f"[agent] command {cmd_id} failed: {exc}")
            submit_command_result(agent_uuid, cmd_id, error=str(exc))


def sync_loop(agent_uuid):
    state = load_state()
    last_applied_version = state.get("last_applied_version")
    # Конфиги предыдущей применённой версии (для diff по service)
    last_applied_configs: list[dict] | None = state.get("last_applied_configs")

    while True:
        try:
            url = f"{CORE_URL}/api/v1/agent/{agent_uuid}/config"
            response = session.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            version = payload.get("version")
            configs = extract_configs(payload)

            if version is None:
                print("[agent] config response has no version, skipping")
            elif version != last_applied_version:
                print(f"[agent] detected new desired config version {version}, applying {len(configs)} config(s)")
                try:
                    _applied_files, all_cli, skipped = apply_configs(configs, last_applied_configs)
                    last_applied_version = version
                    last_applied_configs = configs
                    state["agent_uuid"] = agent_uuid
                    state["last_applied_version"] = version
                    state["last_applied_configs"] = configs
                    state["last_error"] = None
                    save_state(state)

                    # Для снапшота собираем СОСТОЯНИЕ ВСЕХ управляемых файлов с диска,
                    # а не только тех что только что применились. Это даёт полную картину
                    # для UI и позволяет Core корректно обновлять managed_files.
                    all_files_state = collect_all_files_state(configs)
                    snapshot = capture_current_snapshot(all_files_state, all_cli if all_cli else None)
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
                # Различаем "конфиг ещё не задан" и "агента нет в Core"
                detail = ""
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:
                    detail = exc.response.text or ""

                if "Agent not found" in detail:
                    print("[agent] Core says this agent does not exist — re-registering")
                    try:
                        new_uuid = register_agent()
                        uuid_file = Path("./agent_uuid.txt")
                        uuid_file.write_text(new_uuid)
                        agent_uuid = new_uuid
                        # Сбрасываем локальное состояние применённого конфига —
                        # это новый агент, у него нет истории
                        last_applied_version = None
                        last_applied_configs = None
                        state.clear()
                        state["agent_uuid"] = new_uuid
                        save_state(state)
                        print(f"[agent] re-registered with new uuid={new_uuid}")
                    except Exception as reg_exc:
                        print(f"[agent] re-registration failed: {reg_exc}")
                else:
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

        # Вместо простого sleep — крутимся POLL_INTERVAL секунд,
        # проверяя ad-hoc команды каждые 15 секунд.
        elapsed = 0
        while elapsed < POLL_INTERVAL:
            try:
                process_commands(agent_uuid)
            except Exception as exc:
                print(f"[agent] command processing error: {exc}")
            time.sleep(15)
            elapsed += 15


if __name__ == "__main__":
    uuid_file = Path("./agent_uuid.txt")
    if uuid_file.exists():
        agent_uuid = uuid_file.read_text().strip()
    else:
        agent_uuid = register_agent()
        uuid_file.write_text(agent_uuid)
        print(f"[agent] registered uuid={agent_uuid}")

    sync_loop(agent_uuid)
