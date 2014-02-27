from __future__ import print_function, unicode_literals
from conceptnet5.uri import ROOT_URL
import sys
import urllib
import codecs

SAME_AS = 'http://www.w3.org/2002/07/owl#sameAs'


if sys.version_info.major >= 3:
    unquote = urllib.parse.unquote_to_bytes
    quote = urllib.parse.quote
    urlsplit = urllib.parse.urlsplit
    string_type = str
else:
    import urlparse
    urlsplit = urlparse.urlsplit
    unquote = urllib.unquote
    quote = urllib.quote
    string_type = basestring


def decode_url(url):
    """
    Take in a URL that is percent-encoded for use in a format such as HTML or
    N-triples, and convert it to a Unicode URL.

    If the URL is contained in angle brackets because it comes from an
    N-triples file, strip those.

    >>> decode_url('<http://dbpedia.org/resource/N%C3%BAria_Espert>')
    'http://dbpedia.org/resource/Núria_Espert'
    """
    return unquote(url.strip('<>')).decode('utf-8', 'replace')


def resource_name(url):
    """
    Get a concise name for a Semantic Web resource, given its URL.

    This is either the "fragment" identifier, or the path after '/resource/',
    or the item after the final slash.

    There's a special case for '/resource/' because resource names are Wikipedia
    article names, which are allowed to contain additional slashes.

    On a Semantic Web URL, this has the effect of getting an object's effective
    "name" while ignoring the namespace and details of where it is stored.

    >>> resource_name('<http://dbpedia.org/resource/N%C3%BAria_Espert>')
    'Núria_Espert'
    """
    parsed = urlsplit(decode_url(url))
    if parsed.fragment:
        return parsed.fragment
    else:
        path = parsed.path.strip('/')
        if '/resource/' in path:
            return path.split('/resource/')[-1]
        else:
            return path.split('/')[-1]


def full_conceptnet_url(uri):
    """
    Translate a ConceptNet URI into a fully-specified URL.

    >>> full_conceptnet_url('/c/en/dog')
    'http://conceptnet5.media.mit.edu/data/5.2/c/en/dog'
    """
    assert uri.startswith('/')
    return ROOT_URL + quote(uri)


class NTriplesWriter(object):
    """
    Write to a file in N-Triples format.

    N-Triples is a very simple format for expressing RDF relations. It is
    a sequence of lines of the form

    <node1> <relation> <node2> .

    The angle brackets are literally present in the lines, and the things
    they contain are URLs.

    The suggested extension for this format is '.nt'.
    """
    def __init__(self, filename_or_stream):
        if isinstance(filename_or_stream, string_type):
            self.stream = codecs.open(filename_or_stream, 'w', encoding='ascii')
        else:
            self.stream = filename_or_stream
        self.seen = set()

    def write(self, triple):
        """
        Write a triple of (node1, rel, node2) to a file, if it's not already
        there.
        """
        if triple not in self.seen:
            self.seen.add(triple)
            line = '<%s> <%s> <%s> .' % triple
            print(line, file=self.stream)

    def write_same_as(self, node1, node2):
        """
        Write a line expressing that node1 is the same as node2.
        """
        self.write((node1, SAME_AS, node2))

    def close(self):
        if self.stream is not sys.stdout:
            self.stream.close()


class NTriplesReader(object):
    """
    A class for reading multiple files in N-Triples format, keeping track of
    prefixes that they define and expanding them when they appear.
    """
    def __init__(self):
        self.prefixes = {}

    def parse_file(self, filename):
        for line in codecs.open(filename, encoding='utf-8'):
            line = line.strip()
            if line:
                result = self.parse_line(line)
                if result is not None:
                    yield result

    def parse_line(self, line):
        # Handle prefix definitions, which are lines that look like:
        # @prefix wn30: <http://purl.org/vocabularies/princeton/wn30/> .
        if line.startswith('@prefix'):
            _operator, prefix, url, dot = line.split(' ')
            assert dot == '.'
            prefixname = prefix.rstrip(':')
            self.prefixes[prefixname] = decode_url(url)
            return None
        else:
            subj, rel, obj, dot = line.split(' ')
            assert dot == '.'
            return self.resolve_node(subj), self.resolve_node(rel), self.resolve_node(obj)

    def resolve_node(self, encoded_url):
        """
        Given a Semantic Web node expressed in the N-Triples syntax, expand
        it to either its full, decoded URL or its natural language text
        (whichever is appropriate).

        Returns (lang, text), where `lang` is a language code or the string 'URL'.
        If `lang` is 'URL', the `text` is the expanded, decoded URL.

        >>> reader = NTriplesReader()
        >>> reader.parse_line('@prefix wn30: <http://purl.org/vocabularies/princeton/wn30/> .')
        >>> reader.resolve_node('wn30:synset-Roman_alphabet-noun-1')
        ('URL', 'http://purl.org/vocabularies/princeton/wn30/synset-Roman_alphabet-noun-1')
        >>> reader.resolve_node('<http://purl.org/vocabularies/princeton/wn30/>')
        ('URL', 'http://purl.org/vocabularies/princeton/wn30/')
        >>> reader.resolve_node('"Abelian group"@en-us')
        ('en', 'Abelian group')
        """
        if encoded_url.startswith('<') and encoded_url.endswith('>'):
            # This is a literal URL, so decode_url will handle it directly.
            return 'URL', decode_url(encoded_url)
        elif encoded_url.startswith('"'):
            quoted_string, lang_code = encoded_url.rsplit('@', 1)
            assert quoted_string.startswith('"') and quoted_string.endswith('"')
            lang = lang_code.split('-')[0]
            return lang, quoted_string[1:-1]
        else:
            prefix, resource = encoded_url.split(':', 1)
            if prefix not in self.prefixes:
                raise KeyError("Unknown prefix: %r" % prefix)
            url_base = self.prefixes[prefix]
            return 'URL', decode_url(url_base + resource)
