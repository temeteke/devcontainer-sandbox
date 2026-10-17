# devcontainer-sandbox

`dcs` (Dev Container Sandbox) runs coding agents in disposable [Dev Containers](https://containers.dev/).
It creates an isolated container for each invocation, runs the agent, and removes that container when the agent exits. Source files and selected agent/terminal settings are deliberately shared with the host.

## Requirements

- Linux or WSL2 with an accessible Docker Engine
- Bash 4+, Python 3, `make`, and the [`devcontainer` CLI](https://github.com/devcontainers/cli) (installed by `make install` when missing)
- `npm` for the first installation if `devcontainer` is not already on `PATH`
- Published [temeteke/devcontainer-features](https://github.com/temeteke/devcontainer-features)
- Host-side `~/.tmux.conf`, `~/.vimrc` and `~/.vim/` must exist (required by the shared terminal Features)

## Installation

From a checkout of this repository:

```sh
make install
```

`make install` installs `dcs` into `~/.local/bin`. If `devcontainer` is already available on `PATH`, it is left unchanged. Otherwise the Makefile runs `npm install --global @devcontainers/cli`. npm uses its existing global prefix configuration; the Makefile does not override npm's install location. Ensure the npm global executable directory is on `PATH`.

Ensure `~/.local/bin` is on your `PATH` (including for subsequent shell sessions):

```sh
export PATH="$HOME/.local/bin:$PATH"
```

To change the installation directory **for `dcs` itself**, run `make BINDIR=/your/bin install`. This does not affect npm's install location. To install only the `dcs` script without installing or checking Dev Container CLI, run `make install-dcs`.

### Uninstallation

```sh
make uninstall
```

`make uninstall` invokes `make uninstall-dcs`, which removes only the `dcs` executable from `BINDIR` (by default, `~/.local/bin/dcs`). You can also call `make uninstall-dcs` directly. **Neither target uninstalls `devcontainer`**, regardless of whether it was already present or installed by `make install`. The Dev Container CLI is shared tooling and may be used outside this project. If you also want to remove the npm-managed Dev Container CLI, run `make uninstall-devcontainer` explicitly. This executes `npm uninstall --global @devcontainers/cli`, respecting the current npm global configuration. It does **not** remove `dcs`, and it is **not** called by `make uninstall`. A Dev Container CLI installed through another package manager (such as AUR) must be removed using that manager. Use the same `BINDIR` value as during installation if you customized it.

## Usage

From the project directory you want to edit:

```sh
dcs opencode
dcs codex
dcs claude
```

Use a different base image and add extra Features:

```sh
dcs codex --image mcr.microsoft.com/devcontainers/python:3.12-bookworm \
  --feature ghcr.io/devcontainers/features/go:1
```

Pass agent arguments after `--`:

```sh
dcs codex -- --help
```

Use `dcs --help` for the wrapper's options.

## Behavior

- **Disposable:** Every call gets a unique `dcs.session` Docker label; the corresponding container is removed at process exit or on normal signals. Built Docker images/layers remain cached.
- **Workspace:** The current directory is passed to Dev Container CLI as `--workspace-folder`. `dcs` does not override `--mount-workspace-git-root`, so the CLI's default behavior applies (mounting the Git repository root when detected).
- **Configuration:** `dcs` generates an ephemeral `devcontainer.json` outside your repository. Existing `.devcontainer` files are ignored and never modified.
- **Agents:** `opencode`, `codex`, and `claude` automatically enable the matching `ghcr.io/temeteke/devcontainer-features/{opencode,codex,claude-code}:0` Feature.
- **Terminal tools:** `tmux:0` and `vim:0` Features are always added.
- **Custom tools:** `--feature` may be repeated. Each Feature is configured with its default options.
- **Image:** Defaults to `mcr.microsoft.com/devcontainers/base:ubuntu24.04`. The published tmux and Vim Features require a Debian/Ubuntu-compatible image with `apt-get`.
- **Lifecycle:** `devcontainer up` builds/starts the container and applies Feature lifecycle hooks. `devcontainer exec` runs the selected agent. `docker rm -f` cleans up only the container labeled for this invocation.

The wrapper deliberately does not implement persistent container management, `.devcontainer` generation, or a generic shell subcommand. For persistent environments, use Dev Container CLI and Templates directly.

## Host configuration and safety

The terminal Features mount `~/.tmux.conf`, `~/.vimrc`, and `~/.vim/` from the host. The agent Features also bind-mount their standard authentication, configuration, and session directories (for example, `~/.codex` and `~/.local/share/opencode`). These paths **are writable from the container**; changes survive container deletion. Other Features may add their own mounts.

The sandbox is intended to limit accidental access to files outside the workspace. It is **not a security boundary for untrusted or malicious code**, especially because agent credentials/state are shared and the container retains network access. Do not bind-mount the Docker socket or host root into the container. `dcs` does not do so itself.

A file bind mount requires its host source to exist before container creation. If a terminal configuration is missing, `dcs` aborts with a descriptive error instead of creating empty files on the host.

In rare cases, `SIGKILL`, host shutdown, or Docker failures can leave a container running. Check `docker ps -a --filter label=dcs.session` and remove only stale `dcs` containers after identifying them.

## Development

Run the offline tests (Docker and Dev Container CLI are mocked):

```sh
bash -n bin/dcs
python3 -m unittest discover -s tests -v
```

These tests validate option handling and lifecycle/cleanup behavior, **not** a real Docker container or tmux/Vim Feature installation. Run an integration check on your actual Linux/WSL Docker host before relying on this for daily development.
