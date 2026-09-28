from dataclasses import dataclass, field

from rdkit import Chem
from rdkit.Chem import FindMolChiralCenters, rdCIPLabeler


def canonicalize_smiles(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles) if smiles and smiles.strip() else None
    return Chem.MolToSmiles(mol) if mol is not None else None


def molecule_contains_element(smiles: str, symbol: str) -> bool:
    mol = Chem.MolFromSmiles(smiles) if smiles and smiles.strip() else None
    return mol is not None and any(atom.GetSymbol() == symbol for atom in mol.GetAtoms())


@dataclass
class Substituent:
    priority_rank: int  # 1 = highest priority
    atom_symbol: str
    attached_to: list[str]


@dataclass
class Stereocenter:
    atom_index: int
    label: str  # "R" or "S"
    priorities: list[Substituent] = field(default_factory=list)


@dataclass
class MoleculeValidation:
    valid: bool
    stereocenters: list[Stereocenter] = field(default_factory=list)
    undefined_stereocenters: list[int] = field(default_factory=list)

    @property
    def stereocenter_count(self) -> int:
        return len(self.stereocenters)

    def find_stereocenter(self, atom_index: int) -> Stereocenter | None:
        return next((c for c in self.stereocenters if c.atom_index == atom_index), None)


def validate_molecule(smiles: str) -> MoleculeValidation:
    mol = Chem.MolFromSmiles(smiles) if smiles and smiles.strip() else None
    if mol is None:
        return MoleculeValidation(valid=False)

    # Canonicalize before indexing so the same molecule written in a
    # different atom order always gets the same stereocenter indices.
    mol = Chem.MolFromSmiles(Chem.MolToSmiles(mol))

    # Explicit Hs make all four real substituents visible for CIP ranking.
    # AddHs keeps heavy-atom indices unchanged and only appends H indices.
    mol = Chem.AddHs(mol)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    rdCIPLabeler.AssignCIPLabels(mol)

    stereocenters = []
    for atom in mol.GetAtoms():
        if not atom.HasProp("_CIPCode"):
            continue
        center = Stereocenter(atom_index=atom.GetIdx(), label=atom.GetProp("_CIPCode"))

        if atom.HasProp("_CIPNeighborOrder"):
            order = list(atom.GetPropsAsDict()["_CIPNeighborOrder"])
            for rank, nbr_idx in enumerate(order, start=1):
                nbr = mol.GetAtomWithIdx(nbr_idx)
                center.priorities.append(Substituent(
                    priority_rank=rank,
                    atom_symbol=nbr.GetSymbol(),
                    attached_to=[n.GetSymbol() for n in nbr.GetNeighbors() if n.GetIdx() != atom.GetIdx()],
                ))

        stereocenters.append(center)

    all_centers = FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
    return MoleculeValidation(
        valid=True,
        stereocenters=stereocenters,
        undefined_stereocenters=[idx for idx, label in all_centers if label == "?"],
    )
