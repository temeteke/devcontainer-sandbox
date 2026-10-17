.DEFAULT_GOAL := help

PREFIX ?= $(HOME)/.local
BINDIR := $(PREFIX)/bin

.PHONY: help install install-dcs install-devcontainer test

help:
	@printf 'Targets:\n  make install  Install dcs and, if missing, Dev Container CLI via npm\n  make test     Run offline tests\n'

install: install-devcontainer install-dcs

install-devcontainer:
	@if command -v devcontainer >/dev/null 2>&1; then \
		printf 'Using existing devcontainer: %s\n' "$$(command -v devcontainer)"; \
	else \
		if ! command -v npm >/dev/null 2>&1; then \
			printf 'npm is required to install @devcontainers/cli (on Arch Linux: sudo pacman -S npm)\n' >&2; \
			exit 1; \
		fi; \
		printf 'Installing @devcontainers/cli into %s\n' "$(PREFIX)"; \
		npm install --global --prefix "$(PREFIX)" @devcontainers/cli || exit $$?; \
		if [ ! -x "$(BINDIR)/devcontainer" ]; then \
			printf 'Expected devcontainer at %s; check npm installation\n' "$(BINDIR)/devcontainer" >&2; \
			exit 1; \
		fi; \
		printf 'Installed devcontainer: %s\n' "$(BINDIR)/devcontainer"; \
	fi

install-dcs:
	install -Dm755 bin/dcs "$(BINDIR)/dcs"

test:
	bash -n bin/dcs
	python3 -m unittest discover -s tests -v
