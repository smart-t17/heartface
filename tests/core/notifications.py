#!/usr/bin/env python
# coding=utf-8

import uuid
import json
from django.db import transaction
from django.conf import settings
from mock import patch, Mock
from sendgrid.helpers.mail import Email, Mail, Personalization
from nose_parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from heartface.apps.core.models import Device, Notification
from heartface.libs import notifications
from tests.factories import UserFactory, DeviceFactory, VideoFactory
import sure


class NotificationsAPITestCase(APITestCase):
    @parameterized.expand([
        ([(uuid.uuid4(), 'ios')],),
        ([(uuid.uuid4(), 'ios'), (uuid.uuid4(), 'ios'), (uuid.uuid4(), 'android')],),
    ])
    def test_register_device_for_user(self, device_params):
        user = UserFactory()

        self.client.force_login(user)

        for player_id, dtype in device_params:
            response = self.client.post('/api/v1/notifications/register/', data={'player_id': player_id, 'type': dtype})
            print(response.content)
            response.status_code.should.equal(status.HTTP_201_CREATED)

        user.devices.count().should.equal(len(device_params))

        for d, (player_id, dtype) in zip(user.devices.all(), device_params):
            d.player_id.should.equal(player_id)
            d.type.should.equal(getattr(Device.TYPES, dtype))

    @parameterized.expand([
        (Notification.TYPES.new_follower, UserFactory, UserFactory, lambda: None),
        (Notification.TYPES.new_like, UserFactory, UserFactory, VideoFactory),
        (Notification.TYPES.new_comment, UserFactory, UserFactory, VideoFactory)
    ])
    @patch('heartface.libs.notifications.requests')
    def test_send_notification_no_device_success(self, notification_type, param1_factory, param2_factory, param3_factory, mock):
        mock.post.return_value.status_code = status.HTTP_400_BAD_REQUEST
        mock.post.return_value.json.side_effect = ValueError()

        # With no device, no request to onesignal should have been made
        mock.post.assert_not_called()
        current_user, to_user, video = param1_factory(), param2_factory(), param3_factory()
        notifications._send_sync_impl(notification_type, current_user.username, to_user.pk, video and video.id).should.be.true
        Notification.objects.count().should.equal(1)
        n = Notification.objects.get()
        n.type.should.equal(notification_type)

    @parameterized.expand([
        (Notification.TYPES.new_follower, lambda: None),
        (Notification.TYPES.new_like, VideoFactory),
        (Notification.TYPES.new_comment, VideoFactory)
    ])
    @patch('heartface.libs.notifications.requests')
    def test_send_notification_with_device_success(self, notification_type, param_factory, mock):
        mock.post.return_value.status_code = status.HTTP_201_CREATED
        mock.post.return_value.json.return_value = {'id': str(uuid.uuid4())}

        # NOTE: this is not really a unit test, we should mock out all the external components
        user1 = UserFactory()
        user2 = UserFactory()
        DeviceFactory(user=user2, player_id=str(uuid.uuid4()))

        video = param_factory()
        notifications._send_sync_impl(notification_type, user1.username, user2.pk, video and video.id).should.be.true
        Notification.objects.count().should.equal(1)

        mock.post.assert_called_once()
        mock.post.call_args[0][0].should.equal('https://onesignal.com/api/v1/notifications')

    @patch('heartface.libs.notifications.requests')
    def test_send_notification_failure(self, mock):
        mock.post.return_value.status_code = status.HTTP_400_BAD_REQUEST
        mock.post.return_value.json.side_effect = ValueError()

        # NOTE: this is not really a unit test, we should mock out all the external components
        user1 = UserFactory()
        user2 = UserFactory()
        DeviceFactory(user=user2, player_id=str(uuid.uuid4()))

        notifications._send_sync_impl(Notification.TYPES.new_follower, user1.username, user2.pk, None).should.be.false
        Notification.objects.count().should.equal(0)

        mock.post.assert_called_once()
        mock.post.call_args[0][0].should.equal('https://onesignal.com/api/v1/notifications')

    def test_list_notifications(self):
        # This is mostly a smoke test that covers a previous bug where listing the notifications was broken
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.get('/api/v1/notifications/')
        response.status_code.should.equal(status.HTTP_200_OK)


class NotificationsTransactionTestCase(APITransactionTestCase):
    def test_register_same_device_twice(self):
        """
        Trying to register the same device twice shouldn't create an error. We need to do manual transaction handling
        as the server code will create an SQL error (and for that the transaction has to be closed.
        """

        user = UserFactory()
        device = DeviceFactory(user=user)

        with transaction.atomic():
            self.client.force_login(user)
            response = self.client.post('/api/v1/notifications/register/', data={'player_id': device.player_id, 'type': Device.TYPES._display_map[device.type]})
            # response = self.client.post('/api/v1/notifications/register/', data={'player_id': uuid.uuid4(), 'type': device.type})
            # print(response.content)
            response.status_code.should.equal(status.HTTP_200_OK)

        user.devices.all().count().should.equal(1)


class SendGridNotificationsTestCase(APITestCase):
    """
    Test sendgrid notification emails on like/comment/follow
    """
    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_follow_when_unsubscribed(self, SendGridAPIClient):
        """
        When user email is on the unsub list, no notification email should be sent
        """
        user = UserFactory()
        follower_user = UserFactory()

        m_sg = SendGridAPIClient()

        # Case 1: user email is in ubsubscribe group
        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps([user.email])
        m_sg.client.asm.groups._(settings.SENDGRID_FOLLOW_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(follower_user)
        response = self.client.post('/api/v1/users/{}/followers/'.format(user.id))
        response.status_code.should.equal(status.HTTP_201_CREATED)
        m_sg.client.mail.send.post.assert_not_called()

    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_follow_when_subscribed(self, SendGridAPIClient):
        """
        When user email is not on the unsub list, notification email should be sent
        """
        user = UserFactory()
        follower_user = UserFactory()

        m_sg = SendGridAPIClient()

        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps(['someother@email.com'])
        m_sg.client.asm.groups._(settings.SENDGRID_FOLLOW_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(follower_user)
        response = self.client.post('/api/v1/users/{}/followers/'.format(user.id))
        response.status_code.should.equal(status.HTTP_201_CREATED)
        # Expected request_body
        mail = Mail()
        mail.from_email = Email(settings.SENDGRID_NOTIFICATIONS_EMAIL)
        mail.template_id = settings.SENDGRID_FOLLOW_TEMPLATE_ID
        p = Personalization()
        p.add_to(Email(user.email))
        p.dynamic_template_data = {"subject": "User {} has followed you".format(follower_user.full_name),
                                   "photo": 'http://testserver/backend/static/img/LogoBig.png',
                                   "followed_name": user.full_name,
                                   "follower_name": follower_user.full_name}
        mail.add_personalization(p)
        m_sg.client.mail.send.post.assert_called_once_with(request_body=mail.get())

    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_like_when_unsubscribed(self, SendGridAPIClient):
        """
        When user email is on the unsub list, no notification email should be sent
        """
        user = UserFactory()
        video = VideoFactory(owner=user)
        liker_user = UserFactory()

        m_sg = SendGridAPIClient()

        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps([user.email])
        m_sg.client.asm.groups._(settings.SENDGRID_VIDEO_LIKE_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(liker_user)
        response = self.client.post('/api/v1/videos/{}/like/'.format(video.id))
        response.status_code.should.equal(status.HTTP_201_CREATED)
        m_sg.client.mail.send.post.assert_not_called()

    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_like_when_subscribed(self, SendGridAPIClient):
        """
        When user email is not on the unsub list, notification email should be sent
        """
        user = UserFactory()
        video = VideoFactory(owner=user)
        liker_user = UserFactory()

        m_sg = SendGridAPIClient()

        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps(['someother@email.com'])
        m_sg.client.asm.groups._(settings.SENDGRID_VIDEO_LIKE_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(liker_user)
        response = self.client.post('/api/v1/videos/{}/like/'.format(video.id))
        response.status_code.should.equal(status.HTTP_201_CREATED)
        # Expected request_body
        mail = Mail()
        mail.from_email = Email(settings.SENDGRID_NOTIFICATIONS_EMAIL)
        mail.template_id = settings.SENDGRID_VIDEO_LIKES_TEMPLATE_ID
        p = Personalization()
        p.add_to(Email(user.email))
        p.dynamic_template_data = {"subject": "User {} has liked your video {}".format(liker_user.full_name, video.title),
                                   "photo": 'http://testserver/backend/static/img/LogoBig.png',
                                   "video_cover": video.cover_picture_cdn_url,
                                   "liked_name": video.owner.full_name,
                                   "liker_name": liker_user.full_name,
                                   "video_title": video.title}
        mail.add_personalization(p)
        m_sg.client.mail.send.post.assert_called_once_with(request_body=mail.get())

    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_comment_when_unsubscribed(self, SendGridAPIClient):
        """
        When user email is on the unsub list, no notification email should be sent
        """
        user = UserFactory()
        video = VideoFactory(owner=user)
        liker_user = UserFactory()

        m_sg = SendGridAPIClient()

        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps([user.email])
        m_sg.client.asm.groups._(settings.SENDGRID_VIDEO_COMMENT_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(liker_user)
        response = self.client.post('/api/v1/videos/{}/like/'.format(video.id))
        response.status_code.should.equal(status.HTTP_201_CREATED)
        m_sg.client.mail.send.post.assert_not_called()

    @patch('heartface.libs.utils.sendgrid.SendGridAPIClient')
    def test_send_notification_comment_when_subscribed(self, SendGridAPIClient):
        """
        When user email is not on the unsub list, notification email should be sent
        """
        user = UserFactory()
        video = VideoFactory(owner=user)
        commentor_user = UserFactory()

        m_sg = SendGridAPIClient()

        mock_unsub_response = Mock()
        mock_unsub_response.body = json.dumps(['someother@email.com'])
        m_sg.client.asm.groups._(settings.SENDGRID_VIDEO_COMMENT_UNSUB_GROUP_ID).suppressions.search.post.return_value = mock_unsub_response

        # Check m_sg.client.mail.send.post was not called at all
        self.client.force_login(commentor_user)
        response = self.client.post('/api/v1/videos/{}/comments/'.format(video.id),
                                    data={'text': 'test comment'})
        response.status_code.should.equal(status.HTTP_201_CREATED)
        # Expected request_body
        mail = Mail()
        mail.from_email = Email(settings.SENDGRID_NOTIFICATIONS_EMAIL)
        mail.template_id = settings.SENDGRID_VIDEO_COMMENT_TEMPLATE_ID
        p = Personalization()
        p.add_to(Email(user.email))
        p.dynamic_template_data = {"subject": "User {} has commented on your video {}".format(commentor_user.full_name, video.title),
                                   "photo": 'http://testserver/backend/static/img/LogoBig.png',
                                   "video_cover": video.cover_picture_cdn_url,
                                   "comment_text": "test comment",
                                   "commented_name": video.owner.full_name,
                                   "commentor_name": commentor_user.full_name,
                                   "video_title": video.title}
        mail.add_personalization(p)
        m_sg.client.mail.send.post.assert_called_once_with(request_body=mail.get())
