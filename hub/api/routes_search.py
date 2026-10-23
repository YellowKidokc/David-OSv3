"""Exact search shared by human clients and AI agents."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from hub.services.exact_search import search, health, register_location
import os
router = APIRouter(prefix="/search", tags=["search"])
class LocationRequest(BaseModel):
    path: str = Field(min_length=3, max_length=4096)

@router.post('/locations')
def add_location(request: LocationRequest):
    if not os.environ.get('FIHUB_API_TOKEN'):
        raise HTTPException(503, 'Start the authenticated David OS Search launcher first')
    try:
        return register_location(request.path)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4096)
    roots: list[str] | None = None
    file_types: list[str] | None = None
    maximum_results: int = Field(default=50, ge=1, le=500)
    regex: bool = False
    case_sensitive: bool = False
    include_hidden: bool = False
@router.get("/health")
def search_health():
    return health()
@router.post("/exact")
def exact(request: SearchRequest):
    try:
        return search(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (RuntimeError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
