import json
from typing import Any

from agents.model_factory import get_model
from agents.state import AtlasState
from evals.fixtures import EvalCase

DEFAULT_JUDGE_RESULT = {
    "score": 0,
    "historical_accuracy": "fail",
    "geographic_coherence": "fail",
    "major_errors": [],
    "reasoning": "",
}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )
    return str(content)


def judge_case(case: EvalCase, state: AtlasState) -> dict:
    llm = get_model(role="reviewer")
    prompt = (
        "You are grading a historical map generation.\n"
        "Return JSON only with keys: score, historical_accuracy, geographic_coherence, "
        "major_errors, reasoning.\n"
        "Score must be 0-10.\n\n"
        f"Case:\n{json.dumps(case.__dict__, indent=2)}\n\n"
        f"Output:\n{json.dumps(state.get('map_config', {}), indent=2)}"
    )
    response = llm.invoke(prompt)
    text = _coerce_text(getattr(response, "content", ""))

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {**DEFAULT_JUDGE_RESULT, "reasoning": "Judge response was not valid JSON."}

    return {
        "score": int(parsed.get("score", 0)),
        "historical_accuracy": parsed.get("historical_accuracy", "fail"),
        "geographic_coherence": parsed.get("geographic_coherence", "fail"),
        "major_errors": list(parsed.get("major_errors", [])),
        "reasoning": str(parsed.get("reasoning", "")),
    }
