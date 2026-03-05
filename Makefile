PYTHON := python3
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
SCENARIO ?= still
METHODS ?= all
CORPUS ?= ubfc_rppg_v1
GT_MODE ?= bpm_row
MAX_LAG_SECONDS ?= 2.0
ROI_FUSION_MODE ?= multi_snr
ROI_SNR_EXPONENT ?= 1.0

.PHONY: venv install run freeze clean-venv test evaluate plots diagnostics sweep corpus-manifest corpus-batch corpus-download corpus-latex corpus-render paper-figures

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
	$(VENV_PY) scripts/offline_evaluate.py --video "$(VIDEO)" --scenario "$(SCENARIO)" --methods "$(METHODS)" --ground-truth-mode "$(GT_MODE)" --max-lag-seconds "$(MAX_LAG_SECONDS)" --roi-fusion-mode "$(ROI_FUSION_MODE)" --roi-snr-exponent "$(ROI_SNR_EXPONENT)" $(if $(GT),--ground-truth "$(GT)",) $(if $(RUN_ID),--run-id "$(RUN_ID)",)

plots:
	$(VENV_PY) scripts/generate_figures.py --run-dir "$(RUN_DIR)"

diagnostics:
	$(VENV_PY) scripts/generate_subject_diagnostics.py --run-dir "$(RUN_DIR)"

sweep:
	$(VENV_PY) scripts/sweep_method_params.py --manifest "$(MANIFEST)" --method "$(METHOD)"

corpus-manifest:
	$(VENV_PY) scripts/build_corpus_manifest.py --corpus "$(CORPUS)" --root "$(CORPUS_ROOT)" $(if $(MANIFEST_OUT),--output "$(MANIFEST_OUT)",)

corpus-batch:
	$(VENV_PY) scripts/run_manifest_batch.py --manifest "$(MANIFEST)" --protocol "configs/experiment_protocol.json" --methods "$(METHODS)" --scenario "$(SCENARIO)" --ground-truth-mode "$(GT_MODE)" --max-lag-seconds "$(MAX_LAG_SECONDS)" --roi-fusion-mode "$(ROI_FUSION_MODE)" --roi-snr-exponent "$(ROI_SNR_EXPONENT)" $(if $(AGG_OUT),--aggregate-out "$(AGG_OUT)",)

corpus-download:
	$(VENV_PY) scripts/download_public_corpora.py $(if $(URLS_JSON),--urls-json "$(URLS_JSON)",) $(if $(UBFC_URL),--ubfc-url "$(UBFC_URL)",) $(if $(FORCE),--force,)

corpus-latex:
	$(VENV_PY) scripts/export_latex_table.py $(if $(LATEX_IN),--input "$(LATEX_IN)",) $(if $(LATEX_OUT),--output "$(LATEX_OUT)",)

corpus-render:
	$(VENV_PY) scripts/render_latex_table.py $(if $(LATEX_TEX),--input "$(LATEX_TEX)",) $(if $(RENDER_OUT),--output "$(RENDER_OUT)",)

paper-figures:
	$(VENV_PY) scripts/create_paper_illustrations.py --run-id "$(RUN_ID)" --video "$(VIDEO)" $(if $(PAPER_FIG_OUT),--output-dir "$(PAPER_FIG_OUT)",)

freeze:
	$(VENV_PIP) freeze > requirements.txt

clean-venv:
	rm -rf $(VENV_DIR)
