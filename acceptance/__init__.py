"""Project-specific half of the DAE acceptance pipeline (ATDD).

- ``generator.py`` reads a feature's ``.build/spec.json`` (the fixed IR
  produced by the portable ``dae_gherkin.py`` parser) and emits pytest
  files into ``<feature>/.build/generated/``.
- ``handlers/`` binds each Gherkin step's text to Quaestor's service
  layer (``backend/src/quaestor``).

Committed source. The IR and the generated tests are gitignored artifacts.
Entry point: ``./run-acceptance-tests.sh`` at the repo root.
"""
