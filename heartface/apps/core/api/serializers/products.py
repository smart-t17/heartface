#!/usr/bin/env python
# coding=utf-8
import stripe
import logging

from django.templatetags.static import static
from django.conf import settings

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from heartface.apps.core.search_indexes import ProductIndex
from .accounts import CustomElasticModelSerializer
from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
from heartface.apps.core.models import Product, Order, Supplier, SupplierProduct, Video, MarketplaceURL, \
    Marketplace, MissingProduct

from urllib.parse import urljoin

from django_countries.serializers import CountryFieldMixin


from .fields import HumanChoiceField

logger = logging.getLogger(__name__)


class SupplierSerializer(CountryFieldMixin, serializers.ModelSerializer):
    # supplier_logo = serializers.ReadOnlyField(source='get_supplier_logo')
    shipping_method = HumanChoiceField(choices=Supplier.SHIPPING_METHODS)
    returns_method = HumanChoiceField(choices=Supplier.RTN_SHIPPING_METHODS)

    class Meta:
        model = Supplier
        fields = [
            'name',
            # 'affiliate_code',
            'logo',
            'shipping_cost',
            'returns_cost',
            'shipping_method',
            'returns_method',
            'return_period',
            'shipping_time',
            'privacy_policy_url',
            'terms_url',
            'returns_url',
            'country',
        ]


class ProductOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'stockx_id',
            'colorway',
            'style_code',
            'release_date',
            'name',
            'description',
            'primary_picture',
            'id',
            'url'
        ]


class VideoOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = [
            'id',
            'url',
            'title',
            'description',
        ]

    def run_validation(self, data=empty):
        return data if self.root and not data == empty else super().run_validation(data)


class SupplierProductSerializer(serializers.HyperlinkedModelSerializer):
    supplier = SupplierSerializer()
    logo = serializers.URLField(source='supplier.logo', read_only=True)
    product = ProductOrderSerializer()

    class Meta:
        model = SupplierProduct

        fields = [
            'id',
            'supplier',
            'product',
            'price',
            'link',
            'sizes',
            'logo',
        ]

    def run_validation(self, data=empty):
        return data if self.root and not data == empty else super().run_validation(data)


class MarketplaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketplace
        fields = [
            'id',
            'name',
            'logo',
        ]


class MarketplaceURLSerializer(serializers.ModelSerializer):
    marketplace = MarketplaceSerializer()

    class Meta:
        model = MarketplaceURL
        fields = [
            'id',
            'link',
            'marketplace',
        ]


class ProductSerializer(CustomElasticModelSerializer):
    supplier_info = SupplierProductSerializer(many=True)
    pictures = serializers.SerializerMethodField()
    marketplace_urls = MarketplaceURLSerializer(many=True)
    primary_picture = serializers.SerializerMethodField()

    class Meta:
        es_model = ProductIndex
        model = Product
        fields = [
            'name',
            'stockx_id',
            'colorway',
            'style_code',
            'release_date',
            'description',
            'primary_picture',
            'supplier_info',
            'id',
            'url',
            'pictures',
            'marketplace_urls',
            'created',
            'updated',
        ]
        read_only_fields = ['created', 'updated', ]

    def get_pictures(self, obj):
        request = self.context.get('request', None)
        return [request.build_absolute_uri(pp.picture.url) for pp in obj.pictures.all()]

    def get_primary_picture(self, obj):
        """
        If not primary_picture, use a placeholder
        """
        if hasattr(obj, 'primary_picture') and obj.primary_picture:
            primary_picture_url = urljoin(urljoin(settings.BUNNY_CDN_PULL_ZONE, settings.BUNNY_CDN_PATH_PREFIX)
                                          , obj.primary_picture.name)
        else:
            primary_picture_url = static(settings.PRODUCT_PLACEHOLDER_IMAGE)
        return self.context.get('request').build_absolute_uri(primary_picture_url)


class OrderSerializer(serializers.HyperlinkedModelSerializer):
    customer = PublicUserSerializer(read_only=True)
    product = SupplierProductSerializer()
    video = VideoOrderSerializer()
    stripe_token = serializers.CharField(required=False, write_only=True)
    status = HumanChoiceField(choices=Order.STATUSES, required=False)

    class Meta:
        model = Order
        fields = [
            'created',
            'customer',
            'product',
            'video',
            'status',
            'size',
            'stripe_token',
            'id',
            'url'
        ]

        read_only_fields = ['created', 'status', ]

    def validate_product(self, value):
        try:
            return SupplierProduct.objects.get(pk=value)
        except SupplierProduct.DoesNotExist:
            raise ValidationError('SupplierProduct with id %s does not exist' % value)

    def validate(self, attrs):
        # Verify that the video contains the product from order
        if 'video' in attrs and 'product' in attrs:
            try:
                attrs['video'] = Video.objects.get(pk=attrs['video'], products__supplier_info=attrs['product'])
            except Video.DoesNotExist:
                raise ValidationError('Video with id %s does not exist or is not associated with the product having '
                                      'supplierproduct %s.' % (attrs['video'], attrs['product'].id))

        if 'product' in attrs and attrs.get('size', None) not in attrs['product'].sizes:
            raise ValidationError('Product not available in requested size "%s". [Available sizes: %s]' %
                                  (attrs['size'], attrs['product'].sizes))

        return attrs

    def validate_stripe_token(self, value):
        # NOTE: this could be done (a bit more efficiently, but less elegantly) in the create method
        if not self.context['request'].user.customer.can_charge() and not value:
            raise ValidationError('User doesn\'t have a payment method assigned yet, stripe card token is required.')

        return value

    def create(self, validated_data):
        stripe_token = validated_data.pop('stripe_token')
        product = validated_data.pop('product')
        video = validated_data.pop('video')
        user = self.context['request'].user

        try:
            if not user.customer.can_charge():
                logger.debug('No valid payment method for customer exists, using token to add a new card [user=%s]', user)
                user.customer.add_card(source=stripe_token)
                logger.debug('Added new card to customer [user=%s]', user)

            logger.debug('Charing customer [user=%s, product=%s]', user, product)

            charge = user.customer.charge(
                amount=product.price + product.supplier.shipping_cost,
                currency=user.get_currency(),
                description='%s [via Heartface]' % product.product.name
            )

            logger.debug('Successfully charged customer, creating Order [user=%s, product=%s]', user, product)

            return Order.objects.create(charge=charge, product=product, video=video, customer=user,
                                        status=Order.STATUSES.new, **validated_data)
        except stripe.error.InvalidRequestError as e:
            logger.info('Charging credit card failed. Reason: "%s". [user=%s, product=%s, video=%s]', str(e), user,
                        product, video)
            raise ValidationError('Charging credit card failed [Stripe error: %s]' % str(e))


class OrderAdminSerializer(serializers.HyperlinkedModelSerializer):

    customer = PublicUserSerializer()
    product = SupplierProductSerializer()
    video = VideoOrderSerializer()
    status = HumanChoiceField(choices=Order.STATUSES, required=False)

    class Meta:
        model = Order
        fields = [
            'created',
            'customer',
            'product',
            'video',
            'status',
            'id',
            'url'
        ]


class VideoProductTagRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class MissingProductVideoSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField()

    class Meta:
        model = Video
        fields = [
            'id',
        ]


class MissingProductSerializer(serializers.ModelSerializer):

    user = PublicUserSerializer(read_only=True)
    video = MissingProductVideoSerializer()

    class Meta:
        model = MissingProduct
        fields = [
            'id',
            'name',
            'color',
            'style_code',
            'notes',
            'photo',
            'user',
            'video'
        ]

    def validate_video(self, value):
        try:
            return Video.objects.get(pk=value['id'])
        except Video.DoesNotExist:
            raise ValidationError('Video with id %s does not exist' % value['id'])

    def create(self, validated_data):
        """
        Accepts request body like
        {"name": "test prod 1", "color": "red", "video": 1}
        """
        video = validated_data.pop("video")
        user = self.context['request'].user
        return MissingProduct.objects.create(video=video, user=user, **validated_data)
