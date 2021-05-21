#!/usr/bin/python3
#
# Naming conventions used in this script:
#   * product: fedora, epel
#   * release: fedora-31, epel-7, ...
#   * branch: base (= none), updates, updates-testing
#   * release_branch: fedora-31, fedora-31-updates, fedora-31-updates-testing, ...
import os
import re
import sys
import json
import shutil
import sqlite3
import argparse
import requests

from datetime import date
from collections import defaultdict
from xml.etree.ElementTree import Element, tostring

SOLR_URL=os.environ.get('SOLR_URL')
SOLR_CORE=os.environ.get('SOLR_CORE')
DBS_DIR=os.environ.get('DB_DIR') or "repositories"
SCM_MAINTAINER_MAPPING=os.environ.get('MAINTAINER_MAPPING') or "pagure_owner_alias.json"

class Package:
    def __init__(self, name):
        self.name = name
        self.summary = ""
        self.description = ""

        self.license = "unknown"
        self.upstream = ""
        self.maintainers = []
        self.releases = {}
        self.subpackage_of = None
        self.subpackages = []

    def set_release(self, name, pkgKey, branch, revision):
        if name not in self.releases:
            self.releases[name] = {}

        if branch not in self.releases[name]:
            self.releases[name][branch] = {}

        self.releases[name][branch]['revision'] = revision
        self.releases[name][branch]['pkg_key'] = pkgKey

    def get_release(self, name):
        return self.releases[name]

    def source(self):
        if self.subpackage_of == None:
            return self.name
        else:
            return self.subpackage_of

def open_db(db):
    conn = sqlite3.connect(os.path.join(DBS_DIR, db))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    return (conn, c)

def main():
    # Load maintainer mapping (imported from dist-git).
    # TODO: check that mapping exist / error.
    print("Loading maintainer mapping...")
    with open(SCM_MAINTAINER_MAPPING) as raw:
        maintainer_mapping = json.load(raw)

    # Group databases files.
    databases = {}
    db_pattern = re.compile('^(fedora|epel)-([\w|-]+)_(primary|filelists|other).sqlite$')
    for db in os.listdir(DBS_DIR):
        if (not db_pattern.match(db)):
            sys.exit("Invalid object in {}: {}".format(DBS_DIR, db))

        (product, branch, db_type) = db_pattern.findall(db)[0]
        release_branch = "{}-{}".format(product, branch)
        if release_branch in databases:
            databases[release_branch][db_type] = db
        else:
            databases[release_branch] = { db_type: db }

    # Build internal package metadata structure / cache.
    packages = {}
    srpm_pattern = re.compile("^(.+)-.+-.+.src.rpm$")
    changelog_mail_pattern = re.compile("<(.+@.+)>")
    release_branch_pattern = re.compile("^([fedora|epel]+-[\w|\d]+)-?([a-z|-]+)?$")
    for release_branch in databases.keys():
        print("> Processing database files for {}.".format(release_branch))

        for db_type in ["primary", "filelists", "other"]:
            if db_type not in databases[release_branch]:
                sys.exit("No {} database for {}.".format(db_type, release_branch))

        (_, primary) = open_db(databases[release_branch]["primary"])
        (_, filelist) = open_db(databases[release_branch]["filelists"])
        (_, other) = open_db(databases[release_branch]["other"])

        for raw in primary.execute('SELECT * FROM packages'):
            pkg = packages.get(raw["name"])
            revision = "{}-{}".format(raw["version"], raw["release"])
            first_pkg_encounter = False

            # Register unknown packages.
            if pkg == None:
                pkg = Package(raw["name"])
                packages[pkg.name] = pkg
                first_pkg_encounter = True

            # Override package metadata with rawhide (= lastest) values.
            if first_pkg_encounter or release_branch == "rawhide":
                pkg.summary = raw["summary"]
                pkg.description = raw["description"]
                pkg.upstream = raw["url"]
                pkg.license = raw["rpm_license"]
                pkg.maintainers = maintainer_mapping["rpms"].get(pkg.name, [])

            # Handle subpackage specific case.
            (srpm_name) = srpm_pattern.findall(raw["rpm_sourcerpm"])[0]
            if pkg.name != srpm_name:
                pkg.subpackage_of = srpm_name

            # XXX: we do not resolve files and changelog here because storing
            # them in the packages hash would require multiple GBs of RAM
            # (roughly 1GB per repository).

            # Always register branch-specific metadata.
            (release, branch) = release_branch_pattern.findall(release_branch)[0]
            if branch == "":
                branch = "base"

            pkg.set_release(release, raw["pkgKey"], branch, revision)

    # Set license and maintainers for subpackages. We have to wait for all
    # packages to have been processed since subpackage might have been
    # processed before its parent.
    print(">> Handling subpackages...")
    for pkg in packages.values():
        if pkg.subpackage_of != None:
            parent = packages.get(pkg.subpackage_of)
            if parent != None:
                parent.subpackages += [pkg.name]
                pkg.maintainers = packages[pkg.subpackage_of].maintainers

    print(">>> {} packages have been extracted.".format(len(packages)))

    print("Sending data to Solr index...")

    pkg_xml = Element('add')
    pkg_count = 0
    max_pkg_count = len(packages)

    # Submit packages to Solr index, 500 at a time.
    for pkg in packages.values():
        pkg_el = Element('doc')

        pkg_el_name = Element('field', { "name": "id" })
        pkg_el_name.text = pkg.name
        pkg_el.append(pkg_el_name)

        pkg_el_desc = Element('field', { "name": "description" })
        pkg_el_desc.text = pkg.description
        pkg_el.append(pkg_el_desc)

        pkg_xml.append(pkg_el)

        pkg_count += 1
        if (pkg_count % 500 == 0 or pkg_count == max_pkg_count):
            requests.post(f"{SOLR_URL}solr/{SOLR_CORE}/update?commit={str(pkg_count == max_pkg_count).lower()}", data=tostring(pkg_xml), headers={'Content-Type': 'application/xml'})
            pkg_xml.clear()
            # print("Submitted {}/{} packages.".format(pkg_count, max_pkg_count))

    print("DONE.")
    print("> {} packages submitted to solr.".format(len(packages)))

if __name__ == '__main__':
    main()
