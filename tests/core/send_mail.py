#!/usr/bin/env python
# coding=utf-8
from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase
import sendgrid
from sendgrid.helpers.mail import *
import sure


class SendEmailTestCase(APITestCase):
    def test_send_email(self):
        sg = sendgrid.SendGridAPIClient(apikey=settings.SENDGRID_API_KEY)
        from_email = Email("test@example.com")
        to_email = Email("levon2111@gmail.com")
        subject = "Sending with SendGrid is Fun"
        content = Content("text/plain", "and easy to do anywhere, even with Python")

        mail = Mail(from_email, subject, to_email, content)

        response = sg.client.mail.send.post(request_body=mail.get())
        response.status_code.should.equal(status.HTTP_202_ACCEPTED)
