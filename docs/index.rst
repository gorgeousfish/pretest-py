.. pretest documentation master file

pretest: Conditional Extrapolation Pre-Testing for DID
======================================================

**pretest** is a Python package implementing the conditional extrapolation
pre-testing framework for difference-in-differences designs, based on
Mikhaeil & Harshaw (2026).

Key Features
------------

- Severity-based pre-testing with configurable thresholds
- Conditional confidence intervals with proven coverage guarantees
- Influence-function covariance estimation, including cluster-robust
- Monte Carlo simulation for critical values and coverage diagnostics
- M-sensitivity analysis for threshold robustness
- DataFrame pipeline API for panel and repeated cross-section data
- Built-in DGP generator for simulation studies
- Event-study plotting aligned with the paper's visual conventions

.. toctree::
   :maxdepth: 2
   :caption: Contents

   getting_started
   user_guide
   theory
   api/index
   tutorials/index
   changelog
   citation
