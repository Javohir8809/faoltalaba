"""Optional isolated PostgreSQL cluster using already installed native binaries."""

import argparse
import os
import subprocess
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".local" / "postgres"
PORT = 55432


def main() -> int:
    parser = argparse.ArgumentParser(description="Loyiha uchun alohida lokal PostgreSQL")
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--bin", required=True, type=Path)
    args = parser.parse_args()
    suffix = ".exe" if os.name == "nt" else ""
    binary = args.bin / f"pg_ctl{suffix}"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    if args.action == "stop":
        return subprocess.run(
            [str(binary), "-D", str(DATA), "stop", "-m", "fast"],
            creationflags=flags,
            check=False,
        ).returncode
    values = dotenv_values(ROOT / ".env")
    password = values.get("POSTGRES_PASSWORD")
    if not password:
        parser.error("Avval lokal .env yarating.")
    user = values["POSTGRES_USER"]
    database = values["POSTGRES_DB"]
    DATA.parent.mkdir(exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        password_path = DATA.parent / "postgres-init-password"
        try:
            password_path.write_text(password, encoding="utf-8")
            subprocess.run(
                [
                    str(args.bin / f"initdb{suffix}"),
                    "-D",
                    str(DATA),
                    "--username",
                    user,
                    "--pwfile",
                    str(password_path),
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                ],
                creationflags=flags,
                check=True,
            )
        finally:
            password_path.unlink(missing_ok=True)
    status = subprocess.run(
        [str(binary), "-D", str(DATA), "status"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        check=False,
    )
    if status.returncode != 0:
        subprocess.run(
            [
                str(binary),
                "-D",
                str(DATA),
                "-l",
                str(DATA.parent / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {PORT}",
                "-w",
                "start",
            ],
            creationflags=flags,
            check=True,
        )
    with psycopg.connect(
        host="127.0.0.1",
        port=PORT,
        user=user,
        password=password,
        dbname="postgres",
        autocommit=True,
        connect_timeout=5,
    ) as connection:
        if not connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    print(f"Lokal PostgreSQL tayyor: 127.0.0.1:{PORT}. POSTGRES_PORT={PORT} bilan ishlating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
