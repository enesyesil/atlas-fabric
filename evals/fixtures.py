from dataclasses import dataclass

from knowledge.validator import verify_polity_exists


@dataclass(frozen=True)
class EvalCase:
    year: int
    region: str
    required_polities: list[str]
    forbidden_polities: list[str]
    description: str


EVAL_CASES = [
    EvalCase(
        year=800,
        region="europe",
        required_polities=["Frankish Empire", "Byzantine Empire"],
        forbidden_polities=["Holy Roman Empire", "Kingdom of France"],
        description="Reject post-962 and post-987 European anachronisms.",
    ),
    EvalCase(
        year=1200,
        region="middle_east",
        required_polities=["Abbasid Caliphate", "Crusader States"],
        forbidden_polities=["Ottoman Empire"],
        description="Ensure Levantine crusader presence without Ottoman anachronism.",
    ),
    EvalCase(
        year=1500,
        region="europe",
        required_polities=["Holy Roman Empire", "Kingdom of France"],
        forbidden_polities=["German Empire", "Austrian Empire"],
        description="Reject modern imperial labels in early modern Europe.",
    ),
]


for case in EVAL_CASES:
    for polity_name in case.required_polities:
        result = verify_polity_exists(polity_name, case.year)
        if not result["found"]:
            raise ValueError(
                f"Required eval polity '{polity_name}' is missing or inactive for year {case.year}."
            )
