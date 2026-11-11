"""Remove uploaded photo files that nothing uses any more (copied products share photo files)."""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Product, ProductImage, StoredFile


def delete_if_unused(name):
    if not name:
        return
    if Product.objects.filter(image=name).exists() or ProductImage.objects.filter(image=name).exists():
        return
    # Only uploads kept in the database are removed; files bundled with the project stay.
    StoredFile.objects.filter(name=name).delete()


@receiver(post_delete, sender=ProductImage)
def _photo_deleted(sender, instance, **kwargs):
    delete_if_unused(instance.image.name)


@receiver(post_delete, sender=Product)
def _product_deleted(sender, instance, **kwargs):
    delete_if_unused(instance.image.name if instance.image else "")


@receiver(pre_save, sender=Product)
def _remember_old_photo(sender, instance, **kwargs):
    if instance.pk:
        instance._old_image = Product.objects.filter(pk=instance.pk).values_list("image", flat=True).first()


@receiver(post_save, sender=Product)
def _product_saved(sender, instance, **kwargs):
    old = getattr(instance, "_old_image", None)
    if old and old != (instance.image.name if instance.image else ""):
        delete_if_unused(old)

