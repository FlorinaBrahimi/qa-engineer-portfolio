# Performance testing with JMeter

`submissions_load_test.jmx` drives the create / read / delete cycle of the Submission Service.

## Run it

```bash
make perf                                  # 20 users for 30 s against a locally started app
USERS=50 DURATION=120 performance/run.sh   # heavier run
open reports/perf-html/index.html          # the JMeter dashboard
```

The script starts the app, runs the plan, and stops the app again. No second terminal is needed.

## How results are linked to each test run

Every pipeline run includes the load test, so performance sits next to the functional results:

| Output | Where it appears |
|---|---|
| `reports/perf.xml` (JUnit format, one test case per request type) | Jenkins **Test Result** page, alongside the pytest and Java results |
| `reports/perf.md` (summary table) | The **Summary** page of each GitHub Actions run |
| `reports/perf-html/` (JMeter dashboard) | Downloadable artifact `jmeter-report` on GitHub; **Build Artifacts** in Jenkins |
| Exit code | A breached threshold fails the job, which blocks the deploy to AWS |

`tools/jmeter_report.py` does the conversion and enforces the thresholds.

## Pass / fail criteria (agreed with the team in the test plan)

| Metric | Target |
|---|---|
| p95 latency, POST /api/submissions | < 500 ms |
| Error rate | < 0.5 % |
| Throughput at 50 virtual users | > 100 req/s |

Assertions inside the plan enforce the 201/200 codes and the 500 ms ceiling per sample, and
`tools/jmeter_report.py` enforces the p95 and error-rate limits across the whole run.

The pipelines run 20 users for 30 seconds on every build. Jenkins runs 50 users for 120 seconds
on its nightly build. The in-process concurrency checks in `tests/scale/` also run on every build.

## Latest recorded run

20 virtual users, 5 s ramp, 30 s duration, against the app on localhost (in-memory backend).
Open `reports/perf-html/index.html` in a browser for the full dashboard.

| Sampler | Requests | Errors | Average | p95 | Max |
|---|---:|---:|---:|---:|---:|
| POST /api/submissions | 892 | 0% | 3 ms | 8 ms | 28 ms |
| GET /api/submissions/{id} | 884 | 0% | 3 ms | 7 ms | 13 ms |
| DELETE /api/submissions/{id} | 880 | 0% | 3 ms | 7 ms | 14 ms |

Overall throughput was 88.6 requests per second, limited by the plan's 200 ms think time, not
by the server. All three criteria above are met at this load. The 50-user criterion needs a run
against a deployed environment; do not point it at the Lambda demo without setting a reserved
concurrency limit first, since load there is billable.
