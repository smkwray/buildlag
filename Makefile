PYTHON ?= python

build-demo:
	PYTHONPATH=src $(PYTHON) -m underbuilt_overpriced.cli build-demo

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

serve:
	cd site && $(PYTHON) -m http.server 8000
