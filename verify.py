import sys
import types
import json

MAX_INT = (2**31) - 1
MIN_INT = -MAX_INT - 1


def extend_path(key, previous=''):
    if isinstance(key, int):
        key = '[%s]' % key
    elif len(previous) > 0:
        previous = previous + '.'
    return previous + key


class Doc:
    def __init__(self, data, schema):
        self.raw_data = data
        self.schema = schema
        self.indices = {}
        schema.build_index(data, '', self)

    def register_index(self, index, path):
        assert path not in self.indices
        self.indices[path] = index

    def check_ref(self, ref_path, key, test):
        test.assertTrue(key in self.indices[ref_path],
                        "Key reference '%s' not found at index path '%s'"
                        % (key, ref_path))

    def validate(self, test):
        self.schema.validate(self.raw_data, self, test)


class Schema(object):
    def __init__(self):
        self.is_key = False

    def get_key(self, data):
        return None

    def build_index(self, data, path, doc):
        return data

    def validate(self, data, doc, test):
        pass


class DictSchema(Schema):
    def __init__(self, items):
        super(DictSchema, self).__init__()
        self.items = items
        key_items = filter(lambda (k, v): v.is_key, items.items())
        assert len(key_items) < 2, "Multiple fields marked as key"
        self.key = None if len(key_items) == 0 else key_items[0][0]

    def get_key(self, data):
        if self.key is None:
            return None
        else:
            return data[self.key]

    def build_index(self, data, path, doc):
        for k, schema in self.items.items():
            if k in data:
                schema.build_index(
                    data[k],
                    extend_path(k, path),
                    doc)

    def validate(self, data, doc, test):
        for k, schema in self.items.items():
            if k in data:
                test.validate(data[k], schema, k, doc)


class ListSchema(Schema):
    def __init__(self, item_schema):
        super(ListSchema, self).__init__()
        self.item_schema = item_schema

    def build_index(self, data, path, doc):
        index = {}
        for i, item in enumerate(data):
            key = self.item_schema.get_key(item)
            if key is not None:
                assert key not in index, "Duplicate key (%s) at path '%s'" % (key, path)
                index[key] = i
                self.item_schema.build_index(
                    item,
                    extend_path(key or i, path),
                    doc)
        if len(index) > 0:
            doc.register_index(index, path)

    def validate(self, data, doc, test):
        for i, item in enumerate(data):
            test.validate(item, self.item_schema, i, doc)


class IntSchema(Schema):
    def __init__(self, min=MIN_INT, max=MAX_INT, coerce=False):
        super(IntSchema, self).__init__()
        self.min = int(min)
        self.max = int(max)
        self.coerce = coerce

    def validate(self, data, doc, test):
        if self.coerce:
            data = int(data)
        test.assertTrue(isinstance(data, int),
                        "Incorrect type, expected int, found '%s'" % type(data))
        test.assertTrue(data >= self.min,
                        "Int value (%s) less than minimum (%s)" % (data, self.min))
        test.assertTrue(data <= self.max,
                        "Int value (%s) greater than maximum (%s)" % (data, self.max))


class StrSchema(Schema):
    def __init__(self, ref=None):
        super(StrSchema, self).__init__()
        self.ref = ref

    def get_key(self, data):
        if self.is_key:
            return data
        return None

    def validate(self, data, doc, test):
        test.assertTrue(isinstance(data, str) or isinstance(data, unicode),
                        "Incorrect type, expected str or unicode, found '%s'"
                        % type(data))
        if self.ref:
            doc.check_ref(self.ref, data, test)


def make_int_schema(params):
    return IntSchema(min=params.get('min', MIN_INT),
                     max=params.get('max', MAX_INT),
                     coerce=params.get('coerce', False))


def make_str_schema(params):
    return StrSchema(ref=params.get('ref', None))


def make_value_schema(desc):
    assert isinstance(desc, str)
    value_schemas = {
        'int': make_int_schema,
        'str': make_str_schema
    }
    tokens = map(str.strip, desc.split(','))
    field_type = tokens[0]
    tokens = [tok.split('=', 1) for tok in tokens[1:]]
    params = {tok[0]: tok[1] if len(tok) > 1 else True for tok in tokens}
    schema = value_schemas[field_type](params)
    schema.is_key = params.get('key', False)
    return schema


def make_schema(desc):
    if isinstance(desc, dict):
        return DictSchema({k: make_schema(v) for (k, v) in desc.items()})
    elif isinstance(desc, list):
        return ListSchema(make_schema(desc[0]))
    elif isinstance(desc, str) or isinstance(desc, unicode):
        return make_value_schema(desc)


class Checker:
    def __init__(self, reporter, path=''):
        self.reporter = reporter
        self.path = path

    def validate(self, data, schema, key, doc):
        schema.validate(data, doc,
                        Checker(self.reporter,
                                extend_path(key, self.path)))

    def raiseError(self, msg):
        self.reporter.raiseError("Error at path '%s': %s" % (self.path, msg))

    def assertTrue(self, v, msg):
        if not v:
            self.raiseError(msg)


class FailFastReporter:
    def raiseError(self, msg):
        raise AssertionError(msg)

    def validate(self, doc):
        doc.validate(Checker(self))


class AggregateReporter:

    def __init__(self):
        self.errors = []

    def raiseError(self, msg):
        self.errors.append(AssertionError(msg))

    def validate(self, doc):
        doc.validate(Checker(self))
        if len(self.errors) > 0:
            for e in self.errors:
                print e
            raise AssertionError("Validation failed with %s errors!"
                                 % len(self.errors))


types_schema = make_schema({
    "types": ["str, key"]
    })

levels_schema = make_schema({
     "types": ["str, key"],
     "levels": [{
         "name": "str, key",
         "width": "int, min=0, max=18",
         "height": "int, min=0, max=25",
         "blocks": [{
             "type": "str, ref=types",
             "column": "int, min=0, max=18, coerce",
             "row": "int, min=0, max=25, coerce",
             "prototype": "str"
         }]
     }]
})


if __name__ == '__main__':
    with open('data.json', 'r') as f:
        data = json.load(f)

        try:
            doc = Doc(data, levels_schema)
            AggregateReporter().validate(doc)
            # FailFastReporter().validate(doc)
        except AssertionError, e:
            sys.exit(e)
    print "Ok"
