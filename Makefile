PYTHON := python3
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

.PHONY: venv install run freeze clean-venv

venv:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip

install: venv
	$(VENV_PIP) install -r requirements.txt

run:
	$(VENV_PY) main.py

freeze:
	$(VENV_PIP) freeze > requirements.txt

clean-venv:
	rm -rf $(VENV_DIR)
