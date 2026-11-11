"""Serves /media/: uploads kept in the database first, then the files bundled in media/."""
from django.conf import settings
from django.http import HttpResponse
from django.views.static import serve

from .models import StoredFile


def media(request, path):
    row = StoredFile.objects.filter(name=path).only("content", "content_type").first()
    if row is not None:
        response = HttpResponse(bytes(row.content), content_type=row.content_type or "application/octet-stream")
        response["Cache-Control"] = "public, max-age=86400"
        return response
    return serve(request, path, document_root=settings.MEDIA_ROOT)
