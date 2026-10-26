"""Check that distribution defects are caught, then restore and verify again."""
from pathlib import Path
import shutil
import tempfile
from verify_package import verify

root = Path(__file__).resolve().parents[1]
scratch = root / ".work"
scratch.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="integrity-", dir=scratch) as temp:
    copied = Path(temp).resolve() / "package"
    assert copied.is_relative_to(scratch.resolve())
    shutil.copytree(root, copied, ignore=shutil.ignore_patterns(".git", ".work", "__pycache__"))
    assert verify(copied)["passed"]
    skill = copied / ".agents/skills/mw-research-office-hours"
    license_path = skill / "LICENSE"
    license_bytes = license_path.read_bytes()
    license_path.write_bytes(b"MIT without required original notice")
    try:
        verify(copied)
    except AssertionError as error:
        assert "Original MIT notice changed" in str(error)
    else:
        raise AssertionError("Damaged MIT notice was not caught")
    license_path.write_bytes(license_bytes)
    assert verify(copied)["passed"]
    instruction = skill / "SKILL.md"
    original = instruction.read_text(encoding="utf-8")
    instruction.write_text(original + "\n[required](references/missing.md)\n", encoding="utf-8")
    try:
        verify(copied)
    except AssertionError as error:
        assert "Missing local resource" in str(error)
    else:
        raise AssertionError("Missing standalone resource was not caught")
    instruction.write_text(original, encoding="utf-8")
    assert verify(copied)["passed"]
print("PASS: normal package, damaged license blocked, missing resource blocked, repaired package")
