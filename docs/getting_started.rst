Getting Started
===============

Installation
------------

**From source** (current recommended method):

.. code-block:: bash

   git clone https://github.com/gorgeousfish/pretest-py.git
   cd pretest-py
   pip install -e ".[data]"

**From PyPI** (available after public release):

.. code-block:: bash

   pip install "pretest-py[data]"

**Development install** (from a local clone):

.. code-block:: bash

   git clone https://github.com/gorgeousfish/pretest-py.git
   cd pretest-py
   pip install -e ".[test,data]"

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

The package ships with several dependency groups:

.. list-table::
   :header-rows: 1
   :widths: 15 40 25 20

   * - Extra
     - Purpose
     - Install
     - Used by
   * - ``data``
     - pandas DataFrame API (:func:`pretest.pretest_from_dataframe`)
     - ``pip install "pretest-py[data]"``
     - DataFrame API, Tutorials 1--3
   * - ``progress``
     - tqdm progress bars in Monte Carlo runs
     - ``pip install "pretest-py[progress]"``
     - Monte Carlo long runs (optional)
   * - ``paper``
     - matplotlib plotting, numpy, build/publish tools
     - ``pip install "pretest-py[paper]"``
     - Event Study Plot, Tutorial 4
   * - ``docs``
     - Sphinx documentation build chain
     - ``pip install "pretest-py[docs]"``
     - Documentation builds only
   * - ``test``
     - pytest and related testing utilities
     - ``pip install "pretest-py[test]"``
     - Test suite only

Python version
^^^^^^^^^^^^^^

**pretest-py** requires Python **>= 3.11**.  Python 3.11 and 3.12 are
tested in CI.


Quick Start
-----------

The fastest path from data to inference is :func:`pretest.pretest_from_dataframe`.
The example below uses the built-in DGP generator so you can run it without
downloading external datasets.

.. code-block:: python

   from pretest import generate_did_data_from_preset, pretest_from_dataframe

   # 1. Generate a synthetic DID panel (Section 6 baseline scenario)
   df, config = generate_did_data_from_preset("section6_baseline", n_units=200)

   # 2. Run the conditional extrapolation pre-test
   snapshot = pretest_from_dataframe(
       df,
       outcome="outcome",
       treatment="treatment",
       time="time",
       threshold=0.5,
       treat_time=float(config.t_pre + 1),
       p=2.0,
       alpha=0.05,
       mode="iterative",
       simulations=5000,
       seed=12345,
   )

   # 3. Inspect the results
   summary = snapshot.reporting_summary()
   print(summary["decision"])        # 'PASS' or 'FAIL'
   print(summary["S_pre"])           # estimated severity
   print(summary["conditional_interval"])  # conditionally valid CI

The ``reporting_summary()`` dictionary contains:

- ``decision`` -- ``"PASS"`` if the observed severity does not exceed the
  threshold (``S_pre <= M``), meaning the conditional CI is valid; ``"FAIL"``
  otherwise.
- ``S_pre`` -- the estimated severity statistic (L_p power mean of estimated
  violations).
- ``threshold`` -- the user-specified bound *M*.
- ``delta_bar`` -- weighted average of post-treatment DID estimates.
- ``f_alpha`` -- Monte Carlo critical value used for CI construction.
- ``conditional_interval`` -- the conditionally valid confidence interval
  ``[lower, upper]`` (available only when the pre-test passes).
- ``conventional_interval`` -- the standard Wald-type CI ignoring the
  pre-test step.

Interpreting the output
^^^^^^^^^^^^^^^^^^^^^^^

When the pre-test **passes** (``decision == "PASS"``):

The data are consistent with at most *M* severity of parallel-trends
violations.  The conditional confidence interval accounts for the
pre-testing step and maintains valid coverage conditional on passing.

When the pre-test **fails** (``decision == "FAIL"``):

The observed pre-treatment pattern exceeds the researcher-specified
tolerance *M*.  No conditional CI is reported.  Consider:

1. Increasing *M* (more tolerant of violations).
2. Investigating the source of trend divergence.
3. Using a sensitivity analysis (:func:`pretest.compute_m_sensitivity`) to
   find the breakdown point.

What to do with the result
^^^^^^^^^^^^^^^^^^^^^^^^^^

When the pre-test **passes**, report the conditional confidence interval
as your primary interval for the average DID estimand. Comparing it to
the conventional interval shows how much the pre-testing step widens the
range. Running :func:`pretest.compute_m_sensitivity` around your chosen
threshold demonstrates stability of the decision.

When the pre-test **fails**, the conditional CI is undefined by design.
This signals that the observed pre-trend exceeds your tolerance M.
Investigate which periods drive the violation, whether certain groups
behave differently, or whether a more tolerant M is defensible. The
:func:`pretest.compute_m_sensitivity` function locates the breakdown
point—the smallest M at which your data would pass.


What next?
----------

- :doc:`user_guide` -- full parameter guidance and advanced features.
- :doc:`tutorials/index` -- worked examples from simple to complex.
- :doc:`api/index` -- complete API reference.
