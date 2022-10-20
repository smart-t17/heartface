from django.conf import settings
from elasticsearch_dsl import DocType as OrigDocType
from elasticsearch_dsl import Integer, Text, Date, Keyword
from elasticsearch_dsl.utils import DOC_META_FIELDS, AttrList
from six import iteritems


from elasticsearch_dsl.connections import connections

from heartface.libs.search import CustomJSONSerializer

connections.create_connection(hosts=[settings.ELASTIC_URL], serializer=CustomJSONSerializer())


class DocType(OrigDocType):
    # Enforce skip_empty is default False. We want to keep fields like []
    # for video likes etc
    def to_dict(self, include_meta=False, skip_empty=False):
        """
        Temporary fix to allow keeping empty fields (later can upgrade
        and achieve more easily by just forcing skip_empty=False)
        """
        # ObjectBase method
        out = {}
        for k, v in iteritems(self._d_):
            try:
                f = self._doc_type.mapping[k]
            except KeyError:
                pass
            else:
                if f._coerce:
                    v = f.serialize(v)

            # if someone assigned AttrList, unwrap it
            if isinstance(v, AttrList):
                v = v._l_

            # don't serialize empty values
            # careful not to include numeric zeros
            if skip_empty:
                if v in ([], {}, None):
                    continue

            out[k] = v

        # Method from DocType
        d = out
        if not include_meta:
            return d

        meta = dict(
            ('_' + k, self.meta[k])
            for k in DOC_META_FIELDS
            if k in self.meta
        )

        # in case of to_dict include the index unlike save/update/delete
        if 'index' in self.meta:
            meta['_index'] = self.meta.index
        elif self._doc_type.index:
            meta['_index'] = self._doc_type.index

        meta['_type'] = self._doc_type.name
        meta['_source'] = d
        return meta


class UserIndex(DocType):
    """
    Get more control over the mapping, see
    curl -X GET "localhost:9200/user/_mapping?pretty"
    """
    pk = Integer()
    # Keyword means only searchable exactly
    username = Text(fields={'raw': Keyword()})
    email = Text()
    full_name = Text()
    gender = Text()
    description = Text()
    date_joined = Date()
    age = Integer()

    class Meta:
        index = 'user'


class HashtagIndex(DocType):
    pk = Integer()
    name = Text(fields={'raw': Keyword()})

    class Meta:
        index = 'hashtag'


class VideoIndex(DocType):
    pk = Integer()
    title = Text(fields={'raw': Keyword()})
    created = Date()

    class Meta:
        index = 'video'


class ProductIndex(DocType):
    pk = Integer()
    name = Text(fields={'raw': Keyword()})
    description = Text()

    class Meta:
        index = 'product'


SEARCH_INDEXES = [
    {
        'index': 'user',
        'model': 'User',
        'es_model': UserIndex,
    }, {
        'index': 'hashtag',
        'model': 'Hashtag',
        'es_model': HashtagIndex,
    }, {
        'index': 'video',
        'model': 'Video',
        'es_model': VideoIndex,
    }, {
        'index': 'product',
        'model': 'Product',
        'es_model': ProductIndex,
    }
]
