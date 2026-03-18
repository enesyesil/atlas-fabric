import os

from agents.runtime_env import load_environment
from evals.checks import run_deterministic_checks
from evals.fixtures import EVAL_CASES
from evals.judge import judge_case
from evals.report import print_report


def get_prerequisite_errors() -> list[str]:
    errors: list[str] = []

    for env_var in ("GENERATOR_MODEL", "REVIEWER_MODEL"):
        if not os.environ.get(env_var):
            errors.append(
                f"{env_var} is not set. Example: {env_var}=anthropic/claude-opus-4-5"
            )

    data_path = os.environ.get(
        "NATURAL_EARTH_DATA_PATH",
        "./data/ne_10m_admin_1_states_provinces.geojson",
    )
    if not os.path.exists(data_path):
        errors.append(
            f"Natural Earth data not found at {data_path}. "
            "Set NATURAL_EARTH_DATA_PATH to the downloaded GeoJSON."
        )

    return errors


def run_evals(*, load_env: bool = True) -> list[dict]:
    if load_env:
        load_environment()

    from agents.orchestrator import run_pipeline

    results = []

    for case in EVAL_CASES:
        state = run_pipeline(case.year, case.region, dry_run=True)
        checks = run_deterministic_checks(case, state)
        judge = judge_case(case, state)
        passed = checks["passed"] and judge["score"] >= 6
        results.append(
            {
                "case": case,
                "state": state,
                "checks": checks,
                "judge": judge,
                "passed": passed,
            }
        )

    return results


def main(*, load_env: bool = True) -> None:
    if load_env:
        load_environment()

    errors = get_prerequisite_errors()
    if errors:
        message = "Cannot run evals:\n- " + "\n- ".join(errors)
        raise SystemExit(message)

    try:
        results = run_evals(load_env=False)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"Cannot run evals: {exc}") from exc

    print_report(results)
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
