import requests

from django.core.files.storage import Storage
from django.core.files.base import File
from django.utils.deconstruct import deconstructible
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone as tz

from tempfile import SpooledTemporaryFile

from storages.utils import setting, clean_name


from urllib.parse import urljoin

import logging
logger = logging.getLogger(__name__)


class BunnyCDNStorageException(Exception):
    pass


@deconstructible
class BunnyCDNStorage(Storage):
    """Bunny Storage class for Django pluggable storage system."""

    max_memory_size = setting('BUNNY_CDN_MAX_MEMORY-SIZE', 2*1024*1024)

    def __init__(self, base_url=None, storage_name=None, path_prefix=None, access_key=None):
        """
        base_url: https://storage.bunnycdn.com
        storage_name: hfproductstaging
        path_prefix: images
        access_key: the storage access key
        """

        self.path_prefix = setting('BUNNY_CDN_PATH_PREFIX') or path_prefix

        access_key = setting('BUNNY_CDN_ACCESS_KEY') or access_key
        if access_key is None:
            raise ImproperlyConfigured("You must set an access_key at "
                                       "instanciation or at "
                                       "settings.BUNNY_CDN_ACCESS_KEY")

        storage_name = setting('BUNNY_CDN_STORAGE_NAME') or storage_name
        if storage_name is None:
            raise ImproperlyConfigured("You must set a storage_name at "
                                       "instanciation or at "
                                       "settings.BUNNY_CDN_STORAGE_NAME")

        base_url = setting('BUNNY_CDN_BASE_URL') or base_url
        if base_url is None:
            raise ImproperlyConfigured("You must set a base_url at "
                                       "instanciation or at "
                                       "settings.BUNNY_CDN_BASE_URL")

        self.pull_zone = setting('BUNNY_CDN_PULL_ZONE')
        if self.pull_zone is None:
            raise ImproperlyConfigured("You must set a pull_zone at "
                                       "at settings.BUNNY_CDN_PULL_ZONE")

        self.headers = {'AccessKey': access_key}
        self.storage_url = '{}/{}/'.format(base_url, storage_name)
        if self.path_prefix:
            self.storage_url += self.path_prefix
            self.pull_zone += self.path_prefix
            if not self.storage_url.endswith('/'):
                self.storage_url += '/'
            if not self.pull_zone.endswith('/'):
                self.pull_zone += '/'

    def _normalize_name(self, name):
        return name.lstrip('/')

    def size(self, name):
        full_storage_url = urljoin(self.storage_url, name)
        try:
            r = requests.get(full_storage_url, headers=self.headers)
            r.raise_for_status()
            return r.headers['Content-Length']
        except requests.exceptions.RequestException as e:
            logger.error(e)
            raise e

    def exists(self, name):
        full_storage_url = urljoin(self.storage_url, name)
        # Would be better to use head, but doesn't work with bunny (always
        # 200 even when doesn't exist)
        r = requests.get(full_storage_url, headers=self.headers)
        return r.status_code == 200

    def _open(self, name, mode='rb'):
        name = self._normalize_name(clean_name(name))
        file_object = BunnyCDNStorageFile(name, self, mode)
        if not self.exists(name):
            raise IOError(u'File does not exist: %s' % name)
        return file_object

    def _save(self, name, content):
        name = self._normalize_name(clean_name(name))
        try:
            full_storage_url = urljoin(self.storage_url, name)
            r = requests.put(full_storage_url, headers=self.headers, data=content)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise IOError(e)
        return name

    def _download_to_file(self, file, name):
        try:
            full_storage_url = urljoin(self.storage_url, name)
            r = requests.get(full_storage_url, headers=self.headers)
            r.raise_for_status()
            for block in r.iter_content(1024 * 8):
                if not block:
                    break
                file.write(block)
        except requests.exceptions.RequestException as e:
            logger.error(e)
            raise e

    def delete(self, name):
        name = self._normalize_name(clean_name(name))
        try:
            full_storage_url = urljoin(self.storage_url, name)
            r = requests.delete(full_storage_url, headers=self.headers)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(e)
            raise e

    def get_modified_time(self, name):
        full_storage_url = urljoin(self.storage_url, name)
        r = requests.get(full_storage_url, headers=self.storage.headers)
        r.raise_for_status()
        last_mod_str = response.headers.get('Last-Modified')
        dt = dateutil.parser.parse(last_mod_str)
        return dt if setting('USE_TZ') else tz.make_naive(dt)

    def url(self, name):
        # Same as in product api
        return urljoin(self.pull_zone, name)


class BunnyCDNStorageFile(File):
    def __init__(self, name, storage, mode):
        self.name = name
        self._storage = storage
        self._mode = mode
        self._is_dirty = False
        self._file = None

    @property
    def file(self):
        if self._file is not None:
            return self._file

        self._file = SpooledTemporaryFile(
            max_size=self._storage.max_memory_size,
            suffix=".BunnyCDNStorageFile",
            dir=setting("FILE_UPLOAD_TEMP_DIR", None))

        if 'r' in self._mode:
            self._storage._download_to_file(self._file, self.name)
            self._is_dirty = False
            self._file.seek(0)

        return self._file

    @file.setter
    def file(self, value):
        self._file = value

    def read(self, *args, **kwargs):
        if 'r' not in self._mode and 'a' not in self._mode:
            raise AttributeError("File was not opened in read mode.")
        return super(BunnyCDNStorageFile, self).read(*args, **kwargs)

    def write(self, content):
        if len(content) > 100*1024*1024:
            raise ValueError("Max chunk size is 100MB")
        if ('w' not in self._mode and
                '+' not in self._mode and
                'a' not in self._mode):
            raise AttributeError("File was not opened in write mode.")
        self._is_dirty = True
        return super(BunnyCDNStorageFile, self).write(force_bytes(content))

    def close(self):
        if self._file is None:
            return
        if self._is_dirty:
            self._file.seek(0)
            self._storage._save(self.name, self._file)
            self._is_dirty = False
        self._file.close()
        self._file = None
