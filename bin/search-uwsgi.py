#!/usr/bin/python3
# uwsgi script to show search results

# from wsgiref.simple_server import make_server
from urllib.parse import parse_qs, urlencode
from jinja2 import Environment, PackageLoader, select_autoescape
from os import environ
from sys import exc_info
from requests import get
from copy import deepcopy

SOLR_URL=environ.get('SOLR_URL')
SOLR_CORE=environ.get('SOLR_CORE')
TEMPLATE_DIR='../templates'

env = Environment(
            loader=PackageLoader('search-uwsgi', TEMPLATE_DIR),
            autoescape=True)
search_results = env.get_template('search-results.html.j2')

def application(params, start_response):
    query_str = params.get('QUERY_STRING')
    if query_str == None:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Error: No query string']
    d = parse_qs(query_str)

    query = d.get('query', [''])[0]

    try:
        start = d.get('start', [0])[0]
        start = int(start)
    except:
        start = 0

    try:
        query_params = {
            "defType": "dismax",
            "facet": "true",
            "facet.field": "releases",
            "rows": 20,
            "start": start,
            "q": query,
            "qf": "name^2 srcName^1.5 summary^0.75",
            "fq": []
        }

        if not d.get("show_related", False):
            query_params["fq"].append("{!collapse field=srcName_string}")

        for release in d.get('releases', []):
            query_params["fq"].append(f"releases:\"{release}\"")

        query_res = get(f"{SOLR_URL}solr/{SOLR_CORE}/select?{urlencode(query_params, True)}")
    except:
        print("Solr request error: ", str(exc_info()[0]))
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Error communicating with Solr']

    if query_res.ok:
        results_html = search_results.render(results=query_res.json(), qdict=d, modify_query=modify_query)
        start_response('200 OK', [('Content-Type','text/html')])
        return [bytes(results_html, 'utf-8')]
    else:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b'Solr query error']

def modify_query(qdict, **new_values):
    finaldict = deepcopy(qdict)
    for key, value in new_values.items():
        # if faceting, remove if found otherwise add
        if key == "releases":
            if key not in finaldict:
                finaldict[key] = []

            try:
                index = finaldict[key].index(value)
                finaldict[key].pop(index)
            except ValueError:
                finaldict[key].append(value)
        elif key == "show_related":
            try:
                finaldict.pop(key)
            except KeyError:
                finaldict[key] = value
        else:
            finaldict[key] = value

    return urlencode(finaldict, True)
