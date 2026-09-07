# Achieved Milestones and Findings

## Known Limitations & Findings (from real testing, updated)
 
Everything below was discovered by actually building and stress-testing the
pipeline against a 29-molecule verified test set (`decimer_test_set_20.py`
plus 9 more), not assumed in advance.
 
**DECIMER accuracy baseline:** ~80% exact match on the 29-molecule set,
roughly in line with DECIMER's own published benchmarks (~96% without
stereochemistry, ~90% with stereochemistry, exact match).
 
**R/S (tetrahedral) stereocenters -- reliable.** Correctly handled single,
double, and triple stereocenter molecules, including the hard case of
distinguishing meso-tartaric acid from its chiral (2R,3R) form, a
non-carbon (nitrogen) stereocenter, and a charged zwitterion. This is the
part of the app safe to build the MVP around.
 
**E/Z (double bond) stereochemistry -- unreliable, real gap.** DECIMER
failed both E/Z test molecules (dropped the stereo info entirely, or
hallucinated a different structure). `validate_molecule` also doesn't
currently check bonds at all, only atoms, so it can't grade E/Z even in
principle yet. Treat E/Z as out of scope for the MVP until this is
deliberately addressed.
 
**Undefined stereochemistry -- real gap.** A structure with a real
stereocenter but no wedge/dash specified (e.g. `CC(O)C(=O)O`) gets zero
CIP labels from RDKit -- correct chemistry, but `validate_molecule`
currently can't tell "no stereocenter exists" apart from "stereocenter
exists but wasn't specified." A real student who forgets to draw
stereochemistry would silently fall into the wrong bucket. Worth fixing
before grading real hand-drawn input (RDKit's `FindMolChiralCenters(...,
includeUnassigned=True)` is the likely fix).
 
**Atom-index fragility -- real gap, fix in progress.** The same molecule
written with atoms in a different order places its stereocenter(s) at a
different atom index. Grading currently identifies "which stereocenter"
by raw index, which breaks (fails safely, with an error, not a silent
wrong grade) whenever the SMILES being graded isn't in the exact order
expected. Matters because DECIMER's predicted SMILES is not guaranteed to
match the original ordering.
 
**Fischer projections -- unconfirmed, high priority to test.** Could not
confirm whether DECIMER supports this drawing convention at all. Fischer
projections are a completely different visual convention (horizontal/
vertical line meaning vs. wedge/dash) and are central to how stereochemistry
is actually taught for sugars and amino acids -- exactly this app's
subject matter. Untested so far.
 
**Hand-drawn / photographed images -- untested.** All testing so far used
clean, computer-generated images (the easiest case). DECIMER has a
separate hand-drawn model; real-world accuracy is likely meaningfully
lower than the ~80% baseline above until this is tested.
 
**Occasional hallucination on simple molecules.** Even a plain achiral
molecule (acetone) was once misread as a different, structurally invalid
guess -- a reminder that stereocenter-count matching alone isn't enough;
full canonical-structure comparison matters even for non-stereo cases.
 
## Future Goal (noted, not yet started)
 
Once the notebook-based logic (OCSR pipeline, validation, grading, tutoring prompt)
is proven out, migrate from a single notebook into a proper multi-file Python
project structure (e.g. separate modules for OCSR, validation, grading, and
tutoring, plus tests and a requirements.txt) -- an "industry-level" repo layout,
not a research notebook. Explicitly sequenced *after* the logic is proven, not
before.
 
## Next Concrete Step
 
Milestone 0 + first half of Milestone 1: install RDKit and DECIMER locally, run one test molecule through each, and confirm you can go image → SMILES → validated molecule object. This is pure setup/engineering and doesn't require chemistry knowledge to complete.