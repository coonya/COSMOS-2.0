import sqlalchemy.types as types
from sqlalchemy.ext.mutable import Mutable
import six

class Enum34_ColumnType(types.TypeDecorator):
    """
    Enum compatible with enum34 package
    """

    impl = types.String

    def __init__(self, enum_class, *args, **kwargs):
        self.enum_class = enum_class
        return types.TypeDecorator.__init__(self, *args, **kwargs)

    def _set_table(self, table, column):
        """
        Required for sqlalchemy to create enum types for postgres
        """
        self.impl._set_table(table, column)

    def process_bind_param(self, value, dialect):
        assert isinstance(value, self.enum_class) or value is None, "'%s' must be of type %s" % (value, self.enum_class)
        return None if value is None else value.name

    def process_result_value(self, value, dialect):
        return None if value is None else getattr(self.enum_class, value)

    def copy(self):
        return Enum34_ColumnType(self.enum_class)


class ListOfStrings(types.TypeDecorator):
    """
    Enum compatible with enum34 package
    """
    impl = types.Text

    def __init__(self):
        return types.TypeDecorator.__init__(self, '')

    def process_bind_param(self, value, dialect):
        assert isinstance(value, list), '%s must be a list' % value
        return ', '.join(value) if value else None

    def process_result_value(self, value, dialect):
        return value.split(', ') if value else []


def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        # session.add(instance)
        return instance, True


from sqlalchemy.types import TypeDecorator, VARCHAR
import json


class JSONEncodedDict(TypeDecorator):
    "Represents an immutable structure as a json-encoded string."

    impl = types.UnicodeText

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value = six.text_type(json.dumps(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                value = json.loads(value)
            except Exception:
                return dict()
        return value


class MutableDict(Mutable, dict):
    @classmethod
    def coerce(cls, key, value):
        "Convert plain dictionaries to MutableDict."

        if not isinstance(value, MutableDict):
            if isinstance(value, dict):
                return MutableDict(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def __setitem__(self, key, value):
        "Detect dictionary set events and emit change events."

        dict.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key):
        "Detect dictionary del events and emit change events."

        dict.__delitem__(self, key)
        self.changed()