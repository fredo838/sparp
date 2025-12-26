SHELL := /bin/bash

.PHONY: $(MAKECMDGOALS)
.DEFAULT_GOAL := help

VENV := .venv
VENV_UV := .venv-uv
SRC := src/sparp

# get PYTHON_VERSION from 'requires-python' section in pyproject.toml
PYTHON_VERSION := $(shell grep '^requires-python' pyproject.toml | sed -E 's/.*([0-9]+\.[0-9]+).*/\1/')
UV_VERSION := 0.9.17

PYTHONV := python$(PYTHON_VERSION)
PYTHON_UV := $(VENV_UV)/bin/$(PYTHONV)
PYTHON := $(VENV)/bin/$(PYTHONV)
UV := VIRTUAL_ENV=$(VENV) $(PYTHON_UV) -m uv


bootstrap-uv:
	@if [ ! -f $(PYTHON_UV) ]; then \
		echo "--- Creating UV bootstrap venv ---"; \
		$(PYTHONV) -m venv $(VENV_UV); \
	fi
	@if ! $(PYTHON_UV) -m uv --version | grep -q "$(UV_VERSION)"; then \
		echo "--- Installing/Updating UV to $(UV_VERSION) ---"; \
		$(PYTHON_UV) -m pip install --upgrade pip; \
		$(PYTHON_UV) -m pip install "uv==$(UV_VERSION)" \
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


help:
	@echo "Available targets:"
	@echo "  venv                          - Create or sync development venv"
	@echo "  freeze                        - List installed packages in .venv"
	@echo "  purge                         - Remove all venvs and build artifacts"
	@echo "  venv-purge                    - Purge then recreate the dev venv"
	@echo "  run-basic-example             - Run the basic example"
	@echo "  run-example EXAMPLE=callbacks - Run other examples"