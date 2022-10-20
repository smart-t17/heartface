from allauth.account.forms import ResetPasswordForm
from django.http import Http404
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from rest_framework.authtoken.models import Token

from heartface.apps.core.api.serializers.accounts import UserSerializer
from heartface.apps.core.models import User
from .adapters import DuplicateSocialEmailException, NoSocialEmailException, \
    MissingUsernameException, UsernameTakenException

from rest_auth.registration.serializers import RegisterSerializer, SocialLoginSerializer
from rest_auth.serializers import PasswordResetSerializer



class TokenSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Token
        fields = ['key', 'user']


class CustomRegisterSerializer(RegisterSerializer):
    full_name = serializers.CharField(max_length=30, required=True)

    def get_cleaned_data(self):
        return {
            'full_name': self.validated_data.get('full_name', ''),
            'username': self.validated_data.get('username', ''),
            'password1': self.validated_data.get('password1', ''),
            'email': self.validated_data.get('email', '')
        }


class PasswordSerializer(PasswordResetSerializer):
    """
    See https://github.com/Tivix/django-rest-auth/issues/135
    rest-auth reset password endpoint uses django.contrib.auth.forms.ResetPasswordForm
    (which would require implementing the URL for password_reset_confirm)
    whereas allauth uses allauth.account.forms.ResetPasswordForm, which
    uses the URL account_reset_password_from_key)
    """
    password_reset_form_class = ResetPasswordForm


class CustomSocialLoginSerializer(SocialLoginSerializer):
    username = serializers.CharField(max_length=30, required=False)

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except NoSocialEmailException:
            raise serializers.ValidationError(_('We cannot proceed as there is no email associated with your social account.'))
        except DuplicateSocialEmailException:
            raise serializers.ValidationError(_('We already have that email, please login with it.'))
        except UsernameTakenException:
            raise serializers.ValidationError(_('Username already in use.'))
        except MissingUsernameException:
            raise Http404()


class CustomUserDetailsSerializer(serializers.ModelSerializer):
    """
    User model w/o password
    """
    class Meta:
        model = User
        fields = ('pk', 'username', 'email', 'full_name')
        read_only_fields = ('email', )
