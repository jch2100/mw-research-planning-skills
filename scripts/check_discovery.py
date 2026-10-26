"""Read-only Codex app-server discovery check; never creates a thread or model turn."""
from pathlib import Path
import json
import queue
import shutil
import subprocess
import sys
import threading
import time

root = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
binary = shutil.which("codex")
if not binary:
    raise SystemExit("Codex CLI not found; discovery is not tested.")
process = subprocess.Popen([binary, "app-server"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
messages = queue.Queue()
def read_lines():
    for line in process.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            pass
threading.Thread(target=read_lines, daemon=True).start()
def send(value):
    process.stdin.write(json.dumps(value) + "\n")
    process.stdin.flush()
def receive(message_id):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            value = messages.get(timeout=1)
        except queue.Empty:
            if process.poll() is not None:
                raise RuntimeError("Codex app-server exited before responding")
            continue
        if value.get("id") == message_id:
            if "error" in value:
                raise RuntimeError(str(value["error"]))
            return value["result"]
    raise RuntimeError("Codex app-server response timed out")
try:
    send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "mw-skill-discovery-check", "version": "0.1.0"}}})
    receive(1)
    send({"method": "initialized"})
    send({"id": 2, "method": "skills/list", "params": {"cwds": [str(root)], "forceReload": True}})
    result = receive(2)
    expected = {"mw-research-office-hours", "mw-business-plan-review"}
    found = [s for entry in result.get("data", []) for s in entry.get("skills", []) if s.get("name") in expected]
    assert {s["name"] for s in found} == expected, "Expected skills were not both discovered"
    for skill in found:
        assert skill.get("enabled", True), "Skill is disabled"
        assert Path(skill["path"]).resolve().is_relative_to(root / ".agents" / "skills"), "Wrong discovery source"
    print(json.dumps({"scope": "fresh-codex-process-discovery-only", "passed": True, "model_turns": 0, "skills": [{"name": s["name"], "scope": s.get("scope"), "enabled": s.get("enabled", True)} for s in found]}, ensure_ascii=False, indent=2))
finally:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
