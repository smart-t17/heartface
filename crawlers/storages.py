import requests
import time
import dateutil.parser
from urllib.parse import urljoin
from twisted.internet import threads


class BunnyCDNFilesStore(object):

    BUNNY_CDN_ACCESS_KEY = None

    def __init__(self, uri):
        # bunnyCDN://hfproduct/images
        assert uri.startswith('bunnycdn://')
        self.HEADERS = {
            'AccessKey': self.BUNNY_CDN_ACCESS_KEY
        }
        self.storage_name, self.prefix = uri[11:].split('/', 1)
        self.storage_url = 'https://storage.bunnycdn.com/{}/{}/'.format(self.storage_name, self.prefix)

    def stat_file(self, path, info):
        def _onsuccess(response):
            if response.status_code == 200:
                checksum = response.headers.get('ETag')
                last_mod_str = response.headers.get('Last-Modified')
                last_mod_obj = dateutil.parser.parse(last_mod_str)
                last_mod_stamp = time.mktime(last_mod_obj.timetuple())
                return {'checksum': checksum, 'last_modified': last_mod_stamp}
            return {}

        return self._get_cdn_file(path).addCallback(_onsuccess)

    def _get_cdn_file(self, path):
        # NB Head doesn't return the last-modified header unfortunately
        # I contacted BunnyCDN and they said they would look into that issue
        full_storage_url = urljoin(self.storage_url, path.lstrip('/'))
        return threads.deferToThread(requests.get, full_storage_url, headers=self.HEADERS)

    def persist_file(self, path, buf, info, meta=None, headers=None):
        """Upload file to CDN storage"""
        full_storage_url = urljoin(self.storage_url, path.lstrip('/'))
        buf.seek(0)
        return threads.deferToThread(requests.put, full_storage_url,
                                     headers=self.HEADERS, data=buf.getvalue())
