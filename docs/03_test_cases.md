# Test Cases

Each case maps to an automated test where one exists. Manual-only cases are marked.

## API

| ID | Title | Preconditions | Steps | Expected | Priority | Automated in |
|---|---|---|---|---|---|---|
| TC-API-001 | Health endpoint responds | Service running | GET /health | 200, `status: ok` | P1 | `test_health_endpoint_is_up` |
| TC-API-002 | Create valid submission | Valid API key | POST valid JSON | 201, body has id, score, status | P1 | `test_create_submission_returns_201_with_expected_shape` |
| TC-API-003 | Copied text is flagged | Fixture `plagiarised_paper` | POST fixture | score 100, status `flagged` | P1 | `test_fully_copied_text_is_flagged` |
| TC-API-004 | Original text is clear | Fixture `clean_paper` | POST fixture | score 0, status `clear` | P1 | `test_original_text_is_clear` |
| TC-API-005 | Partial overlap scores between 0 and 100 | Fixture `partial_overlap_paper` | POST fixture | 0 < score < 100 | P2 | `test_partial_overlap_scores_between_bounds` |
| TC-API-006 | Word count accurate | – | POST 12-word text | `word_count` = 12 | P2 | `test_word_count_is_accurate` |
| TC-API-007 | Get by id | Submission exists | GET /api/submissions/{id} | 200, same body as create | P1 | `test_get_submission_by_id` |
| TC-API-008 | List includes created | Submission exists | GET /api/submissions | item present | P1 | `test_list_contains_created_submission` |
| TC-API-009 | Delete then get | Submission exists | DELETE then GET | 204 then 404 | P1 | `test_delete_then_get_returns_404` |
| TC-API-010 | Unknown id | – | GET/DELETE unknown id | 404 | P2 | `test_unknown_id_returns_404` |
| TC-API-011 | Validation names field | – | POST missing title / short text | 400, `fields` contains name | P1 | `test_validation_errors_name_the_field` |
| TC-API-012 | Title boundary 200/201 chars | – | POST 200 then 201 chars | 201 then 400 | P2 | `test_title_boundary_200_chars_accepted_201_rejected` |

## UI

| ID | Title | Steps | Expected | Priority | Automated in |
|---|---|---|---|---|---|
| TC-UI-001 | Home renders form and table | Open / | Inputs visible, button enabled | P1 | `test_home_page_renders_form_and_table` |
| TC-UI-002 | Original paper shows clear | Fill form, submit | Row appears, status `clear` | P1 | `test_submitting_original_paper_shows_clear_status` |
| TC-UI-003 | Copied paper shows flagged | Fill with fixture, submit | Status `flagged` | P1 | `test_submitting_copied_paper_shows_flagged_status` |
| TC-UI-004 | Inline validation | Submit empty form | Messages next to each field | P1 | `test_validation_messages_appear_inline` |
| TC-UI-005 | Form keeps input on error | Submit with one bad field | Good fields retain values | P2 | `test_form_retains_input_after_validation_failure` |
| TC-UI-006 | Similarity badge colour band | Submit 100% match | Badge shows 100.0% in red band | P2 | `test_similarity_badge_uses_colour_band_for_score` |
| TC-UI-007 | Overview stats | Submit one clear, one flagged | Total 2, flagged 1, average 50% | P2 | `test_overview_stats_reflect_submissions` |

## Security

Mapped to standards in [12_security.md](12_security.md). 137 cases across six files.

| File | Standard | Cases | Covers |
|---|---|---:|---|
| `test_owasp_api_top10.py` | OWASP API Security Top 10 (2023) | 64 | Authentication, object ids, mass assignment, resource limits, hidden endpoints, misconfiguration, inventory |
| `test_secure_headers.py` | OWASP Secure Headers Project | 14 | Required headers on every response type, CSP content, caching, no cookies |
| `test_input_validation.py` | ASVS V5, Top 10 Injection | 44 | Fifteen hostile payload classes, hostile ids, media types, malformed JSON, type confusion, stored and reflected XSS, CSP |
| `test_browser_defences.py` | ASVS V4.2, V14.4 | 5 | Cross-site form posts, clickjacking |
| `test_logging_and_monitoring.py` | ASVS V7 | 4 | Security events logged; keys and content never logged |
| `test_transport_live.py` | ASVS V9 | 5 | TLS versions, certificate, no plain HTTP, HSTS. Live deployment only |

## Accessibility, scale, mobile, AWS

| ID | Title | Expected | Automated in |
|---|---|---|---|
| TC-A11Y-001 | Language + single h1 | `lang=en`, one h1 | `test_page_declares_language_and_single_h1` |
| TC-A11Y-002 | Labels on every control | 1 label per input | `test_every_form_control_has_a_label` |
| TC-A11Y-003 | Table header scope | `scope=col` | `test_table_headers_declare_scope` |
| TC-A11Y-004 | axe WCAG 2.1 A/AA with clear and flagged rows present | No serious/critical | `test_axe_core_reports_no_serious_violations` |
| TC-A11Y-005 | axe scan of the validation-error state | No serious/critical | `test_axe_core_reports_no_violations_after_validation_error` |
| TC-SCALE-001 | 100 concurrent creates | all 201, unique ids, p95 < 500 ms | `test_concurrent_creates_all_succeed_with_unique_ids` |
| TC-SCALE-002 | List with 200 records | 200, < 1 s | `test_list_endpoint_scales_with_store_size` |
| TC-MOB-001 | No horizontal scroll at 390px | scrollWidth <= clientWidth | `test_no_horizontal_scroll_on_phone_viewport` |
| TC-MOB-002 | Touch submit flow | Row appears | `test_submit_flow_works_with_touch` |
| TC-MOB-003 | Real-device Safari via Appium | Row appears | `test_submit_flow_in_mobile_safari_via_appium` (needs device) |
| TC-AWS-001 | Archive writes dated JSON key | key format, content-type, body | `test_archive_writes_json_under_dated_prefix` |
| TC-AWS-002 | Metric with status dimension | metric listed | `test_metric_is_published_with_status_dimension` |
| TC-AWS-003 | Lambda processes/rejects | 1 processed, 1 rejected | `test_lambda_processes_valid_and_rejects_malformed_objects` |

## Manual / exploratory

| ID | Charter | Time box | Notes |
|---|---|---|---|
| EXP-001 | Explore the similarity scorer with near-duplicate text (punctuation, casing, Unicode) to find scoring surprises | 60 min | Outcome feeds new fixtures |
| EXP-002 | Abuse the web form: paste 20k chars, emoji, RTL text, rapid double-submit | 60 min | Watch for 500s and duplicate rows |
| MAN-001 | Cross-browser visual check (Firefox, Safari) of results table | 20 min | Until Playwright multi-browser is added to CI |

## Java API suite (REST Assured)

The Java suite verifies the same contract from a second stack. Run with `make java`, or select by tag with `mvn test -Dgroups=smoke`.

| Class | Tests | Covers |
|---|---:|---|
| `HealthTest` | 2 | Health endpoint, published OpenAPI contract |
| `SubmissionsCrudTest` | 8 | Create with JSON-schema validation, read, list ordering, delete, trimming, word count |
| `SimilarityScoringTest` | 4 | 100%, 0%, partial overlap, case and punctuation insensitivity |
| `SubmissionsValidationTest` | 23 | Field rules, exact boundaries, malformed bodies, missing fields, hostile and Unicode input |
| `SecurityTest` | 13 | Missing and wrong key on every endpoint, hardening headers, no stack disclosure |
| `AwsDeploymentTest` | 11 | Live stack only (`make java-aws`): stack state, API writes land in DynamoDB, API serves items written directly to the table, deletes remove them, table and Lambda configuration, public URL still enforces the API key, error alarm exists and is quiet, warm p95 latency under 1 s |

## Unit tests

`tests/unit/test_similarity.py` holds 29 tests of the scorer, the colour bands at every boundary, validation and record building, with no HTTP involved.
