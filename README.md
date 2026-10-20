# devcontainer-sandbox

`dcs` (Dev Container Sandbox) runs commands in disposable [Dev Containers](https://containers.dev/).
Each invocation names zero or more components. A component contributes a base image (a language image such as Python or Node, or the plain base image), a set of Dev Container Features (a coding agent, tmux, Vim, ...), and the command to run. `dcs` creates an isolated container, runs the first component that carries a command (or the command you choose instead), and removes that container when the command exits. Source files and selected agent/terminal settings are deliberately shared with the host.

## Requirements

- Linux or WSL2 with an accessible Docker Engine
- Bash 4+, `make`, and the [`devcontainer` CLI](https://github.com/devcontainers/cli) (installed by `make install` when missing)
- `npm` for the first installation if `devcontainer` is not already on `PATH`
- The published Features the components use: [temeteke/devcontainer-features](https://github.com/temeteke/devcontainer-features) and [devcontainers/features](https://github.com/devcontainers/features)

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

The first argument names zero or more components, separated by commas. A component is a named entry that may carry a base image, one Dev Container Feature (with options) and the command to run. Components are processed in order: a component that carries an image sets it when no image is set yet, and otherwise its Feature is added. So the first language gives its image and later ones are layered on as Features. The first component that carries a command is run (and `bash` runs when none does). The `base` component stays where it is when named, and is appended otherwise.
`bash` runs when no component carries a command, so `dcs` on its own starts a `bash` shell.

| Component | Image | Feature (options) | Default command |
| --- | --- | --- | --- |
| `base` | `mcr.microsoft.com/devcontainers/base:ubuntu24.04` | — | — |
| `python` | `mcr.microsoft.com/devcontainers/python:latest` | `ghcr.io/devcontainers/features/python:1` | `python` |
| `python:3.14` … `python:3.10` | `mcr.microsoft.com/devcontainers/python:<version>` | `ghcr.io/devcontainers/features/python:1` (`version`) | `python` |
| `node` | `mcr.microsoft.com/devcontainers/javascript-node:latest` | `ghcr.io/devcontainers/features/node:1` | `node` |
| `node:24` / `node:22` / `node:20` | `mcr.microsoft.com/devcontainers/javascript-node:<version>` | `ghcr.io/devcontainers/features/node:1` (`version`) | `node` |
| `go` | `mcr.microsoft.com/devcontainers/go:latest` | `ghcr.io/devcontainers/features/go:1` | — |
| `go:1.27` / `go:1.26` / `go:1.25` | `mcr.microsoft.com/devcontainers/go:<version>` | `ghcr.io/devcontainers/features/go:1` (`version`) | — |
| `rust` | `mcr.microsoft.com/devcontainers/rust:latest` | `ghcr.io/devcontainers/features/rust:1` | — |
| `rust:1.87` / `rust:1.86` / `rust:1.85` | — | `ghcr.io/devcontainers/features/rust:1` (`version`) | — |
| `java` | `mcr.microsoft.com/devcontainers/java:latest` | `ghcr.io/devcontainers/features/java:1` | — |
| `java:25` / `java:21` / `java:17` | `mcr.microsoft.com/devcontainers/java:<version>` | `ghcr.io/devcontainers/features/java:1` (`version`) | — |
| `dotnet` | `mcr.microsoft.com/devcontainers/dotnet:latest` | `ghcr.io/devcontainers/features/dotnet:2` | — |
| `dotnet:10.0` / `dotnet:9.0` / `dotnet:8.0` | `mcr.microsoft.com/devcontainers/dotnet:<version>` | `ghcr.io/devcontainers/features/dotnet:2` (`version`) | — |
| `ruby` | `mcr.microsoft.com/devcontainers/ruby:latest` | `ghcr.io/devcontainers/features/ruby:2` | — |
| `ruby:3.4` / `ruby:3.3` / `ruby:3.2` | `mcr.microsoft.com/devcontainers/ruby:<version>` | `ghcr.io/devcontainers/features/ruby:2` (`version`) | — |
| `php` | `mcr.microsoft.com/devcontainers/php:latest` | `ghcr.io/devcontainers/features/php:1` | — |
| `php:8.5` / `php:8.4` / `php:8.3` | `mcr.microsoft.com/devcontainers/php:<version>` | `ghcr.io/devcontainers/features/php:1` (`version`) | — |
| `cpp` | `mcr.microsoft.com/devcontainers/cpp:latest` | — | — |
| `opencode` | — | `ghcr.io/temeteke/devcontainer-features/opencode:0` | `opencode` |
| `codex` | — | `ghcr.io/temeteke/devcontainer-features/codex:0` | `codex --no-daemon` |
| `claude` | — | `ghcr.io/temeteke/devcontainer-features/claude-code:0` | `claude` |
| `tmux` | — | `ghcr.io/temeteke/devcontainer-features/tmux:0` | `tmux` |
| `vim` | — | `ghcr.io/temeteke/devcontainer-features/vim:0` | `vim` |
| `playwright` | — | `ghcr.io/temeteke/devcontainer-features/playwright:0` | — |
| `gitlab-cli` | — | `ghcr.io/temeteke/devcontainer-features/gitlab-cli:0` | — |
| `github-cli` | — | `ghcr.io/devcontainers/features/github-cli:1` | — |

A language component carries both an image and a Feature: the first language named uses its (prebuilt) image, and any further ones are installed as Features on top. Its Feature is therefore skipped when its image was the one chosen. Layering a language as a Feature means the container is built (installing the Feature) instead of only pulling a prebuilt image; Docker layer caching makes repeated runs fast.

A versioned component such as `python:3.12`, `node:22` or `go:1.26` pins the language version: when it comes first the image tag does it, and when it is layered on as a Feature the Feature's `version` option does. Rust images only publish a major-tag image, so `rust:1.87` and friends are Feature-only and run on whatever image the other components chose. `cpp` has no Feature to layer, so it is image-only. Adding a component, a version or a Feature option means adding one `add_component` line in `bin/dcs`; its command is an argv, so it may carry fixed arguments. `dcs --help` prints the same list.

A component with no command of its own — base, go, rust, Java, .NET, Ruby, PHP, cpp and the CLI components — leaves the choice to a later component, and `bash` runs when none carries a command. `python`, `node` and the agents, tmux and Vim carry the command they open.

## Usage

From the project directory you want to edit:

```sh
dcs opencode
```

That installs the opencode component and runs it. Combine components by separating them with commas; the first component that carries a command decides what runs:

```sh
dcs opencode,tmux,vim     # opencode, with tmux and Vim installed
dcs opencode,python       # opencode on the Python image
dcs tmux,opencode         # tmux, with opencode available inside it
```

Name several languages to get all of them. The first uses its image and the rest are added as Features:

```sh
dcs python,node           # the Python image plus the Node Feature
dcs python,node bash      # both languages, in a shell
dcs base,python,node      # the plain base image, with languages as Features
dcs python:3.12           # the Python 3.12 image
dcs node,python:3.12      # the Node image, with the Python 3.12 Feature
dcs node:20               # the Node.js 20 image
```

The first named component that carries a command runs; for example `dcs python` opens the Python REPL and `dcs base,python` does too because `base` carries no command.

Options come before the component list. Everything after it is the container command, replacing the component's default command:

```sh
dcs opencode bash                 # a shell instead of opencode
dcs opencode opencode --help      # run opencode --help
dcs python python script.py       # run script.py in the Python sandbox
```

So an argument is only passed to the component's default command if you name that command yourself.

`--` ends the wrapper's option parsing, and the arguments after it are the command and its arguments. It lets a command name that begins with a dash be passed.

Use a different base image and add extra Features (remember that options come before the component list):

```sh
dcs --image mcr.microsoft.com/devcontainers/python:3.12-bookworm \
  --feature ghcr.io/devcontainers/features/go:1 codex
```

`--image` sets the base image before the components are processed, so a language named after it is added as a Feature instead of replacing the image; `--feature` takes a full Feature reference (short names are not expanded). The bundled Features require a Debian/Ubuntu-compatible image with `apt-get`.

`--help` is dcs's own help only before the component list. `dcs --help` prints it, while anything after the component list is run in the container, so pass a component's options by naming its command: `dcs opencode opencode --help`.

Use `dcs --help` for the wrapper's options.

## Behavior

- **Disposable:** Every call gets a unique `dcs.session` Docker label; the corresponding container is removed at process exit or on normal signals. Built Docker images/layers remain cached, but packages installed in the running container (for example with `pip install`) are discarded with it.
- **Components:** The first positional argument names zero or more built-in components (see [Components](#components)). They are processed in order: a component that carries an image sets it when none is set yet, and its Feature is added otherwise (without duplicates). The first component that carries a command is run.
- **Command:** dcs options come before the component list, and everything after it is the container command, replacing the component's default command. With no command, `dcs` runs the first component's command, or `bash` when no component carries one; `dcs` on its own appends the `base` component, so it starts a `bash` shell. Pass a component's options by naming its command, as in `dcs opencode opencode --help`.
- **Workspace:** The current directory is passed to Dev Container CLI as `--workspace-folder`. `dcs` does not override `--mount-workspace-git-root`, so the CLI's default behavior applies (mounting the Git repository root when detected).
- **Configuration:** `dcs` generates an ephemeral `devcontainer.json` outside your repository. Existing `.devcontainer` files are ignored and never modified.
- **Extra Features:** `--feature` may be repeated and takes a full Feature reference (short names are not expanded). Each Feature is configured with its default options, and is added on top of the components' Features.
- **Image:** The first component that carries an image sets the base image; later languages are added as Features instead. `--image` pre-sets the image. With no image at all, the `base` component provides `mcr.microsoft.com/devcontainers/base:ubuntu24.04`. The bundled Features require a Debian/Ubuntu-compatible image with `apt-get`.
- **Lifecycle:** `devcontainer up` builds/starts the container and applies Feature lifecycle hooks. `devcontainer exec` runs the selected command there, locating the container by the same `dcs.session` label. `docker rm -f` cleans up only the container labeled for this invocation.

The wrapper deliberately does not implement persistent container management or `.devcontainer` generation. For persistent environments, use Dev Container CLI and Templates directly.

## Host configuration and safety

Some Features bind-mount host files and directories. A bind-mount source must exist on the host before container creation; `dcs` does not check host paths, so a missing one surfaces as a container-creation error. The mounted paths **are writable from the container** and changes survive container deletion. See each Feature's documentation for the paths it uses.

The sandbox is intended to limit accidental access to files outside the workspace. It is **not a security boundary for untrusted or malicious code**, especially because credentials and state may be shared and the container retains network access. Do not bind-mount the Docker socket or host root into the container. `dcs` does not do so itself.

In rare cases, `SIGKILL`, host shutdown, or Docker failures can leave a container running. Check `docker ps -a --filter label=dcs.session` and remove only stale `dcs` containers after identifying them.

## Development

Run the offline tests (Docker and Dev Container CLI are mocked). The test suite requires Python 3; `dcs` itself does not.

```sh
bash -n bin/dcs
python3 -m unittest discover -s tests -v
```

These tests validate option handling and lifecycle/cleanup behavior, **not** a real Docker container or tmux/Vim Feature installation. Run an integration check on your actual Linux/WSL Docker host before relying on this for daily development.
