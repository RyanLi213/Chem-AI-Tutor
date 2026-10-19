from dataclasses import dataclass, field

from rdkit import Chem

from app.chemistry.validation import Substituent, prepare_cip_mol, validate_molecule

MAX_TIE_BREAK_LAYER = 12
PHANTOM = 0  # CIP phantom atom (atomic number 0) that fills out a duplicate atom


def get_substituent_priorities(smiles: str, atom_index: int) -> list[Substituent]:
    center = validate_molecule(smiles).find_stereocenter(atom_index)
    return center.priorities if center else []


def _atomic_number(symbol: str) -> int:
    return Chem.GetPeriodicTable().GetAtomicNumber(symbol)


def _name_from_number(atomic_num: int) -> str:
    return Chem.GetPeriodicTable().GetElementName(atomic_num).lower()


def element_name(symbol: str) -> str:
    # Explanations use names, not symbols: the symbol "S" (sulfur) is
    # indistinguishable from the configuration label S in the LLM's text.
    return _name_from_number(_atomic_number(symbol))


@dataclass
class _Node:
    """One atom in the CIP digraph, walked outward from a stereocenter."""
    atomic_num: int
    atom_idx: int | None = None  # None for duplicate/phantom atoms, which are never expanded
    parent_idx: int | None = None
    path: frozenset = frozenset()  # atoms between this one and the stereocenter
    duplicate: bool = False
    children: list["_Node"] = field(default_factory=list)


@dataclass
class TieBreak:
    layer: int  # 2 = atoms attached to the first atoms, 3 = one step further out, ...
    top_wins: bool
    top_atoms: tuple[int, ...]  # atomic numbers at the deciding spot, highest first
    next_atoms: tuple[int, ...]
    involves_double_bond: bool


def _expand(mol: Chem.Mol, node: _Node) -> list[_Node]:
    """CIP children: real neighbors, plus duplicate atoms for multiple bonds and ring closures."""
    if node.atom_idx is None:
        return [_Node(PHANTOM)] * 3 if node.duplicate else []
    atom = mol.GetAtomWithIdx(node.atom_idx)
    children = []
    for bond in atom.GetBonds():
        nbr = bond.GetOtherAtom(atom)
        order = int(round(bond.GetBondTypeAsDouble()))
        duplicate = _Node(nbr.GetAtomicNum(), duplicate=True)
        if nbr.GetIdx() == node.parent_idx:
            children += [duplicate] * (order - 1)  # C=O: the O counts again on the way back
        elif nbr.GetIdx() in node.path:
            children += [duplicate] * order  # ring closure: count it, then stop
        else:
            children.append(_Node(nbr.GetAtomicNum(), nbr.GetIdx(), node.atom_idx,
                                  node.path | {node.atom_idx}))
            children += [duplicate] * (order - 1)
    return children


def _carried(node: _Node) -> tuple[int, ...]:
    nums = sorted((c.atomic_num for c in node.children), reverse=True)
    return tuple(nums + [PHANTOM] * (3 - len(nums)))


def _next_layer(mol: Chem.Mol, layer: list[_Node]) -> list[_Node]:
    # Children of higher-ranked atoms are compared first, so keep them grouped
    # under their parent and order each group by what it carries.
    result = []
    for node in layer:
        for child in node.children:
            child.children = _expand(mol, child)
        result += sorted(node.children, key=lambda c: (c.atomic_num, _carried(c)), reverse=True)
    return result


def find_tie_break(mol: Chem.Mol, center_idx: int, top_idx: int, next_idx: int) -> TieBreak | None:
    """Walk both groups outward layer by layer and report the first layer where they differ.

    A simplified version of the CIP comparison: callers must check `top_wins`
    against RDKit's own ranking before trusting it.
    """
    layers = []
    for idx in (top_idx, next_idx):
        root = _Node(mol.GetAtomWithIdx(idx).GetAtomicNum(), idx, center_idx, frozenset({center_idx}))
        root.children = _expand(mol, root)
        layers.append([root])

    for layer_num in range(2, MAX_TIE_BREAK_LAYER + 1):
        top_layer, next_layer = layers
        size = max(len(top_layer), len(next_layer))
        for i in range(size):
            a = top_layer[i] if i < len(top_layer) else None
            b = next_layer[i] if i < len(next_layer) else None
            carried_a = _carried(a) if a else (PHANTOM,) * 3
            carried_b = _carried(b) if b else (PHANTOM,) * 3
            if carried_a != carried_b:
                double = any(c.duplicate for n in (a, b) if n for c in n.children)
                return TieBreak(layer_num, carried_a > carried_b, carried_a, carried_b, double)
        layers = [_next_layer(mol, top_layer), _next_layer(mol, next_layer)]
        if not any(n.atom_idx is not None for layer in layers for n in layer):
            return None
    return None


def _atom_list(nums: tuple[int, ...]) -> str:
    names = [_name_from_number(z) for z in nums if z != PHANTOM]
    return ", ".join(names) if names else "no further atoms"


def _describe_tie_break(element: str, tie: TieBreak) -> str:
    if tie.layer == 2:
        text = (
            f"Both groups start with {element}, so they tie on atomic number. "
            f"Comparing what each {element} carries, the top group's carries "
            f"{_atom_list(tie.top_atoms)} while the next group's carries "
            f"{_atom_list(tie.next_atoms)}, so the top group ranks higher."
        )
    else:
        steps = tie.layer - 2
        span = "for one more step" if steps == 1 else f"for {steps} more steps"
        text = (
            f"Both groups start with {element}, so they tie on atomic number, and the atoms "
            f"along each chain stay identical {span}. One step further out, the top group has "
            f"an atom carrying {_atom_list(tie.top_atoms)} where the next group's matching atom "
            f"carries {_atom_list(tie.next_atoms)}, so the top group ranks higher."
        )
    if tie.involves_double_bond:
        text += " Under CIP rules, a double bond counts its partner atom twice."
    return text


def build_priority_reason(smiles: str, atom_index: int) -> str:
    """Deterministic reason the top group outranks the next -- never decided by the LLM."""
    mol = prepare_cip_mol(smiles)
    if mol is None or not 0 <= atom_index < mol.GetNumAtoms():
        return ""
    center = mol.GetAtomWithIdx(atom_index)
    if not center.HasProp("_CIPNeighborOrder"):
        return ""
    order = list(center.GetPropsAsDict()["_CIPNeighborOrder"])
    if len(order) < 2:
        return ""

    top, nxt = mol.GetAtomWithIdx(order[0]), mol.GetAtomWithIdx(order[1])
    top_name, next_name = element_name(top.GetSymbol()), element_name(nxt.GetSymbol())

    if top.GetAtomicNum() != nxt.GetAtomicNum():
        return (
            f"{top_name} (atomic number {top.GetAtomicNum()}) outranks "
            f"{next_name} (atomic number {nxt.GetAtomicNum()}) because it has "
            f"the higher atomic number."
        )

    walk_mol = Chem.Mol(mol)
    try:
        Chem.Kekulize(walk_mol, clearAromaticFlags=True)  # CIP counts rings as single/double bonds
        tie = find_tie_break(walk_mol, atom_index, order[0], order[1])
    except Chem.KekulizeException:
        tie = None

    # RDKit is the authority: only explain a tie-break that agrees with its ranking.
    if tie is None or not tie.top_wins:
        return (
            f"Both groups start with {top_name}, so they tie on atomic number; comparing the "
            f"atoms further along each chain under CIP rules breaks the tie in favour of the top group."
        )
    return _describe_tie_break(top_name, tie)


# R/S is *defined* as this rotation direction: lowest-priority group pointing
# away, trace priority 1 -> 2 -> 3; clockwise is R, counterclockwise is S.
ROTATION_BY_LABEL = {"R": "clockwise", "S": "counterclockwise"}


def describe_rotation(label: str) -> str:
    """Deterministic lookup, not something the LLM decides."""
    return ROTATION_BY_LABEL[label]
