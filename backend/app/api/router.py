from fastapi import APIRouter

from app.api.endpoints import sources, products, runs, config, stats

api_router = APIRouter()

api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
