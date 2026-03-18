def print_report(results: list[dict]) -> None:
    passed = sum(1 for result in results if result["passed"])
    total = len(results)

    print(f"Evals: {passed}/{total} passed")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        case = result["case"]
        print(f"[{status}] year={case.year} region={case.region} - {case.description}")
        print(
            "  coverage="
            f"{result['checks']['coverage_pct']} "
            f"judge={result['judge']['score']} "
            f"missing_required={result['checks']['missing_required']} "
            f"forbidden={result['checks']['found_forbidden']} "
            f"anachronisms={result['checks']['anachronisms']}"
        )
