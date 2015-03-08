import verify
import unittest


class TestFunctions(unittest.TestCase):
    def test_extend_path(self):
        self.assertEqual('a', verify.extend_path('a'))
        self.assertEqual('a.b', verify.extend_path('b', 'a'))
        self.assertEqual('a[0]', verify.extend_path(0, 'a'))

class MockDoc:
    def register_index(self, index, path):
        pass

    def check_ref(self, path, key, test):
        pass

    def validate(self, test):
        pass


class MockChecker:
    def assertTrue(self, v, msg):
        if not v:
            raise AssertionError(msg)


class TestStrSchema(unittest.TestCase):
    def test_type(self):
        schema = verify.StrSchema()
        doc = MockDoc()
        with self.assertRaises(AssertionError):
            schema.validate(1, doc, self) # MockChecker())
        schema.validate('a_string', doc, self)


class TestIntSchema(unittest.TestCase):
    def test_type(self):
        schema = verify.IntSchema()
        doc = MockDoc()
        schema.validate(2, doc, self)
        with self.assertRaises(AssertionError):
            schema.validate("a", doc, self)
        with self.assertRaises(AssertionError):
            schema.validate("1", doc, self)

    def test_coerce(self):
        schema = verify.IntSchema(coerce=True)
        doc = MockDoc()
        schema.validate(2, doc, self)
        schema.validate("1", doc, self)
        with self.assertRaises(AssertionError):
            schema.validate("a1", doc, self)

    def test_min(self):
        schema = verify.IntSchema(min=1)
        doc = MockDoc()
        schema.validate(2, doc, self)
        schema.validate(1, doc, self)
        with self.assertRaises(AssertionError):
            schema.validate(0, doc, self)

    def test_max(self):
        schema = verify.IntSchema(max=10000)
        doc = MockDoc()
        schema.validate(-100000, doc, self)
        schema.validate(1, doc, self)
        schema.validate(10000, doc, self)
        with self.assertRaises(AssertionError):
            schema.validate(20000, doc, self)


if __name__ == '__main__':
    unittest.main()
    
