import json
import logging

import requests
import uuid
from django.conf import settings
from rest_framework import status
from rest_framework.utils.encoders import JSONEncoder as RestJSONEncoder

from heartface.apps.core.models import User, Notification, Video

logger = logging.getLogger(__name__)


NOTIFICATION_TEMPLATES = {
    Notification.TYPES.new_follower: '{username} is now following you!',
    Notification.TYPES.new_like: '{username} liked your video',
    Notification.TYPES.new_comment: '{username} commented on your video',
}


def send(notification_type, current_user, to_user, video_id=None):
    from heartface.apps.core.tasks import send_notification
    send_notification.delay(notification_type, current_user.username, to_user.pk, video_id=video_id)


class OneSignalException(Exception):
    pass


def send_one_signal(include_player_ids, content):
    header = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': 'Basic {}'.format(settings.ONESIGNAL_REST_API_KEY)
    }

    payload = {
        'app_id': settings.ONESIGNAL_APP_ID,
        'include_player_ids': include_player_ids,
        'contents': {'en': content}
    }
    try:
        response = requests.post('https://onesignal.com/api/v1/notifications',
                                 headers=header, data=json.dumps(payload, cls=RestJSONEncoder))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise OneSignalException({'message': 'Failed connection to onesignal: %r' % e})

    try:
        response_data = response.json()
    except ValueError:
        raise OneSignalException({'message': 'Failed to parse JSON from %r' % response.content})

    if not (299 >= response.status_code >= status.HTTP_200_OK) or 'error' in response_data:
        message = (
            'Failure to send push notification to player_ids: %s, http_code %s, message: %s' %
            (include_player_ids, response.status_code, response.content)
        )
        raise OneSignalException({'message': message, 'response_data': response_data})

    return response_data['id']


def _send_sync_impl(notification_type, current_user_username, user_id, video_id=None):
    user = User.objects.get(pk=user_id)
    sender = User.objects.get(username=current_user_username)
    video = Video.objects.get(pk=video_id) if video_id else None

    notification_id = None
    include_player_ids = list(user.devices.values_list('player_id', flat=True))
    content = NOTIFICATION_TEMPLATES[notification_type].format(username=current_user_username)

    # If user has registered devices use onesignal
    if include_player_ids:
        try:
            notification_id = send_one_signal(include_player_ids, content)
        except OneSignalException as e:
            detail = e.args[0]
            logger.error(detail['message'])
            if 'invalid_player_ids' in detail.get('response_data', {}).get('errors', {}):
                user.devices.filter(player_id__in=detail.get('response_data')['errors']['invalid_player_ids']).delete()
            return False

    # If not player IDs we don't make the push, but always create a
    # Notification. Else we only create the Notification if push was successful
    Notification.objects.create(
        type=notification_type,
        recipient=user,
        sender=sender,
        video=video,
        notification_id=notification_id or uuid.uuid4(),
        message=content
    )

    # Notification has been sent to user
    return True
