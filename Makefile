# Tiny shortcuts. TRAIN_PY = a Python with requirements-train.txt installed.
TRAIN_PY ?= python3
.PHONY: demo test intent
demo:    ## start the hub (venv + deps + DEMO data)
	./run.sh
test:    ## hub tests
	.venv/bin/pip install -q pytest httpx && .venv/bin/python -m pytest tests -q
intent:  ## rebuild data/intent/examples.csv and retrain the SMS intent classifier
	python3 -m hub.build_intent_examples && $(TRAIN_PY) -m hub.train_intent
