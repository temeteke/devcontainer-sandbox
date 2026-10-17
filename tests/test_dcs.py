"""Offline CLI tests. Docker and Dev Container CLI are replaced by small fakes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

DCS = Path(__file__).resolve().parents[1] / "bin" / "dcs"

FAKE_DEVCONTAINER = '''#!/usr/bin/env python3
import json, os, pathlib, sys
argv = sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as f:
    f.write(json.dumps(['devcontainer', *argv]) + '\\n')
if argv[0] == 'up':
    config = argv[argv.index('--config') + 1]
    pathlib.Path(os.environ['TEST_CONFIG_JSON']).write_text(pathlib.Path(config).read_text())
    if os.environ.get('MOCK_UP_FAIL') == '1':
        print('mock build failed', file=sys.stderr)
        sys.exit(9)
    print(json.dumps({'outcome':'success','containerId':'test-container'}))
elif argv[0] == 'exec':
    sys.exit(int(os.environ.get('MOCK_EXEC_EXIT', '0')))
else:
    sys.exit(11)
'''
FAKE_DOCKER = '''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as f:
    f.write(json.dumps(['docker', *argv]) + '\\n')
if argv[0] == 'info':
    sys.exit(0)
if argv[0] == 'ps':
    print('test-container')
    sys.exit(0)
if argv[:2] == ['rm', '-f']:
    sys.exit(0)
sys.exit(12)
'''


class TestDcs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.home = root / "home"
        self.home.mkdir()
        (self.home / ".tmux.conf").write_text("set -g mouse on\n")
        (self.home / ".vimrc").write_text("set number\n")
        (self.home / ".vim").mkdir()
        mocks = root / "mock-bin"
        mocks.mkdir()
        for name, source in (("devcontainer", FAKE_DEVCONTAINER), ("docker", FAKE_DOCKER)):
            path = mocks / name
            path.write_text(source)
            path.chmod(0o755)
        self.log = root / "calls.jsonl"
        self.config = root / "generated-config.json"
        self.env = {**os.environ, "HOME": str(self.home),
                    "PATH": str(mocks) + os.pathsep + os.environ["PATH"],
                    "TEST_LOG": str(self.log),
                    "TEST_CONFIG_JSON": str(self.config)}

    def run_dcs(self, *args, **extra_env):
        return subprocess.run([str(DCS), *args], cwd=self.workspace,
                              env={**self.env, **extra_env},
                              capture_output=True, text=True)

    def calls(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def test_profiles_features_and_workspace(self):
        prefix = "ghcr.io/temeteke/devcontainer-features/"
        terminal = {prefix + "tmux:0", prefix + "vim:0"}
        profiles = {
            "minimal": set(),
            "base": set(terminal),
            "opencode": terminal | {prefix + "opencode:0"},
            "codex": terminal | {prefix + "codex:0"},
            "claude": terminal | {prefix + "claude-code:0"},
        }
        for profile, expected in profiles.items():
            with self.subTest(profile=profile):
                self.log.write_text("")
                result = self.run_dcs(profile)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                up = next(c for c in calls if c[:2] == ["devcontainer", "up"])
                exec_ = next(c for c in calls if c[:2] == ["devcontainer", "exec"])
                self.assertFalse(any(arg.startswith("--mount-workspace-git-root") for arg in up))
                self.assertFalse(any(arg.startswith("--mount-workspace-git-root") for arg in exec_))
                self.assertEqual(up[up.index("--workspace-folder") + 1], str(self.workspace))
                self.assertIn("--no-lockfile", up)
                session = up[up.index("--id-label")+1]
                self.assertTrue(session.startswith("dcs.session="))
                self.assertNotIn("--container-id", exec_)
                self.assertEqual(exec_[exec_.index("--id-label")+1], session)
                self.assertEqual(exec_[exec_.index("--")+1], "bash")
                config = json.loads(self.config.read_text())
                self.assertEqual(set(config["features"]), expected)
                self.assertEqual(calls[-1][:3], ["docker", "rm", "-f"])

    def test_image_and_extra_features_and_command(self):
        result = self.run_dcs("codex", "--image", "python:3.12",
                              "--feature", "ghcr.io/devcontainers/features/go:1",
                              "--feature", "ghcr.io/devcontainers/features/rust:1",
                              "--", "echo", "hello world")
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["image"], "python:3.12")
        self.assertIn("ghcr.io/devcontainers/features/go:1", cfg["features"])
        self.assertIn("ghcr.io/devcontainers/features/rust:1", cfg["features"])
        exec_ = next(c for c in self.calls() if c[:2] == ["devcontainer", "exec"])
        self.assertEqual(exec_[exec_.index("--")+1:], ["echo", "hello world"])

    def test_generated_config_escapes_json_values(self):
        weird_image = 'weird"image\\path'
        weird_feature = 'example.com/"quoted"/feature\\name:0'
        result = self.run_dcs("minimal", "--image", weird_image,
                              "--feature", weird_feature)
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["image"], weird_image)
        self.assertEqual(set(cfg["features"]), {weird_feature})

    def test_positional_command_and_args_are_forwarded(self):
        result = self.run_dcs("opencode", "tmux", "new", "-s", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        exec_ = next(c for c in self.calls() if c[:2] == ["devcontainer", "exec"])
        self.assertEqual(exec_[exec_.index("--")+1:], ["tmux", "new", "-s", "dev"])

    def test_command_failure_preserves_status_and_cleans_up(self):
        r = self.run_dcs("opencode", MOCK_EXEC_EXIT="37")
        self.assertEqual(r.returncode, 37, r.stderr)
        self.assertTrue(any(c[:3] == ["docker", "rm", "-f"] for c in self.calls()))

    def test_up_failure_still_cleans_up(self):
        r = self.run_dcs("codex", MOCK_UP_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c[:2] == ["devcontainer", "exec"] for c in self.calls()))
        self.assertTrue(any(c[:3] == ["docker", "rm", "-f"] for c in self.calls()))

    def test_host_config_is_not_required(self):
        for name in (".tmux.conf", ".vimrc"):
            (self.home / name).unlink()
        (self.home / ".vim").rmdir()
        r = self.run_dcs("opencode")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(c[:2] == ["devcontainer", "up"] for c in self.calls()))

    def test_unknown_profile_is_rejected(self):
        r = self.run_dcs("nope")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown profile", r.stderr)
        self.assertFalse(self.config.exists())
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:2] == ["devcontainer", "up"] for c in calls))

    def test_help_lists_profiles_and_rejects_invalid_option(self):
        help_ = self.run_dcs("--help")
        self.assertEqual(help_.returncode, 0)
        for profile in ("minimal", "base", "opencode", "codex", "claude"):
            self.assertIn(profile, help_.stdout)
        r = self.run_dcs("opencode", "--bad")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown option", r.stderr)


if __name__ == "__main__":
    unittest.main()
