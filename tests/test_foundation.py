"""Checks for credential safety and portable infrastructure commands."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

from tools.dev import COMPOSE_ACTIONS, ROOT, compose_command, initialize_env, main


class FoundationTests(unittest.TestCase):
    def test_compose_services_are_local_and_credentials_required(self) -> None:
        config = yaml.safe_load((ROOT / "infra/compose.yaml").read_text())
        services = config["services"]
        self.assertEqual(set(services), {"postgres", "redis", "minio", "backend"})
        for service in services.values():
            self.assertTrue(all(port.startswith("127.0.0.1:") for port in service["ports"]))
        self.assertEqual(services["postgres"]["image"], "postgres:18")
        for name, key in (("postgres", "POSTGRES_PASSWORD"), ("minio", "MINIO_ROOT_PASSWORD")):
            self.assertIn(":?", services[name]["environment"][key])
        self.assertIn("postgres_data:/var/lib/postgresql", services["postgres"]["volumes"])
        self.assertEqual(services["minio"]["pull_policy"], "build")
        self.assertEqual(services["minio"]["build"]["context"], "./minio")

    def test_init_generates_distinct_credentials_and_preserves_existing_file(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text(
                (ROOT / ".env.example").read_text(), encoding="utf-8"
            )
            self.assertTrue(initialize_env(root))
            content = (root / ".env").read_text()
            values = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
            passwords = [values[key] for key in ("POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD")]
            self.assertTrue(all(len(value) >= 32 for value in passwords))
            self.assertNotEqual(*passwords)
            self.assertGreaterEqual(len(values["DJANGO_SECRET_KEY"]), 50)
            self.assertGreaterEqual(len(values["JWT_SIGNING_KEY"]), 50)
            self.assertNotEqual(values["JWT_SIGNING_KEY"], values["DJANGO_SECRET_KEY"])
            self.assertFalse(initialize_env(root))
            self.assertEqual((root / ".env").read_text(), content)

    def test_down_preserves_volumes_and_paths_with_spaces(self) -> None:
        root = Path("workspace with spaces")
        command = compose_command("down", root)
        self.assertIn(str(root / "infra/compose.yaml"), command)
        self.assertEqual(command[-1], "down")
        self.assertNotIn("--volumes", command)
        self.assertNotIn("-v", command)
        self.assertEqual(command[command.index("--profile") + 1], "*")

    def test_backend_start_activates_profile_and_build(self) -> None:
        command = compose_command("up-backend", ROOT)
        self.assertEqual(command[command.index("--profile") + 1], "backend")
        self.assertIn("--build", command)
        # Compose-relative build/env_file paths must resolve from infra/compose.yaml.
        self.assertNotIn("--project-directory", command)

    def test_config_does_not_print_resolved_secrets(self) -> None:
        self.assertEqual(COMPOSE_ACTIONS["config"], ["config", "--quiet"])

    def test_missing_env_fails_before_docker(self) -> None:
        with (
            TemporaryDirectory() as directory,
            patch("tools.dev.ROOT", Path(directory)),
        ):
            self.assertEqual(main(["up"]), 2)

    def test_missing_docker_has_actionable_failure(self) -> None:
        with (
            TemporaryDirectory() as directory,
            patch("tools.dev.ROOT", Path(directory)),
        ):
            (Path(directory) / ".env").write_text("", encoding="utf-8")
            with patch("tools.dev.find_docker", return_value=None):
                self.assertEqual(main(["up"]), 2)

    def test_docker_helpers_are_on_child_process_path(self) -> None:
        with TemporaryDirectory() as directory, patch("tools.dev.ROOT", Path(directory)):
            (Path(directory) / ".env").write_text("", encoding="utf-8")
            executable = str(Path(directory) / "bin" / "docker")
            with (
                patch("tools.dev.find_docker", return_value=executable),
                patch("tools.dev.subprocess.run") as run,
            ):
                run.return_value.returncode = 0
                self.assertEqual(main(["config"]), 0)
                self.assertTrue(
                    run.call_args.kwargs["env"]["PATH"].startswith(str(Path(executable).parent))
                )

    def test_foundation_files_exist(self) -> None:
        for name in ("backend", "admin-web", "mobile", "infra", "docs"):
            self.assertTrue((ROOT / name).is_dir(), name)
        for name in (
            ".gitignore",
            ".editorconfig",
            ".env.example",
            "infra/compose.yaml",
        ):
            self.assertTrue((ROOT / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
