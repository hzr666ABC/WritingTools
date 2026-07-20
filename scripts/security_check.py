"""Repository release gate for secrets and private build artifacts."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from pathlib import PurePosixPath


SECRET_PATTERNS = {
    "Groq API key": re.compile(rb"(?<![A-Za-z0-9])gsk_[A-Za-z0-9]{20,}(?![A-Za-z0-9])"),
    "OpenAI API key": re.compile(rb"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{20,}(?![A-Za-z0-9])"),
    "Google API key": re.compile(rb"(?<![A-Za-z0-9])AIza[A-Za-z0-9_-]{20,}(?![A-Za-z0-9])"),
    "GitHub token": re.compile(rb"(?<![A-Za-z0-9])(?:ghp|github_pat)_[A-Za-z0-9_]{20,}(?![A-Za-z0-9])"),
    "AWS access key": re.compile(rb"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    "Private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "JWT": re.compile(rb"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"),
}
FORBIDDEN_NAMES = {"config.json", "history.json", ".env"}
FORBIDDEN_SUFFIXES = {
    ".exe", ".msi", ".zip", ".7z", ".pfx", ".p12", ".pem", ".key", ".log"
}
MAX_BLOB_BYTES = 25_000_000


def git(*args: str, input_data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], input=input_data, capture_output=True, check=True
    ).stdout


def tracked_paths() -> list[str]:
    return [
        item
        for item in git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
        .decode("utf-8")
        .split("\0")
        if item
    ]


def check_paths(paths: list[str]) -> list[str]:
    findings = []
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        lowered = path.name.lower()
        if lowered in FORBIDDEN_NAMES and not lowered.endswith(".example"):
            findings.append(f"forbidden tracked local-data file: {raw_path}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden tracked private/binary artifact: {raw_path}")
    return findings


def object_inventory(history: bool) -> list[tuple[str, str]]:
    if history:
        lines = git("rev-list", "--objects", "--all").splitlines()
        output = []
        for line in lines:
            parts = line.split(b" ", 1)
            output.append((parts[0].decode(), parts[1].decode("utf-8", "replace") if len(parts) > 1 else ""))
        return output
    output = []
    for path in tracked_paths():
        oid = git("rev-parse", f"HEAD:{path}").decode().strip()
        output.append((oid, path))
    return output


def scan_worktree(paths: list[str]) -> list[str]:
    findings = []
    for path in paths:
        file_path = Path(path)
        try:
            size = file_path.stat().st_size
            data = file_path.read_bytes()
        except OSError as error:
            findings.append(f"unable to inspect tracked file {path}: {error}")
            continue
        if size > MAX_BLOB_BYTES:
            findings.append(f"oversized tracked file ({size} bytes): {path}")
            continue
        if b"\0" in data[:8192]:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1
                fingerprint = hashlib.sha256(match.group()).hexdigest()[:10]
                findings.append(f"{label}: {path}:{line} fingerprint={fingerprint}")
    return findings


def scan_objects(objects: list[tuple[str, str]]) -> list[str]:
    unique = {}
    for oid, path in objects:
        unique.setdefault(oid, path)
    request = ("\n".join(unique) + "\n").encode()
    checks = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", input_data=request)
    metadata = {
        fields[0].decode(): (fields[1].decode(), int(fields[2]))
        for line in checks.splitlines()
        if len(fields := line.split()) == 3
    }
    findings = []
    for oid, path in unique.items():
        object_type, size = metadata.get(oid, ("", 0))
        if object_type != "blob":
            continue
        if size > MAX_BLOB_BYTES:
            findings.append(f"oversized Git blob ({size} bytes): {path or oid[:12]}")
            continue
        data = git("cat-file", "blob", oid)
        if b"\0" in data[:8192]:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1
                fingerprint = hashlib.sha256(match.group()).hexdigest()[:10]
                findings.append(
                    f"{label}: {path or '<deleted>'}:{line} fingerprint={fingerprint}"
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true", help="scan every reachable Git object")
    args = parser.parse_args()
    paths = tracked_paths()
    findings = check_paths(paths)
    findings.extend(scan_worktree(paths))
    if args.history:
        findings.extend(scan_objects(object_inventory(True)))
    if findings:
        print("Security check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("Security check passed: no secrets or private release artifacts detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
