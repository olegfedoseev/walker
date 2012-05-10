#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Oleg Fedoseev <oleg.fedoseev@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from optparse import OptionParser
import urllib2
from urllib import urlencode
import datetime
import time
import zlib
import sys
import re
import os
from urllib2 import HTTPError

from collections import defaultdict

from StringIO import StringIO
import gzip

import ujson
import gevent
from gevent.monkey import patch_all
from gevent.pool import Pool
from gevent.server import DatagramServer

patch_all()

from hashlib import md5

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


class CodeHtmlFormatter(HtmlFormatter):
    def _highlight_lines(self, tokensource):
        hls = self.hl_lines
        line = """
          <tr%s>
            <td class="line">%d</td>
            <td class="hits"></td>
            <td class="source">%s</td>
          </tr>
        """
        for i, (t, value) in enumerate(tokensource):
            if t != 1:
                yield t, line % ('', i + 1, value)
            if i + 1 in hls:  # i + 1 because Python indexes start at 0
                yield 1, line % (' class="highlight"', i + 1, value)
            else:
                yield 1, line % ('', i + 1, value)

HEADER = u"""
<!DOCTYPE html>
<html>
<head>
    <title>Coverage</title>
    <script>
        headings = [];
        onload = function(){ headings = document.querySelectorAll('h2'); };
        onscroll = function(e){
          var heading = find(window.scrollY);
          if (!heading) return;
          var links = document.querySelectorAll('#menu a'), link;
          for (var i = 0, len = links.length; i < len; ++i) {
            link = links[i];
            link.className = link.getAttribute('href') == '#' + heading.id ? 'active' : '';
          }
        };

        function find(y) {
          var i = headings.length, heading;
          while (i--) {
            heading = headings[i];
            if (y > heading.offsetTop) {
              return heading;
            }
          }
        }
    </script>

    <style type="text/css">
        body {
          font: 14px/1.6 "Helvetica Neue", Helvetica, Arial, sans-serif;
          margin: 0;
          color: #2C2C2C;
          border-top: 2px solid #ddd;
        }

        #coverage { padding: 60px; }
        h1 a { color: inherit; font-weight: inherit; }
        h1 a:hover { text-decoration: none; }
        .onload h1 { opacity: 1; }
        h2 {
          width: 80%;
          margin-top: 80px;
          margin-bottom: 0;
          font-weight: 100;
          letter-spacing: 1px;
          border-bottom: 1px solid #eee;
        }

        a {
          color: #8A6343;
          font-weight: bold;
          text-decoration: none;
        }

        a:hover { text-decoration: underline;
        }

        ul {
          margin-top: 20px;
          padding: 0 15px;
          width: 100%;
        }

        ul li {
          float: left;
          width: 40%;
          margin-top: 5px;
          margin-right: 60px;
          list-style: none;
          border-bottom: 1px solid #eee;
          padding: 5px 0;
          font-size: 12px;
        }

        ul::after {
          content: '.';
          height: 0;
          display: block;
          visibility: hidden;
          clear: both;
        }

        code {
          font: 12px monaco, monospace;
        }

        pre {
          margin: 30px;
          padding: 30px;
          border: 1px solid #eee;
          border-bottom-color: #ddd;
          -webkit-border-radius: 2px;
          -moz-border-radius: 2px;
          -webkit-box-shadow: inset 0 0 10px #eee;
          -moz-box-shadow: inset 0 0 10px #eee;
          overflow-x: auto;
        }

        img {
          margin: 30px;
          padding: 1px;
          -webkit-border-radius: 3px;
          -moz-border-radius: 3px;
          -webkit-box-shadow: 0 3px 10px #dedede, 0 1px 5px #888;
          -moz-box-shadow: 0 3px 10px #dedede, 0 1px 5px #888;
          max-width: 100%;
        }

        footer {
          background: #eee;
          width: 100%;
          padding: 50px 0;
          text-align: right;
          border-top: 1px solid #ddd;
        }

        footer span {
          display: block;
          margin-right: 30px;
          color: #888;
          font-size: 12px;
        }

        #menu {
          position: fixed;
          font-size: 12px;
          top: 0;
          right: 0;
          margin: 0;
          height: 100%;
          padding: 15px 0;
          text-align: right;
          border-left: 1px solid #eee;
          -moz-box-shadow: 0 0 2px #888
             , inset 5px 0 20px rgba(0,0,0,.5)
             , inset 5px 0 3px rgba(0,0,0,.3);
          -webkit-box-shadow: 0 0 2px #888
             , inset 5px 0 20px rgba(0,0,0,.5)
             , inset 5px 0 3px rgba(0,0,0,.3);
          -webkit-font-smoothing: antialiased;
          background: url("data:image/png;base64,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");
        }

        #logo {
          position: fixed;
          bottom: 10px;
          right: 10px;
          background: rgba(255,255,255,.1);
          font-size: 11px;
          display: block;
          width: 20px;
          height: 20px;
          line-height: 20px;
          text-align: center;
          -webkit-border-radius: 20px;
          -moz-border-radius: 20px;
          -webkit-box-shadow: 0 0 3px rgba(0,0,0,.2);
          -moz-box-shadow: 0 0 3px rgba(0,0,0,.2);
          color: inherit;
        }

        #menu li a {
          display: block;
          color: white;
          padding: 0 35px 0 25px;
          -webkit-transition: background 300ms;
          -moz-transition: background 300ms;
        }

        #menu li {
          position: relative;
          list-style: none;
        }

        #menu a:hover,
        #menu a.active {
          text-decoration: none;
          background: rgba(255,255,255,.1);
        }

        #menu li:hover .cov {
          opacity: 1;
        }

        #menu li .dirname {
          opacity: .60;
          padding-right: 2px;
        }

        #menu li .basename {
          opacity: 1;
        }

        #menu .cov {
          background: rgba(0,0,0,.4);
          position: absolute;
          top: 0;
          right: 8px;
          font-size: 9px;
          opacity: .6;
          text-align: left;
          width: 17px;
          -webkit-border-radius: 10px;
          -moz-border-radius: 10px;
          padding: 2px 3px;
          text-align: center;
        }

        #stats:nth-child(2n) {
          display: inline-block;
          margin-top: 15px;
          border: 1px solid #eee;
          padding: 10px;
          -webkit-box-shadow: inset 0 0 2px #eee;
          -moz-box-shadow: inset 0 0 2px #eee;
          -webkit-border-radius: 5px;
          -moz-border-radius: 5px;
        }

        #stats div {
          float: left;
          padding: 0 5px;
        }

        #stats::after {
          display: block;
          content: '';
          clear: both;
        }

        #stats .sloc::after {
          content: ' SLOC';
          color: #b6b6b6;
        }

        #stats .percentage::after {
          content: ' coverage';
          color: #b6b6b6;
        }

        #stats .hits,
        #stats .misses {
          display: none;
        }

        .high {
          color: #00d4b4;
        }
        .medium {
          color: #e87d0d;
        }
        .low {
          color: #d4081a;
        }
        .terrible {
          color: #d4081a;
          font-weight: bold;
        }

        table {
          width: 80%;
          margin-top: 10px;
          border-collapse: collapse;
          border: 1px solid #cbcbcb;
          color: #363636;
          -webkit-border-radius: 3px;
          -moz-border-radius: 3px;
        }

        table thead {
          display: none;
        }

        table td.line,
        table td.hits {
          width: 20px;
          background: #eaeaea;
          text-align: center;
          font-size: 11px;
          padding: 0 10px;
          color: #949494;
        }

        table td.hits {
          width: 10px;
          padding: 2px 5px;
          color: rgba(0,0,0,.2);
          background: #f0f0f0;
        }

        tr.miss td.line,
        tr.miss td.hits {
          background: #e6c3c7;
        }

        tr.miss td {
          background: #f8d5d8;
        }

        td.source {
          padding-left: 15px;
          line-height: 15px;
          white-space: pre;
          font: 12px monaco, monospace;
        }

        code .comment { color: #ddd }
        code .init { color: #2F6FAD }
        code .string { color: #5890AD }
        code .keyword { color: #8A6343 }
        code .number { color: #2F6FAD }

        tr.highlight {
            background-color: #DCF7DD;
        }

        .hll { background-color: #ffffcc }
        .c { color: #586E75 } /* Comment */
        .err { color: #93A1A1 } /* Error */
        .g { color: #93A1A1 } /* Generic */
        .k { color: #859900 } /* Keyword */
        .l { color: #93A1A1 } /* Literal */
        .n { color: #93A1A1 } /* Name */
        .o { color: #859900 } /* Operator */
        .x { color: #CB4B16 } /* Other */
        .p { color: #93A1A1 } /* Punctuation */
        .cm { color: #586E75 } /* Comment.Multiline */
        .cp { color: #859900 } /* Comment.Preproc */
        .c1 { color: #586E75 } /* Comment.Single */
        .cs { color: #859900 } /* Comment.Special */
        .gd { color: #2AA198 } /* Generic.Deleted */
        .ge { color: #93A1A1; font-style: italic } /* Generic.Emph */
        .gr { color: #DC322F } /* Generic.Error */
        .gh { color: #CB4B16 } /* Generic.Heading */
        .gi { color: #859900 } /* Generic.Inserted */
        .go { color: #93A1A1 } /* Generic.Output */
        .gp { color: #93A1A1 } /* Generic.Prompt */
        .gs { color: #93A1A1; font-weight: bold } /* Generic.Strong */
        .gu { color: #CB4B16 } /* Generic.Subheading */
        .gt { color: #93A1A1 } /* Generic.Traceback */
        .kc { color: #CB4B16 } /* Keyword.Constant */
        .kd { color: #268BD2 } /* Keyword.Declaration */
        .kn { color: #859900 } /* Keyword.Namespace */
        .kp { color: #859900 } /* Keyword.Pseudo */
        .kr { color: #268BD2 } /* Keyword.Reserved */
        .kt { color: #DC322F } /* Keyword.Type */
        .ld { color: #93A1A1 } /* Literal.Date */
        .m { color: #2AA198 } /* Literal.Number */
        .s { color: #2AA198 } /* Literal.String */
        .na { color: #93A1A1 } /* Name.Attribute */
        .nb { color: #B58900 } /* Name.Builtin */
        .nc { color: #268BD2 } /* Name.Class */
        .no { color: #CB4B16 } /* Name.Constant */
        .nd { color: #268BD2 } /* Name.Decorator */
        .ni { color: #CB4B16 } /* Name.Entity */
        .ne { color: #CB4B16 } /* Name.Exception */
        .nf { color: #268BD2 } /* Name.Function */
        .nl { color: #93A1A1 } /* Name.Label */
        .nn { color: #93A1A1 } /* Name.Namespace */
        .nx { color: #93A1A1 } /* Name.Other */
        .py { color: #93A1A1 } /* Name.Property */
        .nt { color: #268BD2 } /* Name.Tag */
        .nv { color: #268BD2 } /* Name.Variable */
        .ow { color: #859900 } /* Operator.Word */
        .w { color: #93A1A1 } /* Text.Whitespace */
        .mf { color: #2AA198 } /* Literal.Number.Float */
        .mh { color: #2AA198 } /* Literal.Number.Hex */
        .mi { color: #2AA198 } /* Literal.Number.Integer */
        .mo { color: #2AA198 } /* Literal.Number.Oct */
        .sb { color: #586E75 } /* Literal.String.Backtick */
        .sc { color: #2AA198 } /* Literal.String.Char */
        .sd { color: #93A1A1 } /* Literal.String.Doc */
        .s2 { color: #2AA198 } /* Literal.String.Double */
        .se { color: #CB4B16 } /* Literal.String.Escape */
        .sh { color: #93A1A1 } /* Literal.String.Heredoc */
        .si { color: #2AA198 } /* Literal.String.Interpol */
        .sx { color: #2AA198 } /* Literal.String.Other */
        .sr { color: #DC322F } /* Literal.String.Regex */
        .s1 { color: #2AA198 } /* Literal.String.Single */
        .ss { color: #2AA198 } /* Literal.String.Symbol */
        .bp { color: #268BD2 } /* Name.Builtin.Pseudo */
        .vc { color: #268BD2 } /* Name.Variable.Class */
        .vg { color: #268BD2 } /* Name.Variable.Global */
        .vi { color: #268BD2 } /* Name.Variable.Instance */
        .il { color: #2AA198 } /* Literal.Number.Integer.Long */
    </style>
</head>
"""

HTML = """
<body>
<div id="coverage">
    <h1 id="overview">%(title)s</h1>

    <div id="menu">
        <li><a href="#overview">overview</a></li>
        %(menu)s
    </div>

    <div id="stats" class="high">
        <div class="percentage">%(percentage)3.2f%%</div>
        <div class="sloc">%(sloc)s</div>
        <div class="hits">%(hits)s</div>
        <div class="misses">%(misses)s</div>
    </div>

    <div id="files">
        %(files)s
    </div>
</div>
</body>
</html>
"""

MENU_FILE = """
        <li>
            <span class="cov high">%(percentage)3.0f</span>
            <a href="#%(file_id)s">
                <span class="basename">%(basename)s</span>
            </a>
        </li>
"""

MENU_DIR = """
        <li>
            <span class="cov high">%(percentage)3.0f</span>
            <a href="#%(file_id)s">
                <span class="dirname">%(dirname)s</span>
                <span class="basename">%(basename)s</span>
            </a>
        </li>
"""

FILE = """
        <div class="file">
            <h2 id="%(file_id)s">%(filename)s</h2>
            <div id="stats" class="high">
                <div class="percentage">%(percentage)3.2f%%</div>
                <div class="sloc">%(sloc)s</div>
                <div class="hits">%(hits)s</div>
                <div class="misses">%(misses)s</div>
            </div>

            <table>
                <tbody>
                %(table)s
                </tbody>
            </table>
        </div>
"""


def generate_report(coverage=None, output='report.html'):
    lexer = get_lexer_by_name("php", stripall=True, encoding="utf-8")

    if not coverage:
        with open('/tmp/walker.json', 'r') as f:
            coverage = ujson.decode(f.read())

    prefix = os.path.commonprefix(coverage.keys())
    menu = []
    code = []
    sum_sloc = 0
    sum_hits = 0

    for filename in sorted(coverage.keys(), reverse=True):
        try:
            source = open(filename).read()
        except OSError, e:
            print e
            continue
        sloc = len(source.split('\n'))
        sum_sloc = sum_sloc + sloc
        file_id = md5(filename).hexdigest()
        lines_cov = sorted([int(str(l)) for l in coverage[filename].keys()])
        hits = len(lines_cov)
        sum_hits = sum_hits + hits
        formatter = CodeHtmlFormatter(linenos=True, hl_lines=lines_cov, nowrap=True, encoding="utf-8")

        result = {
            'table': highlight(source, lexer, formatter).decode("utf-8"),
            'file_id': file_id,
            'filename': filename.replace(prefix, ''),
            'basename': os.path.basename(filename),
            'dirname': os.path.dirname(filename.replace(prefix, '')),
            'sloc': sloc,
            'hits': hits,
            'misses': sloc - hits,
            'percentage': (float(hits) / float(sloc)) * 100.0
        }

        if result['basename'] != result['filename']:
            menu.append(MENU_DIR % result)
        else:
            menu.append(MENU_FILE % result)
        code.append(FILE % result)

    report = HTML % {
        'files': '\n\n'.join(code),
        'menu': '\n\n'.join(menu),
        'title': "Coverage for %s" % prefix,
        'sloc': sum_sloc,
        'hits': sum_hits,
        'misses': sum_sloc - sum_hits,
        'percentage': (float(sum_hits) / float(sum_sloc)) * 100.0
    }

    with open(output, 'w+') as f:
        f.write(HEADER.encode("utf-8", 'ignore') + report.encode("utf-8", 'ignore'))
        f.close()


def html_escape(text):
    """Produce entities within text."""
    html_escape_table = {"&": "&amp;", '"': "&quot;", "'": "&apos;", ">": "&gt;", "<": "&lt;", "\t": "    "}
    return "".join(html_escape_table.get(c, c) for c in text)


class NoneContext(object):
    def __enter__(self):
        return None

    def __exit__(self, exc, value, traceback):
        return True


class ResponseError(Exception):
    pass


class HttpResponse(object):
    url = None
    code = None
    data = None
    catch_response = False
    allow_http_error = False
    _trigger_success = None
    _trigger_failure = None

    def __init__(self, method, url, name, code, data, info, gzip):
        self.method = method
        self.url = url
        self._name = name
        self.code = code
        self.data = data
        self._info = info
        self._gzip = gzip
        self._decoded = False

    @property
    def info(self):
        return self._info()

    def _get_data(self):
        if self._gzip and not self._decoded and self._info().get("Content-Encoding") == "gzip":
            self._data = gzip.GzipFile(fileobj=StringIO(self._data)).read()
            self._decoded = True
        return self._data

    def _set_data(self, data):
        self._data = data

    def __enter__(self):
        if not self.catch_response:
            raise ResponseError("If using response in a with() statement you must use catch_response=True")
        return self

    def __exit__(self, exc, value, traceback):
        if exc:
            if isinstance(value, ResponseError):
                self._trigger_failure(value)
            else:
                raise value
        else:
            self._trigger_success()
        return True

    data = property(_get_data, _set_data)


class HttpBrowser(object):
    def __init__(self, base_url, gzip=False):
        self.base_url = base_url
        self.gzip = gzip
        handlers = [urllib2.HTTPCookieProcessor()]
        self.opener = urllib2.build_opener(*handlers)
        urllib2.install_opener(self.opener)

    def request(self, method, path, data=None, headers={}, name=None):
        if self.gzip:
            headers["Accept-Encoding"] = "gzip"

        if data is not None:
            try:
                data = urlencode(data)
            except TypeError:
                pass  # ignore if someone sends in an already prepared string

        url = self.base_url + path
        request = urllib2.Request(url, data, headers)
        request.get_method = lambda: method
        try:
            f = self.opener.open(request)
            data = f.read()
            f.close()
        except HTTPError, e:
            data = e.read()
            e.locust_http_response = HttpResponse(method, url, name, e.code, data, e.info, self.gzip)
            e.close()
            raise e

        return HttpResponse(method, url, name, f.code, data, f.info, self.gzip)


class CoverageServer(DatagramServer):
    chunk = 0
    data = ""
    coverage = defaultdict(dict)
    lines = False
    path = None

    def lines(self, only_line=False):
        self.lines_only = only_line
        return self

    def path(self, path=False):
        self.prefix = path
        return self

    def handle(self, data, address):
        if len(data) == 8192:
            self.chunk = self.chunk + 1
            self.data = self.data + data
            return
        if self.chunk > 0:
            data = self.data + data
            self.chunk = 0
            self.data = ""

        try:
            report = ujson.decode(zlib.decompress(data))
        except OSError, e:
            print e
        """
        'coverage' => $coverage,
        'pinba' => Ngs_Debug::pinbaRaw()
        """

        #request = "http://%s%s" % (report['server'], report['uri'])
        query = "http://%s%s" % (report['server'], report['query'])
        #pinba = report['pinba']
        #group = report['group']

        for filename, lines in report['coverage'].items():
            filename = str(filename)
            if self.prefix and self.prefix not in filename:
                continue
            if '/data/tmp/' in filename:  # skip templates
                continue

            for line in lines.keys():
                self.process_line(filename, int(line), query)

        #print "Got report for", request, query, group, pinba['request']['time']['human'], len(coverage)

    def process_line(self, filename, lineno, query):
        if line not in self.coverage[filename].keys():
            self.coverage[filename][lineno] = 0 if self.lines else []

        if self.lines:
            self.coverage[filename][lineno] = self.coverage[filename][lineno] + 1
        else:
            self.coverage[filename][lineno].append(query)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-u", "--urls", dest="urls", help="path to urls file")
    parser.add_option("-g", "--group", dest="group", help="code coverage group", default="walker")
    parser.add_option("-r", "--regex", dest="regex", help="regex to match urls", default=None)
    parser.add_option("-o", "--report", dest="report", help="file name for report")
    parser.add_option("-l", "--lines", dest="lines", help="collect only lines, not count", action="store_true", default=False)
    parser.add_option("-p", "--path", dest="path", help="path to collect coverage for", default=None)
    parser.add_option("-v", "--verbose", dest="verbose", help="verbose output", action="store_true", default=False)
    (options, args) = parser.parse_args()

    host = "127.0.0.1"
    port = 5555

    if not options.urls:
        sys.stderr.write("No urls file specified!\n")
        parser.print_usage()
        sys.exit(1)

    if not options.report:
        sys.stderr.write("No report filename specified!\n")
        parser.print_usage()
        sys.exit(1)

    client = HttpBrowser('', True)
    headers = {'X-Walker': 'yes', 'X-Walker-Group': options.group, 'X-Walker-Host': host, 'X-Walker-Port': port}
    if options.regex:
        regex = re.compile(options.regex)
        urls = [line.rstrip() for line in open(options.urls) if re.search(options.regex, line)]
        print len(urls), "urls in file", options.urls, "matched by regex", options.regex
    else:
        urls = [line.rstrip() for line in open(options.urls)]
        print len(urls), "urls in file", options.urls

    def walker(urls, client, headers, server):
        idx = 0
        for url in urls:
            t = time.time()
            idx = idx + 1
            url = url.replace(".ru", ".ru.mm.t0")
            progress = "%04d/%04d" % (idx, len(urls))
            result = client.request('GET', url, headers=headers)  # , allow_http_error=True)
            if not result:
                print progress, 'result is none!', url
            else:
                print progress, "%3.3f %d %d: %s" % (time.time() - t, result.code, len(result.data), url)
        server.stop()

    pool = Pool(100)
    server = CoverageServer("%s:%d" % (host, int(port)), spawn=pool)
    server.lines(options.lines).path(options.path)
    print "Start at", datetime.datetime.now()
    t = time.time()
    try:
        gevent.spawn(walker, urls, client, headers, server)
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
    except Exception, e:
        print e

    print "Stop walking at", datetime.datetime.now(), "walk for %3.4fsec" % (time.time() - t)
    generate_report(server.coverage, options.report)
    print "Report saved to %s" % options.report
    print "Bye, bye!"
