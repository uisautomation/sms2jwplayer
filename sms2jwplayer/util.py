"""
The :py:mod:`~sms2jwplayer.util` module contains general utility functions for the rest of the
program to use.

"""

import contextlib
import os
import sys

import jwplatform


class JWPlatformClientError(RuntimeError):
    """
    An error which is thrown if appropriate credentials for the jwplatform cannot be found in the
    environment.

    """
    pass


def get_jwplatform_client():
    """
    Examine the environment and return an authenticated jwplatform.Client instance. Raises
    JWPlatformClientError if credentials are not available

    """
    api_key = os.environ.get('JWPLAYER_API_KEY')
    if api_key is None:
        raise JWPlatformClientError('Set jwplayer API key in JWPLAYER_API_KEY environment '
                                    'variable')

    api_secret = os.environ.get('JWPLAYER_API_SECRET')
    if api_secret is None:
        raise JWPlatformClientError('Set jwplayer API secret in JWPLAYER_API_SECRET environment '
                                    'variable')

    return jwplatform.Client(api_key, api_secret)


@contextlib.contextmanager
def output_stream(opts, opt_key='--output'):
    """
    Given the docopt options dictionary, yield a file-like object suitable for writing output to.
    *opt_key* is the key used to retrieve the output file from the options.

    """
    out_file = opts[opt_key]

    if out_file is None:
        yield sys.stdout
    else:
        with open(out_file, 'w') as fobj:
            yield fobj


@contextlib.contextmanager
def input_stream(opts, opt_key):
    """
    Given the docopt options dictionary, yield a file-like object suitable for reading input from.
    *opt_key* is the key used to retrieve the input file from the options.

    """
    in_file = opts[opt_key]

    if in_file is None:
        yield sys.stdin
    else:
        with open(in_file) as fobj:
            yield fobj


def get_key_path(obj, keypath):
    """
    Given a dotted key path like "a.b.c", attempt to retrieve obj["a"]["b"]["c"]. If there is no
    such key at any stage, return None

    """
    for key in keypath.split('.'):
        if obj is None:
            return None
        obj = obj.get(key)
    return obj
