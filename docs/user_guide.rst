User Guide
==========

.. contents:: On this page
   :local:
   :depth: 2


Core Concepts
-------------

The conditional extrapolation pre-testing framework
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Standard difference-in-differences (DID) estimation relies on the parallel
trends assumption: absent treatment, the outcome gap between groups would have
remained constant.  Researchers routinely inspect pre-treatment coefficients
to assess this assumption, yet such "pre-tests" lack formal justification
when the subsequent inference depends on whether the test passes.

Mikhaeil & Harshaw (2026) develop a framework that formalizes this practice.
Their approach defines a *severity measure* that quantifies how badly
parallel trends are violated in pre-treatment periods, tests whether this
severity exceeds a researcher-specified tolerance, and produces confidence
intervals whose coverage is valid *conditional* on the pre-test outcome.

The framework proceeds in three stages: (1) estimate period-by-period DID
violations from pre-treatment data; (2) aggregate them into a scalar severity
measure and compare against a threshold; (3) if the severity is acceptable,
construct a bias-corrected confidence interval that accounts for the
pre-testing step.

The severity measure S_pre
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The pre-treatment severity statistic aggregates estimated violations
:math:`\hat\nu_t` across pre-treatment periods using an :math:`L_p` power
mean:

.. math::

   \hat S_{\text{pre}} = \left(\frac{1}{T_0 - 1}
   \sum_{t=2}^{T_0} |\hat\nu_t|^p \right)^{1/p}

where :math:`T_0` is the number of pre-treatment periods and :math:`p \geq 1`
is a user-chosen norm exponent.  Higher *p* places more weight on the single
largest violation; *p* = 2 (default) gives the root-mean-square, balancing
overall magnitude with sensitivity to outliers.

Computed by :func:`pretest.compute_severity`.

The pre-test decision phi(M)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Given a threshold *M* > 0, the binary decision rule is:

.. math::

   \varphi(M) = \mathbf{1}\{\hat S_{\text{pre}} > M\}

If :math:`\varphi = 0` the pre-test *passes*: violations are tolerable and the
conditional CI is reported.  If :math:`\varphi = 1` the pre-test *fails*:
violations are too large for the chosen *M*.

The threshold *M* is the researcher's maximum acceptable severity.  It is not a
statistical critical value but a substantive judgment: "I am willing to
tolerate at most *M* units of extrapolation bias per period."

In code, the decision is exposed as ``result.reporting_summary()["decision"]``:

- ``"PASS"`` corresponds to :math:`\varphi(M) = 0` (severity within tolerance).
- ``"FAIL"`` corresponds to :math:`\varphi(M) = 1` (severity exceeds threshold).

Computed by :func:`pretest.classify_pretest`.

Conditional confidence intervals
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When the pre-test passes, the framework constructs a confidence interval
for the average treatment effect :math:`\bar\delta` that is valid conditional
on the event :math:`\{\varphi = 0\}`:

.. math::

   \bar\delta \pm \left(\kappa \cdot \hat S_{\text{pre}} + \frac{f_\alpha}{\sqrt{n}}\right)

where :math:`\kappa` is a known extrapolation constant (depending on norm,
mode, and post-treatment horizon), :math:`\hat S_{\text{pre}}` is the observed
severity statistic, and :math:`f_\alpha / \sqrt{n}` is a simulation-based critical value
scaled by sample size to deliver :math:`1-\alpha` conditional coverage.  The threshold *M*
controls only the pre-test decision :math:`\varphi(M) = \mathbf{1}\{\hat S_{\text{pre}} > M\}`;
the CI half-width is determined by the observed severity, not by *M* itself.

The conditional CI is wider than a conventional CI because it incorporates
the pre-testing step; it buys honest coverage at the cost of precision.

Computed by :func:`pretest.compute_ci_half_width`.


Data Preparation
----------------

Input format
^^^^^^^^^^^^

:func:`pretest.pretest_from_dataframe` expects a "long-format" pandas
DataFrame with at minimum three columns:

- **outcome** -- the numeric outcome variable :math:`Y_{it}`.
- **treatment** -- a binary indicator (0 = control, 1 = treated).
- **time** -- the time-period identifier (numeric or ordinal).

An optional **cluster** column can be supplied for cluster-robust standard
errors.

Panel vs. repeated cross-section
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The estimator computes group-time means internally, so it works with
both balanced panels and repeated cross-sections.  The critical requirement
is that every (group, time) cell has positive observation count.

.. code-block:: python

   # Verify complete support
   import pandas as pd
   cell_counts = df.groupby(["treatment", "time"]).size()
   assert (cell_counts > 0).all(), "Incomplete group-time cells"

Treatment timing
^^^^^^^^^^^^^^^^

The ``treat_time`` argument specifies the *first post-treatment period*.  All
periods strictly before ``treat_time`` are used as the pre-treatment sample.
If your data has treatment at year 2004, set ``treat_time=2004``.

Working with existing DID workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``pretest`` complements standard DID estimators rather than replacing them:

- If you estimate event-study models with ``statsmodels`` or ``linearmodels``,
  continue using those for exploratory analysis.
- For the formal pre-test and conditional CI, pass the underlying long-format
  data to :func:`pretest.pretest_from_dataframe`. The package computes
  group-time means internally, aligned with the theory in Mikhaeil & Harshaw (2026).
- This design ensures that severity, CI width, and the pre-test decision are
  based on a unified covariance structure, rather than mixing estimators.


Parameter Selection
-------------------

threshold (M)
^^^^^^^^^^^^^

This is the core tuning parameter.  There is no single "correct" choice;
it encodes how much violation the researcher finds acceptable.

- In units of the outcome variable's standard deviation, *M* = 0.1--0.5 is
  typical for well-behaved panel data.
- To explore sensitivity, use :func:`pretest.compute_m_sensitivity` across a
  grid of *M* values.
- The *breakdown point* is the smallest *M* at which the pre-test passes
  (i.e., *M* = :math:`\hat S_{\text{pre}}`).

.. note::

   This parameter is named ``threshold`` in :func:`~pretest.pretest_from_dataframe`
   and ``threshold_m`` in lower-level functions like :func:`~pretest.classify_pretest`
   and :func:`~pretest.compute_m_sensitivity`. In mathematical notation, it is
   denoted :math:`M`.

p_norm
^^^^^^

Controls the shape of the severity aggregation:

- **p = 1**: arithmetic mean of absolute violations.  Tolerant of isolated
  large violations.
- **p = 2** (default): root-mean-square.  Standard Euclidean norm.
- **p → ∞**: maximum absolute violation.  Sensitive to the worst single
  period.

For most applications *p* = 2 provides a balanced default.

.. note::

   This exponent is named ``p`` in :func:`~pretest.pretest_from_dataframe`
   and ``p_norm`` in lower-level functions like :func:`~pretest.compute_severity`
   and :func:`~pretest.compute_kappa`.

Practical recipes for choosing M and p
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Start from your substantive tolerance for extrapolation bias. If
violations of about 0.1 standard deviations per period would not
change your conclusions, ``threshold_m=0.1`` is a reasonable baseline.
Stricter choices like ``threshold_m=0.05`` are useful when you want to
emphasize robustness.

The ``p_norm`` parameter reflects how you read pre-trend patterns.
The default ``p_norm=2`` balances overall magnitude and occasional
spikes. Smaller values (``p_norm=1``) downweight isolated large
movements; large values (``float('inf')``) treat any single violation
as unacceptable.

Once you have a provisional pair, run
:func:`pretest.compute_m_sensitivity` on your snapshot. The breakdown
point shows how much tolerance your data actually require and whether
your chosen M is defensible.

alpha
^^^^^

Significance level for the conditional CI.  Default 0.05 (95% coverage).

mode
^^^^

- ``"iterative"`` (default): severity is computed from period-level violations
  :math:`\hat\nu_t`.  Kappa grows with the post-treatment horizon, reflecting
  extrapolation risk over longer horizons.
- ``"overall"``: severity uses cumulative sums :math:`\bar\nu_t`.  Kappa = 1
  regardless of horizon (Appendix C).

The iterative mode is generally recommended as it produces tighter inference
when the number of post-treatment periods is small.


Result Interpretation
---------------------

The :class:`pretest.PretestResultSnapshot` object returned by
:func:`pretest.pretest_from_dataframe` carries the complete estimation record.
The ``reporting_summary()`` method returns a flat dictionary suitable for
display or serialization.

Key fields:

.. code-block:: python

   # Continues from the Getting Started example (df and snapshot defined above)
   summary = snapshot.reporting_summary()

   summary["decision"]            # "PASS" or "FAIL"
   summary["S_pre"]               # float: severity statistic
   summary["threshold"]           # float: M
   summary["delta_bar"]           # float: average DID estimand (not traditional ATT)
   summary["kappa"]               # float: extrapolation constant
   summary["f_alpha"]             # float: MC critical value
   summary["conditional_interval"]   # [lower, upper] or None
   summary["conventional_interval"]  # [lower, upper]

In empirical work, we recommend reporting the conditional interval for the
average DID estimand \u03b4\u0304 whenever ``decision == "PASS"``, and using the
conventional interval only as a benchmark for comparison.


Advanced Features
-----------------

Weighted estimands (post_weights)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default the post-treatment estimand is the simple average of period-level
ATTs.  For custom linear combinations (e.g., weighting toward later periods),
pass ``post_weights``:

.. code-block:: python

   # Continues from the Getting Started example (df defined above)
   snapshot = pretest_from_dataframe(
       df,
       outcome="outcome",
       treatment="treatment",
       time="time",
       threshold=0.5,
       treat_time=6.0,
       post_weights=[0.2, 0.3, 0.5],  # 3 post periods, emphasize last
   )

The weights rescale the kappa constant via :func:`pretest.compute_kappa_weighted`
(Appendix B).

M-sensitivity analysis
^^^^^^^^^^^^^^^^^^^^^^^

Evaluate how the decision and CI change across a range of *M* values:

.. code-block:: python

   # Continues from the Getting Started example (snapshot defined above)
   from pretest import compute_m_sensitivity

   sensitivity = compute_m_sensitivity(
       snapshot,
       m_values=[0.05 * i for i in range(1, 21)],
   )
   print(sensitivity)  # tabular display with breakdown point

The :class:`pretest.MSensitivityResult` reports for each *M*:

- Whether the pre-test passes (``phi_values``).
- Whether the conditional CI is reportable (``can_report``).
- The breakdown point *M** where the decision flips.

Monte Carlo coverage verification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Verify finite-sample coverage properties via simulation:

.. code-block:: python

   from pretest import DGPConfig, run_monte_carlo_coverage
   from pretest.simulation import compute_section6_violation_path

   violation_path = compute_section6_violation_path(
       t_start=2, t_end=5, total_periods=8,
       target_severity=0.3, p_norm=2.0,
   )

   config = DGPConfig(
       n_units=200,
       t_pre=5,
       t_post=3,
       true_effect=0.5,
       violation_path=violation_path,
       seed=42,
   )

   mc = run_monte_carlo_coverage(
       config,
       threshold_m=0.5,
       replications=500,
       alpha=0.05,
       progress=True,
   )
   print(mc)  # conditional_coverage, pass_rate, mean_ci_width

The conditional coverage should be at or above :math:`1-\alpha` when *M*
is above the DGP's true severity.

Event study plotting
^^^^^^^^^^^^^^^^^^^^^

Produce event study figures:

.. code-block:: python

   from pretest.plotting import plot_event_study_from_dataframe

   ax = plot_event_study_from_dataframe(
       df,
       outcome="outcome",
       treatment="treatment",
       time="time",
       threshold=0.5,
       treat_time=6.0,
       title="Conditional Extrapolation Pre-Test",
       save_path="event_study.pdf",
       dpi=300,
   )

The plot displays estimated DID coefficients with conventional and conditional
confidence bands, and marks the treatment onset.

Cluster-robust inference
^^^^^^^^^^^^^^^^^^^^^^^^^

When observations are clustered (e.g., units within states), pass the cluster
column to obtain cluster-robust covariance estimates:

.. code-block:: python

   # Continues from the Getting Started example (df defined above)
   snapshot = pretest_from_dataframe(
       df,
       outcome="outcome",
       treatment="treatment",
       time="time",
       threshold=0.5,
       treat_time=2004,
       cluster="state_id",
   )

The covariance is computed via the influence-function approach with
group-level clustering (Cameron & Miller, 2015).


Scope and Limitations
---------------------

pretest implements the conditional extrapolation pre-testing framework
for block-adoption DID designs. In version 0.1.0:

**Supported:**

- Block adoption designs with a single treatment onset time
- Panel data and repeated cross-sections with complete group-time cells
- Cluster-robust covariance estimation
- Weighted estimands (Appendix B general linear estimators)

**Not supported:**

- Staggered treatment adoption (multiple treatment cohorts)
- Triple-difference specifications
- Covariate-adjusted DID estimation within the package
- Unbalanced panels with missing group-time cells

