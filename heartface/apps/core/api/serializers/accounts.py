from django.conf import settings
from django.core import signing
from django.templatetags.static import static
from django.utils.functional import lazy

from rest_framework import serializers
from allauth.account import app_settings
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from rest_framework_elasticsearch.es_serializer import ElasticModelSerializer
from heartface.apps.core.search_indexes import UserIndex

from django_countries.serializers import CountryFieldMixin

from .fields import HumanChoiceField

from heartface.apps.core.models import User


class CustomElasticModelSerializer(ElasticModelSerializer):

    def es_save(self, using=None, index=None, validate=True, save_to_db=True, **kwargs):
        super().save(using=using, index=index, validate=validate, **kwargs)

    def save(self, using=None, index=None, validate=True, **kwargs):
        return serializers.ModelSerializer.save(self, **kwargs)

    def delete(self, using=None, index=None, **kwargs):
        return serializers.ModelSerializer.delete(self, **kwargs)

    def es_delete(self, using=None, index=None, data=None, **kwargs):
        if data:
            # For celery ES delete tasks we don't have an instance to init
            # serializer with (could override es_instance but maybe that
            # could be used adversely for saving too)
            model = self.get_es_model()
            data['meta'] = dict(id=data['id'])
            model(**data).delete(using=using, index=index, **kwargs)
        else:
            super().delete(using=using, index=index, **kwargs)


class UserSerializer(CountryFieldMixin, serializers.HyperlinkedModelSerializer):
    email_verified = serializers.SerializerMethodField()
    can_charge = serializers.ReadOnlyField(source='customer.can_charge')
    gender = HumanChoiceField(choices=User.GENDER)

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'username',
            'email',
            'age',
            'gender',
            'photo',
            'description',
            'email_verified',
            'can_charge',
            'disabled',
            'country',
            # Can't add url without fixing rest_auth.registartion.views.RegisterView.get_response_data to pass in the
            #   request in the context to TokenSerializer.
            # 'url'
        ]

        read_only_fields = [
            'username'
        ]

    def get_email_verified(self, instance):
        return instance.emailaddress_set.filter(email=instance.email, verified=True).exists()
        # try:
        #     return instance.emailaddress_set.get(email=instance.email).verified
        # except EmailAddress.DoesNotExist:
        #     return False


# NOTE: we could probably do this with a simple Serializer instead
class GenericIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = ['id']
        read_only_fields = ['id']

    @staticmethod
    def for_model(m):
        class IDSerializer(GenericIDSerializer):
            class Meta(GenericIDSerializer.Meta):
                model = m

        return IDSerializer


class PublicUserSerializer(CountryFieldMixin, CustomElasticModelSerializer):

    # Used to store if User is following owner of Video when this Serializer
    # used in within VideoSerializer (Non-required so won't be displayed unless present)
    # is_followed = serializers.BooleanField(read_only=True, required=False)
    following = serializers.BooleanField(read_only=True, source='is_followed', required=False)
    photo = serializers.SerializerMethodField()

    def to_representation(self, obj):
        rep = super().to_representation(obj)
        if obj.disabled:
            rep.update(self.Meta.disabled_defaults)
        return rep

    def get_photo(self, user):
        if hasattr(user, 'photo') and user.photo:
            photo_url = user.photo.url
        else:
            photo_url = static(settings.DEFAULT_USER_AVATAR)
        return self.context.get('request').build_absolute_uri(photo_url)

    class Meta:
        # TODO: fix the photo
        disabled_defaults = {'username': 'disabled_user',
                             'full_name': 'Disabled User',
                             'email': 'disabled@disabled.com',
                             'age': None,
                             'address': '',
                             'description': '',
                             'phone': '',
                             # The lazy lambda thing below is needed so that we avoid errors on importing this module
                             # while running collectstatic
                             'photo': lazy(static, str)(settings.DISABLED_USER_AVATAR)}
        model = User
        es_model = UserIndex
        fields = [
            'id',
            'full_name',
            'photo',
            'description',
            'username',
            'url',
            'following',
            'follower_count',
            'country',
        ]

        read_only_fields = [
            'username',
            'follower_count'
        ]
