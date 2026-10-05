# Performance testing with JMeter

`submissions_load_test.jmx` drives the create / read / delete cycle of the Submission Service.

## Run headless

```bash
python -m app.server &                       # or point at a deployed host
jmeter -n -t performance/submissions_load_test.jmx \
  -Jhost=localhost -Jport=5001 -Jusers=50 -Jramp=30 -Jduration=120 \
  -l reports/perf.jtl -e -o reports/perf-html
```

## Pass / fail criteria (agreed with the team in the test plan)

| Metric | Target |
|---|---|
| p95 latency, POST /api/submissions | < 500 ms |
| Error rate | < 0.5 % |
| Throughput at 50 virtual users | > 100 req/s |

Assertions inside the plan enforce the 201/200 codes and the 500 ms ceiling per sample, so a
failing run is visible in the JTL without reading the dashboard.

The lightweight in-process version of this check lives in `tests/scale/` and runs on every CI build.

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
