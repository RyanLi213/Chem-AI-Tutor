from app.chemistry.cip import build_priority_reason, element_name
from app.chemistry.validation import Substituent


def build_explanation_prompt(grading_result: dict, smiles: str, priorities: list[Substituent] | None = None, rotation: str | None = None) -> str:
    correct = f"({grading_result['correct_label']})"
    student = f"({grading_result['student_answer']})"

    priority_block = ""
    if priorities:
        lines = "\n".join(
            f"  {p.priority_rank}. {element_name(p.atom_symbol)}"
            f" (attached to: {', '.join(element_name(a) for a in p.attached_to) or 'nothing else'})"
            for p in priorities
        )
        reason = build_priority_reason(priorities)
        priority_block = (
            "\n- Substituent priority order at this stereocenter, highest to lowest "
            f"(from CIP rules):\n{lines}"
            f"\n- Why the top group outranks the next one: {reason}"
        )

    rotation_block = ""
    if rotation:
        rotation_block = (
            "\n- Geometric fact (from CIP rules): with the lowest-priority group "
            f"pointing away from you, tracing priority 1 -> 2 -> 3 goes {rotation}, "
            f"which is what defines this as {correct}."
        )

    return f"""### Role
You are a friendly, encouraging organic chemistry tutor helping a student learn stereochemistry.

### Context
- Molecule (SMILES): {smiles}
- Student's answer: {student}
- Correct answer: {correct}
- Was the student correct?: {grading_result['is_correct']}{priority_block}{rotation_block}

### Task
Write a short explanation (3-4 sentences) telling the student whether they got it right or wrong.
If a priority order, reason, or geometric fact are listed above, restate them in your own words --
do not compute or invent a new one.

### Rules (important)
- Only use the facts listed in Context above. Do NOT invent, guess, or compute any new chemistry
  beyond what's listed.
- Only mention a rotation direction (clockwise/counterclockwise) if a Geometric fact is given above,
  and use that exact direction -- never guess one, and never describe any other spatial detail
  (left/right, top/bottom, "points toward", wedge/dash) that isn't given to you word-for-word.
- If correct: briefly confirm it and give quick encouragement.
- If incorrect: clearly state the correct answer — never just say "wrong" without including it.
- Always write a configuration with parentheses, exactly as (R) or (S).
- Refer to atoms by element name (oxygen, sulfur, carbon), never by chemical symbol.
- Keep the tone encouraging, never harsh.

### Output format
Return ONLY the explanation text. No headers, no bullet points, no restating these instructions.
"""
