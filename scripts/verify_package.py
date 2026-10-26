"""Offline distribution checks. These checks do not evaluate model behavior."""
from pathlib import Path
import hashlib
import json
import re
import sys

NAMES = ("mw-research-office-hours", "mw-business-plan-review")
LICENSE_HASH = "e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c"

def verify(root: Path) -> dict:
    root = root.resolve()
    checked = []
    for name in NAMES:
        folder = root / ".agents" / "skills" / name
        source = folder / "SKILL.md"
        raw = source.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM: {source}"
        text = raw.decode("utf-8")
        parts = text.split("---", 2)
        assert len(parts) == 3 and parts[0] == "", f"Frontmatter missing: {source}"
        fields = dict(line.split(":", 1) for line in parts[1].strip().splitlines())
        assert fields.get("name", "").strip() == name, f"Wrong skill name: {source}"
        assert fields.get("description", "").strip(), f"Description missing: {source}"
        assert set(fields) == {"name", "description"}, f"Unexpected runtime metadata: {source}"
        assert "TODO" not in text, f"Unfinished scaffold: {source}"
        assert not re.search(r"gstack-skill-start|~[/\\]\.claude|mode-handoff-hook", text), f"Upstream runtime dependency: {source}"
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (source.parent / target.split("#")[0]).resolve()
            assert resolved.is_relative_to(folder.resolve()), f"Skill is not self-contained: {target}"
            assert resolved.is_file(), f"Missing local resource: {target}"
        assert hashlib.sha256((folder / "LICENSE").read_bytes()).hexdigest() == LICENSE_HASH, f"Original MIT notice changed: {folder}"
        ui = (folder / "agents" / "openai.yaml").read_text(encoding="utf-8")
        assert f"${name}" in ui, f"UI invocation mismatch: {folder}"
        assert not re.search(r"^\s*(hooks|dependencies|policy):", ui, re.M), f"Unexpected installation behavior: {folder}"
        checked.append({"skill": name, "bytes": len(raw), "self_contained": True})
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "INSTRUCTOR.md", "tests/SCENARIOS.md", "qa/VALIDATION.md"):
        assert (root / name).is_file(), f"Required distribution material missing: {name}"
    for path in root.rglob("*"):
        if any(part in {".git", ".work", "__pycache__"} for part in path.relative_to(root).parts):
            continue
        assert not (path.is_file() and path.suffix.lower() in {".exe", ".dll", ".sh", ".ps1", ".bat", ".cmd"}), f"Unexpected executable distribution: {path}"
    return {"scope": "offline-package-integrity-not-behavior", "passed": True, "skills": checked}

if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
    except (AssertionError, OSError, UnicodeError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
