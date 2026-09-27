import requests

from app.chemistry.cip import describe_rotation, get_substituent_priorities
from app.tutoring.checks import check_explanation
from app.tutoring.llm_client import generate_completion
from app.tutoring.prompts import build_explanation_prompt


def get_safe_explanation(grading_result: dict, smiles: str, atom_index: int | None = None) -> dict:
    if "error" in grading_result:
        return {
            "text": f"Couldn't grade that: {grading_result['error']}",
            "used_fallback": True,
            "raw_response": None,
            "checks": None,
        }

    label = grading_result["correct_label"]
    fallback_text = (
        f"Correct! The stereocenter is {label}."
        if grading_result["is_correct"]
        else f"Not quite — the correct answer is {label}."
    )

    priorities = get_substituent_priorities(smiles, atom_index) if atom_index is not None else None
    priorities = priorities or None  # treat an empty list the same as "no data available"
    rotation = describe_rotation(label) if priorities else None

    prompt = build_explanation_prompt(grading_result, smiles, priorities, rotation)

    try:
        response = generate_completion(prompt)
    except requests.exceptions.RequestException as e:
        # LLM down, slow, or erroring -- a plain-but-correct answer beats a crash.
        return {
            "text": fallback_text,
            "used_fallback": True,
            "raw_response": None,
            "checks": None,
            "error": str(e),
        }

    checks = check_explanation(grading_result, response, priorities, rotation)

    return {
        "text": response["text"] if checks["passed"] else fallback_text,
        "used_fallback": not checks["passed"],
        "raw_response": response,
        "checks": checks,
        "priorities": priorities,
        "rotation": rotation,
    }
