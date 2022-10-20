import analytics
from django.db.models import F
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from typing import Set
from django.contrib.sites.models import Site

from heartface.apps.core.models import User, Hashtag, Video, Product, SupplierProduct, Supplier, MarketplaceURL, \
    Marketplace, Follow, VideoCDNStatus
from heartface.libs.utils import _req_ctx_with_request
from heartface.apps.core.tasks import update_es_record_task, delete_es_record_task


@receiver(post_save, sender=User, dispatch_uid="update_user_index")
def update_es_user_record(sender, instance, update_fields:Set=None, **kwargs):
    """
    Update if serialized fields changed via celery task (else
    can make things like login slow)
    """
    request_ctx = kwargs.get('request_ctx', _req_ctx_with_request())
    from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
    obj = PublicUserSerializer(instance, context=request_ctx)
    if not (update_fields and update_fields.isdisjoint(set(obj.fields.keys()))):
        if instance.disabled:
            # No point indexing disabled users that will have field like 'disabled@disabled.com' etc
            # and don't want disabled users to be searchable
            delete_es_record_task.delay(instance.pk, "PublicUserSerializer")
        else:
            # Segment (update on create but also when traits changed)
            analytics.identify(instance.pk, {
                    'created': instance.date_joined,
                    'sign_up_method': 'Facebook' if instance.socialaccount_set.count() else 'Email',
                    'email': instance.email,
                    'name': instance.full_name,
                    'username': instance.username,
                    'age': instance.age,
                    'gender': instance.gender,
                    'description': instance.description,
                    'profile_picture': 'https://%s%s' % (Site.objects.get_current().domain, instance.photo.url) if instance.photo else '',
                    'country': instance.country.code,
                    'creator': True if instance.videos.count() else False,
                    'last_login': instance.last_login,
            })
            update_es_record_task.delay(instance.pk, "User")
        # We also want to update all Video indexes (could potentially do it
        # by overriding save method of UserIndex also?)
        for video in instance.videos.all():
            update_es_record_task.delay(video.pk, "Video")


@receiver(post_delete, sender=User, dispatch_uid="delete_user_index")
def delete_es_user_record(sender, instance, *args, **kwargs):
    delete_es_record_task.delay(instance.pk, "PublicUserSerializer")


@receiver(post_save, sender=Hashtag, dispatch_uid="update_hashtag_index")
def update_es_hashtag_record(sender, instance, **kwargs):
    update_es_record_task.delay(instance.pk, "Hashtag")


@receiver(post_delete, sender=Hashtag, dispatch_uid="delete_hashtag_index")
def delete_es_hashtag_record(sender, instance, *args, **kwargs):
    delete_es_record_task.delay(instance.pk, "HashtagSerializer")


@receiver(m2m_changed, sender=Product.videos.through, dispatch_uid="reindex_products_vids_changed")
def reindex_prods(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in ["post_remove", "post_add"]:
        if isinstance(instance, Video):
            products = Product.objects.filter(pk__in=pk_set)
        else:
            products = [instance]
        for product in products:
            update_es_record_task(product.pk, "Product")


@receiver(post_save, sender=Video, dispatch_uid="update_video_index")
def update_es_video_record(sender, instance, created, **kwargs):
    update_es_record_task.delay(instance.pk, "Video")


@receiver(post_delete, sender=Video, dispatch_uid="delete_video_index")
def delete_es_video_record(sender, instance, *args, **kwargs):
    delete_es_record_task.delay(instance.pk, "VideoSerializer")


@receiver(post_save, sender=Product, dispatch_uid="update_product_index")
def update_es_product_record(sender, instance, **kwargs):
    # Update videos that have the product associated with this Product too
    vid_count = 0
    for video in instance.videos.all():
        vid_count += 1
        update_es_record_task.delay(instance.pk, "Video")
    update_es_record_task.delay(instance.pk, "Product")


@receiver(post_delete, sender=Product, dispatch_uid="delete_product_index")
def delete_es_product_record(sender, instance, *args, **kwargs):
    delete_es_record_task.delay(instance.pk, "ProductSerializer")
    # Update videos that have the product associated with this Product too
    for video in instance.videos.all():
        delete_es_record_task.delay(video.pk, "VideoSerializer")


@receiver(post_save, sender=SupplierProduct, dispatch_uid="update_supplierproduct_in_product_index")
@receiver(post_delete, sender=SupplierProduct, dispatch_uid="delete_supplierproduct_in_product_index")
def update_es_product_supplierproduct_record(sender, instance, *args, **kwargs):
    """
    If SupplierProduct is updated/deleted then associated Product index should be updated
    and each video index associated with the Product of the SupplierProduct should
    be updated.
    """
    update_es_record_task.delay(instance.pk, "Product")
    # Update videos that have the product associated with this SupplierProduct too
    for video in instance.product.videos.all():
        update_es_record_task.delay(video.pk, "Video")


@receiver(post_save, sender=Supplier, dispatch_uid="update_supplier_in_product_index")
@receiver(post_delete, sender=Supplier, dispatch_uid="delete_supplier_in_product_index")
def update_es_product_supplier_record(sender, instance, *args, **kwargs):
    """
    If Supplier updated/deleted then all associated Products (via SupplierProduct)
    should be updated, and all video indexes associated with each Product (of
    each SupplierProduct) should be updated.
    """
    for supp_prod in instance.products.all():
        update_es_record_task.delay(supp_prod.pk, "Product")
    for video in Video.objects.filter(products__in=Product.objects.filter(supplier_info__supplier=instance)):
        update_es_record_task.delay(video.pk, "Video")


@receiver(post_save, sender=Product)
def create_marketplace_urls(sender, instance, created, model=MarketplaceURL, marketplace_model=Marketplace, **kwargs):
    if created:
        # Autogenerate any marketplace URL defaults
        for marketplace in marketplace_model.objects.exclude(search_url_template__isnull=True).exclude(search_url_template=''):
            model.objects.get_or_create(marketplace=marketplace, product=instance, link=marketplace.url_for(instance))


@receiver(post_save, sender=Follow, dispatch_uid="update_follower_count_on_create")
def update_follower_count_on_create(sender, instance, created, **kwargs):
    if created:
        User.objects.filter(pk=instance.followed.pk).update(follower_count=F('follower_count')+1)


@receiver(post_delete, sender=Follow, dispatch_uid="update_follower_count_on_delete")
def update_follower_count_on_delete(sender, instance, **kwargs):
    User.objects.filter(pk=instance.followed.pk).update(follower_count=F('follower_count')-1)


@receiver(post_save, sender=VideoCDNStatus)
def update_video_status(sender, instance, **kwargs):
    if instance.status == 'complete':
        instance.video.cdn_available = instance.timestamp
        instance.video.save()
