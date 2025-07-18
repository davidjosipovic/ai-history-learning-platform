from fastapi import APIRouter
from app.schemas.parse import ParseRequest

router = APIRouter()

@router.post("/parse")
def parse(request: ParseRequest):
    # TODO: Implement parsing logic (extract entities, dates, etc.)
    return {"parsed": f"Parsed: {request.text}"}
