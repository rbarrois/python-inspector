# coding: utf-8
# Copyright (c) 2012 Raphaël Barrois

"""Functions for inspecting a view and extracting information."""


import collections
import inspect
import sys


class BasePrinter(object):
    def __init__(self, out=None, prefix='', first_prefix=None, *args, **kwargs):
        self.out = out or sys.stdout
        self.prefix = prefix
        if first_prefix is None:
            first_prefix = prefix
        self.first_prefix = first_prefix
        self._first_write_done = False

    def _write(self, txt, auto_eol=True):
        suffix = '\n' if auto_eol else ''
        prefix = self.prefix
        if not self._first_write_done:
            self._first_write_done = True
            prefix = self.first_prefix

        self.out.write('%s%s%s' % (prefix, txt, suffix))


class FunctionPrinter(BasePrinter):
    def __init__(self, fun, *args, **kwargs):
        super(FunctionPrinter, self).__init__(*args, **kwargs)
        self.fun = fun

    def render(self):
        self._write('Function %s at %d, from %s' % (self.fun.__name__, id(self.fun), self.fun.__module__))
        code_printer = CodePrinter(self.fun.__code__,
            out=self.out, prefix=self.prefix + '|   ', first_prefix=self.prefix + '+-> ')
        code_printer.render()
        if self.fun.__closure__:
            self._write('|')
            self._write_closure()

    def _write_closure(self):
        self._write('+-> Closure:')

        for varname, varvalue in sorted(zip(self.fun.__code__.co_freevars, self.fun.__closure__)):
            if callable(varvalue.cell_contents):
                subprinter = FunctionPrinter(varvalue.cell_contents,
                    out=self.out, prefix=self.prefix + '|   |     ',
                    first_prefix=self.prefix + '|   +-> %s = ' % varname)
                subprinter.render()
            else:
                self._write('|   +-> %s = %r' % (varname, varvalue.cell_contents))

class CodePrinter(BasePrinter):
    """Inspect and prints all code elements of a given function."""

    def __init__(self, code, *args, **kwargs):
        super(CodePrinter, self).__init__(*args, **kwargs)
        self.code = code

    def render(self):
        base_args = list(self.code.co_varnames[:self.code.co_argcount])
        internal_vars = list(self.code.co_varnames[self.code.co_argcount:])
        if self.code.co_flags & 0x04:  # Using '*args'
            base_args.append('*%s' % internal_vars.pop(0))

        if self.code.co_flags & 0x08:  # Using **kwargs
            base_args.append('**%s' % internal_vars.pop(0))

        self._write('Code: %s(%s)'% (self.code.co_name, ', '.join(base_args)))
        self._write('| file: %s:%d' % (self.code.co_filename, self.code.co_firstlineno))
        if self.code.co_freevars:
            self._write('| reusing: %s' % ', '.join(self.code.co_freevars))
        if self.code.co_cellvars:
            self._write('| sharing: %s' % ', '.join(self.code.co_cellvars))

        subcodes = [c for c in self.code.co_consts if isinstance(c, self.code.__class__)]
        for subcode in subcodes:
            self._write('|')
            subprinter = CodePrinter(subcode, out=self.out,
                prefix=self.prefix + '|   ', first_prefix=self.prefix + '+-> ')
            subprinter.render()


import functools
def example1(selected, default):
    def decorator(fun):
        def helper():
            pass
        @functools.wraps(fun)
        def wrapper1(selector, *args, **kwargs):
            def alt_helper():
                pass
            if selector == selected:
                return default
            else:
                return fun(selector, *args, **kwargs)
        return wrapper1
    return decorator


def example2(fun):
    @functools.wraps(fun)
    def wrapper2(x, *args, **kwargs):
        return fun(x + x, *args, **kwargs)
    return wrapper2


@example1(1, 0)
def test1(x, *test_args):
    return x * len(test_args)


@example2
def test2(x, **test_kwargs):
    return x * len(test_kwargs)


@example1(2, 42)
@example2
def test3(x, *_args, **_kwargs):
    return x * len(_args) * len(_kwargs)


@example1(2, test2)
@example2
def test4(x, *_args, **_kwargs):
    return x(*_args, **_kwargs)


def extract_code_objects(function):
    """Extracts all code objects from a given function."""
    pending = [function.__code__]
    while pending:
        code = pending.pop(0)
        yield code
        for e in code.co_consts:
            if isinstance(e, code.__class__):
                pending.append(e)

    if function.__closure__:
        for cell in function.__closure__:
            cell_value = cell.cell_contents
            if callable(cell_value):
                for code in extract_code_objects(cell_value):
                    yield code


def map_code_objects(functions):
    """Creates a map of code object => function."""
    code_to_function = {}
    ambiguous_code = set()
    for function in functions:
        for code in extract_code_objects(function):
            if code in ambiguous_code:
                continue
            elif code in code_to_function:
                del code_to_function[code]
                ambiguous_code.add(code)
            else:
                code_to_function[code] = function
    return code_to_function, ambiguous_code


class Frame(object):
    """Holds information about a decorated function."""
    def __init__(self, fun):
        self.fun = fun
        self.subframes = {}
        self.context = {}
        for cell_name, cell in self._get_cells():
            cell_value = cell.cell_contents
            self.context[cell_name] = cell_value
            if callable(cell_value):
                self.subframes[cell_name] = Frame(cell_value)

    def _get_cells(self):
        if self.fun.__closure__:
            return zip(self.fun.__code__.co_freevars, self.fun.__closure__)
        else:
            return []

    @property
    def argspec(self):
        return inspect.formatargspec(*inspect.getargspec(self.fun))

    def render(self, out=None):
        FunctionPrinter(self.fun, out=out).render()

    def unwrap(self):
        """Finds all possible decorator chains.

        Yields:
           Frame list: all possible decorator chains.
        """
        if self.subframes:
            first_frame = self
            for subframe in self.subframes.values():
                for subchain in subframe.unwrap():
                    yield [first_frame] + subchain
        else:
            yield [Frame(self.fun)]

    def unwrap_decorators(self, decorators):
        """Finds all possible decorator chains, attaching to known decorators."""
        code_to_decorator, ambiguous_code = map_code_objects(decorators)
        def find_decorator(frame):
            for code in extract_code_objects(frame.fun):
                if code in code_to_decorator:
                    return frame, code_to_decorator[code]
            return frame, None

        for unwrap_chain in self.unwrap():
            yield [find_decorator(frame) for frame in unwrap_chain]

    def find_decorator(self, decorator):
        """Finds all (sub)frames potentially using a given decorator."""
        codes = set(extract_code_objects(decorator))
        all_frames = [self]
        while all_frames:
            frame = all_frames.pop(0)
            for code in extract_code_objects(frame.fun):
                if code in codes:
                    yield (frame, code)
                    break
            all_frames.extend(frame.subframes.values())

    @property
    def function_name(self):
        if self.fun.__code__.co_name != self.fun.__name__:
            return '<%s/%s>' % (self.fun.__name__, self.fun.__code__.co_name)
        else:
            return self.fun.__name__

    def __repr__(self):
        return '<Frame for %s%s at %s from %s:%d>' % (
            self.function_name,
            self.argspec,
            id(self.fun),
            self.fun.__code__.co_filename,
            self.fun.__code__.co_firstlineno,
        )


class AltFrame(object):
    def __init__(self, fun, cell=None):
        self.cell = cell
        self.fun = fun
        self.subframes = []
        self.env = []
        for cell in fun.__closure__:
            enclosed = cell.cell_contents
            if callable(enclosed) and enclosed.__closure__:
                self.subframes.append(Frame(enclosed, cell))
            else:
                self.env.append(enclosed)

    @classmethod
    def _extract_code_instances(cls, fun):
        """Extract all code instances from a given function."""
        pending = [fun.__code__]
        found = []
        while pending:
            f = pending.pop()
            found.append(f)
            pending.extend([code for code in f.co_consts if code])
        return found

    def find_decorator_frames(self, decorator):
        code_instances = self._extract_code_instances(decorator)
        frames = []
        if self.fun.__code__ in code_instances:
            frames.append(self)
        for subframe in self.subframes:
            frames.extend(subframe.find_decorator_frames(decorator))
        return frames


def display(obj, out=None):
    """Display all attributes of an object."""
    if not out:
        out = sys.stdout
    out.write("Details of %r\n" % obj)
    for attr in dir(obj):
        out.write('|-> %s = %r\n' % (attr, getattr(obj, attr)))


def extract_decorators(fun):
    """Extract a list of decorators from a given function.

    Args:
        fun (function): the function from which decorators should be extracted.

    Returns:
        ([DecoratorFrame list], base_function): a tuple containing both the list
            of applied decorators (if any), and the base function.
    """
    decorators = []
    while fun.__closure__:
        wrapped = fun.__closure__[-1].cell_contents
        decorator_args = fun.__closure__[:-1]
        decorators.append(DecoratorFrame(fun, decorator_args, wrapped))
        fun = wrapped

    return (decorators, fun)
