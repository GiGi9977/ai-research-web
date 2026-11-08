"""Mutation analysis: copy backend/app + a test suite into a temp dir, apply each mutant,
run pytest, and report which mutants were killed (tests failed) or survived.

Usage (from backend/):  python tests/mutation/run_mutation.py [path/to/test_dir]
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mutants import MUTANTS

BACKEND = Path(__file__).resolve().parents[2]


def run(test_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copytree(BACKEND / "app", work / "app", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(test_dir, work / "tests", ignore=shutil.ignore_patterns("__pycache__", "mutation"))
        (work / "tests" / "__init__.py").touch()
        shutil.copy(BACKEND / "pytest.ini", work / "pytest.ini")
        cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-p", "no:cov"]
        base = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
        if base.returncode != 0:
            sys.exit("Suite fails on the unmutated app; fix it first:\n" + base.stdout[-2000:])
        killed = 0
        for mid, rel, old, new, desc in MUTANTS:
            path = work / rel
            src = path.read_text()
            assert src.count(old) == 1, f"{mid}: snippet not unique/found in {rel}"
            path.write_text(src.replace(old, new))
            res = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
            path.write_text(src)
            status = "KILLED" if res.returncode != 0 else "survived"
            killed += res.returncode != 0
            print(f"{mid} {status:8} {rel:28} {desc}")
        print(f"\nMutation score: {killed}/{len(MUTANTS)} = {killed / len(MUTANTS):.0%}")


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BACKEND / "tests")
