"""AI-assisted test generation.

Reads the service's OpenAPI contract plus the existing test files, asks Claude for
additional pytest cases that cover gaps (boundaries, negative paths, idempotency), and
writes them to ai_testing/generated/ for human review before they are promoted into tests/.

Usage
-----
    python ai_testing/generate_tests.py --spec-url http://localhost:5001/api/openapi.json
    python ai_testing/generate_tests.py --spec-file testdata/openapi_snapshot.json --dry-run

--dry-run prints the prompt and exits without calling the API, so the script can be
exercised in CI with no credentials. A real run needs ANTHROPIC_API_KEY or an
`ant auth login` profile.

Server-side refusal fallbacks are enabled by default, so if the primary model declines a
request the API retries on a fallback model inside the same call.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are a senior software quality engineer writing pytest tests.
You are given an OpenAPI document for a service and the tests that already exist.
Produce ONLY new tests that cover behaviour the existing suite misses: boundary values,
negative paths, idempotency, encoding edge cases, and interactions between endpoints.
Rules:
- Use the fixtures `api` (authenticated requests.Session) and `base_url` exactly as the
  existing tests do, and `SubmissionFactory` from testdata.factory for payloads.
- Mark every test with @pytest.mark.api and @pytest.mark.regression.
- Each test asserts one behaviour and has a name that states the expected outcome.
- Do not duplicate an existing test. Do not invent endpoints that are not in the spec.
Return a single complete Python module and nothing else."""


def collect_existing_tests() -> str:
    parts = []
    for path in sorted((ROOT / "tests" / "api").glob("test_*.py")):
        parts.append(f"# ---- {path.relative_to(ROOT)} ----\n{path.read_text()}")
    return "\n\n".join(parts)


def load_spec(args: argparse.Namespace) -> dict:
    if args.spec_file:
        return json.loads(Path(args.spec_file).read_text())
    import requests

    return requests.get(args.spec_url, timeout=10).json()


def build_user_prompt(spec: dict, existing: str) -> str:
    return (
        "OpenAPI document:\n```json\n"
        + json.dumps(spec, indent=2)
        + "\n```\n\nExisting tests:\n```python\n"
        + existing
        + "\n```\n\nWrite the additional tests now."
    )


def generate(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        detail = response.stop_details.explanation if response.stop_details else "no explanation"
        raise SystemExit(f"request refused: {detail}")
    if response.stop_reason == "max_tokens":
        raise SystemExit("output truncated; raise max_tokens")

    text = "".join(block.text for block in response.content if block.type == "text")
    return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--spec-url")
    source.add_argument("--spec-file")
    parser.add_argument("--out", default=str(ROOT / "ai_testing" / "generated" / "test_generated_api.py"))
    parser.add_argument("--dry-run", action="store_true", help="print the prompt; do not call the API")
    args = parser.parse_args(argv)

    spec = load_spec(args)
    prompt = build_user_prompt(spec, collect_existing_tests())

    if args.dry_run:
        print(SYSTEM_PROMPT)
        print("\n---- user prompt ----\n")
        print(prompt)
        return 0

    import anthropic

    try:
        module = generate(prompt)
    except anthropic.AuthenticationError:
        raise SystemExit("Anthropic rejected the API key. Check ANTHROPIC_API_KEY in .env.")
    except anthropic.RateLimitError:
        raise SystemExit("Rate limited by the Anthropic API. Wait a minute and retry.")
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e.message):
            raise SystemExit("The API key is valid but the account has no credit. Add credit under Plans & Billing in the Anthropic Console, then retry.")
        raise SystemExit(f"Request rejected: {e.message}")
    except anthropic.APIConnectionError:
        raise SystemExit("Could not reach the Anthropic API. Check the network connection.")
    except TypeError as e:
        if "authentication" in str(e):
            raise SystemExit("No credentials found. Set ANTHROPIC_API_KEY in .env and load it with: set -a; source .env; set +a")
        raise
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(module)
    print(f"wrote {out} ({module.count('def test_')} tests). Review, then: pytest {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
