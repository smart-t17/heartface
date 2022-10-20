#!/usr/bin/env python
# coding=utf-8
import math
import random

import djstripe
import factory
from django.contrib.auth.hashers import make_password

from heartface.apps.core.models import *

from decimal import Decimal

DEFAULT_PASSWORD = 'password'


class OverridableAutoNowAddMixin(object):
    @classmethod
    def _create(cls, target_class, *args, **kwargs):
        """
        Avoid auto_now_add overriding the created param
        """
        timestamp = kwargs.pop(cls._override_timestamp, None)
        obj = super()._create(target_class, *args, **kwargs)
        if timestamp is not None:
            setattr(obj, cls._override_timestamp, timestamp)
            obj.save()
        return obj


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = User

    @classmethod
    def _setup_next_sequence(cls):
        try:
            # Ensure if pre-existing data (such as when used in shell or management cmd
            # the sequence respects it)
            email = User.objects.filter(email__regex="user(\d+)@whatever.com"
                                        ).order_by('-date_joined').first().email
            return int(re.findall(r'\d+', email)[0]) + 1
        except (User.DoesNotExist, AttributeError):
            return 1

    @classmethod
    def _create(cls, *args, **kwargs):
        # TODO: implement more robust checking whether password is encrypted or not
        if 'password' in kwargs and not kwargs['password'].startswith('bcrypt_sha'):
            kwargs['password'] = make_password(kwargs['password'])

        # return super(UserFactory, cls)._create(*args, **kwargs)
        return super()._create(*args, **kwargs)

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of groups were passed in, use them
            for group in extracted:
                self.groups.add(group)

    email = factory.Sequence(lambda n: 'user%d@whatever.com' % n)
    username = factory.Faker('user_name')
    password = make_password(DEFAULT_PASSWORD)
    full_name = factory.Faker('name')


class SupplierFactory(factory.DjangoModelFactory):
    class Meta:
        model = Supplier

    name = factory.Sequence(lambda n: 'Company %s' % n)
    logo = factory.Faker('file_path', category='image')
    shipping_cost = factory.LazyFunction(lambda: Decimal('%.2f' % (random.randrange(500, 3000)/100)))


class ProductFactory(factory.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker('sentence')
    description = factory.Faker('text')
    primary_picture = factory.Faker('file_path', category='image')
    stockx_id = factory.Faker('uuid4')


class ProductPictureFactory(factory.DjangoModelFactory):
    class Meta:
        model = ProductPicture

    product = factory.SubFactory(ProductFactory)
    picture = factory.Faker('file_path', category='image')


ACCEPTABLE_SIZES_NUM = list(range(1, 50))
ACCEPTABLE_SIZES_LAB1 = ['S', 'M', 'L', 'XL']
ACCEPTABLE_SIZES_LAB2 = ['small', 'medium', 'large']
ACCEPTABLE_SIZES_YRS = ['0-3yrs', '3-5yrs', '5-8yrs', '8+']


class SupplierProductFactory(factory.DjangoModelFactory):
    class Meta:
        model = SupplierProduct

    supplier = factory.SubFactory(SupplierFactory)
    product = factory.SubFactory(ProductFactory)
    link = factory.Sequence(lambda s: 'http%s://%s%s%s.%s' % (
        random.choice(['', 's']), random.choice(['', 'www.']), factory.Faker('word').generate({}), s,
        factory.Faker('tld').generate({})
    ))
    price = factory.LazyFunction(lambda: Decimal('%.2f' % (random.randrange(2000, 10000)/100)))

    # Placeholder data see _create
    sizes = factory.LazyFunction(lambda: [1, 2, 3, 4, 5])

    @classmethod
    def _create(cls, target_class, *args, **kwargs):
        """
        Avoid auto_now_add overriding the created param
        """

        randsizerange = kwargs.pop('randsizerange', (0, 5))
        obj = super()._create(target_class, *args, **kwargs)

        def _sizes(randsizerange):
            # TODO: Size can be anything from S, M, L, XL to small, medium,..to 0-3yrs,
            # 3-5yrs. For now leave it free. Later consider admin managed list of
            # acceptable sizes
            size_list = random.choice([ACCEPTABLE_SIZES_NUM, ACCEPTABLE_SIZES_LAB1,
                                       ACCEPTABLE_SIZES_LAB2, ACCEPTABLE_SIZES_YRS])
            return list(set([random.choice(size_list) for i in range(random.randint(randsizerange[0],
                                                                                    randsizerange[1]))]))

        obj.sizes = _sizes(randsizerange)
        obj.save()
        return obj


class VideoFactory(OverridableAutoNowAddMixin, factory.DjangoModelFactory):
    class Meta:
        model = Video

    title = factory.Faker('sentence')
    owner = factory.SubFactory(UserFactory)
    videofile = factory.django.FileField(filename='video.mp4')
    cdn_available = factory.LazyAttribute(lambda o: timezone.now())
    published = factory.LazyAttribute(lambda o: timezone.now())
    _override_timestamp = 'published'


class GlacierFileFactory(factory.DjangoModelFactory):
    class Meta:
        model = GlacierFile


class HashtagFactory(factory.DjangoModelFactory):
    class Meta:
        model = Hashtag

    name = factory.Faker('word')


class CollectionFactory(factory.DjangoModelFactory):
    class Meta:
        model = Collection

    name = factory.Faker('word')
    description = factory.Faker('sentence')
    cover_photo = '/picture/some_jpg'


class EditorialRecommendationFactory(factory.DjangoModelFactory):
    class Meta:
        model = EditorialRecommendation


class CommentFactory(OverridableAutoNowAddMixin, factory.DjangoModelFactory):
    text = factory.Faker('sentence')
    author = factory.SubFactory(UserFactory)
    video = factory.SubFactory(VideoFactory)
    _override_timestamp = 'created'

    class Meta:
        model = Comment


class OrderFactory(factory.DjangoModelFactory):
    class Meta:
        model = Order

    def _get_video(self):
        video = VideoFactory()
        self.product.product.videos.add(video)
        return video

    customer = factory.SubFactory(UserFactory)
    product = factory.SubFactory(SupplierProductFactory, randsizerange=(1, 10))
    status = Order.STATUSES.new
    size = factory.LazyAttribute(lambda self: random.choice(self.product.sizes))
    video = factory.LazyAttribute(_get_video)


class LikeFactory(OverridableAutoNowAddMixin, factory.DjangoModelFactory):
    class Meta:
        model = Like

    user = factory.SubFactory(UserFactory)
    video = factory.SubFactory(VideoFactory)
    _override_timestamp = 'created'


class ViewFactory(OverridableAutoNowAddMixin, factory.DjangoModelFactory):
    class Meta:
        model = View
    user = factory.SubFactory(UserFactory)
    video = factory.SubFactory(VideoFactory)
    created = factory.LazyAttribute(lambda o: timezone.now())
    _override_timestamp = 'created'


class FollowFactory(OverridableAutoNowAddMixin, factory.DjangoModelFactory):
    class Meta:
        model = Follow

    followed = factory.SubFactory(UserFactory)
    follower = factory.SubFactory(UserFactory)
    created = factory.LazyAttribute(lambda o: timezone.now())
    _override_timestamp = 'created'


class DeviceFactory(factory.DjangoModelFactory):
    class Meta:
        model = Device
    type = Device.TYPES.ios
    player_id = factory.Faker('uuid4')


# djstripe model factories

class ChargeFactory(factory.DjangoModelFactory):
    class Meta:
        model = djstripe.models.Charge

    amount = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    amount_refunded = Decimal(0.0)
    paid = True
    stripe_id = factory.Faker('password', length=18, special_chars=False, digits=True, upper_case=True, lower_case=True)


class DefaultFollowRecommendationFactory(factory.DjangoModelFactory):
    created = factory.LazyAttribute(lambda o: timezone.now())

    class Meta:
        model = DefaultFollowRecommendation


class HomepageContentFactory(factory.DjangoModelFactory):
    created = factory.LazyAttribute(lambda o: timezone.now())
    class Meta:
        model = HomepageContent
