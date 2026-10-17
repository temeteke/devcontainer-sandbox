# devcontainer-sandbox

`dcs` (Dev Container Sandbox) runs commands in disposable [Dev Containers](https://containers.dev/).
Each invocation selects a profile that installs a set of Dev Container Features (a coding agent, or nothing at all), creates an isolated container, runs the command you choose (an interactive bash shell by default), and removes that container when the command exits. Source files and selected agent/terminal settings are deliberately shared with the host.

## Requirements

- Linux or WSL2 with an accessible Docker Engine
- Bash 4+, `make`, and the [`devcontainer` CLI](https://github.com/devcontainers/cli) (installed by `make install` when missing)
- `npm` for the first installation if `devcontainer` is not already on `PATH`
- Published [temeteke/devcontainer-features](https://github.com/temeteke/devcontainer-features)
- Host-side `~/.tmux.conf`, `~/.vimrc` and `~/.vim/` when the selected profile includes the tmux or Vim Feature. `dcs` does not check them (see [Host configuration and safety](#host-configuration-and-safety)).

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

## Profiles

The first argument selects a built-in profile. A profile is just a list of Dev Container Features to install on top of the base image, so you can pick a coding agent, a plain terminal sandbox, or nothing at all.

| Profile | Features added on top of the base image |
| --- | --- |
| `minimal` | none |
| `base` | `tmux:0`, `vim:0` |
| `opencode` | `tmux:0`, `vim:0`, `opencode:0` |
| `codex` | `tmux:0`, `vim:0`, `codex:0` |
| `claude` | `tmux:0`, `vim:0`, `claude-code:0` |

All of these Features come from `ghcr.io/temeteke/devcontainer-features/`. The set is defined in `bin/dcs`; adding a profile means adding one `add_profile` line there. `dcs --help` prints the same list.

## Usage

From the project directory you want to edit:

```sh
dcs opencode
```

With no command, `dcs` starts an interactive bash shell in a fresh container that already has the profile's Features applied. Start an installed agent yourself from that shell:

```sh
opencode
```

Name a command after the profile to run it directly instead of the shell. The first argument that is not a wrapper option starts the command, and every following argument is passed through unchanged:

```sh
dcs opencode tmux                 # start tmux
dcs opencode opencode --help      # pass --help to opencode
dcs base npm test                 # tmux/Vim only, run a command
dcs minimal --image mcr.microsoft.com/devcontainers/python:3.12 python -V
```

`--` ends the wrapper's option parsing, and the arguments after it are the command and its arguments. It behaves like the first non-option argument, with one difference: it also lets a command name that begins with a dash be passed.

Use a different base image and add extra Features:

```sh
dcs codex --image mcr.microsoft.com/devcontainers/python:3.12-bookworm \
  --feature ghcr.io/devcontainers/features/go:1
```

Use `dcs --help` for the wrapper's options.

## Behavior

- **Disposable:** Every call gets a unique `dcs.session` Docker label; the corresponding container is removed at process exit or on normal signals. Built Docker images/layers remain cached.
- **Profiles:** The first argument selects a built-in profile, which lists the Dev Container Features to install (see [Profiles](#profiles)). A profile that omits the tmux and Vim Features needs no host terminal configuration.
- **Command:** With no command, `dcs` runs `bash` interactively (the base image's user has bash). Name a command to run something else, such as an installed agent. The wrapper's own options must come before the command.
- **Workspace:** The current directory is passed to Dev Container CLI as `--workspace-folder`. `dcs` does not override `--mount-workspace-git-root`, so the CLI's default behavior applies (mounting the Git repository root when detected).
- **Configuration:** `dcs` generates an ephemeral `devcontainer.json` outside your repository. Existing `.devcontainer` files are ignored and never modified.
- **Custom tools:** `--feature` may be repeated. Each Feature is configured with its default options, and is added on top of the profile's Features.
- **Image:** Defaults to `mcr.microsoft.com/devcontainers/base:ubuntu24.04`. The tmux and Vim Features require a Debian/Ubuntu-compatible image with `apt-get`, so profiles that include them do too. `minimal` runs on any image.
- **Lifecycle:** `devcontainer up` builds/starts the container and applies Feature lifecycle hooks. `devcontainer exec` runs the selected command there, locating the container by the same `dcs.session` label. `docker rm -f` cleans up only the container labeled for this invocation.

The wrapper deliberately does not implement persistent container management or `.devcontainer` generation. For persistent environments, use Dev Container CLI and Templates directly.

## Host configuration and safety

The tmux and Vim Features mount `~/.tmux.conf`, `~/.vimrc`, and `~/.vim/` from the host. The agent Features also bind-mount their standard authentication, configuration, and session directories (for example, `~/.codex` and `~/.local/share/opencode`). These paths **are writable from the container**; changes survive container deletion. Other Features may add their own mounts.

A file bind mount requires its host source to exist before container creation. `dcs` does not verify the host paths, so a missing file or directory surfaces as a container-creation error.

The sandbox is intended to limit accidental access to files outside the workspace. It is **not a security boundary for untrusted or malicious code**, especially because agent credentials/state are shared and the container retains network access. Do not bind-mount the Docker socket or host root into the container. `dcs` does not do so itself.

In rare cases, `SIGKILL`, host shutdown, or Docker failures can leave a container running. Check `docker ps -a --filter label=dcs.session` and remove only stale `dcs` containers after identifying them.

## Development

Run the offline tests (Docker and Dev Container CLI are mocked). The test suite requires Python 3; `dcs` itself does not.

```sh
bash -n bin/dcs
python3 -m unittest discover -s tests -v
```

These tests validate option handling and lifecycle/cleanup behavior, **not** a real Docker container or tmux/Vim Feature installation. Run an integration check on your actual Linux/WSL Docker host before relying on this for daily development.
