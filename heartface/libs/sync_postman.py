from requests import get, put
from requests.exceptions import HTTPError
import json
import logging

from django.conf import settings
from django.urls import reverse


logger = logging.getLogger(__name__)


class SyncPostman:
    """
    class to sync swagger doc in postman collection
    """

    def __init__(self, collection_name='Heartface API'):
        """
        initialise basic postman json
        postman schema https://schema.getpostman.com/json/collection/v2.1.0/collection.json implemented
        """
        self.swagger_data = {}
        self.postman_json = {
            'collection': {
                'info': {
                    'name': 'Heartface API',
                    'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
                },
                'item': []
            }
        }
        self.headers = {
            'X-Api-Key': settings.POSTMAN_API_KEY
        }
        self.collection_name = collection_name
        self.collection_id = ''

    def get_collection_id(self):
        """
        get collection uid with name collection_name.
        :return: None
        """

        try:
            collection_json = get('https://api.getpostman.com/collections/', headers=self.headers)
            collection_json.raise_for_status()
            collection_json = collection_json.json()
        except (HttpError, TypeError) as htp:
            logger.error(htp)
            return

        for collection in collection_json.get('collections', []):
            if collection['name'] == self.collection_name:
                self.collection_id = collection['uid']

    def get_swagger_data(self):
        """
        get data from swagger endpoint
        hardcoded to https://dev.heartface.io/docs/?format=openapi
        :return: None
        """

        swagger_url = ('https://dev.heartface.io{}?format=openapi'.format(reverse('swagger_docs')))
        try:
            swagger_request = get(swagger_url)
            swagger_request.raise_for_status()
            self.swagger_data = swagger_request.json()
        except (HTTPError, TypeError) as htp:
            logger.error(htp)

    def clean_data(self):
        """
        TODO: restructure collection to folders
              support passing params
        clean swagger data to postman structure
        refer
            https://schema.getpostman.com/json/collection/v2.1.0/docs/index.html
            https://docs.api.getpostman.com/?_ga=2.251005828.368877656.1539339660-2034941182.1539339660

        sample swagger json:
        ...
        ...
        paths": {

        "/api/v1/collections/{id}/": {
            "get": {
                "tags": [
                    "api"
                ],
                "operationId": "v1_collections_read",
                "parameters": [
                    {
                        "description": "A unique integer value identifying this collection.",
                        "type": "integer",
                        "name": "id",
                        "in": "path",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": ""
                    }
                }
            }
        },
        "/api/v1/discovery/": {
            "get": {
                "tags": [
                    "api"
                ],
                "operationId": "v1_discovery_list",
                "parameters": [ ],
                "responses": {
                    "200": {
                        "description": ""
                    }
                }
            }
        },
        ...
        ...

        :return: None
        """
        
        if self.swagger_data:
            self.swagger_data['host'] = '{{url}}'  # enable using environment variables in postman
            api_list = []
            for path, methods in self.swagger_data['paths'].items():
                # /api/v1/collections/{id}/ to be converted to ['api', 'v1', 'collections', ':id', '']
                path_info = path[1:].strip().replace('{', ':').replace('}', '').split('/')
                body_dict = {
                    'body':
                        {
                            'formdata': [],
                            'mode': 'formdata'
                        }
                }

                for method, attributes in methods.items():
                    data_store = {'name': path}
                    data_dict = {
                        'url': {
                            'host': '{{url}}',
                            'path': path_info,
                            'protocol': 'https',
                        }
                    }

                    data_dict['response'] = attributes.get('responses', {})
                    data_dict['name'] = attributes['tags'][0] \
                        if attributes['tags'][0] else ''
                    data_dict['method'] = method.upper()
                    # get parameters
                    for parameter in attributes.get('parameters', []):
                        inner_dict = dict()
                        inner_dict['key'] = parameter['name']
                        inner_dict['type'] = 'text'
                        inner_dict['value'] = '{{%s}}' % parameter['name']
                        body_dict['body']['formdata'].append(inner_dict)
                    data_dict.update(body_dict)
                    data_store['request'] = data_dict
                    api_list.append(data_store)
            self.postman_json['collection']['item'] = api_list

    def sync_postman(self):
        """
        updates swagger data in postman.
        :return:
        """

        self.clean_data()
        if not self.postman_json['collection']['item']:
            return
        try:
            update_request = put('https://api.getpostman.com/collections/{}'.format(self.collection_id),
                                 data=json.dumps(self.postman_json), headers=self.headers)
            update_request.raise_for_status()
        except HTTPError as e:
            logger.debug('Postman update failed with status code {} and reason {}'
                         .format(update_request.status_code, update_request.reason))

    def driver(self):
        """
        triggers fetch from swagger and updates postman
        :return:
        """
        self.get_collection_id()
        if not self.collection_id:
            logger.debug('collection id matching collection name {} not found'.format(self.collection_name))
            return

        self.get_swagger_data()

        if not self.swagger_data:
            logger.debug('swagger data not obtained')
            return
        self.sync_postman()
