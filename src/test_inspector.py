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
        """Test the simplest function."""
        def base_fun():
            return 42

        inspector.FunctionPrinter(base_fun, out=self.out).render()
        out = self.out.getvalue()
        self.assertInTimes('base_fun', out, 2)
        self.assertInTimes('Function', out, 1)
        self.assertInTimes('Code', out, 1)
        self.assertInTimes('Closure', out, 0)

    def test_nested_fun(self):
        """Test a function containing a local, nested function."""
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
        """Test a function carrying another one in its closure."""
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
        """Test a decorator that simply alters a function object."""
        def decorator(fun):
            fun.foo = 42
            return fun

        @decorator
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
        """Test decorating a function without porting __name__ and co."""
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
        """Test a clean decorator, using functools.wraps for __name__ and co."""
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
        """Test a simple function."""
        def base_fun():
            return 42

        code_objects = list(inspector.extract_code_objects(base_fun))
        self.assertEqual(1, len(code_objects))
        self.assertIn(base_fun.__code__, code_objects)

    def test_nested_fun(self):
        """Test extraction with nested functions."""
        def base_fun():
            def nested():
                pass
            return 42

        code_objects = set(inspector.extract_code_objects(base_fun))
        self.assertEqual(2, len(code_objects))
        self.assertIn(base_fun.__code__, code_objects)

    def test_fun_with_closure(self):
        """Test extracting from a function holding another in its closure."""
        def some_fun():
            return 42

        def enclosing():
            return some_fun()

        code_objects = set(inspector.extract_code_objects(enclosing))
        self.assertEqual(set([some_fun.__code__, enclosing.__code__]),
            code_objects)

    def test_map_objects(self):
        """Test map_code_objects with ambiguous code."""
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


class FrameTestCase(unittest.TestCase):
    """Tests inspector.frame-related functions."""

    def test_simple_function(self):
        def simple_fun():
            return 42

        f = inspector.Frame(simple_fun)

        # Properties
        self.assertEqual(simple_fun.__name__, f.function_name)
        self.assertEqual('()', f.argspec)

        # Unwrap
        self.assertEqual([[f]], list(f.unwrap()))

        # Equality
        self.assertEqual(f, inspector.Frame(simple_fun))

    def test_nested_function(self):
        def base_fun(foo):
            def nested_fun(bar):
                return bar * 2
            return nested_fun(foo) + 42

        f = inspector.Frame(base_fun)

        # Properties
        self.assertEqual(base_fun.__name__, f.function_name)
        self.assertEqual('(foo)', f.argspec)

        # Unwrap
        self.assertEqual([[f]], list(f.unwrap()))

        # Equality
        self.assertEqual(f, inspector.Frame(base_fun))

    def test_closure_function(self):
        def enclosed_fun(bar):
            return bar * 2

        def base_fun(foo):
            return enclosed_fun(foo) + 42

        f = inspector.Frame(base_fun)

        # Properties
        self.assertEqual(base_fun.__name__, f.function_name)
        self.assertEqual('(foo)', f.argspec)

        # Unwrap: only one path, with enclosed_fun from base_fun.__closure__
        self.assertEqual([[f, inspector.Frame(enclosed_fun)]], list(f.unwrap()))

        # Equality
        self.assertEqual(f, inspector.Frame(base_fun))

    def test_dual_closure_function(self):
        def enclosed_fun(bar):
            return bar * 2

        def alt_enclosed_fun(baz):
            return baz + 1

        def base_fun(foo):
            return enclosed_fun(foo) + alt_enclosed_fun(foo)

        f = inspector.Frame(base_fun)

        # Properties
        self.assertEqual(base_fun.__name__, f.function_name)
        self.assertEqual('(foo)', f.argspec)

        # Unwrap: two paths, one with enclosed_fun and one with alt_enclosed_fun
        self.assertEqual([
                [f, inspector.Frame(enclosed_fun)],
                [f, inspector.Frame(alt_enclosed_fun)]
            ], list(f.unwrap()))

        # Equality
        self.assertEqual(f, inspector.Frame(base_fun))

    def test_enclosed_and_nested(self):
        def enclosed_fun(bar):
            def nested(baz):
                return 2
            return bar * nested(bar)

        def base_fun(foo):
            return enclosed_fun(foo) + 42

        f = inspector.Frame(base_fun)

        # Properties
        self.assertEqual(base_fun.__name__, f.function_name)
        self.assertEqual('(foo)', f.argspec)

        # Unwrap: only one path, with enclosed_fun from base_fun.__closure__
        self.assertEqual([[f, inspector.Frame(enclosed_fun)]], list(f.unwrap()))

        # Equality
        self.assertEqual(f, inspector.Frame(base_fun))

    def test_not_wrapping_decorator(self):
        """Test a decorator that simply alters a function object."""
        def decorator(fun):
            fun.foo = 42
            return fun

        @decorator
        def base_fun():
            return 42

        f = inspector.Frame(base_fun)

        # Properties
        self.assertEqual(base_fun.__name__, f.function_name)
        self.assertEqual('()', f.argspec)

        # Unwrap
        self.assertEqual([[f]], list(f.unwrap()))

        # Decorator
        self.assertEqual([[(f, None)]], list(f.unwrap_decorators([decorator])))
        self.assertEqual([], list(f.find_decorator(decorator)))

        # Equality
        self.assertEqual(f, inspector.Frame(base_fun))


    def test_dirty_wrapping_decorator(self):
        """Test decorating a function without porting __name__ and co."""
        def decorator(decorated_fun):
            def wrapped(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped

        def base_fun():
            return 42

        decorated = decorator(base_fun)

        f = inspector.Frame(decorated)

        # Properties
        self.assertEqual('wrapped', f.function_name)
        self.assertEqual('(*args, **kwargs)', f.argspec)  # Overridden by decorator

        # Unwrap: one frame with the decorator, one with the decorated
        self.assertEqual([[f, inspector.Frame(base_fun)]], list(f.unwrap()))

        # Decorator
        self.assertEqual([[(f, decorator), (inspector.Frame(base_fun), None)]],
            list(f.unwrap_decorators([decorator])))
        self.assertEqual([(f, f.fun.__code__)], list(f.find_decorator(decorator)))

        # Equality
        self.assertEqual(f, inspector.Frame(decorated))
        self.assertNotEqual(f, inspector.Frame(base_fun))
        self.assertNotEqual(f, inspector.Frame(decorator))

    def test_functools_wrapping_decorator(self):
        """Test a clean decorator, using functools.wraps for __name__ and co."""
        def decorator(decorated_fun):
            @functools.wraps(decorated_fun)
            def wrapped(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped

        def base_fun():
            return 42

        decorated = decorator(base_fun)

        f = inspector.Frame(decorated)

        # Properties
        self.assertEqual('<base_fun/wrapped>', f.function_name)
        self.assertEqual('(*args, **kwargs)', f.argspec)  # Overridden by decorator

        # Unwrap: one frame for the decorator, one for the base function
        self.assertEqual([[f, inspector.Frame(base_fun)]], list(f.unwrap()))

        # Decorator
        self.assertEqual([[(f, decorator), (inspector.Frame(base_fun), None)]],
            list(f.unwrap_decorators([decorator])))
        self.assertEqual([(f, f.fun.__code__)], list(f.find_decorator(decorator)))

        # Equality
        self.assertEqual(f, inspector.Frame(decorated))
        self.assertNotEqual(f, inspector.Frame(base_fun))
        self.assertNotEqual(f, inspector.Frame(decorator))

    def test_functools_chained_decorators(self):
        """Test a clean decorator, using functools.wraps for __name__ and co."""
        def decorator1(decorated_fun):
            @functools.wraps(decorated_fun)
            def wrapped1(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped1

        def decorator2(decorated_fun):
            @functools.wraps(decorated_fun)
            def wrapped2(*args, **kwargs):
                return decorated_fun(*args, **kwargs) + 42
            return wrapped2

        def base_fun():
            return 42

        decorated1 = decorator1(base_fun)
        decorated21 = decorator2(decorated1)
        decorated2 = decorator2(base_fun)
        decorated12 = decorator1(decorated2)

        f1 = inspector.Frame(decorated1)
        f2 = inspector.Frame(decorated2)
        f12 = inspector.Frame(decorated12)
        f21 = inspector.Frame(decorated21)

        # Properties
        self.assertEqual('<base_fun/wrapped1>', f1.function_name)
        self.assertEqual('<base_fun/wrapped2>', f2.function_name)
        self.assertEqual('<base_fun/wrapped1>', f12.function_name)
        self.assertEqual('<base_fun/wrapped2>', f21.function_name)
        self.assertEqual('(*args, **kwargs)', f1.argspec)  # Overridden by decorator
        self.assertEqual('(*args, **kwargs)', f2.argspec)  # Overridden by decorator
        self.assertEqual('(*args, **kwargs)', f12.argspec)  # Overridden by decorator
        self.assertEqual('(*args, **kwargs)', f21.argspec)  # Overridden by decorator

        # Unwrap
        # One frame for the decorator, one for the base function
        self.assertEqual([[f1, inspector.Frame(base_fun)]], list(f1.unwrap()))
        self.assertEqual([[f2, inspector.Frame(base_fun)]], list(f2.unwrap()))
        # One frame for the first decorator, one for the second, one for base
        un12 = list(f12.unwrap())
        self.assertEqual(1, len(un12))
        self.assertEqual(3, len(un12[0]))
        # This is almost f1, but not exactly (not the same closure)
        self.assertEqual(decorator1.__code__.co_consts[1], un12[0][0].fun.__code__)
        self.assertEqual(f2, un12[0][1])
        self.assertEqual(inspector.Frame(base_fun), un12[0][2])

        un21 = list(f21.unwrap())
        self.assertEqual(1, len(un21))
        self.assertEqual(3, len(un21[0]))
        # This is almost f2, but not exactly (not the same closure)
        self.assertEqual(decorator2.__code__.co_consts[1], un21[0][0].fun.__code__)
        self.assertEqual(f1, un21[0][1])
        self.assertEqual(inspector.Frame(base_fun), un21[0][2])

        # Decorator
        # We should detect that f1 might have been decorated
        self.assertEqual([[(f1, decorator1), (inspector.Frame(base_fun), None)]],
            list(f1.unwrap_decorators([decorator1])))
        self.assertEqual([[(f1, None), (inspector.Frame(base_fun), None)]],
            list(f1.unwrap_decorators([decorator2])))
        self.assertEqual([[(f1, None), (inspector.Frame(base_fun), None)]],
            list(f1.unwrap_decorators([])))

        # We should detect that f2 might have been decorated
        self.assertEqual([[(f2, decorator2), (inspector.Frame(base_fun), None)]],
            list(f2.unwrap_decorators([decorator2])))
        self.assertEqual([[(f2, None), (inspector.Frame(base_fun), None)]],
            list(f2.unwrap_decorators([decorator1])))
        self.assertEqual([[(f2, None), (inspector.Frame(base_fun), None)]],
            list(f2.unwrap_decorators([])))

        # We should detect that f12 was decorated twice
        self.assertEqual([[
                (f12, decorator1),
                (f2, decorator2),
                (inspector.Frame(base_fun), None)
            ]], list(f12.unwrap_decorators([decorator1, decorator2])))
        self.assertEqual([[
                (f12, decorator1),
                (f2, decorator2),
                (inspector.Frame(base_fun), None)
            ]], list(f12.unwrap_decorators([decorator2, decorator1])))
        self.assertEqual([[
                (f12, decorator1),
                (f2, None),
                (inspector.Frame(base_fun), None)
            ]], list(f12.unwrap_decorators([decorator1])))
        self.assertEqual([[
                (f12, None),
                (f2, decorator2),
                (inspector.Frame(base_fun), None)
            ]], list(f12.unwrap_decorators([decorator2])))
        self.assertEqual([[
                (f12, None),
                (f2, None),
                (inspector.Frame(base_fun), None)
            ]], list(f12.unwrap_decorators([])))

        # We should detect that f21 was decorated twice
        self.assertEqual([[
                (f21, decorator2),
                (f1, decorator1),
                (inspector.Frame(base_fun), None)
            ]], list(f21.unwrap_decorators([decorator1, decorator2])))
        self.assertEqual([[
                (f21, decorator2),
                (f1, decorator1),
                (inspector.Frame(base_fun), None)
            ]], list(f21.unwrap_decorators([decorator2, decorator1])))
        self.assertEqual([[
                (f21, decorator2),
                (f1, None),
                (inspector.Frame(base_fun), None)
            ]], list(f21.unwrap_decorators([decorator2])))
        self.assertEqual([[
                (f21, None),
                (f1, decorator1),
                (inspector.Frame(base_fun), None)
            ]], list(f21.unwrap_decorators([decorator1])))
        self.assertEqual([[
                (f21, None),
                (f1, None),
                (inspector.Frame(base_fun), None)
            ]], list(f21.unwrap_decorators([])))

        # decorator1 should be found in f1 using decorated1 code (== wrapped1)
        self.assertEqual([(f1, decorated1.__code__)], list(f1.find_decorator(decorator1)))
        self.assertEqual([], list(f1.find_decorator(decorator2)))

        # decorator2 should be found in f2 using decorated2 code (== wrapped2)
        self.assertEqual([(f2, decorated2.__code__)], list(f2.find_decorator(decorator2)))
        self.assertEqual([], list(f2.find_decorator(decorator1)))

        res21 = list(f21.find_decorator(decorator1))
        # res21 is almost (f2, wrapped1), (f1, wrapped1), but for f2's closure.
        self.assertEqual(2, len(res21))
        self.assertEqual(decorated2.__code__, res21[0][0].fun.__code__)
        self.assertEqual(decorator1.__code__.co_consts[1], res21[0][1])
        self.assertEqual((f1, f1.fun.__code__), res21[1])

        res21 = list(f21.find_decorator(decorator2))
        # res21 is almost (f2, wrapped2), but for f2's closure.
        self.assertEqual(1, len(res21))
        self.assertEqual(decorated2.__code__, res21[0][0].fun.__code__)
        self.assertEqual(decorator2.__code__.co_consts[1], res21[0][1])

        res12 = list(f12.find_decorator(decorator1))
        # res12 is almost (f1, wrapped1), but for f1's closure.
        self.assertEqual(1, len(res12))
        self.assertEqual(decorated1.__code__, res12[0][0].fun.__code__)
        self.assertEqual(decorator1.__code__.co_consts[1], res12[0][1])

        res12 = list(f12.find_decorator(decorator2))
        # res12 is almost (f1, wrapped2), (f2, wrapped2), but for f1's closure.
        self.assertEqual(2, len(res12))
        self.assertEqual(decorated1.__code__, res12[0][0].fun.__code__)
        self.assertEqual(decorator2.__code__.co_consts[1], res12[0][1])
        self.assertEqual((f2, f2.fun.__code__), res12[1])


if __name__ == '__main__':
    unittest.main()
