"""Secret guard: nothing that looks like a credential may be committed.

This repo is public (decision D1/D10): before any code is pushed, this test
must be green. It scans every tracked-ish file in the repo (excluding .git,
.venv, caches) for common credential shapes and for risky filenames.

Deliberate design note: the patterns are built by string concatenation so this
file never literally contains the tokens it hunts for, and this file is also
excluded from its own scan.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
THIS_FILE = Path(__file__)

# Built via concatenation so this source file does not self-match.
SECRET_PATTERNS = [
    ("github personal token (classic)", re.compile("^ghp_" + "[A-Za-z0-9]{36}$")),
    ("github oauth token", re.compile("^gho_" + "[A-Za-z0-9]{36}$")),
    ("github fine-grained PAT", re.compile("^github_pat_" + "[A-Za-z0-9_]{22,}$")),
    ("github app token", re.compile("^ghs_" + "[A-Za-z0-9]{36}$")),
    ("aws access key id", re.compile("^AKIA" + "[0-9A-Z]{16}$")),
    ("aws secret access key", re.compile(
        "(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]"
    )),
    ("slack bot token", re.compile("^xoxb-" + "[0-9A-Za-z-]{10,}$")),
    ("private key block", re.compile(
        "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    )),
    ("generic high-entropy assignment", re.compile(
        "(?i)(secret|passwd|password|api_key)\\s*=\\s*['\"][A-Za-z0-9+/=_-]{24,}['\"]"
    )),
]

RISKY_FILES = {".env", "credentials.json", "id_rsa", ".npmrc", ".netrc"}
ALLOWED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def iter_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO_ROOT)
        if path == THIS_FILE:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        yield relative, path


class TestNoSecrets:
    def test_no_file_contains_a_credential_shape(self):
        offenders = []
        for relative, path in iter_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{relative}: {label}")
        assert offenders == [], "possible secrets committed:\n" + "\n".join(offenders)

    def test_no_risky_files_are_committed(self):
        offenders = [
            str(relative)
            for relative, path in iter_files()
            if path.name in RISKY_FILES or path.suffix in ALLOWED_SUFFIXES
        ]
        assert offenders == [], "credential-shaped files present:\n" + "\n".join(offenders)

    def test_gitignore_blocks_env_files_and_venv(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        for needle in (".env", ".venv/", "*.pem", "*.key"):
            assert needle in gitignore, f".gitignore must cover {needle}"
