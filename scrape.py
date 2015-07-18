import collections
import datetime
import html.parser
import json
import re
import urllib.request
import urllib.parse
import uuid
import xml.etree.ElementTree as XML

ARTICLE_HEURISTIC_THRESHOLD = 10
COUNT = 5
RSS_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S'
RSS_FEEDS = {'ars': 'http://feeds.arstechnica.com/arstechnica/index',
             'bbc_tech': 'http://feeds.bbci.co.uk/news/technology/rss.xml',
             'ign': 'http://feeds.ign.com/ign/articles',
             'techcrunch': 'http://feeds.feedburner.com/Mobilecrunch',
             'uxbooth': 'http://feedpress.me/uxbooth'}
XQ_ITEM = 'channel/item'
XQ_ITEM_AUTHOR = '{http://purl.org/dc/elements/1.1/}creator'
XQ_ITEM_DATE = 'pubDate'
XQ_ITEM_LINK = 'link'
XQ_ITEM_TITLE = 'title'


def main():
    for source in RSS_FEEDS.items():
        manifest = fetch_manifest(source)
        try:
            for link, title, author, date_posted in extract_metadata(manifest):
                url, text = fetch_article_contents(link)
                document = generate_document(source, url, title, author, date_posted, text)
                save_document(document)
        except ExtractionError as error:
            log_error(error)


def extract_metadata(document):
    nodes = document.findall(XQ_ITEM)
    log_message('extract_metadata: found {} articles'.format(len(nodes)))
    links = []
    for node in nodes:
        title = node.findtext(XQ_ITEM_TITLE)
        link = node.findtext(XQ_ITEM_LINK)
        date_posted = node.findtext(XQ_ITEM_DATE)
        author = node.findtext(XQ_ITEM_AUTHOR)
        links.append((link, title, author, date_posted))
    return links


def fetch_article_contents(url):
    log_message('fetch_article_contents: `{}`', url)
    contents = urllib.request.urlopen(url)
    parser = ArticleParser()
    parser.feed(contents.read().decode('utf-8'))
    text = ''.join(['<p>{}</p>'.format(s) for s in parser.get_paragraphs()])
    return (contents.geturl(), text)


def fetch_manifest(source):
    _, url = source
    log_message('fetch_manifest: `{0}`', url)
    with urllib.request.urlopen(url) as response:
        raw_bytes = response.read()
        return XML.fromstring(raw_bytes)


def generate_document(source, url, title, author, date_posted, text):
    source_id, _ = source
    document = {}
    document['id']         = generate_id(source_id, url)
    document['headline']   = normalize_text(title)
    document['text']       = normalize_text(text)
    document['authorName'] = normalize_text(author)
    document['timestamp']  = normalize_date(date_posted)
    document['permalink']  = url
    return document


def generate_filename(url):
    url = re.sub(r'[\?#].*$', '', url)
    url = re.sub(r'\W+', '-', url)
    return url + '.json'


def generate_id(source_id, url):
    url = urllib.parse.urlparse(url)
    composites = []
    for s in url.path.split('/'):
        # Heuristics to filter out slug components
        if s.isnumeric(): continue
        if not re.match(r'(.+[-_]|[-_].+)+', s): continue
        s = re.sub(r'\W+', '-', s)  # Normalize
        composites.append(s)

    if not composites:
        hashed_url = str(uuid.uuid3(uuid.NAMESPACE_URL, url.geturl()))
        composites.append(hashed_url)

    slug = ':'.join(composites)
    return '/'.join([source_id, slug])


def log_error(error):
    print('{1}\n{0}\n{1}'.format(error, ''.center(80, '!')))


def log_message(message, *params):
    print(message.format(*params))


def normalize_date(value):
    then = datetime.datetime(1970, 1, 1)
    try:
        truncated = value[0:25]  # TODO cry about this
        then = datetime.datetime.strptime(truncated, RSS_DATE_FORMAT)
    except:
        pass  # Will return the epoch
    finally:
        return then.isoformat() + 'Z'


def normalize_text(value):
    if value:
        return value.strip()
    return ''


def save_document(document):
    filename = generate_filename(document.get('permalink'))
    log_message('save_document: {}', filename)
    with open(filename, 'w') as fp:
        fp.write(json.dumps(document, sort_keys=True, indent=2))


## SUPPORTING JUNK

class ArticleParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.fragments = []
        self.tag_stack = []
        self.registry = collections.OrderedDict()

    def handle_starttag(self, tag, attrib):
        self.tag_stack.append(tag)

    def handle_endtag(self, tag):
        if self.inside_paragraph() and tag == 'p':
            path = '/'.join(self.tag_stack)
            paragraph = ''.join(self.fragments).strip()
            paragraph = re.sub('\s+', ' ', paragraph)  # Collapse whitespace
            self.registry.setdefault(path, []).append(paragraph)
            self.fragments.clear()
        del self.tag_stack[-1]

    def inside_paragraph(self):
        return 'p' in self.tag_stack

    def handle_data(self, data):
        if self.inside_paragraph():
            self.fragments.append(data)

    def get_paragraphs(self):
        paragraphs = []
        for path, candidates in self.registry.items():

            # Large concentration of <p> tags in one container
            heuristic_score = len(candidates)

            # Big bonus if any ancestor is an <article>
            if '/article/' in path: heuristic_score += int(ARTICLE_HEURISTIC_THRESHOLD * 0.8)

            if heuristic_score >= ARTICLE_HEURISTIC_THRESHOLD:
                paragraphs += candidates

        return paragraphs


class ExtractionError(Exception):
    def __init__(self, message, node):
        self.message = message
        self.node = node
    def __str__(self):
        output = 'ExtractionError: {}'.format(self.message)
        if XML.iselement(self.node):
            output += '\n\nXML:\n{}'.format(XML.tostring(self.node))
        return output


## BOOTSTRAPPING

if '__main__' == __name__:
    main()
