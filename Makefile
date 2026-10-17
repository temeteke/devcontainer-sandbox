.DEFAULT_GOAL := help

BINDIR ?= $(HOME)/.local/bin

.PHONY: help install install-dcs install-devcontainer uninstall test

help:
	@printf 'Targets:\n  make install    Install dcs and, if missing, Dev Container CLI via npm\n  make uninstall  Remove dcs only (leave Dev Container CLI installed)\n  make test       Run offline tests\n'

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

uninstall:
	@rm -f -- "$(BINDIR)/dcs"
	@printf 'Removed dcs from %s (Dev Container CLI was not changed)\n' "$(BINDIR)"

test:
	bash -n bin/dcs
	python3 -m unittest discover -s tests -v
