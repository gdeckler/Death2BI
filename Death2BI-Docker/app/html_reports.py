"""Import HTML as inert bytes; recognize versioned snapshots without running scripts."""
import base64
import json
from html.parser import HTMLParser


class SnapshotParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.found = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('id') == 'death2powerbi-snapshot':
            if self.found:
                raise ValueError('Duplicate snapshot package.')
            self.found = self.active = True

    def handle_endtag(self, tag):
        if tag == 'script': self.active = False

    def handle_data(self, data):
        if self.active: self.parts.append(data)


def inspect_html(content):
    try:
        source = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('HTML reports must be saved with UTF-8 encoding.')
    if not source.strip() or '\x00' in source:
        raise ValueError('The HTML report is empty or contains invalid text.')
    parser = SnapshotParser()
    parser.feed(source)
    if not parser.found:
        return source, None
    try:
        package = json.loads(base64.b64decode(''.join(parser.parts).strip(), validate=True))
        if package.get('format') != 'death2powerbi-snapshot' or package.get('version') != 1:
            raise ValueError('Unsupported snapshot format or version.')
        pages = package['pages']
        if not isinstance(pages, list) or not 1 <= len(pages) <= 500:
            raise ValueError('Snapshot must contain between 1 and 500 pages.')
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get('name'), str) or not isinstance(page.get('html'), str):
                raise ValueError('Invalid snapshot page.')
        return source, package
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError('Invalid Death2PowerBI snapshot package: ' + str(error))
