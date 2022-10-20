import sendgrid
import json
from sendgrid.helpers.mail import *
from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models import Count
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


def sendgrid_send_notification(to, template_id, dynamic_template_data, unsubscribe_group_id):
    sg = sendgrid.SendGridAPIClient(apikey=settings.SENDGRID_API_KEY)
    # Check not unsubscribed
    data = {"recipient_emails": [to]}
    response = sg.client.asm.groups._(unsubscribe_group_id).suppressions.search.post(request_body=data)
    try:
        json_response_body = json.loads(response.body)
    except TypeError:
        json_response_body = json.loads(response.body.decode('utf-8'))
    if to not in json_response_body:
        mail = Mail()
        mail.from_email = Email(settings.SENDGRID_NOTIFICATIONS_EMAIL)
        mail.template_id = template_id
        personalization = Personalization()
        personalization.add_to(Email(to))
        personalization.dynamic_template_data = dynamic_template_data
        mail.add_personalization(personalization)
        return sg.client.mail.send.post(request_body=mail.get())


def _dedup(model_class, unique_fields, order_by_field):
    """
    De-deuplicate Django models for which several `unique_fields` are the same.
    Useful in migrations when existing duplicate data and a unique_together is to be
    applied. The last field (according to `order_by_field` ordering will be retained
    of the duplicates)

    NB The values and annotate together means group by unique_fields, getting the count
    where they are the same (duplicates). Then filter to keep only those with cnt>1 (duplicates)

    Args:
        model_class: The Django model to be 'de-duplicated'
        unique_fields: a list of fields that should be unique together
        order_by_field: we will delete all but the last of the duplicates when they
                        ordered according to this field
    """
    duplicates = (model_class.objects.values(*unique_fields)
                                .order_by()
                                .annotate(count_id=Count('id'))
                                .filter(count_id__gt=1))

    for duplicate in duplicates:
        objs_to_del = model_class.objects.filter(
            **{x: duplicate[x] for x in unique_fields}).order_by(order_by_field)[:duplicate['count_id']-1]
        for obj in objs_to_del:
            obj.delete()


def _mock_site_request():
    factory = APIRequestFactory()
    return factory.get('/', SERVER_NAME=Site.objects.get_current().domain, secure=settings.ELASTIC_STORE_URLS_AS_HTTPS)


def _req_ctx_with_request():
    """
    Hyperlinked serializers need request in context
    """
    return {'request': Request(_mock_site_request())}
