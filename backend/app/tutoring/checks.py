import re

from app.chemistry.cip import ROTATION_BY_LABEL
from app.chemistry.validation import Substituent

# Position/layout claims are never granted to the model in any form, so they're
# always fabrication. "top"/"bottom"/"right" are phrase-gated because the bare
# words also mean "highest-ranked"/"correct". Words like "rotation",
# "orientation", "spatial arrangement" are deliberately NOT checked: they carry
# no true/false content. The only checkable claim is the named direction,
# verified against `rotation` below.
ALWAYS_BLOCKED_PATTERN = re.compile(
    r"\b(left|"
    r"on (the )?top\b|at the top\b|top side|top-hand|"
    r"on (the )?bottom\b|at the bottom\b|bottom side|"
    r"in front of|at the front|front side|"
    r"behind|above|below|"
    r"on the right|to the right|right side|right-hand|"
    r"points?\s+toward|pointing\s+toward|faces?\s+(toward|away)|"
    r"toward(s)?|closer to|farther (from|than)|nearest|farthest|"
    r"on the (wedge|dash))\b",
    re.IGNORECASE,
)

LABEL_PATTERN = re.compile(r"(?<![A-Za-z])([RS])(?![A-Za-z])")
# For molecules containing sulfur, a bare "S" may be the atom, not the label,
# so only "(S)" or "S configuration" counts as a configuration label.
STRICT_LABEL_PATTERN = re.compile(r"\(([RS])\)|(?<![A-Za-z])([RS])(?=[\s-]*[Cc]onfiguration)")
DIRECTION_PATTERN = re.compile(r"\b(?:counter-?clockwise|clockwise)\b", re.IGNORECASE)
# Split into clauses so a direction pairs with the label it's actually talking
# about. Commas are deliberately not split on: "R, which is clockwise" is one
# claim and splitting would orphan "clockwise" from its label.
CLAUSE_SPLIT_PATTERN = re.compile(r"[.;\n]|\b(?:while|but|whereas|however)\b", re.IGNORECASE)

FABRICATION_FLAGS = [
    "substituent", "priority", "outrank", "identical",
    "because the", "chiral center is", "double bond", "hydroxyl",
    "highest priority", "lowest priority", "attached group", "functional group",
    "electronegat",
]


def find_labels(text: str, strict: bool) -> list[tuple[int, str]]:
    pattern = STRICT_LABEL_PATTERN if strict else LABEL_PATTERN
    return [(m.start(), next(g for g in m.groups() if g)) for m in pattern.finditer(text)]


def rotation_claims_consistent(text: str, rotation: str | None, strict_labels: bool = False) -> bool:
    # R is clockwise and S is counterclockwise by definition, so naming both
    # directions is fine ("your R is clockwise, the correct S is
    # counterclockwise"); pairing a direction with the wrong label is not.
    for clause in CLAUSE_SPLIT_PATTERN.split(text):
        labels = find_labels(clause, strict_labels)
        for d in DIRECTION_PATTERN.finditer(clause):
            if rotation is None:
                return False  # no direction was granted, so any claim is invented
            direction = d.group().lower().replace("-", "")
            if labels:
                _, nearest_label = min(labels, key=lambda lab: abs(lab[0] - d.start()))
                if ROTATION_BY_LABEL[nearest_label] != direction:
                    return False
            elif direction != rotation:
                # Unlabeled direction is read as describing this molecule.
                return False
    return True


def check_explanation(grading_result: dict, response: dict, priorities: list[Substituent] | None = None, rotation: str | None = None, strict_labels: bool = False) -> dict:
    text = response["text"]
    checks = {}

    checks["non_empty"] = bool(text.strip())
    checks["not_truncated"] = not response.get("truncated", False)

    stated = {label for _, label in find_labels(text, strict_labels)}
    checks["states_correct_label"] = grading_result["correct_label"] in stated

    if not grading_result["is_correct"]:
        wrong_answer_as_correct = re.compile(
            rf"correct answer is\s*[*(]*{re.escape(grading_result['student_answer'])}[*)]*(?![A-Za-z])",
            re.IGNORECASE
        )
        checks["does_not_affirm_wrong_answer"] = not bool(wrong_answer_as_correct.search(text))

    directional_ok = not bool(ALWAYS_BLOCKED_PATTERN.search(text))
    checks["no_spatial_fabrication"] = directional_ok and rotation_claims_consistent(text, rotation, strict_labels)

    if priorities is None:
        # No grounded substituent data was given -- any chemistry-reasoning
        # vocabulary means the model invented the explanation.
        checks["no_fabricated_reasoning"] = not any(flag in text.lower() for flag in FABRICATION_FLAGS)

    checks["passed"] = all(v for k, v in checks.items() if k != "passed")
    return checks
