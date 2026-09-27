from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D


def draw_stereocenters_svg(smiles: str, atom_indices: list[int], width: int = 400, height: int = 400) -> str:
    # Uses the same canonical re-parse as validate_molecule, so the numbers shown
    # match the atom indices the grader expects. Deliberately does not annotate
    # R/S -- that would show the student the answer.
    mol = Chem.MolFromSmiles(Chem.MolToSmiles(Chem.MolFromSmiles(smiles)))
    for idx in atom_indices:
        mol.GetAtomWithIdx(idx).SetProp("atomNote", str(idx))

    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, highlightAtoms=atom_indices)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()
