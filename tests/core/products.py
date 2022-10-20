#!/usr/bin/env python
# coding=utf-8
import random
import logging
from urllib.parse import urlparse

import djstripe
from unittest.mock import patch, MagicMock, ANY
from django.conf import settings
from nose.plugins.attrib import attr
from nose_parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase

from heartface.apps.core.models import ProductPicture, Video, Order, MissingProduct
from tests.factories import UserFactory, OrderFactory, ProductFactory, SupplierProductFactory, \
    ProductPictureFactory, VideoFactory, ChargeFactory

import sure


logger = logging.getLogger(__name__)


class OrderTestCase(APITestCase):

    # db value -> literal identifiers
    # {0: 'new', 1: 'processing', 2: 'ordered', 3: 'confirmed'}
    inv_map = {v: k for k, v in Order.STATUSES._identifier_map.items()}

    def test_order_response(self):
        customer = UserFactory()
        product = ProductFactory()
        supplier_product = SupplierProductFactory(product=product, randsizerange=(1, 10))

        # product = ProductFactory(supplier=supplier)

        order = OrderFactory(customer=customer, product=supplier_product)
        order.save()

        self.client.force_login(customer)

        response = self.client.get('/api/v1/orders/')

        results = response.data.get('results')[0]

        response.status_code.should.equal(status.HTTP_200_OK)
        results.get('product').get('product').get('name').should.equal(product.name)
        results.get('product').get('link').should.equal(supplier_product.link)
        results.get('customer').get('id').should.equal(customer.id)

    def test_access_own_orders(self):
        OrderFactory.create_batch(5, customer=UserFactory())
        customer = UserFactory()
        order_ids = [o.pk for o in OrderFactory.create_batch(7, customer=customer)]

        self.client.force_login(customer)

        response = self.client.get('/api/v1/orders/')

        results = response.data.get('results')
        results.should.have.length_of(len(order_ids))
        for res in results:
            res.get('customer').get('id').should.equal(customer.id)
            res.get('id').should.be.within(order_ids)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_cannot_access_other_orders(self):
        user = UserFactory()
        other_user = UserFactory()
        user.pk.shouldnt.equal(other_user.pk)

        user_orders = OrderFactory.create_batch(5, customer=user)
        other_user_orders = OrderFactory.create_batch(7, customer=other_user)

        self.client.force_login(user)

        response = self.client.get('/api/v1/orders/')

        response.status_code.should.equal(status.HTTP_200_OK)
        results = response.data.get('results')
        results.should.have.length_of(len(user_orders))
        for res in results:
            res['customer']['id'].should.equal(user.id)
            res['id'].should.be.within([order.pk for order in user_orders])

        # Check for the other user
        self.client.force_login(other_user)

        response = self.client.get('/api/v1/orders/')

        response.status_code.should.equal(status.HTTP_200_OK)
        results = response.data.get('results')
        results.should.have.length_of(len(other_user_orders))
        for res in results:
            res['customer']['id'].should.equal(other_user.id)
            res['id'].should.be.within([order.pk for order in other_user_orders])

    def test_non_admin_cant_update_order(self):
        customer = UserFactory()
        order = OrderFactory(customer=customer, status=Order.STATUSES.new)

        self.client.force_login(customer)

        response = self.client.patch('/api/v1/orders/%s/' % order.id, {'status': self.inv_map[Order.STATUSES.processing], 'created': 0})

        # NOTE: we may want to respond with an error instead of ignoring read-only fields
        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)
        order.refresh_from_db()
        order.status.should.equal(Order.STATUSES.new)

    def test_non_admin_cant_delete_order(self):
        customer = UserFactory()
        order = OrderFactory(customer=customer, status=Order.STATUSES.new)

        self.client.force_login(customer)

        response = self.client.delete('/api/v1/orders/%s/' % order.id)

        # NOTE: we may want to respond with an error instead of ignoring read-only fields
        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)
        Order.objects.filter(pk=order.pk).exists().should.be(True)

    def test_update_order_status_admin(self):
        staff_user = UserFactory(is_staff=True)
        order = OrderFactory(customer=staff_user, status=Order.STATUSES.new)

        self.client.force_login(staff_user)
        response = self.client.patch('/api/v1/orders/%s/' % order.pk, {'status': self.inv_map[Order.STATUSES.processing]})
        response.status_code.should.equal(status.HTTP_200_OK)
        response.data['status'].should.equal(self.inv_map[Order.STATUSES.processing])

    @patch('heartface.apps.core.models.send_mail')
    def test_update_order_status_email(self, mock):
        """
        Ensure emails are sent when order status changes
        """
        staff_user = UserFactory(is_staff=True)
        # product = ProductFactory()
        # supplier = SupplierFactory()
        # SupplierProductFactory(supplier=supplier, product=product)

        # Creating Order initially with new should email admin and customer
        order = OrderFactory(customer=staff_user, status=Order.STATUSES.new)
        mock.call_args[0][3].should.equal([settings.DEFAULT_ADMIN_EMAIL, order.customer.email])

        # Should be admin only
        order.status = Order.STATUSES.processing
        order.save()
        mock.call_args[0][3].should.equal([settings.DEFAULT_ADMIN_EMAIL, ])

        # Should be admin and customer
        order.status = Order.STATUSES.ordered
        order.save()
        mock.call_args[0][3].should.equal([settings.DEFAULT_ADMIN_EMAIL, order.customer.email])

        # Should be admin only
        order.status = Order.STATUSES.confirmed
        order.save()
        mock.call_args[0][3].should.equal([settings.DEFAULT_ADMIN_EMAIL, ])

        # Should be 4 emails in total
        mock.call_count.should.equal(4)


class ProductTestCase(APITestCase):
    def test_product_list_format(self):
        """
        A simple test case to test if the product (more or less) looks good. Smoke test, really.
        """
        products = [ProductFactory() for i in range(10)]

        for p in products:
            [ProductPictureFactory(product=p) for i in range(5)]
            [SupplierProductFactory(product=p) for i in range(5)]

        self.client.force_login(UserFactory())
        response = self.client.get('/api/v1/products/')

        response.status_code.should.equal(status.HTTP_200_OK)
        # print(json.dumps(response.data, indent=4))

        # We don't test everything just the latest, important parts
        data = response.data['results']

        for product in data:
            for url in product['pictures']:
                file_name = urlparse(url).path[len(settings.MEDIA_URL):]
                ProductPicture.objects.filter(product_id=product['id'], picture__endswith=file_name).exists().should.be.true


# This is put at the end as for some reason running the test_place_order once screws up everything and
#  make all user creation throw an error (probably due to a problem/bug with mocking or unittest.mock)
@attr('broken')
class WOrderTestCase(APITestCase):

    @parameterized.expand([
        (True,),
        (False,)
    ])
    def test_place_order(self, has_card):
        """
        Test placing an order.
        """
        stripe_token = "fake_stripe_token_98jhkjhe98"
        item_to_buy = SupplierProductFactory(randsizerange=(1, 5))
        size = random.choice(item_to_buy.sizes)
        logger.debug('Size is %s and has type %s' % (size, type(size)))
        video = VideoFactory()
        video.products.add(item_to_buy.product)
        user = UserFactory()
        charge = ChargeFactory(customer=user.customer)

        self.client.force_login(user)

        # Can't patch earlier, as that would prevent creating the needed Customer instances (though it would be nice
        #  if we could do away with that as a requirement for testing e.g. by mocking stripe.Charge.* calls)
        # These are all the solutions that could work, but don't:
        # with patch('heartface.apps.core.models.Customer') as mock:
        # with patch('djstripe.models.Customer', autospec=True) as mock:
        # with patch.object(djstripe.models.Customer, '__new__', new=Mock) as mock:
        # with patch.object(djstripe.models, 'Customer', new=Mock) as mock:

        with patch.object(djstripe.models.Customer, '__new__') as mock:

            mock_customer = MagicMock()
            mock.return_value = mock_customer
            mock_customer.can_charge.return_value = has_card
            mock_customer.charge.return_value = charge

            response = self.client.post('/api/v1/orders/', data={
                'stripe_token': stripe_token,
                'product': item_to_buy.pk,
                'size': size,
                'video': video.pk
            })

            mock_customer.charge.assert_called_once_with(amount=item_to_buy.price + item_to_buy.supplier.shipping_cost,
                                                         currency=user.get_currency(), description=ANY)

            if has_card:
                mock_customer.add_card.assert_not_called()
            else:
                mock_customer.add_card.assert_called_once_with(source=stripe_token)

            response.status_code.should.equal(status.HTTP_201_CREATED)

            # Test with non-existent video
            non_existent_video_id = 2339983721113  # Some big random number
            Video.objects.filter(pk=non_existent_video_id).exists().should.be(False)  # Precondition, just in case

            response = self.client.post('/api/v1/orders/', data={
                'stripe_token': stripe_token,
                'product': item_to_buy.pk,
                'size': size,
                'video': non_existent_video_id
            })

            response.status_code.should.equal(status.HTTP_400_BAD_REQUEST)
            response.data.should.have.key('non_field_errors')
            response.data.should.have.length_of(1)
            response.data['non_field_errors'][0].should.contain('not associated with the product')

            # Test when video doesn't have the product
            video.products.remove(item_to_buy.product)

            response = self.client.post('/api/v1/orders/', data={
                'stripe_token': stripe_token,
                'product': item_to_buy.pk,
                'size': size,
                'video': video.pk
            })

            response.status_code.should.equal(status.HTTP_400_BAD_REQUEST)
            response.data.should.have.key('non_field_errors')
            response.data.should.have.length_of(1)
            response.data['non_field_errors'][0].should.contain('not associated with the product ')


class MissingProductTestCase(APITestCase):

    def authenticated_user_can_create_missing_product(self):
        """
        An authenticated user should be able to create missing product
        for existing video
        """
        user = UserFactory()
        video = VideoFactory()

        self.client.force_login(user)
        response = self.client.post('/api/v1/missing-products/',
                                    data={'name': 'test product 1',
                                          'color': 'red',
                                          'video': {'id': video.id}})
        response.status_code.should.equal(status.HTTP_201_CREATED)
        MissingProduct.objects.count().should.equal(1)
        missing_product = MissingProduct.objects.first()
        # Missing product should belong to request.user
        missing_product.user.pk.should.equal(user.pk)
        missing_product.handled_by.should.be(None)

    def unauthenticated_user_cannot_create_missing_product(self):
        """
        An unauthenticated user should not be able to make missing product req
        """
        video = VideoFactory()

        response = self.client.post('/api/v1/missing-products/',
                                    data={'name': 'test product 1',
                                          'color': 'red',
                                          'video': {'id': video.id}})
        response.status_code.should.equal(status.HTTP_401_UNAUTHORIZED)
        MissingProduct.objects.count().should.equal(0)

    def validation_error_if_video_doesnt_exist(self):
        """
        If video doesnt exist should be validation error
        """
        video_pk = 123459876
        Video.objects.filter(pk=video_pk).exists().should.be(False)
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.post('/api/v1/missing-products/',
                                    data={'name': 'test product 1',
                                          'color': 'red',
                                          'video': {'id': video_pk}})
        response.status_code.should.equal(status.HTTP_400_BAD_REQUEST)
        MissingProduct.objects.count().should.equal(0)
        response.json()['video'][0].should.equal('Video with id {} does not exist'.format(video_pk))
