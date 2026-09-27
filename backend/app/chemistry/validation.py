from rdkit import Chem
from rdkit.Chem import FindMolChiralCenters, rdCIPLabeler


def canonicalize_smiles(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles) if smiles and smiles.strip() else None
    return Chem.MolToSmiles(mol) if mol is not None else None


def validate_molecule(smile_string):
    if isinstance(smile_string, str):
        smile_string = [smile_string]

    results = []

    for smi in smile_string:
        if not smi or not smi.strip():
            results.append({
                "Valid": False,
                "Number of stereocenters": 0,
                "Stereocenters": [],
                "Undefined stereocenters": []
            })
            continue

        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            results.append({
                "Valid": False,
                "Number of stereocenters": 0,
                "Stereocenters": [],
                "Undefined stereocenters": []
            })
            continue

        # Canonicalize before indexing so the same molecule written in a
        # different atom order always gets the same stereocenter indices.
        canon_smiles = Chem.MolToSmiles(mol)
        mol = Chem.MolFromSmiles(canon_smiles)

        # Explicit Hs make all four real substituents visible for CIP ranking.
        # AddHs keeps heavy-atom indices unchanged and only appends H indices.
        mol = Chem.AddHs(mol)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        rdCIPLabeler.AssignCIPLabels(mol)

        stereocenters = []
        for atom in mol.GetAtoms():
            if atom.HasProp("_CIPCode"):
                center = {
                    "Atom index": atom.GetIdx(),
                    "label": atom.GetProp("_CIPCode")
                }

                if atom.HasProp("_CIPNeighborOrder"):
                    order = list(atom.GetPropsAsDict()["_CIPNeighborOrder"])
                    priorities = []
                    for rank, nbr_idx in enumerate(order, start=1):
                        nbr = mol.GetAtomWithIdx(nbr_idx)
                        attached = [n.GetSymbol() for n in nbr.GetNeighbors() if n.GetIdx() != atom.GetIdx()]
                        priorities.append({
                            "priority_rank": rank,  # 1 = highest priority
                            "atom_symbol": nbr.GetSymbol(),
                            "attached_to": attached,
                        })
                    center["Priorities"] = priorities

                stereocenters.append(center)

        all_centers = FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
        undefined_stereocenters = [idx for idx, label in all_centers if label == "?"]

        results.append({
            "Valid": True,
            "Number of stereocenters": len(stereocenters),
            "Stereocenters": stereocenters,
            "Undefined stereocenters": undefined_stereocenters
        })
    return results
