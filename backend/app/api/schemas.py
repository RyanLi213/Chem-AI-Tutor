from pydantic import BaseModel


class GradeRequest(BaseModel):
    smiles: str
    atom_index: int
    answer: str


class AnalyzeResponse(BaseModel):
    valid: bool
    smiles: str
    predicted_smiles: str | None = None
    stereocenters: list[int]
    undefined_stereocenters: list[int]
    svg: str | None


class GradeResponse(BaseModel):
    grading: dict
    explanation: str
    used_fallback: bool
