from app.chemistry.validation import validate_molecule


def grade_stereocenter_answer(correct_smiles: str, atom_index: int, student_answer: str):
    if not isinstance(student_answer, str):
        return {"error": f"Answer must be a string, got: {type(student_answer).__name__}"}

    cleaned_answer = student_answer.strip().upper()

    result = validate_molecule(correct_smiles)
    stereocenters = result[0]["Stereocenters"]

    correct_label = None
    for center in stereocenters:
        if center["Atom index"] == atom_index:
            correct_label = center["label"]

    if correct_label is None:
        return {"error": f"No stereocenter found at atom index {atom_index}"}

    is_correct = (cleaned_answer == correct_label)
    return {
        "correct_label": correct_label,
        "student_answer": cleaned_answer,
        "is_correct": is_correct
    }
