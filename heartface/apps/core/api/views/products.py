#!/usr/bin/env python
# coding=utf-8
import json
import logging

from django.utils import timezone
from django.conf import settings

from rest_framework import mixins
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder
from rest_framework import status

from heartface.apps.core.api.serializers.discovery import VideoSerializer
from heartface.apps.core.api.serializers.products import ProductSerializer, OrderSerializer, OrderAdminSerializer, \
    SupplierProductSerializer, SupplierSerializer, MissingProductSerializer
from heartface.apps.core.models import Product, Supplier, SupplierProduct, Order, MissingProduct
from heartface.apps.core.permissions import IsAuthenticatedAndEnabled
from rest_framework.exceptions import NotFound

from heartface.libs.scrape import update_supplierprod, ScrapingException

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Methods supported: GET, POST
    retrieve:
        Return a Product instance.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/products/:id/
        URL parameters:
        - id*:  A unique integer value identifying this product.
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Product instance with pk=id

    list:
        Return all Products.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/products/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Product instances
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)

    def get_queryset(self):
        qs = Product.objects.all().prefetch_related('pictures', 'supplier_info', 'supplier_info__supplier')
        # return Product.objects.all().prefetch_related('pictures')
        return qs

    @detail_route(methods=['POST'], permission_classes=[IsAuthenticatedAndEnabled])
    def supplierproducts(self, request, pk=None):
        """
        Scrape on-demand the prices/sizes for all supplierproducts
        linked to this Product (scraper uses SupplierProduct.link, and admins
        create these SupplierProducts linked against a Product that was scraped
        from StockX
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/products/:id/supplierproducts/
        URL parameters:
        - id*:  A unique integer value identifying this product.
        Request Body:
        - name: CharField of max_length 200.
        - stockx_id: CharField of max_length 200, Should be unique value from stockx.
        - colorway: CharField of max_length 200.
        - style_code: CharField of max_length 50.
        - release_date: Datetime field.
        - description: Text field
        - supplier_info: List of suppliers.
        - marketplace_urls: List of marketplace.
        Expected status code: HTTP_201_CREATED
        Expected Response: List of serialized Supplier product instances linked to a product.

        """
        product = self.get_object()
        for supplierprod in product.supplier_info.all().\
                filter(last_scraped__lte=(timezone.now() - settings.LAST_SCRAPED_TIMESTAMP_WINDOW)):
            try:
                update_supplierprod(supplierprod)
            except ScrapingException as scr_exc:
                raise NotFound(detail=str(scr_exc))
        serializer = SupplierProductSerializer(product.supplier_info.all(),
                                               many=True, context={'request': request})
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @detail_route(methods=['GET'])
    def videos(self, request, pk=None):
        """
        Get all videos tagged to a product
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/products/:id/videos/
        URL parameters:
        - id*:  A unique integer value identifying this product.
        Expected status code: HTTP_200_OK
        Expected Response: List of serialized Video instances tagged to a product
        """
        product = self.get_object()

        qs = product.videos.all()

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = VideoSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        return Response(VideoSerializer(qs, many=True))


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Methods supported: GET
    retrieve:
        Return a Supplier instance with pk=id.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/supplier/:id/
        URL parameters:
        - id*: A unique integer value identifying this supplier.
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Supplier instance with pk=id

    list:
        Return all Suppliers.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/supplier/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Supplier instances
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)


class SupplierProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Methods supported: GET
    retrieve:
        Return a Supplier product instance with pk=id.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/supplier-products/:id/
        URL parameters:
        - id*: A unique integer value identifying this supplier product.
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Supplier product instance with pk=id

    list:
        Return all Supplier products.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/supplier-products/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Supplier product instances
    """
    queryset = SupplierProduct.objects.all()
    serializer_class = SupplierProductSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)


class OrdersViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.UpdateModelMixin, mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    """
    Methods supported: GET, POST, PUT, PATCH
    retrieve:
        Return a Order instance with pk=id.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/orders/:id/
        URL parameters:
        - id*: A unique integer value identifying this order.
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Order instance with pk=id

    list:
        Return all Orders.
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/orders/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Order instances

    create:
        Creates a new Order.
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/orders/
        Request Body:
        - product: Product instance.
        - status: Choice field
        - video: Video instance.
        - customer: User instance.
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized Order instance with its related Product, Video and Customer data


    partial_update:
        Update one or more fields on an existing Order.
        permissions: authenticated and enabled
        methods accepted: PATCH
        endpoint format: /api/v1/orders/:id/
        URL parameters:
        - id*: A unique integer value identifying this order.
        Request Body:
        - product: Product instance
        - status: Choice field
        - video: Video instance
        - customer: User instance
        Expected status code: HTTP_200_OK
        Expected Response: An Updated serialized Order instance with pk=id

    update:
        Update an Order.
        permissions: authenticated and enabled
        methods accepted: PUT
        endpoint format: /api/v1/orders/:id/
        URL parameters:
        - id*: A unique integer value identifying this order.
        Request Body:
        - product: Product instance
        - status: Choice field
        - video: Video instance
        - customer: User instance
        Expected status code: HTTP_200_OK
        Expected Response: An Updated serialized Order instance with pk=id
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)

    def get_permissions(self):
        """
        - Only staff can update/delete any orders.
        - Authenticated and enabled users can create Orders in their own name
          (see serializer create method for enforcement).
         - Authenticated and enabled users can list/retrieve orders in their own name
         . Staff list/retrive all orders (see get_queryset for enforcement)
        """
        if self.action in ['create', 'retrieve', 'list']:
            # And these will be limited to own name
            permission_classes = self.permission_classes
        else:
            # Update/destroy
            permission_classes = [permissions.IsAdminUser, ]
        return [permission() for permission in permission_classes]

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        logger.debug('Create order request: %s || response: %s', request.body, json.dumps(response.data, cls=JSONEncoder))
        return response

    def get_serializer(self, *args, **kwargs):
        if self.request.user.is_staff:
            serializer_class = OrderAdminSerializer
        else:
            serializer_class = OrderSerializer

        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(customer__id=self.request.user.pk)

    # def perform_create(self, serializer):
    #     order = serializer.save()
    #     stripe_token = self.request.data.get('stripe_token', None)
    #     if stripe_token is not None:
    #         try:
    #             charge = stripe.Charge.create(
    #                 amount=order.product.price,
    #                 currency=self.request.user.get_currency(),
    #                 description=order.product.product.description,
    #                 source=stripe_token,
    #             )
    #             order.charge = charge
    #             order.save()
    #         except stripe.error.InvalidRequestError:
    #             return Response({'detail': 'Invalid Stripe token'}, status=status.HTTP_400_BAD_REQUEST)


class MissingProductViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Methods supported: POST
    create:
        Creates a new Missing Product instance.
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/missing-products/
        Request Body:
        - name*: CharField of max_length 200
        - color*: CharField of max_length 200
        - style_code: CharField of max_length 50
        - notes: Text field
        - photo: image url
        - video*: Video instance.
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized Missing Product instance with its related Video, User instances
    """

    queryset = MissingProduct.objects.all()
    serializer_class = MissingProductSerializer
    permission_classes = (IsAuthenticatedAndEnabled, )
