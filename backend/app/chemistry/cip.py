from rdkit import Chem

from app.chemistry.validation import Substituent, validate_molecule


def get_substituent_priorities(smiles: str, atom_index: int) -> list[Substituent]:
    center = validate_molecule(smiles).find_stereocenter(atom_index)
    return center.priorities if center else []


def _atomic_number(symbol: str) -> int:
    return Chem.GetPeriodicTable().GetAtomicNumber(symbol)


def element_name(symbol: str) -> str:
    # Explanations use names, not symbols: the symbol "S" (sulfur) is
    # indistinguishable from the configuration label S in the LLM's text.
    return Chem.GetPeriodicTable().GetElementName(_atomic_number(symbol)).lower()


def build_priority_reason(priorities: list[Substituent]) -> str:
    """Deterministic, computed reason -- not something the LLM decides."""
    if len(priorities) < 2:
        return ""

    top, second = priorities[0], priorities[1]
    top_num = _atomic_number(top.atom_symbol)
    second_num = _atomic_number(second.atom_symbol)

    top_name = element_name(top.atom_symbol)
    second_name = element_name(second.atom_symbol)

    if top_num != second_num:
        return (
            f"{top_name} (atomic number {top_num}) outranks "
            f"{second_name} (atomic number {second_num}) because it has "
            f"the higher atomic number."
        )

    # Same atom, tied -- CIP breaks the tie using what each is attached to next.
    # Only looks one shell deep; deeper ties can produce a shallow reason.
    def best_attached_number(p: Substituent) -> int:
        nums = [_atomic_number(a) for a in p.attached_to]
        return max(nums) if nums else 0

    top_best = best_attached_number(top)
    second_best = best_attached_number(second)
    top_attached = ", ".join(element_name(a) for a in top.attached_to) or "nothing else"
    second_attached = ", ".join(element_name(a) for a in second.attached_to) or "nothing else"
    return (
        f"Both are {top_name}, so they tie on atomic number and the tie is broken by "
        f"what they're attached to: the {top_name} attached to {top_attached} "
        f"(highest atomic number {top_best}) outranks the {second_name} attached to "
        f"{second_attached} (highest atomic number {second_best})."
    )


# R/S is *defined* as this rotation direction: lowest-priority group pointing
# away, trace priority 1 -> 2 -> 3; clockwise is R, counterclockwise is S.
ROTATION_BY_LABEL = {"R": "clockwise", "S": "counterclockwise"}


def describe_rotation(label: str) -> str:
    """Deterministic lookup, not something the LLM decides."""
    return ROTATION_BY_LABEL[label]
