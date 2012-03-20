# coding: utf-8
# Copyright (c) 2012 Raphaël Barrois

import functools
import unittest
import StringIO

import inspector


class PrinterTestCase(unittest.TestCase):
    """Tests FunctionPrinter and CodePrinter."""

    def setUp(self):
        self.out = StringIO.StringIO()

    def tearDown(self):
        self.out.close()

    def assertInTimes(self, search, into, times):
        """Tests that a given string appears exactly N times in another."""
        nb_seen = into.count(search)
        self.assertEqual(times, nb_seen,
            "%r appears %d times in %r, expected %d times" %
            (search, nb_seen, into, times))

    def test_simple_fun(self):
        def base_fun():
            return 42

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()
        self.assertInTimes('base_fun', out, 2)
        self.assertInTimes('Function', out, 1)
        self.assertInTimes('Code', out, 1)
        self.assertInTimes('Closure', out, 0)

    def test_nested_fun(self):
        def base_fun():
            def nested_fun():
                return 42
            return nested_fun()

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()
        self.assertInTimes('base_fun', out, 2)  # Once as Function, once as code
        self.assertInTimes('nested_fun', out, 1)  # Only as code
        self.assertInTimes('Function', out, 1)
        self.assertInTimes('Code', out, 2)
        self.assertInTimes('Closure', out, 0)

    def test_closure_fun(self):
        def enclosed_fun():
            return 42

        def base_fun():
            return enclosed_fun()

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()

        # Function base_fun at 15421144, from __main__
        # +-> Code: base_fun()
        # |   | file: test_inspector.py:53
        # |   | reusing: enclosed_fun
        # |
        # +-> Closure:
        # |   +-> enclosed_fun = Function enclosed_fun at 15421024, from __main__
        # |   |     +-> Code: enclosed_fun()
        # |   |     |   | file: test_inspector.py:50

        self.assertInTimes('base_fun', out, 2)
        self.assertInTimes('enclosed_fun', out, 4)
        self.assertInTimes('Function', out, 2)
        self.assertInTimes('Code', out, 2)
        self.assertInTimes('Closure', out, 1)

    def test_not_wrapping_decorator(self):
        def decorator(fun):
            fun.foo = 42
            return fun

        def base_fun():
            return 42

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()

        # Function base_fun at 17508544, from __main__
        # +-> Code: base_fun()
        # |   | file: test_inspector.py:79

        self.assertInTimes('base_fun', out, 2)
        self.assertInTimes('Function', out, 1)
        self.assertInTimes('Code', out, 1)
        self.assertInTimes('Closure', out, 0)

    def test_dirty_wrapping_decorator(self):
        def decorator(decorated_fun):
            def wrapped(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped

        @decorator
        def base_fun():
            return 42

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()

        # Function wrapped at 16781392, from __main__
        # +-> Code: wrapped(*args, **kwargs)
        # |   | file: test_inspector.py:95
        # |   | reusing: decorared_fun
        # |
        # +-> Closure:
        # |   +-> decorared_fun = Function base_fun at 16783432, from __main__
        # |   |     +-> Code: base_fun()
        # |   |     |   | file: test_inspector.py:99

        self.assertInTimes('base_fun', out, 2)
        self.assertInTimes('wrapped', out, 2)
        self.assertInTimes('decorated_fun', out, 2)
        self.assertInTimes('Function', out, 2)
        self.assertInTimes('Code', out, 2)
        self.assertInTimes('Closure', out, 1)

    def test_functools_wrapping_decorator(self):
        def decorator(decorated_fun):
            @functools.wraps(decorated_fun)
            def wrapped(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped

        @decorator
        def base_fun():
            return 42

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()

        # Function base_fun at 16781392, from __main__
        # +-> Code: wrapped(*args, **kwargs)
        # |   | file: test_inspector.py:95
        # |   | reusing: decorared_fun
        # |
        # +-> Closure:
        # |   +-> decorared_fun = Function base_fun at 16783432, from __main__
        # |   |     +-> Code: base_fun()
        # |   |     |   | file: test_inspector.py:99

        self.assertInTimes('base_fun', out, 3)
        self.assertInTimes('wrapped', out, 1)
        self.assertInTimes('decorated_fun', out, 2)
        self.assertInTimes('Function', out, 2)
        self.assertInTimes('Code', out, 2)
        self.assertInTimes('Closure', out, 1)


class CodeObjectsExtractionTestCase(unittest.TestCase):
    """Tests extract_code_objects and derivatives."""

    def test_simple_fun(self):
        def base_fun():
            return 42

        code_objects = list(inspector.extract_code_objects(base_fun))
        self.assertEqual(1, len(code_objects))
        self.assertIn(base_fun.__code__, code_objects)

    def test_nested_fun(self):
        def base_fun():
            def nested():
                pass
            return 42

        code_objects = set(inspector.extract_code_objects(base_fun))
        self.assertEqual(2, len(code_objects))
        self.assertIn(base_fun.__code__, code_objects)

    def test_fun_with_closure(self):
        def some_fun():
            return 42

        def enclosing():
            return some_fun()

        code_objects = set(inspector.extract_code_objects(enclosing))
        self.assertEqual(set([some_fun.__code__, enclosing.__code__]),
            code_objects)

    def test_map_objects(self):
        def some_fun(foo):
            return 42

        def fun1(bar):
            return bar + some_fun(bar)

        def fun2(baz):
            return baz * some_fun(baz)

        code_map, ambiguous = inspector.map_code_objects([fun1, fun2])

        self.assertEqual(2, len(code_map))
        self.assertEqual(fun1, code_map[fun1.__code__])
        self.assertEqual(fun2, code_map[fun2.__code__])
        self.assertEqual(set([some_fun.__code__]), ambiguous)



if __name__ == '__main__':
    unittest.main()
