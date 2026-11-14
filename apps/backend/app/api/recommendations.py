"""Jobs for you: postings ranked by similarity to the user's resumes."""

from fastapi import APIRouter, Query, Response, status

from app.api.deps import RecommendationServiceDep
from app.schemas.match import ProfileRead, ProfileUpdate, RecommendationRead, RefreshResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(
    service: RecommendationServiceDep, limit: int = Query(20, ge=1, le=50)
) -> list[RecommendationRead]:
    return service.feed(limit)


@router.post("/refresh", response_model=RefreshResponse)
def refresh_recommendations(service: RecommendationServiceDep) -> RefreshResponse:
    return service.refresh()


@router.get("/profile", response_model=ProfileRead)
def get_profile(service: RecommendationServiceDep) -> ProfileRead:
    return service.get_profile()


@router.put("/profile", response_model=ProfileRead)
def update_profile(data: ProfileUpdate, service: RecommendationServiceDep) -> ProfileRead:
    return service.update_profile(data)


@router.post("/{recommendation_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(recommendation_id: int, service: RecommendationServiceDep) -> Response:
    service.dismiss(recommendation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
