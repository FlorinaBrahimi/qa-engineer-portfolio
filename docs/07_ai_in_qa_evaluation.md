# Evaluating and Integrating AI-driven Testing Capabilities

Written as the output of a one-day spike. Goal: decide which AI-assisted practices to adopt for this team and how to keep them safe.

## What was evaluated

| Capability | Candidate | Result | Decision |
|---|---|---|---|
| AI-assisted test generation | Claude via the Anthropic SDK, prompted with the OpenAPI contract + existing suite (`ai_testing/generate_tests.py`) | Produced useful boundary and negative cases; ~30% were duplicates or asserted implementation details | Adopt with mandatory human review; generated files land in `ai_testing/generated/` and are promoted by PR |
| Predictive analysis | Flakiness / regression scoring over run history (`ai_testing/predict_flaky.py`) | Correctly ranked the known flaky UI test and the regressing scale test on synthetic data | Adopt; runs in CI and posts to the job summary |
| Self-healing locators | Commercial tools | Hides real UI regressions behind "healed" selectors | Not adopted; `data-testid` discipline instead |
| Visual AI regression | Commercial tools | Promising for the results table, but cost not justified at current UI size | Revisit when UI grows |
| AI defect drafting | Claude from failing-test output + logs | Good first drafts of steps/expected/actual | Adopt informally; reporter owns the final text |
| Test impact analysis | Map changed files to tests via coverage data | Needs coverage per test (pytest-cov with `--cov-context=test`) | Spike next sprint |

## Guardrails

1. AI never merges anything. Generated tests are reviewed like any other code.
2. Prompts include the real contract and existing tests so output is grounded, not invented.
3. No customer or student data is sent to a model; synthetic fixtures only.
4. Every AI-suggested test must fail when the behaviour it covers is broken (mutation check before promotion).
5. Model, prompt and date are recorded in the generated file header for traceability.

## Measured benefit (spike)

- Time to first draft of 10 negative API tests: 45 min manual vs 6 min generated + 15 min review.
- Flaky test identified from history in seconds instead of a weekly manual trawl.

## Next steps

- Add `--cov-context=test` to CI to enable test impact analysis.
- Pilot AI-generated exploratory charters from recent defect clusters.

## First real run (2026-10-05)

One run of the generator produced 21 test functions, expanding to 45 cases with parameters.

| Outcome | Count |
|---|---:|
| Cases passing on first run | 42 |
| Cases failing because of a real product defect | 3 |
| Cases wrong or duplicated, discarded in review | 0 |

The three failures were all one defect, DEF-106: a wrongly typed field crashed the API with a 500.
Neither the hand-written Python suite nor the 50-test Java suite covered it. After the fix all
45 pass, and the file was promoted to `tests/api/test_generated_api.py` with a provenance header.

One integration gap surfaced too: generated files could not see the shared fixtures until
`ai_testing/conftest.py` re-exported them.
