# devcontainer-sandbox

`dcs` (Dev Container Sandbox) runs commands in disposable [Dev Containers](https://containers.dev/).
Each invocation names zero or more components. A component contributes a base image, an optional Dev Container Feature, and optionally the command to run. `dcs` starts an isolated container, runs the first component that carries a command (or the command you choose), and removes the container when it exits. Source files and selected agent/terminal settings are shared with the host.

## Requirements

- Linux or WSL2 with an accessible Docker Engine
- Bash 4+, `make`, and the [`devcontainer` CLI](https://github.com/devcontainers/cli)
- `npm` if `make install` needs to install the CLI
- The published Features from [devcontainers/features](https://github.com/devcontainers/features) and [temeteke/devcontainer-features](https://github.com/temeteke/devcontainer-features)

## Install and uninstall

From a checkout of this repository:

```sh
make install                 # dcs and, if missing, the Dev Container CLI
make install-dcs             # dcs only
make uninstall               # remove dcs only
make uninstall-devcontainer  # remove the npm-managed Dev Container CLI
```

`dcs` is installed to `~/.local/bin`; set `BINDIR` to change that (for example,
`make BINDIR=/your/bin install`). `make install` leaves an existing
`devcontainer` on `PATH` unchanged; otherwise it installs `@devcontainers/cli`
using npm's current global prefix. Ensure `~/.local/bin` and the npm global bin
directory are on `PATH`.

`make uninstall` never removes the Dev Container CLI. Use the same `BINDIR` as
at install time; remove a CLI installed by another package manager with that
manager.

## Quick start

From the project directory you want to edit:

```sh
dcs opencode                  # opencode
dcs opencode,tmux,vim         # with tmux and Vim
dcs python,node               # Python image + Node Feature
dcs python,node bash          # both languages, in a shell
dcs python:3.12               # versioned Python image
dcs node,python:3.12          # Node image + Python 3.12 Feature
dcs base bash                 # run a shell on the plain base image
dcs kubectl,helmfile          # Kubernetes tools (see host requirements)
dcs --mount-dir ../shared-lib python,node  # add another host directory
dcs opencode opencode --help  # pass options to opencode
```

Options come before the component list. Everything after the list is the
container command, replacing the default. A component is required before a
command; use `dcs base COMMAND` for a command on the plain base image. `dcs`
alone starts a bash shell. `dcs --help` is the wrapper's help only before the
component list. Name the command yourself to pass options to a component's
default command.

```sh
dcs --image mcr.microsoft.com/devcontainers/python:3.12 \
  --feature ghcr.io/devcontainers/features/go:1 codex
```

`--image` pre-sets the image, so a language named later is added as a Feature.
`--feature` is repeatable and takes a full Feature reference. The bundled
Features require a Debian/Ubuntu-compatible image with `apt-get`. Long options
that take a value accept both `--option VALUE` and `--option=VALUE`; short
options take the value as the next argument.

## Environment

`--env NAME` (or `-e NAME`) forwards a host environment variable to the
container; `--env NAME=VALUE` sets a literal value. The option is repeatable,
and a later value for the same name wins. A missing or unexported host variable
is an error.

```sh
export ANTHROPIC_API_KEY=...
dcs -e ANTHROPIC_API_KEY claude
dcs --env FOO=bar opencode
```

Options come before the component list. Values are available to the command
and to lifecycle hooks, and disappear with the container. Prefer the `NAME`
form for secrets: `NAME=VALUE` appears in shell history, the dcs process
arguments, and the ephemeral config, while `NAME` is resolved from the host
environment without writing the value to the config. A literal value
containing `${...}` may be expanded by the Dev Container CLI; use the `NAME`
form in that case. Avoid forwarding `PATH` or `HOME` unless intended; they
replace the container's values and can break the command.

## Additional directories

`--mount-dir DIR[:TARGET]` bind-mounts another host directory into the
container. The option is repeatable and must come before the component list.
`DIR` is relative to the current directory or absolute; `~` or a leading `~/`
is expanded, and the directory must exist. It is mounted at
`/workspaces/<TARGET>`, where `TARGET` is a single name directly under
`/workspaces`. Without `TARGET`, the directory's basename is used after
resolving symlinks.

```sh
dcs --mount-dir ../shared-lib python,node
dcs --mount-dir ../a/lib:lib-a --mount-dir ../b/lib:lib-b opencode
```

The mount is writable; changes are made on the host and survive container
deletion. There is no read-only mode. The host root and the workspace mount
source (the Git root when applicable) are refused, as are files and paths that
do not exist. A `TARGET` that is already used by the workspace or another mount
is rejected.

In the container, the mount is at `/workspaces/<TARGET>`. When `dcs` runs in a
Git repository, the workspace is mounted from its Git root. If it is run from a
subdirectory, the container's workspace folder is
`/workspaces/<repo>/<subdir>`, so `../<TARGET>` may not resolve to the mount.
Use `/workspaces/<TARGET>` or adjust the relative path.

`TARGET` cannot contain `/`, `:`, `,`, `"`, `${...}`, or control characters,
cannot be `.` or `..`, and cannot start or end with whitespace. `DIR` cannot
contain `,`, `"`, `${...}`, or control characters, and cannot start or end with
whitespace. Internal spaces are allowed in both. `${...}` is rejected because
the Dev Container CLI would expand it in the generated config. `DIR` and
`TARGET` are separated by the last `:`, so a `DIR` containing `:` needs an
explicit `TARGET`. If the whole `DIR:TARGET` string is also an existing
directory, `dcs` refuses the ambiguous mount; choose a different `TARGET` or
add another `:TARGET`. Docker's `-v`, `--volume`, and `--mount` syntax is not
supported; use this option's `DIR[:TARGET]` form. Each mount widens the
sandbox; mount only the directories you need.

## Components

`base` provides the plain `mcr.microsoft.com/devcontainers/base:ubuntu24.04`
image, with no Feature or command. It is appended unless named.

The first argument is a comma-separated list. Components are processed in order:
the first image wins, later components are added as Features, and the first
command runs (`bash` if none does).

| Language | Pinned versions | Command |
| --- | --- | --- |
| `python` | 3.14, 3.13, 3.12, 3.11, 3.10 | `python` |
| `node` | 24, 22, 20 | `node` |
| `go` | 1.27, 1.26, 1.25 | — |
| `rust` | 1.87, 1.86, 1.85 | — |
| `java` | 25, 21, 17 | — |
| `dotnet` | 10.0, 9.0, 8.0 | — |
| `ruby` | 3.4, 3.3, 3.2 | — |
| `php` | 8.5, 8.4, 8.3 | — |
| `cpp` | — | — |

The remaining components are Feature-only (default command in parentheses):
`opencode` (`opencode`), `codex` (`codex --no-daemon`), `claude` (`claude`),
`tmux` (`tmux`), `vim` (`vim`), `playwright`, `gitlab-cli`, `github-cli`,
`kubectl`, `helmfile`, `git-config`.

The bare name uses the latest image; a versioned component such as
`python:3.12` uses the image tag when it comes first and the Feature's `version`
option when layered. Rust version components are Feature-only; `cpp` is
image-only and must come first. An image-only component that follows an
image-setting component is rejected.

Language images come from `mcr.microsoft.com/devcontainers/<language>:<tag>`
(`node` uses `javascript-node`); each language except `cpp` also has a matching
`ghcr.io/devcontainers/features/<language>` Feature. The tool Features come from
`ghcr.io/temeteke/devcontainer-features`: the agent, terminal and Kubernetes
tools, `gitlab-cli`, `github-cli`, and `git-config`. `github-cli` wraps the
official Feature and persists `~/.config/gh`; `gitlab-cli` and `github-cli`
also install `git-config` as a dependency. Run `dcs --help` for the exact tags,
Feature versions and options.

Some of these Features bind-mount host files and need them to exist before the
container starts:

| Component | Host path |
| --- | --- |
| `kubectl` | `~/.kube` |
| `github-cli` | `~/.config/gh`, `~/.gitconfig` |
| `gitlab-cli` | `~/.config/glab-cli`, `~/.gitconfig` |
| `git-config` | `~/.gitconfig` |

Create them first, for example:

```sh
mkdir -p ~/.kube ~/.config/gh ~/.config/glab-cli
touch ~/.gitconfig
```

`dcs` does not check these paths; a missing source surfaces as a container
creation error.

Adding a component, a version or a Feature option means adding one
`add_component` line in `bin/dcs`; its command is an argv, so it may carry fixed
arguments.

## Behavior

- **Disposable**: Every call gets a unique `dcs.session` label and its container is removed at exit or on normal signals. Built images remain cached; packages installed at runtime are discarded with the container.
- **Workspace**: The current directory is passed as `--workspace-folder`; `dcs` leaves the CLI's `--mount-workspace-git-root` default in place. `--mount-dir` adds writable bind mounts directly under `/workspaces`.
- **Configuration**: An ephemeral `devcontainer.json` is generated outside the repository; existing `.devcontainer` files are ignored and never modified.
- **Lifecycle**: `devcontainer up` builds and starts the container and applies Feature lifecycle hooks; `devcontainer exec` runs the command; `docker rm -f` removes only this session's container.

The wrapper does not implement persistent containers or `.devcontainer`
generation. Use Dev Container CLI and Templates for persistent environments.

## Host configuration and safety

Some Features bind-mount host files and directories. A bind-mount source must
exist before container creation; `dcs` does not check the paths used by
Features, so a missing one surfaces as a container-creation error. Mounted
paths are writable from the container and changes survive container deletion.
See each Feature's documentation for the paths it uses. `--mount-dir` sources
are checked before the container starts.

The host paths listed under Components can contain sensitive data: `~/.kube`
holds cluster credentials and client certificates, and `~/.config/gh`,
`~/.config/glab-cli` and `~/.gitconfig` hold tokens or credential
configuration. `git-config` filters host-specific settings from the generated
container config, but the mounted host `~/.gitconfig` itself remains writable.
Enable these components only for projects you trust.

The sandbox limits accidental access to files outside the workspace. It is not
a security boundary for untrusted or malicious code: credentials and state may
be shared, and the container retains network access. Environment variables
passed with `--env` are visible to container processes; the `NAME` form keeps
the value out of the ephemeral config, but the container is not a security
boundary. `--mount-dir` exposes additional host directories; mount only the
directories you need. Do not bind-mount the Docker socket or host root into the
container; `dcs` does not do so itself, and `--mount-dir` refuses the host root.
It does not detect a Docker socket inside a mounted parent directory such as
`/var/run` or `/run`; avoid mounting those directories.

`SIGKILL`, host shutdown or Docker failures can leave a container running. Check
`docker ps -a --filter label=dcs.session` and remove only stale `dcs` containers.

## Development

Run the offline tests (Docker and Dev Container CLI are mocked):

```sh
make test
```

These tests validate option handling and lifecycle/cleanup behavior, not a real
Docker container or tmux/Vim Feature installation. Run an integration check on
your actual Linux/WSL2 Docker host before relying on this for daily development.
