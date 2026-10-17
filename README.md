# devcontainer-sandbox

`dcs` (Dev Container Sandbox) runs commands in disposable [Dev Containers](https://containers.dev/).
Each invocation names zero or more components. A component contributes a base image (a language image such as Python or Node, or the plain base image), a set of Dev Container Features (a coding agent, tmux, Vim, ...), and the command to run. `dcs` creates an isolated container, runs the first component that carries a command (or the command you choose instead), and removes that container when the command exits. Source files and selected agent/terminal settings are deliberately shared with the host.

## Requirements

- Linux or WSL2 with an accessible Docker Engine
- Bash 4+, `make`, and the [`devcontainer` CLI](https://github.com/devcontainers/cli) (installed by `make install` when missing)
- `npm` for the first installation if `devcontainer` is not already on `PATH`
- Published [temeteke/devcontainer-features](https://github.com/temeteke/devcontainer-features)
- Host-side `~/.tmux.conf`, `~/.vimrc` and `~/.vim/` when you name the tmux or Vim component. `dcs` does not check them (see [Host configuration and safety](#host-configuration-and-safety)).

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

## Components

The first argument names zero or more components, separated by commas. A component is a named entry that may carry a base image, Dev Container Features, and the command to run. When several components are named, their Features are combined without duplicates, the first component that carries an image sets the base image, and the first that carries a command is run. The `base` component is always appended as the fallback, so `dcs` on its own starts a `bash` shell.

| Component | Image | Features | Default command |
| --- | --- | --- | --- |
| `python` | `mcr.microsoft.com/devcontainers/python:latest` | — | `python` |
| `node` | `mcr.microsoft.com/devcontainers/javascript-node:latest` | — | `node` |
| `go` | `mcr.microsoft.com/devcontainers/go:latest` | — | `bash` |
| `rust` | `mcr.microsoft.com/devcontainers/rust:latest` | — | `bash` |
| `opencode` | — | `opencode:0` | `opencode` |
| `codex` | — | `codex:0` | `codex` |
| `claude` | — | `claude-code:0` | `claude` |
| `tmux` | — | `tmux:0` | `tmux` |
| `vim` | — | `vim:0` | `vim` |
| `base` | `mcr.microsoft.com/devcontainers/base:ubuntu24.04` | — | `bash` |

Features come from `ghcr.io/temeteke/devcontainer-features/` (the table omits the prefix). The set is defined in `bin/dcs`; adding a component means adding one `add_component` line there. `dcs --help` prints the same list.

## Usage

From the project directory you want to edit:

```sh
dcs opencode
```

That installs the opencode component and runs it. Combine components by separating them with commas; their Features are combined, and the first component that carries a command decides what runs:

```sh
dcs opencode,tmux,vim     # opencode, with tmux and Vim installed
dcs opencode,python       # opencode on the Python image
dcs tmux,opencode         # tmux, with opencode available inside it
```

Name a language component to choose the base image, or pass a full image reference directly as a component:

```sh
dcs python                # the Python REPL
dcs python,opencode       # python comes first, so the Python REPL runs
dcs python:3.12,opencode  # a specific Python tag, then opencode
```

Options come before the component list. Everything after it is the container command: a command name runs instead of the default command, while options are passed to the default command:

```sh
dcs opencode bash                 # a shell instead of opencode
dcs opencode --help               # run opencode --help
dcs opencode opencode --help      # the same, by naming the command explicitly
```

`--` ends the wrapper's option parsing, and the arguments after it are the command and its arguments. It lets a command name that begins with a dash be passed.

Use a different base image and add extra Features (remember that options come before the component list):

```sh
dcs --image mcr.microsoft.com/devcontainers/python:3.12-bookworm \
  --feature ghcr.io/devcontainers/features/go:1 codex
```

`--image` overrides any image a component carries, and `--feature` takes a full Feature reference (short names are not expanded). The tmux, Vim and agent Features require a Debian/Ubuntu-compatible image with `apt-get`.

`--help` is dcs's own help only before the component list: `dcs --help` prints it, while `dcs opencode --help` runs `opencode --help` in the container.

Use `dcs --help` for the wrapper's options.

## Behavior

- **Disposable:** Every call gets a unique `dcs.session` Docker label; the corresponding container is removed at process exit or on normal signals. Built Docker images/layers remain cached.
- **Components:** The first positional argument names zero or more built-in components (see [Components](#components)). Their Features are combined without duplicates; the first component that carries an image sets the base image, and the first that carries a command is run. A component set that omits tmux and Vim needs no host terminal configuration.
- **Command:** dcs options come before the component list, and everything after it is the container command. With no command, `dcs` runs the first component's command; `dcs` on its own appends the `base` component, so it starts a `bash` shell. A command name runs instead of the default command; options are passed to the default command, so `dcs opencode --help` runs `opencode --help`.
- **Workspace:** The current directory is passed to Dev Container CLI as `--workspace-folder`. `dcs` does not override `--mount-workspace-git-root`, so the CLI's default behavior applies (mounting the Git repository root when detected).
- **Configuration:** `dcs` generates an ephemeral `devcontainer.json` outside your repository. Existing `.devcontainer` files are ignored and never modified.
- **Extra Features:** `--feature` may be repeated and takes a full Feature reference (short names are not expanded). Each Feature is configured with its default options, and is added on top of the components' Features.
- **Image:** A component may carry a base image; the first one named wins, and `--image` overrides it. With no image, the `base` component provides `mcr.microsoft.com/devcontainers/base:ubuntu24.04`. The tmux, Vim and agent Features require a Debian/Ubuntu-compatible image with `apt-get`.
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
