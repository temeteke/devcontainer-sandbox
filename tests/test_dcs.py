"""Offline CLI tests. Docker and Dev Container CLI are replaced by small fakes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

DCS = Path(__file__).resolve().parents[1] / "bin" / "dcs"
IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/"
FEATURE_PREFIX = "ghcr.io/temeteke/devcontainer-features/"
BASE_IMAGE = IMAGE_PREFIX + "base:ubuntu24.04"

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

    def up_and_exec(self):
        calls = self.calls()
        up = next(c for c in calls if c[:2] == ["devcontainer", "up"])
        exec_ = next(c for c in calls if c[:2] == ["devcontainer", "exec"])
        return calls, up, exec_

    def test_component_defaults_and_workspace(self):
        components = {
            "python": (IMAGE_PREFIX + "python:latest", set(), "python"),
            "node": (IMAGE_PREFIX + "javascript-node:latest", set(), "node"),
            "go": (IMAGE_PREFIX + "go:latest", set(), "bash"),
            "rust": (IMAGE_PREFIX + "rust:latest", set(), "bash"),
            "opencode": (BASE_IMAGE, {FEATURE_PREFIX + "opencode:0"}, "opencode"),
            "codex": (BASE_IMAGE, {FEATURE_PREFIX + "codex:0"}, "codex"),
            "claude": (BASE_IMAGE, {FEATURE_PREFIX + "claude-code:0"}, "claude"),
            "tmux": (BASE_IMAGE, {FEATURE_PREFIX + "tmux:0"}, "tmux"),
            "vim": (BASE_IMAGE, {FEATURE_PREFIX + "vim:0"}, "vim"),
        }
        for component, (image, features, command) in components.items():
            with self.subTest(component=component):
                self.log.write_text("")
                result = self.run_dcs(component)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls, up, exec_ = self.up_and_exec()
                self.assertFalse(any(a.startswith("--mount-workspace-git-root") for a in up))
                self.assertFalse(any(a.startswith("--mount-workspace-git-root") for a in exec_))
                self.assertEqual(up[up.index("--workspace-folder") + 1], str(self.workspace))
                self.assertIn("--no-lockfile", up)
                session = up[up.index("--id-label") + 1]
                self.assertTrue(session.startswith("dcs.session="))
                self.assertNotIn("--container-id", exec_)
                self.assertEqual(exec_[exec_.index("--id-label") + 1], session)
                self.assertEqual(exec_[exec_.index("--") + 1], command)
                config = json.loads(self.config.read_text())
                self.assertEqual(config["image"], image)
                self.assertEqual(set(config["features"]), features)
                self.assertEqual(calls[-1][:3], ["docker", "rm", "-f"])

    def test_no_components_starts_base_shell(self):
        result = self.run_dcs()
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "bash")
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(config["features"], {})

    def test_combined_components(self):
        result = self.run_dcs("opencode,python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "python:latest")
        self.assertEqual(set(config["features"]), {FEATURE_PREFIX + "opencode:0"})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "opencode")

    def test_first_image_and_command_win(self):
        cases = {
            "python,node": (IMAGE_PREFIX + "python:latest", "python"),
            "node,python": (IMAGE_PREFIX + "javascript-node:latest", "node"),
            "go,opencode": (IMAGE_PREFIX + "go:latest", "bash"),
            "opencode,python": (IMAGE_PREFIX + "python:latest", "opencode"),
        }
        for components, (image, command) in cases.items():
            with self.subTest(components=components):
                self.log.write_text("")
                result = self.run_dcs(components)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(self.config.read_text())
                self.assertEqual(config["image"], image)
                _, _, exec_ = self.up_and_exec()
                self.assertEqual(exec_[exec_.index("--") + 1], command)

    def test_base_is_always_last(self):
        result = self.run_dcs("base,python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "python:latest")
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")

    def test_inline_image_reference(self):
        result = self.run_dcs("python:3.12,opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], "python:3.12")
        self.assertEqual(set(config["features"]), {FEATURE_PREFIX + "opencode:0"})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "opencode")

    def test_image_option_overrides_component_image(self):
        result = self.run_dcs("--image", "example.com/custom:1", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], "example.com/custom:1")

    def test_options_before_components(self):
        result = self.run_dcs("--image", "example.com/custom:1", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], "example.com/custom:1")
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "opencode")

    def test_explicit_command_overrides_default(self):
        result = self.run_dcs("opencode", "bash")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["bash"])

    def test_image_and_extra_features_and_command(self):
        result = self.run_dcs("--image", "python:3.12",
                              "--feature", "ghcr.io/devcontainers/features/go:1",
                              "--feature", "ghcr.io/devcontainers/features/rust:1",
                              "codex", "--", "echo", "hello world")
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["image"], "python:3.12")
        self.assertIn("ghcr.io/devcontainers/features/go:1", cfg["features"])
        self.assertIn("ghcr.io/devcontainers/features/rust:1", cfg["features"])
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["echo", "hello world"])

    def test_features_are_deduplicated(self):
        feature = FEATURE_PREFIX + "tmux:0"
        result = self.run_dcs("--feature", feature, "tmux,tmux")
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = self.config.read_text()
        self.assertEqual(raw.count(feature), 1)
        self.assertEqual(set(json.loads(raw)["features"]), {feature})

    def test_generated_config_escapes_json_values(self):
        weird_image = 'weird"image\\path'
        weird_feature = 'example.com/"quoted"/feature\\name:0'
        result = self.run_dcs("--image", weird_image, "--feature", weird_feature)
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg["image"], weird_image)
        self.assertEqual(set(cfg["features"]), {weird_feature})

    def test_positional_command_and_args_are_forwarded(self):
        result = self.run_dcs("opencode", "tmux", "new", "-s", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["tmux", "new", "-s", "dev"])

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

    def test_unknown_component_is_rejected(self):
        r = self.run_dcs("nope")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown component", r.stderr)
        self.assertFalse(self.config.exists())
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:2] == ["devcontainer", "up"] for c in calls))

    def test_empty_component_name_is_rejected(self):
        r = self.run_dcs(",opencode")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("empty component name", r.stderr)
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:2] == ["devcontainer", "up"] for c in calls))

    def test_help_is_only_before_components(self):
        help_ = self.run_dcs("--help")
        self.assertEqual(help_.returncode, 0)
        self.assertIn("Usage: dcs", help_.stdout)
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:1] == ["devcontainer"] for c in calls))

    def test_options_after_components_go_to_default_command(self):
        result = self.run_dcs("opencode", "--help", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:],
                         ["opencode", "--help", "--version"])

    def test_help_lists_components_and_rejects_invalid_option(self):
        help_ = self.run_dcs("--help")
        self.assertEqual(help_.returncode, 0)
        for component in ("python", "node", "go", "rust", "opencode", "codex",
                          "claude", "tmux", "vim", "base"):
            self.assertIn(component, help_.stdout)
        r = self.run_dcs("--bad")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown option", r.stderr)


if __name__ == "__main__":
    unittest.main()
