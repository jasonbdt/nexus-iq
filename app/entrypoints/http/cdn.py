"""DDragon file serving; conversion and filesystem access live in the adapter."""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from .dependencies import ServicesDep

router = APIRouter()


@router.get('/cdn/{file_path:path}')
def serve_ddragon(file_path: str, services: ServicesDep):
    """Serve the same WebP assets at the existing public CDN path."""
    return FileResponse(services.assets.file(file_path), media_type='image/webp')
