"""Portable local foundation commands; no third-party dependencies."""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_ACTIONS = {
    "config": ["config", "--quiet"],
    "up": ["up", "--detach", "--wait", "--wait-timeout", "120"],
    "up-backend": ["up", "--build", "--detach", "--wait", "--wait-timeout", "180"],
    "down": ["down"],
    "status": ["ps"],
    "logs": ["logs", "--tail", "100"],
}


def find_docker() -> str | None:
    """Support Windows installer paths before the terminal PATH is refreshed."""
    if executable := shutil.which("docker"):
        return executable
    if os.name == "nt":
        for directory in (
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin",
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "Docker/Docker/resources/bin",
        ):
            candidate = directory / "docker.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def initialize_env(root: Path) -> bool:
    """Create local credentials exclusively, preserving any existing env file."""
    content = (root / ".env.example").read_text(encoding="utf-8")
    for key in ("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "DJANGO_SECRET_KEY", "JWT_SIGNING_KEY"):
        content = content.replace(f"{key}=\n", f"{key}={secrets.token_urlsafe(48)}\n")
    try:
        with (root / ".env").open("x", encoding="utf-8", newline="\n") as env:
            env.write(content)
    except FileExistsError:
        return False
    return True


def compose_command(action: str, root: Path) -> list[str]:
    """Build an explicit argv command without shell expansion."""
    profiles = []
    if action == "up-backend":
        profiles = ["--profile", "backend"]
    elif action == "down":
        profiles = ["--profile", "*"]
    return [
        "docker",
        "compose",
        "--env-file",
        str(root / ".env"),
        "-f",
        str(root / "infra/compose.yaml"),
        *profiles,
        *COMPOSE_ACTIONS[action],
    ]


def check_storage(root: Path) -> int:
    """Check MinIO readiness without printing credentials or HTTP content."""
    values = dict(
        line.split("=", 1)
        for line in (root / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    port = int(values.get("MINIO_API_PORT", "9000"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid MinIO port")
    try:
        with urlopen(f"http://127.0.0.1:{port}/minio/health/ready", timeout=5) as response:
            return 0 if response.status == 200 else 1
    except (URLError, TimeoutError):
        print("MinIO tayyor emas.", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Faol Talaba lokal buyruqlari")
    parser.add_argument("action", choices=["init", "test", "storage-health", *COMPOSE_ACTIONS])
    args = parser.parse_args(argv)
    if args.action == "init":
        created = initialize_env(ROOT)
        print("Lokal .env yaratildi." if created else "Mavjud .env saqlandi.")
        return 0
    if args.action == "test":
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT,
            check=False,
        ).returncode
    if not (ROOT / ".env").exists():
        print("Avval python tools/dev.py init buyrug'ini bajaring.", file=sys.stderr)
        return 2
    if args.action == "storage-health":
        return check_storage(ROOT)
    docker = find_docker()
    if docker is None:
        print("Docker topilmadi. Docker Engine va Compose v2 kerak.", file=sys.stderr)
        return 2
    command = compose_command(args.action, ROOT)
    command[0] = docker
    command_env = dict(os.environ)
    command_env["PATH"] = str(Path(docker).parent) + os.pathsep + command_env.get("PATH", "")
    return subprocess.run(command, cwd=ROOT, env=command_env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
