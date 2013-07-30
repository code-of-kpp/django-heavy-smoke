import importlib
from collections import OrderedDict
import traceback
import re

from django.test import TestCase
from django.conf import settings
from django.test.client import Client


# first-touch TODO: improve re for analyzing re!
group_finder = re.compile('(\(\?P<(?P<name>[0-9a-zA-Z\-_]+)>[^\)]+\))',
    re.UNICODE)


def get_name(urlpart):
    return {
        'pk': (0, 1, 2, 3, -1),
        'content_type_id': (0, 1, 2, 3, -1),
        'path': ('bla', '/', 'c:\\', ' ', '..', '.'),
        '(.+)': ('bla', '/', 'c:\\', ' ', '..', '.'),
        # TODO: configure URL params somehow
    }.get(urlpart, (urlpart,))


def get_urls(urllist, urlbase=''):
    for entry in urllist:
        pattern = entry.regex.pattern
        if pattern.startswith('^'):
            pattern = pattern[1:]
        if pattern.endswith('$'):
            pattern = pattern[:-1]
        fullurl = (urlbase + pattern)
        yield fullurl, entry.callback
        if hasattr(entry, 'url_patterns'):
            for url in get_urls(entry.url_patterns, fullurl):
                yield url


def get_imported_urls():
    urls = importlib.import_module(settings.ROOT_URLCONF).urlpatterns
    for url in get_urls(urls):
        varlist = []
        for group, val in group_finder.findall(url[0]):
            varlist.append((group, get_name(val)))
        group = '(.+)'
        if group in url[0]:
            varlist.append((group, get_name(group)))

        yield (
            url[0],
            varlist,
            url[1].__name__ if url[1] else None,
            url[1].__module__ if url[1] else None,
        )


def urls_gen(url, args):
    if not args:
        yield url
    else:
        pattern, vals = args[0]
        for val in vals:
            new_url = url.replace(pattern, str(val))
            for gen_url in urls_gen(new_url, args[1:]):
                if '\.' in gen_url:
                    yield gen_url.replace('\.', '.')
                else:
                    yield gen_url


class TestViewsDontFallBase(object):

    #fixtures = ()

    def setUp(self):
        self.clients = []
        self.clients.append(('anonymous', Client(), None))
        self.clients.append(('admin', Client(),
                            ('admin', 'password')))
        # TODO: configure users for smoke test
        for name, client, credentials in self.clients:
            if not credentials:
                continue
            self.assertTrue(
                client.login(username=credentials[0],
                             password=credentials[1]),
                msg='Cannot login as a %s' % name
            )

    def generated_test_no_server_error(self,
                                        base_url, args, view, module):
        for url in urls_gen(base_url, args):
            where = ''

            if view:
                where += view + ' in ' + module + '\n\t'

            where += 'URL: ' + url

            for method in ('get', 'post',
                               #'put', 'delete', 'head', 'options'
                           ):
                for name, client, _ in self.clients:
                    try:
                        caller = getattr(client, method)
                        resp = caller('/' + url)
                        self.assertNotEqual(resp.status_code, 500,
                            'Status code 500 (%s) %s [%s]' %
                                (name, where, method)
                        )
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        self.fail('Raised exception: %r %s\n'
                                  '%s (%s) [%s]\n%s' %
                            (type(e), e, where, name, method,
                               traceback.format_exc()))


TestViewsDontFall = type(
    'TestViewsDontFall',
    (TestViewsDontFallBase, TestCase),
    OrderedDict((
        (
            'test' + str(id(base_url)) + '_' + str(id(args)),
            (lambda base_url, args, view, module: lambda self:
                self.generated_test_no_server_error(base_url,
                                                     args, view,
                                                     module))
                (base_url, args, view, module)
        )
            for base_url, args, view, module in get_imported_urls()
            # Comment to include standard django URLs in smode test
            if module and not module.startswith('django.')
    ))
)
