from twisted.enterprise import adbapi
from django.conf import settings


class ADBApiConfig(object):
    """
    Connect to the database in the pool using adbapi ConnectionPool
    """

    def get_db_connection(self):

        db = settings.DATABASES['default']

        dbargs = dict(
            host=db['HOST'],
            database=db['NAME'],
            user=db['USER'],
            password=db['PASSWORD'],
            port=db['PORT']
        )

        return adbapi.ConnectionPool('psycopg2', **dbargs)
