import contextlib
import io
import os
import unittest.mock as mock


def data_path(path):
    """
    Return the absolute path from one relative to the test-suite data directory.
    *path* must be a relative path. No sanitation is done on path regarding
    escaping the test-suite data directory via, e.g, ``../``.

    """
    assert not os.path.isabs(path)
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), 'data', path
    ))


def open_data(path, *args, **kwargs):
    """
    Open a file relative to the test-suite data directory. *path* must be a
    relative path. No sanitation is done on path regarding escaping the
    test-suite data directory via, e.g, ``../``.

    Other arguments are passed to the builtin open() function.

    """
    return open(data_path(path), *args, **kwargs)


@contextlib.contextmanager
def captured_stdout():
    """
    Context manager which mocks sys.stdout as a StringIO instance and returns
    the instance.

    """
    stdout = io.StringIO()
    with mock.patch('sys.stdout', stdout):
        yield stdout


@contextlib.contextmanager
def captured_stderr():
    """
    Context manager which mocks sys.stderr as a StringIO instance and returns
    the instance.

    """
    stderr = io.StringIO()
    with mock.patch('sys.stderr', stderr):
        yield stderr
