Tutorials
=========

Worked examples demonstrating the **pretest-py** package.  Each tutorial
corresponds to a self-contained script in the ``examples/`` directory of the
source repository.

.. list-table::
   :header-rows: 1
   :widths: 5 25 55 15

   * - #
     - Tutorial
     - Description
     - Difficulty
   * - 1
     - :ref:`Quickstart <tutorial-quickstart>`
     - Short introduction: generate synthetic data, run the pre-test,
       and interpret the output.
     - Beginner
   * - 2
     - :ref:`Prop 99 Replication <tutorial-prop99>`
     - Reproduce the California Proposition 99 case study from
       Mikhaeil & Harshaw (2026), Section 7.
     - Intermediate
   * - 3
     - :ref:`Advanced Pipeline <tutorial-pipeline>`
     - Combine multiple threshold sweeps, weighted estimands, and batch
       processing into a single analysis pipeline.
     - Intermediate
   * - 4
     - :ref:`Event Study Plot <tutorial-eventstudy>`
     - Produces event study figures with conditional and conventional
       confidence bands.
     - Beginner
   * - 5
     - :ref:`Monte Carlo Simulation <tutorial-montecarlo>`
     - Coverage verification using the built-in DGP engine.
     - Advanced


.. _tutorial-quickstart:

1. Quickstart
-------------

**Requires:** ``pip install "pretest-py[data]"``

**File:** ``examples/01_quickstart.py``

The minimal path from installation to a usable result.  Demonstrates
:func:`pretest.pretest_from_dataframe` with a hand-crafted panel dataset,
shows how to read the ``reporting_summary()`` dictionary, and produces a
basic event study plot.

Run:

.. code-block:: bash

   python examples/01_quickstart.py


.. _tutorial-prop99:

2. Prop 99 Replication
----------------------

**Requires:** ``pip install "pretest-py[data]"``

**File:** ``examples/02_prop99_replication.py``

Applies the pre-test to the Abadie, Diamond & Hainmueller (2010) tobacco
control dataset.  Walks through loading real observational data, choosing
appropriate *M* and *p* values, and comparing conditional inference to
standard DID results.  Demonstrates the iterative vs. overall mode
distinction.

Run:

.. code-block:: bash

   python examples/02_prop99_replication.py


.. _tutorial-pipeline:

3. Advanced Pipeline
--------------------

**Requires:** ``pip install "pretest-py[data]"``

**File:** ``examples/03_advanced_pipeline.py``

Shows how to:

- Sweep across multiple thresholds *M* in a single pass.
- Supply custom ``post_weights`` for non-uniform post-treatment weighting.
- Integrate M-sensitivity analysis into an automated reporting workflow.
- Use :func:`pretest.compute_pretest_snapshot` for lower-level control.

Run:

.. code-block:: bash

   python examples/03_advanced_pipeline.py


.. _tutorial-eventstudy:

4. Event Study Plot
-------------------

**Requires:** ``pip install "pretest-py[data,paper]"``

**File:** ``examples/04_event_study_plot.py``

Produces event study figures with conditional and conventional CIs.  Covers:

- Customizing axis labels, colors, and confidence band styles.
- Overlaying conditional vs. conventional CIs.
- Exporting to PDF/PNG at print resolution (300 dpi).
- Multi-panel layouts for comparing scenarios.

Run:

.. code-block:: bash

   python examples/04_event_study_plot.py


.. _tutorial-montecarlo:

5. Monte Carlo Simulation
--------------------------

**Requires:** ``pip install "pretest-py[data]"`` (``progress`` extra optional for progress bars)

**File:** ``examples/05_monte_carlo_simulation.py``

Coverage verification using the built-in DGP engine.
Demonstrates:

- Constructing a :class:`pretest.DGPConfig` with known violation paths.
- Running :func:`pretest.run_monte_carlo_coverage` with progress reporting.
- Interpreting conditional coverage, pass rate, and CI width.
- Varying DGP parameters to explore power–size tradeoffs.

Run:

.. code-block:: bash

   python examples/05_monte_carlo_simulation.py
