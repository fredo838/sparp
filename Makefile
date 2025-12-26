SHELL := /bin/bash

.PHONY: $(MAKECMDGOALS)
.DEFAULT_GOAL := help

VENV := .venv
VENV_UV := .venv-uv
SRC := src/sparp

# get PYTHON_VERSION from 'requires-python' section in pyproject.toml
PYTHON_VERSION := $(shell grep '^requires-python' pyproject.toml | sed -E 's/.*([0-9]+\.[0-9]+).*/\1/')
UV_VERSION := 0.9.17
KEYRING_VERSION := 25.6.0

PYTHONV := python$(PYTHON_VERSION)
PYTHON_UV := $(VENV_UV)/bin/$(PYTHONV)
PYTHON := $(VENV)/bin/$(PYTHONV)
UV := VIRTUAL_ENV=$(VENV) $(PYTHON_UV) -m uv
KEYRING := $(PYTHON_UV) -m keyring

bootstrap-uv:
	@if [ ! -f $(PYTHON_UV) ]; then \
		echo "--- Creating UV bootstrap venv ---"; \
		$(PYTHONV) -m venv $(VENV_UV); \
	fi
	@if ! $(PYTHON_UV) -m uv --version | grep -q "$(UV_VERSION)"; then \
		echo "--- Installing/Updating UV to $(UV_VERSION) ---"; \
		$(PYTHON_UV) -m pip install --upgrade pip; \
		$(PYTHON_UV) -m pip install "uv==$(UV_VERSION)" "keyring==$(KEYRING_VERSION)"; \
	else \
		echo "--- UV $(UV_VERSION) already installed ---"; \
	fi

sync: bootstrap-uv
	$(UV) sync --all-extras --all-packages --all-groups --python $(PYTHONV)

venv: $(MAKE) sync

precommit:
	$(MAKE) pytest
	$(MAKE) ruff
	$(MAKE) mypy

purge:
	rm -rf $(VENV_UV) $(VENV) dist/ build/ *.egg-info

venv-purge: purge venv

ruff:
	$(MAKE) sync
	$(PYTHON) -m ruff format . 

mypy:
	$(MAKE) sync
	$(PYTHON) -m mypy $(SRC) tests

pytest:
	$(MAKE) sync
	$(PYTHON) -m pytest -s .

# make pytest-single TEST=test_stop_on_hard_fail
pytest-single:
	$(MAKE) sync
	$(PYTHON) -m pytest -s -k $(TEST) .

test:
	$(MAKE) pytest

freeze:
	@$(UV) pip freeze --python $(PYTHON)

build: venv
	@echo "--- Building the package ---"
	rm -rf dist/
	$(UV) build

run-basic-example:
	$(MAKE) sync
	PYTHONPATH=$(shell pwd)/src $(PYTHON) -m examples.basic_example

# make run-example EXAMPLE=custom_parser
run-example:
	$(MAKE) sync
	PYTHONPATH=$(shell pwd)/src $(PYTHON) -m examples.$(EXAMPLE)

## --- Keyring Auth & Release ---

auth: bootstrap-uv
	@echo "Storing PyPI token in system keyring..."
	@$(KEYRING) set https://upload.pypi.org/legacy/ __token__

release: build
	@echo "--- Fetching token from keyring ---"
	@TOKEN=$$( $(KEYRING) get https://upload.pypi.org/legacy/ __token__ ); \
	if [ -z "$$TOKEN" ]; then \
		echo "No token found in keyring."; \
		$(MAKE) auth; \
		TOKEN=$$( $(KEYRING) get https://upload.pypi.org/legacy/ __token__ ); \
	fi; \
	echo "--- Uploading to PyPI ---"; \
	UV_PUBLISH_TOKEN="$$TOKEN" $(UV) publish

help:
	@echo "Available targets:"
	@echo "  venv          - Create or sync development venv"
	@echo "  auth          - Set/Update PyPI token in system keyring"
	@echo "  release       - Build and upload to PyPI (checks keyring)"
	@echo "  freeze        - List installed packages in .venv"
	@echo "  tree          - Show dependency tree of .venv"
	@echo "  purge         - Remove all venvs and build artifacts"
	@echo "  venv-purge    - Purge then recreate the dev venv"