.DEFAULT_GOAL := help

BINDIR ?= $(HOME)/.local/bin

.PHONY: help install install-dcs install-devcontainer uninstall uninstall-dcs uninstall-devcontainer test

help:
	@printf 'Targets:\n  make install                 Install dcs and, if missing, Dev Container CLI via npm\n  make install-dcs             Install only dcs\n  make install-devcontainer    Install Dev Container CLI if missing\n  make uninstall               Remove dcs only\n  make uninstall-dcs           Remove only dcs\n  make uninstall-devcontainer  Remove npm-managed Dev Container CLI only\n  make test                    Run offline tests\n'

install: install-devcontainer install-dcs

install-devcontainer:
	@if command -v devcontainer >/dev/null 2>&1; then \
		printf 'Using existing devcontainer: %s\n' "$$(command -v devcontainer)"; \
	else \
		if ! command -v npm >/dev/null 2>&1; then \
			printf 'npm is required to install @devcontainers/cli (on Arch Linux: sudo pacman -S npm)\n' >&2; \
			exit 1; \
		fi; \
		printf 'Installing @devcontainers/cli using npm global configuration\n'; \
		npm install --global @devcontainers/cli || exit $$?; \
		if ! command -v devcontainer >/dev/null 2>&1; then \
			printf 'devcontainer was installed but is not on PATH; check the npm global bin directory (npm prefix --global)\n' >&2; \
			exit 1; \
		fi; \
		printf 'Installed devcontainer: %s\n' "$$(command -v devcontainer)"; \
	fi

install-dcs:
	install -Dm755 bin/dcs "$(BINDIR)/dcs"

uninstall: uninstall-dcs

uninstall-dcs:
	@rm -f -- "$(BINDIR)/dcs"
	@printf 'Removed dcs from %s (Dev Container CLI was not changed)\n' "$(BINDIR)"

uninstall-devcontainer:
	@if ! command -v npm >/dev/null 2>&1; then \
		printf 'npm is required to uninstall @devcontainers/cli\n' >&2; \
		exit 1; \
	fi
	@npm uninstall --global @devcontainers/cli

test:
	bash -n bin/dcs
	python3 -m unittest discover -s tests -v
