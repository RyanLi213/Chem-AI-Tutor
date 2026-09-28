from app.chemistry.rendering import draw_stereocenters_svg
from app.chemistry.validation import canonicalize_smiles, validate_molecule
from app.grading.stereocenter import grade_stereocenter_answer
from app.ocsr.decimer_client import predict_smiles_from_image
from app.tutoring.safe_explanation import get_safe_explanation


def analyze_smiles(smiles: str) -> dict:
    canonical = canonicalize_smiles(smiles)
    if canonical is None:
        return {"valid": False, "smiles": smiles, "stereocenters": [], "undefined_stereocenters": [], "svg": None}

    validation = validate_molecule(canonical)
    # Only indices go to the client -- the R/S labels are the answers.
    stereocenter_indices = [c.atom_index for c in validation.stereocenters]
    return {
        "valid": True,
        "smiles": canonical,
        "stereocenters": stereocenter_indices,
        "undefined_stereocenters": validation.undefined_stereocenters,
        "svg": draw_stereocenters_svg(canonical, stereocenter_indices),
    }


def analyze_image(image_path: str) -> dict:
    predicted = predict_smiles_from_image(image_path)
    result = analyze_smiles(predicted)
    result["predicted_smiles"] = predicted
    return result


def grade_and_explain(smiles: str, atom_index: int, answer: str) -> dict:
    grading = grade_stereocenter_answer(smiles, atom_index, answer)
    explanation = get_safe_explanation(grading, smiles, atom_index=atom_index)
    return {
        "grading": grading,
        "explanation": explanation["text"],
        "used_fallback": explanation["used_fallback"],
    }
