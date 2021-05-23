#!/usr/bin/python3
# uwsgi script to show search results

# from wsgiref.simple_server import make_server
from urllib.parse import parse_qs
from jinja2 import Environment, PackageLoader, select_autoescape
from os import environ
from sys import exc_info
from urllib.parse import quote
from requests import get

SOLR_URL=environ.get('SOLR_URL')
SOLR_CORE=environ.get('SOLR_CORE')
TEMPLATE_DIR='../templates'

env = Environment(
            loader=PackageLoader('search-uwsgi', TEMPLATE_DIR),
            autoescape=select_autoescape(['html']))
search_results = env.get_template('search-results.html.j2')

def application(params, start_response):
    query_str = params.get('QUERY_STRING')
    if query_str == None:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Error: No query string']
    d = parse_qs(query_str)
    query = d.get('query', [''])[0]
    query = quote(query)

    try:
        query_res = get(f"{SOLR_URL}solr/{SOLR_CORE}/select?defType=simple&q={query}")
    except:
        print("Solr request error: ", str(exc_info()[0]))
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Error communicating with Solr']

    if query_res.ok:
        results_html = search_results.render(results=query_res.json())
        start_response('200 OK', [('Content-Type','text/html')])
        return [bytes(results_html, 'utf-8')]
    else:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Solr query error']
