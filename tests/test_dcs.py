"""Offline CLI tests. Docker and Dev Container CLI are replaced by small fakes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

DCS = Path(__file__).resolve().parents[1] / "bin" / "dcs"
GIT = shutil.which("git")
IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/"
FEATURE_PREFIX = "ghcr.io/temeteke/devcontainer-features/"
DEV_FEATURES = "ghcr.io/devcontainers/features/"
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
        print(json.dumps({'outcome': 'error', 'message': 'mock build failed'}))
        sys.exit(9)
    print(json.dumps({'outcome':'success','containerId':'test-container'}))
elif argv[0] == 'exec':
    print('exec-ok')
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
                    "TEST_CONFIG_JSON": str(self.config),
                    # Do not discover a repository above the temporary tree.
                    "GIT_CEILING_DIRECTORIES": str(root)}

    def run_dcs(self, *args, cwd=None, **extra_env):
        return subprocess.run([str(DCS), *args], cwd=cwd or self.workspace,
                              env={**self.env, **extra_env},
                              capture_output=True, text=True)

    def calls(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def up_and_exec(self):
        calls = self.calls()
        up = next(c for c in calls if c[:2] == ["devcontainer", "up"])
        exec_ = next(c for c in calls if c[:2] == ["devcontainer", "exec"])
        return calls, up, exec_

    def generated_mounts(self):
        return json.loads(self.config.read_text()).get("mounts", [])

    def assert_no_up(self):
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:2] == ["devcontainer", "up"] for c in calls))

    def test_component_defaults_and_workspace(self):
        components = {
            "python": (IMAGE_PREFIX + "python:latest", set(), "python"),
            "python:3.12": (IMAGE_PREFIX + "python:3.12", set(), "python"),
            "node": (IMAGE_PREFIX + "javascript-node:latest", set(), "node"),
            "node:22": (IMAGE_PREFIX + "javascript-node:22", set(), "node"),
            "go": (IMAGE_PREFIX + "go:latest", set(), "bash"),
            "go:1.26": (IMAGE_PREFIX + "go:1.26", set(), "bash"),
            "rust": (IMAGE_PREFIX + "rust:latest", set(), "bash"),
            # Rust images publish no minor tags, so a versioned Rust component
            # is Feature-only and runs on the base image.
            "rust:1.87": (BASE_IMAGE, {DEV_FEATURES + "rust:1"}, "bash"),
            "java": (IMAGE_PREFIX + "java:latest", set(), "bash"),
            "java:21": (IMAGE_PREFIX + "java:21", set(), "bash"),
            "dotnet": (IMAGE_PREFIX + "dotnet:latest", set(), "bash"),
            "dotnet:9.0": (IMAGE_PREFIX + "dotnet:9.0", set(), "bash"),
            "ruby": (IMAGE_PREFIX + "ruby:latest", set(), "bash"),
            "ruby:3.4": (IMAGE_PREFIX + "ruby:3.4", set(), "bash"),
            "php": (IMAGE_PREFIX + "php:latest", set(), "bash"),
            "php:8.4": (IMAGE_PREFIX + "php:8.4", set(), "bash"),
            # cpp has no Feature, so it is an image-only component.
            "cpp": (IMAGE_PREFIX + "cpp:latest", set(), "bash"),
            "playwright": (BASE_IMAGE, {FEATURE_PREFIX + "playwright:0"}, "bash"),
            "opencode": (BASE_IMAGE, {FEATURE_PREFIX + "opencode:0"}, "opencode"),
            "codex": (BASE_IMAGE, {FEATURE_PREFIX + "codex:0"}, "codex"),
            "claude": (BASE_IMAGE, {FEATURE_PREFIX + "claude-code:0"}, "claude"),
            "tmux": (BASE_IMAGE, {FEATURE_PREFIX + "tmux:0"}, "tmux"),
            "vim": (BASE_IMAGE, {FEATURE_PREFIX + "vim:0"}, "vim"),
            "gitlab-cli": (BASE_IMAGE, {FEATURE_PREFIX + "gitlab-cli:0"}, "bash"),
            "github-cli": (BASE_IMAGE, {FEATURE_PREFIX + "github-cli:0"}, "bash"),
            "kubectl": (BASE_IMAGE, {FEATURE_PREFIX + "kubectl:0"}, "bash"),
            "helmfile": (BASE_IMAGE, {FEATURE_PREFIX + "helmfile:0"}, "bash"),
            "git-config": (BASE_IMAGE, {FEATURE_PREFIX + "git-config:0"}, "bash"),
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

    def test_stdout_contains_only_the_command_output(self):
        result = self.run_dcs("python")
        self.assertEqual(result.returncode, 0, result.stderr)
        # devcontainer up's JSON must not leak into the wrapped command's stdout.
        self.assertEqual(result.stdout, "exec-ok\n")

    def test_env_forwards_host_variable(self):
        result = self.run_dcs("--env", "DCS_TEST_TOKEN", "opencode",
                              DCS_TEST_TOKEN="s3cret")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"],
                         {"DCS_TEST_TOKEN": "${localEnv:DCS_TEST_TOKEN}"})
        _, up, _ = self.up_and_exec()
        self.assertIn("--omit-config-remote-env-from-metadata", up)

    def test_env_short_option_and_literal(self):
        result = self.run_dcs("-e", "DCS_TEST_TOKEN=s3cret", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"], {"DCS_TEST_TOKEN": "s3cret"})
        _, up, _ = self.up_and_exec()
        self.assertIn("--omit-config-remote-env-from-metadata", up)

    def test_env_long_equals_form(self):
        result = self.run_dcs("--env=DCS_TEST_TOKEN=s3cret", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"], {"DCS_TEST_TOKEN": "s3cret"})

    def test_env_long_equals_host_form(self):
        result = self.run_dcs("--env=DCS_TEST_TOKEN", "opencode",
                              DCS_TEST_TOKEN="s3cret")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"],
                         {"DCS_TEST_TOKEN": "${localEnv:DCS_TEST_TOKEN}"})

    def test_long_equals_forms(self):
        feature = DEV_FEATURES + "go:1"
        result = self.run_dcs("--image=example.com/custom:1",
                              "--feature=" + feature, "--env=FOO=bar",
                              "base", "bash")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], "example.com/custom:1")
        self.assertEqual(config["features"], {feature: {}})
        self.assertEqual(config["remoteEnv"], {"FOO": "bar"})

    def test_env_multiple_values_and_last_wins(self):
        result = self.run_dcs("-e", "FOO=one", "--env", "BAR=two",
                              "--env", "FOO=three", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"], {"FOO": "three", "BAR": "two"})

    def test_env_allows_empty_literal_and_empty_host_value(self):
        result = self.run_dcs("--env", "FOO=", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"], {"FOO": ""})

        self.log.write_text("")
        result = self.run_dcs("--env", "DCS_TEST_EMPTY", "opencode",
                              DCS_TEST_EMPTY="")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"],
                         {"DCS_TEST_EMPTY": "${localEnv:DCS_TEST_EMPTY}"})

    def test_env_literal_is_json_escaped(self):
        value = 'a"b\\c=d\ne\tf\x01g😀é'
        result = self.run_dcs("--env", "FOO=" + value, "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["remoteEnv"]["FOO"], value)

    def test_env_rejects_unset_host_variable(self):
        result = self.run_dcs("--env", "DCS_TEST_UNSET_9F3C", "opencode")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DCS_TEST_UNSET_9F3C", result.stderr)
        self.assertIn("not set", result.stderr)
        calls = self.calls() if self.log.exists() else []
        self.assertFalse(any(c[:2] == ["devcontainer", "up"] for c in calls))

    def test_env_rejects_invalid_names(self):
        for spec in ("1FOO", "=value", "FOO-BAR"):
            with self.subTest(spec=spec):
                self.log.write_text("")
                result = self.run_dcs("--env", spec, "opencode")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid environment variable name", result.stderr)
                self.assertFalse(any(c[:2] == ["devcontainer", "up"]
                                     for c in self.calls()))

    def test_env_requires_a_value(self):
        for args in (("--env",), ("-e",)):
            with self.subTest(args=args):
                self.log.write_text("")
                result = self.run_dcs(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing value for", result.stderr)
                self.assertFalse(any(c[:2] == ["devcontainer", "up"]
                                     for c in self.calls()))

    def test_long_equals_rejects_empty_values(self):
        for option in ("--image=", "--feature=", "--env=", "--mount-dir="):
            with self.subTest(option=option):
                self.log.write_text("")
                result = self.run_dcs(option)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing value for", result.stderr)
                self.assertFalse(any(c[:2] == ["devcontainer", "up"]
                                     for c in self.calls()))

    def test_no_env_leaves_remote_env_absent(self):
        result = self.run_dcs("opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertNotIn("remoteEnv", config)
        _, up, _ = self.up_and_exec()
        self.assertNotIn("--omit-config-remote-env-from-metadata", up)

    def test_env_without_components_starts_base_shell(self):
        result = self.run_dcs("--env", "FOO=bar")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(config["remoteEnv"], {"FOO": "bar"})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "bash")

    def test_mount_dir_default_target(self):
        shared = Path(self.temp.name) / "shared-lib"
        shared.mkdir()
        result = self.run_dcs("--mount-dir", "../shared-lib", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(shared.resolve()),
            "target": "/workspaces/shared-lib",
        }])
        calls, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")
        self.assertEqual(calls[-1][:3], ["docker", "rm", "-f"])

    def test_mount_dir_explicit_target_and_equals_form(self):
        shared = Path(self.temp.name) / "shared-lib"
        shared.mkdir()
        result = self.run_dcs("--mount-dir", "../shared-lib:lib-a", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts()[0]["target"],
                         "/workspaces/lib-a")

        self.log.write_text("")
        result = self.run_dcs("--mount-dir=../shared-lib:lib-b", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts()[0]["target"],
                         "/workspaces/lib-b")

    def test_mount_dir_multiple_and_order(self):
        root = Path(self.temp.name)
        for name in ("shared-lib", "api"):
            (root / name).mkdir()
        result = self.run_dcs("--mount-dir", "../shared-lib",
                              "--mount-dir=../api:api2", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [(m["source"], m["target"]) for m in self.generated_mounts()],
            [(str((root / "shared-lib").resolve()), "/workspaces/shared-lib"),
             (str((root / "api").resolve()), "/workspaces/api2")])

    def test_mount_dir_same_basename_with_explicit_targets(self):
        root = Path(self.temp.name)
        (root / "a" / "lib").mkdir(parents=True)
        (root / "b" / "lib").mkdir(parents=True)
        result = self.run_dcs("--mount-dir", "../a/lib:lib-a",
                              "--mount-dir", "../b/lib:lib-b", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([m["target"] for m in self.generated_mounts()],
                         ["/workspaces/lib-a", "/workspaces/lib-b"])

    def test_mount_dir_expands_tilde_and_resolves_symlinks(self):
        real = self.home / "real-repo"
        real.mkdir()
        (self.home / "alias-repo").symlink_to(real)
        result = self.run_dcs("--mount-dir", "~/alias-repo", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(real.resolve()),
            "target": "/workspaces/real-repo",
        }])

    def test_mount_dir_source_with_colon_needs_explicit_target(self):
        colon = Path(self.temp.name) / "a:b"
        colon.mkdir()
        result = self.run_dcs("--mount-dir", "../a:b:lib-ab", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(colon.resolve()),
            "target": "/workspaces/lib-ab",
        }])

    def test_mount_dir_rejects_variable_substitution(self):
        root = Path(self.temp.name)
        literal = root / "${localWorkspaceFolderBasename}"
        literal.mkdir()
        (root / "${localEnv:OLDPWD}").mkdir()
        (root / "shared-lib").mkdir()
        (root / "alias").symlink_to(literal)
        cases = [
            ("../${localWorkspaceFolderBasename}", "mount source"),
            ("../${localEnv:OLDPWD}:x", "mount source"),
            ("../shared-lib:${localWorkspaceFolderBasename}", "mount target"),
            ("../alias", "mount source"),
        ]
        for spec, message in cases:
            with self.subTest(spec=spec):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", spec, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("${...}", result.stderr)
                self.assertIn(message, result.stderr)
                self.assert_no_up()

    def test_mount_dir_rejects_leading_or_trailing_whitespace(self):
        root = Path(self.temp.name)
        (root / "shared-lib").mkdir()
        (root / "space ").mkdir()
        (root / " space").mkdir()
        (root / "tab\tname").mkdir()
        cases = [
            ("../space ",
             "mount source must not start or end with whitespace"),
            ("../ space",
             "mount target must not start or end with whitespace"),
            ("../tab\tname",
             "mount source must not contain control characters"),
            ("../shared-lib:lib ",
             "mount target must not start or end with whitespace"),
            ("../shared-lib: lib",
             "mount target must not start or end with whitespace"),
            ("../shared-lib:lib\tx",
             "mount target must not contain control characters"),
        ]
        for spec, message in cases:
            with self.subTest(spec=spec):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", spec, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assert_no_up()

    def test_mount_dir_allows_internal_spaces(self):
        shared = Path(self.temp.name) / "shared lib"
        shared.mkdir()
        result = self.run_dcs("--mount-dir", "../shared lib", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(shared.resolve()),
            "target": "/workspaces/shared lib",
        }])

    def test_mount_dir_allows_leading_space_in_source_with_explicit_target(self):
        shared = Path(self.temp.name) / " space"
        shared.mkdir()
        result = self.run_dcs("--mount-dir", "../ space:safe", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(shared.resolve()),
            "target": "/workspaces/safe",
        }])

    def test_mount_dir_rejects_ambiguous_colon_source(self):
        root = Path(self.temp.name)
        (root / "a").mkdir()
        (root / "a:b").mkdir()
        result = self.run_dcs("--mount-dir", "../a:b", "python")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous mount", result.stderr)
        self.assert_no_up()

    @unittest.skipUnless(GIT, "git is required")
    def test_mount_dir_from_git_subdirectory_uses_sibling_target(self):
        root = Path(self.temp.name)
        repo = root / "repo"
        (repo / "sub").mkdir(parents=True)
        subprocess.run([GIT, "init", "-q", str(repo)], check=True)
        shared = root / "other" / "shared"
        shared.mkdir(parents=True)
        result = self.run_dcs("--mount-dir", "../../other/shared", "python",
                              cwd=repo / "sub")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.generated_mounts(), [{
            "type": "bind",
            "source": str(shared.resolve()),
            "target": "/workspaces/shared",
        }])
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")

    def test_mount_dir_absent_by_default(self):
        result = self.run_dcs("opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertNotIn("mounts", config)

    def test_mount_dir_without_components_starts_base_shell(self):
        (Path(self.temp.name) / "shared-lib").mkdir()
        result = self.run_dcs("--mount-dir", "../shared-lib")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(self.generated_mounts()[0]["target"],
                         "/workspaces/shared-lib")
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "bash")

    def test_mount_dir_rejects_invalid_sources(self):
        (Path(self.temp.name) / "file.txt").write_text("x")
        cases = {
            "../missing": "does not exist",
            "../file.txt": "not a directory",
            "/": "host root",
            ".": "is the workspace",
        }
        for spec, message in cases.items():
            with self.subTest(spec=spec):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", spec, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assert_no_up()

    def test_mount_dir_rejects_invalid_targets(self):
        (Path(self.temp.name) / "shared-lib").mkdir()
        cases = {
            "../shared-lib:/workspaces/lib": "must be relative",
            "../shared-lib:deps/lib": "single name",
            "../shared-lib:.": "invalid mount target",
            "../shared-lib:..": "invalid mount target",
            "../shared-lib:": "missing mount target",
            "../shared-lib:lib,a": "must not contain",
        }
        for spec, message in cases.items():
            with self.subTest(spec=spec):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", spec, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assert_no_up()

    def test_mount_dir_rejects_comma_or_quote_in_source(self):
        root = Path(self.temp.name)
        for name in ("a,b", 'a"b'):
            (root / name).mkdir()
        for name in ("a,b", 'a"b'):
            with self.subTest(name=name):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", "../" + name, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must not contain", result.stderr)
                self.assert_no_up()

    def test_mount_dir_rejects_duplicate_target(self):
        root = Path(self.temp.name)
        (root / "a" / "lib").mkdir(parents=True)
        (root / "b" / "lib").mkdir(parents=True)
        result = self.run_dcs("--mount-dir", "../a/lib:shared",
                              "--mount-dir", "../b/lib:shared", "python")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already used", result.stderr)
        self.assert_no_up()

    def test_mount_dir_rejects_workspace_target(self):
        other = Path(self.temp.name) / "other" / "workspace"
        other.mkdir(parents=True)
        for spec in ("../other/workspace",
                     "../other/workspace:workspace"):
            with self.subTest(spec=spec):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs("--mount-dir", spec, "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already used by the workspace", result.stderr)
                self.assert_no_up()

    @unittest.skipUnless(GIT, "git is required")
    def test_mount_dir_rejects_git_root_workspace_target(self):
        root = Path(self.temp.name)
        repo = root / "repo"
        (repo / "sub").mkdir(parents=True)
        subprocess.run([GIT, "init", "-q", str(repo)], check=True)
        (root / "other" / "repo").mkdir(parents=True)
        result = self.run_dcs("--mount-dir", "../../other/repo", "python",
                              cwd=repo / "sub")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already used by the workspace", result.stderr)
        self.assert_no_up()

    def test_mount_dir_rejects_empty_value(self):
        for args in (("--mount-dir",), ("--mount-dir=",)):
            with self.subTest(args=args):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing value for --mount-dir", result.stderr)
                self.assert_no_up()

    def test_docker_mount_options_are_rejected(self):
        for option in ("--mount", "--volume", "-v"):
            with self.subTest(option=option):
                if self.log.exists():
                    self.log.write_text("")
                result = self.run_dcs(option, "../shared-lib", "python")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--mount-dir", result.stderr)
                self.assert_no_up()

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
            # go carries no command, so opencode is the first one that does.
            "go,opencode": (IMAGE_PREFIX + "go:latest", "opencode"),
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

    def test_language_feature_layering(self):
        cases = {
            "python,node": (IMAGE_PREFIX + "python:latest",
                            {DEV_FEATURES + "node:1"}, "python"),
            "node,python": (IMAGE_PREFIX + "javascript-node:latest",
                            {DEV_FEATURES + "python:1"}, "node"),
            "opencode,python": (IMAGE_PREFIX + "python:latest",
                                {FEATURE_PREFIX + "opencode:0"}, "opencode"),
        }
        for components, (image, features, command) in cases.items():
            with self.subTest(components=components):
                self.log.write_text("")
                result = self.run_dcs(components)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(self.config.read_text())
                self.assertEqual(config["image"], image)
                self.assertEqual(set(config["features"]), features)
                _, _, exec_ = self.up_and_exec()
                self.assertEqual(exec_[exec_.index("--") + 1], command)

    def test_base_is_processed_in_place(self):
        result = self.run_dcs("base,python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(set(config["features"]), {DEV_FEATURES + "python:1"})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")

    def test_versioned_component(self):
        # First named: the versioned image provides the language, and its
        # Feature is skipped.
        result = self.run_dcs("python:3.12")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "python:3.12")
        self.assertEqual(config["features"], {})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")

        # Image already set: the version becomes the Feature's option.
        self.log.write_text("")
        result = self.run_dcs("node,python:3.12")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "javascript-node:latest")
        self.assertEqual(config["features"],
                         {DEV_FEATURES + "python:1": {"version": "3.12"}})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "node")

        self.log.write_text("")
        result = self.run_dcs("base,python:3.11")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(config["features"],
                         {DEV_FEATURES + "python:1": {"version": "3.11"}})
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1], "python")

    def test_versioned_node_go_rust(self):
        cases = {
            # An image tag exists, so the versioned component can be first.
            "node:20": (IMAGE_PREFIX + "javascript-node:20", {}, "node"),
            "go:1.25": (IMAGE_PREFIX + "go:1.25", {}, "bash"),
            # Rust has no minor image tag: it is a Feature on the base image.
            "rust:1.86": (BASE_IMAGE,
                          {DEV_FEATURES + "rust:1": {"version": "1.86"}}, "bash"),
            # Layered on another image, the version goes to the Feature.
            "base,node:22": (BASE_IMAGE,
                             {DEV_FEATURES + "node:1": {"version": "22"}}, "node"),
            # go and rust carry no command, so opencode decides what runs.
            "go:1.26,opencode": (IMAGE_PREFIX + "go:1.26",
                                 {FEATURE_PREFIX + "opencode:0": {}}, "opencode"),
            "base,java:21": (BASE_IMAGE,
                             {DEV_FEATURES + "java:1": {"version": "21"}}, "bash"),
            "base,dotnet:9.0": (BASE_IMAGE,
                                {DEV_FEATURES + "dotnet:2": {"version": "9.0"}}, "bash"),
            "base,ruby:3.4": (BASE_IMAGE,
                              {DEV_FEATURES + "ruby:2": {"version": "3.4"}}, "bash"),
            "base,php:8.4": (BASE_IMAGE,
                             {DEV_FEATURES + "php:1": {"version": "8.4"}}, "bash"),
        }
        for components, (image, features, command) in cases.items():
            with self.subTest(components=components):
                self.log.write_text("")
                result = self.run_dcs(components)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(self.config.read_text())
                self.assertEqual(config["image"], image)
                self.assertEqual(config["features"], features)
                _, _, exec_ = self.up_and_exec()
                self.assertEqual(exec_[exec_.index("--") + 1], command)

    def test_image_option_overrides_component_image(self):
        result = self.run_dcs("--image", "example.com/custom:1", "python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], "example.com/custom:1")
        # With the image already set by --image, python is added as a Feature.
        self.assertEqual(set(config["features"]), {DEV_FEATURES + "python:1"})

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

    def test_command_requires_a_component(self):
        cases = (("--",), ("--", "bash"),
                 ("--image", "example.com/custom:1", "--", "bash"))
        for args in cases:
            with self.subTest(args=args):
                self.log.write_text("")
                result = self.run_dcs(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing component list before --", result.stderr)
                self.assertNotIn("dcs base COMMAND", result.stderr)
                self.assertFalse(any(c[:2] == ["devcontainer", "up"]
                                     for c in self.calls()))

    def test_base_component_runs_explicit_command(self):
        result = self.run_dcs("base", "bash")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], BASE_IMAGE)
        self.assertEqual(config["features"], {})
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
        self.assertEqual(r.returncode, 9)
        self.assertEqual(r.stdout, "")
        self.assertIn('"outcome": "error"', r.stderr)
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

    def test_component_that_adds_nothing_is_rejected(self):
        for args in (("python,cpp",),
                     ("--image", "example.com/custom:1", "cpp")):
            with self.subTest(args=args):
                self.log.write_text("")
                result = self.run_dcs(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("component 'cpp' adds nothing", result.stderr)
                self.assertFalse(any(c[:2] == ["devcontainer", "up"]
                                     for c in self.calls()))

    def test_image_only_component_can_be_first(self):
        result = self.run_dcs("cpp,python")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "cpp:latest")
        self.assertEqual(set(config["features"]), {DEV_FEATURES + "python:1"})

    def test_base_is_exempt_from_the_no_op_check(self):
        result = self.run_dcs("python,base")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["image"], IMAGE_PREFIX + "python:latest")

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

    def test_component_command_is_an_argv(self):
        result = self.run_dcs("codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["codex", "--no-daemon"])

        # An explicit command replaces the whole default argv.
        self.log.write_text("")
        result = self.run_dcs("codex", "codex", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["codex", "--help"])

    def test_command_after_components_replaces_the_default(self):
        # Naming the command runs it, with the following arguments untouched.
        result = self.run_dcs("opencode", "opencode", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["opencode", "--help"])

        # Everything after the component list is the command, even when it
        # starts with a dash.
        self.log.write_text("")
        result = self.run_dcs("opencode", "--help", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, exec_ = self.up_and_exec()
        self.assertEqual(exec_[exec_.index("--") + 1:], ["--help", "--version"])

    def test_help_lists_components_and_rejects_invalid_option(self):
        help_ = self.run_dcs("--help")
        self.assertEqual(help_.returncode, 0)
        self.assertEqual(help_.stderr, "")
        self.assertIn("-e, --env NAME[=VALUE]", help_.stdout)
        self.assertIn("--mount-dir DIR[:TARGET]", help_.stdout)
        self.assertIn("${...}", help_.stdout)
        self.assertIn("no read-only mode", help_.stdout)
        self.assertIn("--volume", help_.stdout)
        self.assertIn("--option=VALUE", help_.stdout)
        for component in ("python", "python:3.12", "node", "node:22",
                          "go:1.26", "rust:1.87", "opencode", "codex",
                          "claude", "tmux", "vim", "github-cli", "gitlab-cli",
                          "kubectl", "helmfile", "git-config", "base"):
            self.assertIn(component, help_.stdout)
        r = self.run_dcs("--bad")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown option", r.stderr)


if __name__ == "__main__":
    unittest.main()
