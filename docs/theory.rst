Mathematical Background
=======================

This page provides the mathematical foundations underlying the **pretest-py**
API.  It is not a reproduction of the full paper; rather, it gives the
practitioner enough notation to understand what each function computes
and why.  For proofs and detailed assumptions, see Mikhaeil & Harshaw (2026).

.. contents:: Sections
   :local:
   :depth: 2


Setup and Notation (Paper Section 2)
-------------------------------------

Consider a DID design with :math:`T_0` pre-treatment periods and
:math:`T_1` post-treatment periods (total :math:`T = T_0 + T_1`).
Let :math:`\hat\delta_t` denote the DID estimator for period *t* relative
to the baseline period *t* = 1.

Define the *iterative violation* at period *t*:

.. math::

   \hat\nu_t = \hat\delta_t - \hat\delta_{t-1}, \quad t = 2, \ldots, T_0

These measure the incremental departure from parallel trends between
consecutive pre-treatment periods.  Under exact parallel trends,
:math:`\nu_t = 0` for all *t*.

The DID estimation and violation extraction is handled internally by
:func:`pretest.pretest_from_dataframe`.


Severity Measure (Paper Section 3.1)
-------------------------------------

The severity statistic aggregates violations into a single scalar via an
:math:`L_p` power mean:

.. math::

   \hat S_{\text{pre}} = \left(\frac{1}{T_0 - 1}
   \sum_{t=2}^{T_0} |\hat\nu_t|^p \right)^{1/p}

For the supremum norm (:math:`p = \infty`):

.. math::

   \hat S_{\text{pre}} = \max_{t=2,\ldots,T_0} |\hat\nu_t|

In **overall mode** (Appendix C), the severity uses cumulative violations
:math:`\bar\nu_t = \sum_{s=2}^t \nu_s` instead of the iterative increments.

The function :func:`pretest.compute_severity` implements this formula.

.. code-block:: python

   from pretest import compute_severity

   s_pre = compute_severity(nu_vector=[0.02, -0.05, 0.03, 0.01], p_norm=2.0)


Pre-Test Decision (Paper Section 4.2, Theorem 1)
-------------------------------------------------

The decision function is a simple thresholding rule:

.. math::

   \varphi(M) = \mathbf{1}\{\hat S_{\text{pre}} > M\}

- :math:`\varphi = 0` (PASS): violations are within tolerance.
- :math:`\varphi = 1` (FAIL): violations exceed the threshold.

The parameter *M* > 0 is chosen by the researcher to reflect the maximum
acceptable magnitude of parallel-trends violations, measured in the same
units as the outcome variable (after normalization by sample size via the
asymptotic framework).

This decision rule is evaluated by :func:`pretest.classify_pretest`.

.. code-block:: python

   from pretest import classify_pretest

   decision = classify_pretest(s_pre_hat=0.12, threshold_m=0.5)
   # decision.phi == 0, decision.pretest_pass == 1


Kappa Constant (Paper Section 5, below Theorem 2)
--------------------------------------------------

The constant :math:`\kappa` translates pre-treatment severity into a
worst-case post-treatment bias bound.  In iterative mode with norm *p*
and :math:`T_1` post-treatment periods:

.. math::

   \kappa = \left(\frac{1}{T_1}
   \sum_{j=1}^{T_1} j^q \right)^{1/q}

where :math:`q = p/(p-1)` is the Hölder conjugate exponent.

Special cases:

- :math:`p = 1`: :math:`\kappa = T_1`
- :math:`p = 2`: :math:`\kappa = \left(\frac{1}{T_1}\sum_{j=1}^{T_1} j^2\right)^{1/2}`
- :math:`p = \infty`: :math:`\kappa = (T_1 + 1)/2`

In overall mode, :math:`\kappa = 1` regardless of horizon.

The constant is computed by :func:`pretest.compute_kappa`.

.. code-block:: python

   from pretest import compute_kappa

   kappa = compute_kappa(t_post=3, p_norm=2.0, mode="iterative")


Critical Value f_alpha (Paper Appendix D.5)
--------------------------------------------

The critical value :math:`f_\alpha` is calibrated via Monte Carlo simulation
from the asymptotic covariance matrix :math:`\hat\Sigma`:

.. math::

   f_\alpha = \inf\left\{c \geq 0 :
   \Pr\!\left(\left|\bar Z_{T_1}\right| \leq c \;\middle|\;
   S_{\text{pre}}(Z) \leq M\right) \geq 1 - \alpha \right\}

where :math:`Z \sim N(0, \hat\Sigma)`.  This is the :math:`(1-\alpha)`
conditional quantile of the absolute post-treatment average, given that
the simulated severity does not exceed *M*.

The simulation draws ``simulations`` (default 5000) multivariate normal
vectors, filters to those passing the pre-test, and takes the empirical
:math:`(1-\alpha)` quantile of the post-treatment statistic among survivors.

The calibration is performed by :func:`pretest.compute_critical_value`.

.. code-block:: python

   from pretest import compute_critical_value

   # Example: 4 pre-periods, 3 post-periods -> 6-dimensional covariance
   covariance_matrix = [[1.0 if i == j else 0.3 for j in range(6)] for i in range(6)]

   f_alpha = compute_critical_value(
       covariance_matrix,
       alpha=0.05,
       t_pre=4,
       t_post=3,
       p_norm=2.0,
       simulations=5000,
       seed=12345,
   )


Conditional Confidence Interval (Paper Section 5.1, Theorem 2)
---------------------------------------------------------------

The conditionally valid CI for the average treatment effect
:math:`\bar\delta` is:

.. math::

   \bar\delta \;\pm\; \left(\kappa \cdot \hat S_{\text{pre}}
   + \frac{f_\alpha}{\sqrt{n}}\right)

The half-width incorporates two sources of uncertainty:

1. **Bias correction** (:math:`\kappa \cdot \hat S_{\text{pre}}`): the worst-case
   extrapolation scaled by the observed pre-treatment severity.
2. **Sampling uncertainty** (:math:`f_\alpha / \sqrt{n}`): the conditional critical
   value scaled by sample size, accounting for the randomness in the
   post-treatment estimator given that the pre-test passed.

Note that the threshold *M* controls only the binary pre-test decision
:math:`\varphi(M) = \mathbf{1}\{\hat S_{\text{pre}} > M\}`.  The CI
half-width depends on the realized severity :math:`\hat S_{\text{pre}}`,
not on *M* itself.

The CI is valid in the sense that:

.. math::

   \Pr\!\left(\bar\delta \in \text{CI} \;\middle|\; \varphi = 0\right)
   \geq 1 - \alpha

uniformly over all DGPs with true severity at most *M*.

The half-width calculation is implemented by :func:`pretest.compute_ci_half_width`.

.. code-block:: python

   from pretest import compute_ci_half_width

   half_width = compute_ci_half_width(
       mode="iterative",
       s_pre_hat=0.3,
       kappa=2.16,
       f_alpha=1.96,
       n=200,
   )


Weighted Estimands (Paper Appendix B)
--------------------------------------

For general linear post-treatment estimands
:math:`\sum_{t} c_t \hat\delta_{T_0+t}` with user-supplied weights
:math:`c = (c_1, \ldots, c_{T_1})`, the kappa constant generalizes to:

.. math::

   \kappa_c = T_1^{1/p} \left(
   \sum_{t=1}^{T_1} |c_{T_1-t+1} \cdot t|^q
   \right)^{1/q}

This generalized constant is computed by :func:`pretest.compute_kappa_weighted`.


References
----------

- Mikhaeil, J. M. and C. Harshaw (2026). "Valid Inference when Testing
  Violations of Parallel Trends for Difference-in-Differences."
  arXiv:2510.26470.


Next steps
----------

- See :doc:`user_guide` for practical guidance on choosing parameters and
  interpreting results.
- See :doc:`tutorials/index` for worked examples that apply these
  quantities in a full DID analysis.
