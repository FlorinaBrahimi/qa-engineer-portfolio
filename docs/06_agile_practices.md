# Agile Practices: how QE works inside the scrum team

## Ceremonies and QE's contribution

| Ceremony | QE brings |
|---|---|
| Refinement | Testability questions ("how will we know this works?"), risk score per story, acceptance criteria in Given/When/Then |
| Planning | Test tasks as sub-tasks of each story with estimates; capacity reserved for exploratory testing and flaky-test fixes |
| Daily stand-up | Test signal from last night's run, blocked verifications, risks crossing the ≥ 12 line |
| Review | Demo of the test evidence, not only the feature |
| Retro | Escaped-defect root causes, pipeline time, flakiness trend |

## Definition of Ready (story)

- Acceptance criteria written and agreed.
- Test data needs identified (fixture vs factory).
- Risk score assigned.

## Definition of Done (story)

- Acceptance criteria covered by automated tests at the lowest practical level.
- Tests green in CI on the merged commit.
- No open S1/S2 defects on the story.
- Exploratory session done for risk ≥ 12 stories.
- Docs (test cases, risk register) updated.

## Estimation

Test work is estimated in story points alongside dev work, using the same reference stories:

| Points | Reference |
|---|---|
| 1 | Add a parametrised case to an existing test |
| 2 | New API test group for an existing endpoint |
| 3 | New Page Object method + 2-3 UI tests |
| 5 | New test type with tooling (e.g. first JMeter plan, first Appium test) |
| 8 | Framework change affecting all suites (e.g. new environment strategy) |

Spikes are time-boxed (usually 1 day) and produce a written recommendation.

## Kanban for maintenance work

Flaky-test fixes, tooling upgrades and defect verification flow through a Kanban board with a WIP limit of 2 per person, so sprint commitments are not silently eroded.

## Test data management

| Need | Approach | Where |
|---|---|---|
| Deterministic outcomes | Static fixtures with known scores | `testdata/submissions.json` |
| Isolation under parallel runs | Factory with unique titles/authors | `testdata/factory.py` |
| Cleanup | Fixtures delete what they create; `clean_store` for list assertions | `tests/conftest.py` |
| Environment portability | `BASE_URL` + API key from env, never hard-coded | `tests/conftest.py` |
| Sensitive data | No real student text; synthetic only. Staging uses masked snapshots | policy |
| Large volumes | Generated on the fly (`build_many`) and by JMeter functions | `tests/scale/`, `performance/` |
