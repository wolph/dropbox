from __future__ import absolute_import

import base64
import re
import os
import sys
import urllib
from StringIO import StringIO
try:
    import json
except ImportError:
    import simplejson as json

from .rest import ErrorResponse, RESTClient
from .session import BaseSession, DropboxSession, DropboxOAuth2Session
from . import metadata


def format_path(path):
    '''Normalize path for use with the Dropbox API.

    This function turns multiple adjacent slashes into single
    slashes, then ensures that there's a leading slash but
    not a trailing slash.
    '''
    if not path:
        return path

    path = re.sub(r'/+', '/', path)

    if path == '/':
        return (u'' if isinstance(path, unicode) else '')
    else:
        return '/' + path.strip('/')


class DropboxClient(object):

    '''
    The class that lets you make Dropbox API calls.  You'll need to obtain an
    OAuth 2 access token first.  You can get an access token using either
    :class:`DropboxOAuth2Flow` or :class:`DropboxOAuth2FlowNoRedirect`.

    Args:
      - ``oauth2_access_token``: An OAuth 2 access token (string).
      - ``rest_client``: A :class:`dropbox.rest.RESTClient`-like object to use
        for making requests. [optional]

    All of the API call methods can raise a
    :class:`dropbox.rest.ErrorResponse` exception if the server returns a
    non-200 or invalid HTTP response. Note that a 401 return status at any
    point indicates that the access token you're using is no longer valid and
    the user must be put through the OAuth 2 authorization flow again.
    '''

    def __init__(self, oauth2_access_token, locale=None, rest_client=None):
        if rest_client is None:
            rest_client = RESTClient
        if isinstance(oauth2_access_token, basestring):
            self.session = DropboxOAuth2Session(oauth2_access_token, locale)
        elif isinstance(oauth2_access_token, DropboxSession):
            # Backwards compatibility with OAuth 1
            if locale is not None:
                raise ValueError(
                    'The "locale" parameter to DropboxClient is only useful '
                    'when also passing in an OAuth 2 access ' 'token')
            self.session = oauth2_access_token
        else:
            raise ValueError('"oauth2_access_token" must either be a string '
                             'or a DropboxSession')
        self.rest_client = rest_client

    def request(self, target, params=None,
                method='POST', content_server=False):
        '''
        An internal method that builds the url, headers, and params for a
        Dropbox API request.  It is exposed if you need to make API calls not
        implemented in this library or if you need to debug requests.

        Args:
            - ``target``: The target URL with leading slash (e.g. '/files')
            - ``params``: A dictionary of parameters to add to the request
            - ``method``: An HTTP method (e.g. 'GET' or 'POST')
            - ``content_server``: A boolean indicating whether the request is
              to the API content server, for example to fetch the contents of
              a file rather than its metadata.

        Returns:
            - A tuple of ``(url, params, headers)`` that should be used to
              make the request.  OAuth will be added as needed within these
              fields.
        '''
        assert method in [
            'GET', 'POST', 'PUT'], 'Only GET, POST, and PUT are allowed.'
        if params is None:
            params = {}

        host = (
            self.session.API_CONTENT_HOST
            if content_server
