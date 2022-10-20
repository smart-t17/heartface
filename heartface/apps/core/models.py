"""
(C) 2016 - Laszlo Marai <atleta@atleta.hu>
"""
import re
import os
import uuid
import logging
from datetime import date

from urllib.parse import urljoin
from urllib.parse import quote
from moviepy.editor import VideoFileClip
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import (AbstractBaseUser, PermissionsMixin)
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.http import urlquote
from django.utils.translation import ugettext_lazy as _
from djstripe.models import Charge
from django.core.mail import send_mail
from smtplib import SMTPException
from django.template.loader import render_to_string
from model_utils import Choices
from django_countries.fields import CountryField
from django_countries import countries
from country_currencies import get_by_country

from .storages import BunnyCDNStorage

logger = logging.getLogger(__name__)


@deconstructible
class UploadDir:
    def __init__(self, path):
        self.path = path

    def __call__(self, instance, filename):
        return "%s/%s%s" % (self.path, uuid.uuid4(), os.path.splitext(filename)[1])


# NOTE: dummy function needed because old migrations refer to it
def get_file_path():
    pass


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, **kwargs):
        """
        Creates and saves a User with the given email and password.
        """
        if not kwargs.get(self.model.USERNAME_FIELD, None):
            raise ValueError('The USERNAME_FIELD (%s) must be provided' % self.model.USERNAME_FIELD)

        # TODO: clean this up and make generic. Why is username normalized by the model and email by the manager?
        for k, v in kwargs.items():
            method_name = 'normalize_%s' % k
            normalizer = getattr(self, method_name, getattr(self.model, method_name, None))
            if normalizer:
                kwargs[k] = normalizer(v)

        password = kwargs.pop('password')
        user = self.model(**kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, **kwargs):
        kwargs.setdefault('is_superuser', False)
        return self._create_user(**kwargs)

    def create_superuser(self, **kwargs):
        kwargs.setdefault('is_superuser', True)
        kwargs.setdefault('is_staff', True)

        # What's the point?
        if kwargs.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if kwargs.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(**kwargs)


class User(AbstractBaseUser, PermissionsMixin):
    """User model for email based authentication. As sad as it is, much of it has been copied
    from Django's AbstractUser class
    """
    GENDER = Choices(('male', 'male', 'male'), ('female', 'female', 'female'), ('other', 'other', 'other'))

    email = models.EmailField(_('email address'), unique=True, db_index=True, validators=[validators.EmailValidator()])

    username = models.CharField(_('username'), max_length=30, unique=True,
                                help_text=_(
                                    'Required. 30 characters or fewer. Letters, numbers and '
                                    '@/./+/-/_ characters'),
                                validators=[
                                    validators.RegexValidator(re.compile('^[\w.+-]+$'),
                                                              _('Enter a valid username.'),
                                                              'invalid')
                                ],
                                error_messages={
                                    'unique': _("User with this username already exists."),
                                }, )

    country = CountryField(default=countries.by_name('United Kingdom'), blank=True)

    full_name = models.CharField(_('full name'), max_length=60)
    is_staff = models.BooleanField(_('staff status'), default=False,
                                   help_text=_(
                                       'Designates whether the user can log into this admin '
                                       'site.'))
    is_active = models.BooleanField(_('active'), default=True,
                                    help_text=_(
                                        'Designates whether this user should be treated as '
                                        'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    followers = models.ManyToManyField('User', related_name='following', through='Follow')
    disabled = models.BooleanField(_('disabled'), default=False)
    # TODO: add the generated path to the directory with the photo
    photo = models.FileField(blank=True, upload_to=UploadDir('photo'))
    description = models.TextField(blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=6, choices=GENDER)
    address = models.CharField(_('address'), max_length=255, null=True)
    phone = models.CharField(_('phone'), max_length=255, null=True)

    # De-normalized follower count
    follower_count = models.PositiveIntegerField(default=0, blank=False, null=False)

    objects = UserManager()

    @property
    def customer(self):
        return self.djstripe_customers.first()

    @property
    def age(self):
        if self.birthday:
            today = date.today()
            return relativedelta(today, self.birthday).years
        return 0

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def get_absolute_url(self):
        return "/users/%s/" % urlquote(self.username)

    def get_full_name(self):
        """
        Returns the full name.
        """
        return '%s' % self.full_name

    def get_short_name(self):
        "Returns the short name for the user."
        return ''

    def get_currency(self):
        # Stripe uses lower case currency code
        return get_by_country(self.country.code)[0].lower()

    def get_profile(self):
        return None

    def follow(self, other_user):
        return Follow.objects.create(followed=other_user, follower=self)

    def unfollow(self, other_user):
        Follow.objects.filter(followed=other_user, follower=self).delete()

    def add_follower(self, other_user):
        return other_user.follow(self)

    def remove_follower(self, other_user):
        other_user.unfollow(self)


class DefaultFollowRecommendation(models.Model):
    users = models.ManyToManyField(User, related_name='+', through='DefaultFollowRecommendationRank')
    created = models.DateTimeField(auto_now_add=True)

    def add_user(self, user, rank):
        dfrr, created = DefaultFollowRecommendationRank.objects.get_or_create(user=user,
                                                                              rec=self, rank=rank)
        return dfrr

    def __str__(self):
        users_str = ' '.join(['%s) %s.' % (user.rank, user.username)
                             for user in self.users.order_by('follow_rank_users__rank')
                             .annotate(rank=models.F('follow_rank_users__rank'))])
        return 'Created: %s. Users: %s' % (self.created.strftime('%Y-%m-%d %H:%M'), users_str)


class DefaultFollowRecommendationRank(models.Model):
    user = models.ForeignKey(User, related_name='follow_rank_users', on_delete=models.CASCADE)
    rec = models.ForeignKey(DefaultFollowRecommendation, on_delete=models.CASCADE)

    rank = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta(object):
        ordering = ('rank', )


# TODO: the below may not be needed, delete when design is finalized
# class Affiliation(models.Model):
#     affiliate_code = models.CharField(max_length=200)
#     code_generator = models.IntegerField(choices=...)
#     config = models.CharField(max_length=200)
#
#     def apply_affiliate_code(self, url):
#         """
#         This method applies the affiliate code to the provided (product) url. The affiliate code will be applied through
#         a strategy. For most cases regexes (or indeed simply appending) should work.
#
#         :param url:
#         :type url:
#         :return:
#         :rtype:
#         """
#         raise NotImplementedError('Implement me')


class Supplier(models.Model):

    SHIPPING_METHODS = Choices((0, 'yodel', 'Standard Delivery UK & NI YODEL'),
                               (1, 'uk_standard', 'UK Standard Delivery'),
                               (2, 'standard', 'Standard Shipping'),
                               (3, 'parcelforce', 'Parcelforce'))
    RTN_SHIPPING_METHODS = Choices((0, 'na', 'N/A'),
                                   (1, 'collectplus', 'CollectPlus'),
                                   (2, 'website', 'See Website'))

    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to=UploadDir('supplier_logo'))
    country = CountryField(default=countries.by_name('United Kingdom'), blank=True)
    shipping_cost = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False)
    returns_cost = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False)
    shipping_method = models.PositiveIntegerField(choices=SHIPPING_METHODS, default=1)
    returns_method = models.PositiveIntegerField(choices=RTN_SHIPPING_METHODS, default=0)
    return_period = models.CharField(max_length=20, null=True)
    shipping_time = models.CharField(max_length=20, null=True)
    privacy_policy_url = models.URLField(_("Privacy policy"), max_length=500, unique=True, null=True, blank=True)
    terms_url = models.URLField(_("T&Cs"), max_length=500, unique=True, null=True, blank=True)
    returns_url = models.URLField(_("Returns"), max_length=500, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Products will be scraped from StockX's huge database
    rather than other supplier's. Price data from other supplier's
    like Footlocker, should be associated with this Product via
    SupplierProduct model
    """

    STATUSES = Choices((0, 'scraped', 'scraped'), (1, 'queued', 'queued'), (2, 'processed', 'processed'))

    status = models.IntegerField(choices=STATUSES, default=STATUSES.scraped)
    handled_by = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    stockx_id = models.CharField(max_length=200, unique=True)
    colorway = models.CharField(max_length=200, blank=True)
    style_code = models.CharField(max_length=50, blank=True)
    release_date = models.DateField(default=None, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # We could use a flag on ProductPicture instead *and* create a partial unique index that prevents multiple primaries
    # for the same product, but it may not make life (API and admin usage) easier
    primary_picture = models.ImageField(null=True, blank=True,
                                        upload_to=UploadDir(''),
                                        storage=BunnyCDNStorage())

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return self.name


class ProductPicture(models.Model):
    product = models.ForeignKey(Product, related_name='pictures', on_delete=models.CASCADE)
    picture = models.ImageField(upload_to=UploadDir('product_images'))


class Marketplace(models.Model):
    marketplace_id = models.CharField(max_length=255, unique=True, null=False)
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to=UploadDir('marketplace_logo'))
    search_url_template = models.CharField(max_length=500, blank=True)
    affil_url_template = models.CharField(max_length=500, blank=True)

    def url_for(self, product):
        url = self.search_url_template % quote(product.name)
        if self.affil_url_template:
            url = self.affil_url_template % url
        return url

    def __str__(self):
        return self.name


class MarketplaceURL(models.Model):
    product = models.ForeignKey(Product, related_name='marketplace_urls', on_delete=models.CASCADE)
    marketplace = models.ForeignKey(Marketplace, related_name='marketplace_urls', on_delete=models.CASCADE)
    link = models.URLField(max_length=500)

    class Meta:
        unique_together = (("marketplace", "product"), )


class SupplierProduct(models.Model):
    supplier = models.ForeignKey(Supplier, related_name='products', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='supplier_info', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False, null=True, blank=True)
    link = models.URLField(max_length=500, unique=True)
    sizes = ArrayField(models.CharField(max_length=30), blank=True, default=list)
    last_scraped = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("supplier", "product"), )


class Hashtag(models.Model):
    # TODO: Should be unique?
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


def uuid4_title(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    title = uuid.uuid4()
    return 'videos/{}{}'.format(title, file_extension)


class VideoQuerySet(models.QuerySet):
    def with_liked_and_following(self, follower):
        return self.annotate(
            following_owner=models.Exists(Follow.objects.filter(followed=models.OuterRef('owner'),
                                                                follower=follower)))\
            .annotate(liked=models.Exists(Like.objects.filter(video_id=models.OuterRef('id'),
                                                              user=follower)))


class Video(models.Model):
    # TODO: clarify deletion strategy. What happens if a user deletes their account? Do we delete their videos?
    # NOTE: We allow empty titles because of the current API use strategy: Video objects can be created by uploading a
    #  file first and editing content only after.
    title = models.CharField(default='', max_length=255)
    description = models.TextField(blank=True, default='')
    view_count = models.PositiveIntegerField(default=0)
    owner = models.ForeignKey(User, related_name='videos', on_delete=models.SET_DEFAULT, default=None)
    likes = models.ManyToManyField(User, related_name='likes', blank=True, through='Like')
    products = models.ManyToManyField(Product, related_name='videos', blank=True)
    hashtags = models.ManyToManyField(Hashtag, related_name='videos', blank=True)
    videofile = models.FileField(upload_to=UploadDir('videos'))
    recommended = models.BooleanField(default=False)
    published = models.DateTimeField(default=None, null=True, blank=True)
    cdn_available = models.DateTimeField(default=None, null=True, blank=True)

    video_length = models.PositiveIntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(VideoQuerySet)()

    @property
    def videofile_cdn_url(self):
        # The CDN uses a different layout (and as we can't control it, we don't want to use the local one)
        cdn_file_name = '%s.%s' % (os.path.splitext(os.path.basename(self.videofile.name))[0], settings.CDN_VIDEO_EXTENSION)
        cdn_file_path = os.path.join(settings.CDN_VIDEO_ROOT, cdn_file_name)
        return urljoin(settings.CDN_FILES_BASE_URL, cdn_file_path[1:] if os.path.isabs(cdn_file_path) else cdn_file_path)

    @property
    def cover_picture(self):
        file_name = "%s.%s" % (
            os.path.splitext(os.path.basename(self.videofile.name))[0], settings.CDN_COVER_PICTURE_EXTENSION)
        cdn_file = os.path.join(settings.CDN_COVER_PICTURE_ROOT, file_name)
        return cdn_file[1:] if os.path.isabs(cdn_file) else cdn_file

    @property
    def cover_picture_cdn_url(self):
        return urljoin(settings.CDN_FILES_BASE_URL, self.cover_picture)

    def __str__(self):
        return self.title

    @property
    def feed_order(self):
        return self.published

    @classmethod
    def publish(cls, video, force=False):
        from .tasks import upload_video
        updated_rows = cls.objects.filter(pk=video.pk, published__isnull=True).update(published=timezone.now())
        if updated_rows:
            upload_video.delay(video.pk)
        elif force:
            logger.warn('Forcing upload_video task on already published video')
            upload_video.delay(video.pk)

    # possible exceptions: corrupted video, file missing
    # Note: Video files removed from server after 24hrs and pushed to CDN.
    def video_duration(self):
        """
        This method is called when a new video instance is created and
        it updates the video_length of the instance.
        """
        try:
            video = VideoFileClip(str(self.videofile.file))
            return int(video.duration)
        except FileNotFoundError as e:
            logger.error('Video file is missing: %s' % e)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Set the video_length when creating
        if self._state.adding is True:
            self.video_length = self.video_duration()

        # Extract hashtags from title/description
        hashtag_re = re.compile("(?:^|\s)[＃#]{1}(\w+)", re.UNICODE)

        # find all tags in title and description
        tag_names = hashtag_re.findall(self.title) + hashtag_re.findall(self.description)

        # make list contains only unique tags
        tag_names = list(set(tag_names))

        # find all tags in 1 SQL query
        tags = list(Hashtag.objects.filter(name__in=tag_names))
        if len(tags) != len(tag_names):
            existing_tags = [t.name for t in tags]
            # not all tags existing - do slow operation to find and create
            tags.extend([
                Hashtag.objects.get_or_create(name=tag)[0]
                for tag in tag_names
                if tag not in existing_tags
            ])

        # Add tags to M2M
        self.hashtags.add(*tags)

        # Remove stale tags
        self.hashtags.remove(*self.hashtags.exclude(name__in=tag_names))


class VideoCDNStatus(models.Model):
    video = models.ForeignKey('Video', on_delete=models.CASCADE, related_name='cdn_status')
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    description = models.TextField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['video']),
        ]

    def __str__(self):
        return 'VideoCDN status for %s' % self.filename


class GlacierFile(models.Model):
    video = models.OneToOneField('Video', on_delete=models.CASCADE)
    size = models.BigIntegerField()
    archive_id = models.CharField(max_length=255)
    created = models.DateTimeField(null=True, auto_now_add=True)


class Like(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    @property
    def feed_order(self):
        return self.created

    class Meta:
        unique_together = ('video', 'user')


class Follow(models.Model):
    # The user being *followed*
    followed = models.ForeignKey(User, related_name='followed', on_delete=models.CASCADE)
    # The user *following*
    follower = models.ForeignKey(User, related_name='follower', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    @property
    def feed_order(self):
        return self.created

    class Meta:
        unique_together = ('follower', 'followed')


class View(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    created = models.DateTimeField(auto_now_add=True)


class ReportedVideo(models.Model):
    reporting_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    reviewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created', )


class Order(models.Model):
    # TODO: the statuses below are just an example. They need to be defined based on the actual business/ordering process
    # TODO: consider switching to an FSA field that doesn't allow arbitrary transitions
    STATUSES = Choices((0, 'new', 'new'), (1, 'processing', 'processing'), (2, 'ordered', 'ordered'),
                       (3, 'confirmed', 'confirmed'))

    # Actions to take depending on status
    EMAIL_CONF = {
        STATUSES.new: {
            'plain_template': 'email/core/new_order.txt',
            'html_template': 'email/core/new_order.html',
            'subj': 'New order',
            'email_customer': True,
            'recipients': [settings.DEFAULT_ADMIN_EMAIL, ]
        },
        STATUSES.processing: {
            'plain_template': 'email/core/processing_order.txt',
            'html_template': 'email/core/processing_order.html',
            'subj': 'Order processing',
            'email_customer': False,
            'recipients': [settings.DEFAULT_ADMIN_EMAIL, ]
        },
        STATUSES.ordered: {
            'plain_template': 'email/core/success_order.txt',
            'html_template': 'email/core/success_order.html',
            'subj': 'Order successful',
            'email_customer': True,
            'recipients': [settings.DEFAULT_ADMIN_EMAIL, ]
        },
        STATUSES.confirmed: {
            'plain_template': 'email/core/complete_order.txt',
            'html_template': 'email/core/complete_order.html',
            'subj': 'Order completed',
            'email_customer': False,
            'recipients': [settings.DEFAULT_ADMIN_EMAIL, ]
        },
    }

    status = models.IntegerField(choices=STATUSES, default=STATUSES.new)

    # TODO: review/define deletion strategy
    customer = models.ForeignKey(User, related_name='orders', on_delete=models.CASCADE)
    product = models.ForeignKey(SupplierProduct, related_name='orders', on_delete=models.CASCADE)
    video = models.ForeignKey(Video, related_name='orders', on_delete=models.CASCADE)
    size = models.CharField(max_length=30)
    created = models.DateTimeField(auto_now_add=True)
    retailer_order_id = models.CharField(max_length=255, null=True, blank=True)
    charge = models.OneToOneField(Charge, on_delete=models.CASCADE, blank=True, null=True)
    handled_by = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    commission_earned = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False)

    def __init__(self, *args, **kwargs):
        super(Order, self).__init__(*args, **kwargs)
        # So we can track changes to status on save
        self.__original_status = self.status

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        """
        Override save method so that on status changing we can
        send appropriate emails

        TESTING: Can view emails under tests/sent_email during dev (filebackend)
        """
        # TODO: For now send emails from main thread, later move to celery

        # Context for email templates
        ctx = {'retailer_order_id': self.retailer_order_id,
               'product': self.product,
               'customer': self.customer}

        is_new = self.pk is None
        logger.debug('Is this creation: %s' % is_new)
        if self.status != self.__original_status or is_new:
            try:
                email_conf = self.EMAIL_CONF[self.status]
                logger.debug('Send email with subj %s' % email_conf['subj'])
                recipients = email_conf['recipients'].copy()
                if email_conf['email_customer']:
                    recipients.append(self.customer.email)
                send_mail(
                    email_conf['subj'],
                    render_to_string(email_conf['plain_template'], ctx),
                    settings.DEFAULT_ORDERS_FROM_EMAIL,
                    recipients,
                    html_message=render_to_string(email_conf['html_template'], ctx),
                )
            except SMTPException as e:
                logger.error('Could not send order email: %s' % e)

        super(Order, self).save(force_insert, force_update, *args, **kwargs)
        self.__original_status = self.status


class Comment(models.Model):
    # TODO: discuss deletion strategy. We may want to retain comments from deleted users and show it as such on the UI
    #   (or we may have to delete them)
    author = models.ForeignKey(User, related_name='comments', on_delete=models.CASCADE)
    video = models.ForeignKey(Video, related_name='comments', on_delete=models.CASCADE)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    @property
    def feed_order(self):
        return self.created


class Notification(models.Model):
    """
    NOTE: This is a demo model to allow integrating the API
    """
    TYPES = Choices((0, 'new_follower', 'New Follower'),
                    (1, 'new_like', 'New Like'), (2, 'new_comment', 'New Comment'))

    recipient = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    # Who did the like/comment/follow:
    sender = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE)
    # Video needed for new_like, new_comment
    video = models.ForeignKey(Video, related_name='notifications', on_delete=models.CASCADE, blank=True, null=True)
    message = models.TextField()
    type = models.IntegerField(choices=TYPES)
    read = models.BooleanField(default=False)
    # notification_id = models.CharField(max_length=50, null=True) #in one signal
    notification_id = models.UUIDField(unique=True)  # in one signal
    timestamp = models.DateTimeField(auto_now_add=True)


# NOTE: FeaturedVideo can probably be removed
class FeaturedVideo(models.Model):
    """
    This model is for selecting the (system wide) featured video. The actual featured video will always be the last
    (newest, highest ID) one.
    """
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='featured_video')


class Collection(models.Model):
    """
    A (manually) edited collection of videos to present on the discovery screen of the app.
    """
    name = models.CharField(max_length=200)
    description = models.TextField()
    cover_photo = models.FileField(upload_to=UploadDir('collection_covers'))
    videos = models.ManyToManyField(Video, related_name='+')

    def __str__(self):
        return self.name


class HomepageContent(models.Model):
    """
    A (manually) edited collection of videos/profiles to display on the webapp homepage
    """
    created = models.DateTimeField(auto_now_add=True)
    videos = models.ManyToManyField(Video, related_name='+')
    profiles = models.ManyToManyField(User, related_name='+')

    def __str__(self):
        return str(self.created)

    class Meta:
        ordering = ('-created', )


class EditorialRecommendation(models.Model):
    """
    An editorial recommendation consists of collcetions and featured videos and make up the manually edited content
    on the discovery screen of the app. The actual editorial content will always be the last (newest, highest ID) one.
    """
    featured_video = models.ForeignKey(Video, related_name='+', on_delete=models.CASCADE)
    collections = models.ManyToManyField(Collection, related_name='+')


class Device(models.Model):
    TYPES = Choices((0, 'ios', 'ios'), (1, 'android', 'android'), )

    # player_id = models.CharField(max_length=50, null=True)
    player_id = models.UUIDField(unique=True)
    type = models.IntegerField(choices=TYPES)
    user = models.ForeignKey(User, related_name='devices', on_delete=models.CASCADE)

    def __repr__(self):
        return "<Device: %s (type: %s)>" % (self.player_id, self.get_type_display())


class Trending(models.Model):
    # TODO: maybe pick a better name. This should really show (and be!) the time used in the actual calculations
    created = models.DateTimeField(auto_now_add=True)
    profiles = models.ManyToManyField(User, through='TrendingProfile')
    hashtags = models.ManyToManyField(Hashtag, through='TrendingHashtag')


class TrendingProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trending = models.ForeignKey(Trending, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False)

    class Meta:
        ordering = ('-score', )
        unique_together = ('user', 'trending')


class TrendingHashtag(models.Model):
    hashtag = models.ForeignKey(Hashtag, on_delete=models.CASCADE)
    trending = models.ForeignKey(Trending, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=9, decimal_places=2, default=0, unique=False)

    class Meta:
        ordering = ('-score', )
        unique_together = ('hashtag', 'trending')


class TaskRunManager(models.Manager):
    def last_run_at(self, task_label):
        return TaskRun.objects.filter(task_label=task_label).order_by('-started_at').\
            values_list('started_at', flat=True).first()


class TaskRun(models.Model):
    objects = TaskRunManager()

    # Keep track of celery tasks
    task_label = models.CharField(_('task label'), max_length=30)
    started_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(default=None, null=True, blank=True)

    class Meta:
        ordering = ('-started_at', )


class Proxy(models.Model):
    ip_address = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=443)
    # Optional creds
    username = models.CharField(_("Username"), max_length=30, blank=True)
    password = models.CharField(_("Password"), max_length=30, blank=True)
    fail_count = models.IntegerField(default=0, db_index=True)

    class Meta:
        verbose_name_plural = 'Proxies'
        unique_together = (("ip_address", "port"), )

    def __str__(self):
        return '{}:{}'.format(self.ip_address, self.port)


class AdminAnalytic(Video):
    """ Analytics reporting - Video model as proxy """

    class Meta:
        proxy = True


class MissingProduct(models.Model):
    """ Product request from User """

    name = models.CharField(max_length=200)
    color = models.CharField(max_length=200)
    style_code = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to=UploadDir('missing_products'), blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    handled_by = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING, related_name='handled_by')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '{}'.format(self.name)
