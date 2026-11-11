"""File storage that keeps uploads in the database, with the bundled media/ folder as a read-only fallback.

Vercel's disk is read-only, so product photos uploaded from the dashboard are saved in the StoredFile
table instead. Files that ship with the project (media/products/...) are still read from disk.
"""
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


class DatabaseStorage(FileSystemStorage):
    def _model(self):
        from .models import StoredFile  # imported late: storage is created before the apps are ready
        return StoredFile

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        content_type = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0] or ""
        self._model().objects.update_or_create(
            name=name, defaults={"content": data, "content_type": content_type, "size": len(data)})
        return name

    def _open(self, name, mode="rb"):
        row = self._model().objects.filter(name=name).first()
        if row is not None:
            f = ContentFile(bytes(row.content), name=name)
            return f
        return super()._open(name, mode)

    def exists(self, name):
        return self._model().objects.filter(name=name).exists() or super().exists(name)

    def delete(self, name):
        if not name:
            return
        deleted, _ = self._model().objects.filter(name=name).delete()
        if not deleted:
            try:
                super().delete(name)
            except OSError:  # bundled files on a read-only disk stay where they are
                pass

    def size(self, name):
        row = self._model().objects.filter(name=name).only("size").first()
        return row.size if row is not None else super().size(name)
