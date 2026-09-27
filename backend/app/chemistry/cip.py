from rdkit import Chem

from app.chemistry.validation import validate_molecule


def get_substituent_priorities(smiles: str, atom_index: int) -> list[dict]:
    result = validate_molecule(smiles)[0]
    for center in result["Stereocenters"]:
        if center["Atom index"] == atom_index:
            return center.get("Priorities", [])
    return []


def _atomic_number(symbol: str) -> int:
    return Chem.GetPeriodicTable().GetAtomicNumber(symbol)


def build_priority_reason(priorities: list[dict]) -> str:
    """Deterministic, computed reason -- not something the LLM decides."""
    if len(priorities) < 2:
        return ""

    top, second = priorities[0], priorities[1]
    top_num = _atomic_number(top["atom_symbol"])
    second_num = _atomic_number(second["atom_symbol"])

    if top_num != second_num:
        return (
            f"{top['atom_symbol']} (atomic number {top_num}) outranks "
            f"{second['atom_symbol']} (atomic number {second_num}) because it has "
            f"the higher atomic number."
        )

    # Same atom, tied -- CIP breaks the tie using what each is attached to next.
    # Only looks one shell deep; deeper ties can produce a shallow reason.
    def best_attached_number(p):
        nums = [_atomic_number(a) for a in p["attached_to"]]
        return max(nums) if nums else 0

    top_best = best_attached_number(top)
    second_best = best_attached_number(second)
    return (
        f"{top['atom_symbol']} and {second['atom_symbol']} tie on atomic number, "
        f"so the tie is broken by what they're attached to: the group attached to "
        f"{top['attached_to']} (highest atomic number {top_best}) outranks the one "
        f"attached to {second['attached_to']} (highest atomic number {second_best})."
    )


# R/S is *defined* as this rotation direction: lowest-priority group pointing
# away, trace priority 1 -> 2 -> 3; clockwise is R, counterclockwise is S.
ROTATION_BY_LABEL = {"R": "clockwise", "S": "counterclockwise"}


def describe_rotation(label: str) -> str:
    """Deterministic lookup, not something the LLM decides."""
    return ROTATION_BY_LABEL[label]
