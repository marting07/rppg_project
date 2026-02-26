PYTHON := python3
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
SCENARIO ?= still
METHODS ?= all
CORPUS ?= ubfc_rppg_v1

.PHONY: venv install run freeze clean-venv test evaluate plots corpus-manifest corpus-batch corpus-download corpus-latex corpus-render

venv:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip

install: venv
	$(VENV_PIP) install -r requirements.txt

run:
	$(VENV_PY) main.py

test:
	$(VENV_PY) -m unittest discover -s tests -p "test_*.py"

evaluate:
	$(VENV_PY) scripts/offline_evaluate.py --video "$(VIDEO)" --scenario "$(SCENARIO)" --methods "$(METHODS)" $(if $(GT),--ground-truth "$(GT)",) $(if $(RUN_ID),--run-id "$(RUN_ID)",)

plots:
	$(VENV_PY) scripts/generate_figures.py --run-dir "$(RUN_DIR)"

corpus-manifest:
	$(VENV_PY) scripts/build_corpus_manifest.py --corpus "$(CORPUS)" --root "$(CORPUS_ROOT)" $(if $(MANIFEST_OUT),--output "$(MANIFEST_OUT)",)

corpus-batch:
	$(VENV_PY) scripts/run_manifest_batch.py --manifest "$(MANIFEST)" --protocol "configs/experiment_protocol.json" --methods "$(METHODS)" --scenario "$(SCENARIO)" $(if $(AGG_OUT),--aggregate-out "$(AGG_OUT)",)

corpus-download:
	$(VENV_PY) scripts/download_public_corpora.py --datasets "$(CORPUS)" $(if $(URLS_JSON),--urls-json "$(URLS_JSON)",) $(if $(UBFC_URL),--ubfc-url "$(UBFC_URL)",) $(if $(COHFACE_URL),--cohface-url "$(COHFACE_URL)",) $(if $(PURE_URL),--pure-url "$(PURE_URL)",) $(if $(FORCE),--force,)

corpus-latex:
	$(VENV_PY) scripts/export_latex_table.py $(if $(LATEX_IN),--input "$(LATEX_IN)",) $(if $(LATEX_OUT),--output "$(LATEX_OUT)",)

corpus-render:
	$(VENV_PY) scripts/render_latex_table.py $(if $(LATEX_TEX),--input "$(LATEX_TEX)",) $(if $(RENDER_OUT),--output "$(RENDER_OUT)",)

freeze:
	$(VENV_PIP) freeze > requirements.txt

clean-venv:
	rm -rf $(VENV_DIR)
