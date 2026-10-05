.PHONY: install app smoke test ui api java perf lint clean deploy destroy live-test audit unit lint-workflows

install:
	pip install -r requirements.txt && python -m playwright install chromium

app:
	python -m app.server

smoke:
	pytest -m smoke

test:
	pytest --junitxml=reports/all.xml --html=reports/all.html --self-contained-html

api:
	pytest -m "api or security or aws" -n auto

ui:
	pytest -m "ui or a11y or mobile"

java:
	cd java-api-tests && mvn -B clean test -Dbase.url=http://localhost:5001

# Java suite against the deployed stack, including checks of DynamoDB, Lambda and CloudWatch.
java-aws:
	cd java-api-tests && mvn -B clean test -Paws -Dapi.key=$${SUBMISSION_API_KEY:-qa-demo-key}

# Starts the app itself, runs JMeter, writes reports/perf-html, perf.xml and perf.md.
perf:
	performance/run.sh

flaky:
	python ai_testing/predict_flaky.py ai_testing/test_history.csv

clean:
	rm -rf reports/*.xml reports/*.html .pytest_cache java-api-tests/target

deploy:
	infra/deploy.sh submission-service

destroy:
	infra/destroy.sh submission-service

live-test:
	@test -n "$$BASE_URL" || (echo "set BASE_URL to the deployed URL first" && exit 1)
	pytest -m "smoke or api or security or ui" --junitxml=reports/live.xml --html=reports/live.html --self-contained-html

audit:
	python3 -m pip_audit -r requirements.txt -f json -o reports/pip-audit.json || true
	python3 -m pip_audit -r requirements.txt
	bandit -c security/bandit.yaml -r app aws -f json -o reports/bandit.json || true
	bandit -c security/bandit.yaml -r app aws -ll

unit:
	pytest tests/unit --cov=app --cov=aws --cov-report=term-missing --cov-report=html:reports/coverage

lint-workflows:
	actionlint .github/workflows/*.yml

jira:
	python3 -m tools.jira_sync

jira-dry-run:
	python3 -m tools.jira_sync --dry-run

# Accessibility audit: writes reports/accessibility.html, .json and .md
a11y:
	python3 -m tools.a11y_report
