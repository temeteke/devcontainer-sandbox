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

    def test_agents_features_and_workspace(self):
        for agent, feature in (("opencode", "opencode"), ("codex", "codex"),
                               ("claude", "claude-code")):
            with self.subTest(agent=agent):
                self.log.write_text("")
                result = self.run_dcs(agent)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                up = next(c for c in calls if c[:2] == ["devcontainer", "up"])
                exec_ = next(c for c in calls if c[:2] == ["devcontainer", "exec"])
                self.assertFalse(any(arg.startswith("--mount-workspace-git-root") for arg in up))
                self.assertFalse(any(arg.startswith("--mount-workspace-git-root") for arg in exec_))
                self.assertEqual(up[up.index("--workspace-folder") + 1], str(self.workspace))
                self.assertIn("--no-lockfile", up)
                self.assertIn("dcs.session=", up[up.index("--id-label")+1])
                self.assertEqual(exec_[exec_.index("--")+1], "bash")
                config = json.loads(self.config.read_text())
                features = config["features"]
                prefix = "ghcr.io/temeteke/devcontainer-features/"
                self.assertEqual(set(features), {prefix+"tmux:0", prefix+"vim:0", prefix+feature+":0"})
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

    def test_positional_command_and_args_are_forwarded(self):
        result = self.run_dcs("opencode", "tmux", "new", "-s", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        exec_ = next(c for c in self.calls() if c[:2] == ["devcontainer", "exec"])
        self.assertEqual(exec_[exec_.index("--")+1:], ["tmux", "new", "-s", "dev"])

    def test_agent_failure_preserves_status_and_cleans_up(self):
        r = self.run_dcs("opencode", MOCK_EXEC_EXIT="37")
        self.assertEqual(r.returncode, 37, r.stderr)
        self.assertTrue(any(c[:3] == ["docker", "rm", "-f"] for c in self.calls()))

    def test_up_failure_still_cleans_up(self):
        r = self.run_dcs("codex", MOCK_UP_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c[:2] == ["devcontainer", "exec"] for c in self.calls()))
        self.assertTrue(any(c[:3] == ["docker", "rm", "-f"] for c in self.calls()))

    def test_missing_host_config_fails_before_up(self):
        (self.home / ".vimrc").unlink()
        r = self.run_dcs("codex")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("~/.vimrc", r.stderr)
        self.assertFalse(self.config.exists())

    def test_help_and_invalid_option(self):
        self.assertEqual(self.run_dcs("--help").returncode, 0)
        r = self.run_dcs("opencode", "--bad")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown option", r.stderr)


if __name__ == "__main__":
    unittest.main()
