import os
import tempfile

from fastapi import APIRouter, File, UploadFile

from app.api.schemas import AnalyzeResponse, GradeRequest, GradeResponse
from app.pipeline import analyze_image, grade_and_explain

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# Plain `def` (not async) so the slow DECIMER/LLM calls run in FastAPI's
# threadpool instead of blocking the event loop.
@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(image: UploadFile = File(...)):
    suffix = os.path.splitext(image.filename or "")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image.file.read())
        path = tmp.name
    try:
        return analyze_image(path)
    finally:
        os.remove(path)


@router.post("/grade", response_model=GradeResponse)
def grade(req: GradeRequest):
    return grade_and_explain(req.smiles, req.atom_index, req.answer)
