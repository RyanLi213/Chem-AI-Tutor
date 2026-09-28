from app.chemistry.validation import validate_molecule


def grade_stereocenter_answer(correct_smiles: str, atom_index: int, student_answer: str):
    if not isinstance(student_answer, str):
        return {"error": f"Answer must be a string, got: {type(student_answer).__name__}"}

    cleaned_answer = student_answer.strip().upper()

    center = validate_molecule(correct_smiles).find_stereocenter(atom_index)
    if center is None:
        return {"error": f"No stereocenter found at atom index {atom_index}"}

    return {
        "correct_label": center.label,
        "student_answer": cleaned_answer,
        "is_correct": cleaned_answer == center.label,
    }
