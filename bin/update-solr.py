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
import sqlite3
import requests
import defusedxml
import time

# This is used to encode xml, not parse it. Security warning is irrelevant.
# defusedxml does not have an Element import and defuse_stdlib() is called anyway for caution's sake.
from xml.etree.ElementTree import Element, tostring # nosec

SOLR_URL=os.environ.get('SOLR_URL')
SOLR_CORE=os.environ.get('SOLR_CORE')
SOLR_CONF_SET="packages"
DBS_DIR=os.environ.get('DB_DIR') or "repositories"
SCM_MAINTAINER_MAPPING=os.environ.get('MAINTAINER_MAPPING') or "pagure_owner_alias.json"
PRODUCT_VERSION_MAPPING=os.environ.get('PRODUCT_VERSION_MAPPING') or "product_version_mapping.json"

class Package:
    def __init__(self, name):
        self.name = name
        self.summary = "No summary specified."
        self.description = "No description specified."

        self.license = "unknown"
        self.upstream = ""
        self.maintainers = []
        self.releases = {}
        self.source = ""

    def set_release(self, name, pkgKey, branch, arch, revision, human_name=None):
        if name not in self.releases:
            self.releases[name] = {}

        if 'branches' not in self.releases[name]:
            self.releases[name]['branches'] = {}

        if branch not in self.releases[name]:
            self.releases[name]['branches'][branch] = {}

        self.releases[name]['branches'][branch]['revision'] = revision
        self.releases[name]['branches'][branch]['pkg_key'] = pkgKey
        self.releases[name]['branches'][branch]['arch'] = arch
        self.releases[name]['human_name'] = human_name or name

    def get_release(self, name):
        return self.releases[name]['branches']

def open_db(db):
    conn = sqlite3.connect(os.path.join(DBS_DIR, db))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    return (conn, c)

def do_regex(pattern, string):
    (result) = pattern.findall(string)[0]
    return result

def main():
    # Load maintainer mapping (imported from dist-git).
    # TODO: check that mapping exist / error.
    print("Loading maintainer mapping...")
    with open(SCM_MAINTAINER_MAPPING) as raw:
        maintainer_mapping = json.load(raw)

    # Load product release->name mapping
    print("Loading release name mapping...")
    with open(PRODUCT_VERSION_MAPPING) as raw:
        release_mapping = json.load(raw)

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
    # { "src_pkg": { "subpackage": pkg, ... } }
    packages = {}
    packages_count = 0
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
            # Get source rpm name
            srpm_name = do_regex(srpm_pattern, raw["rpm_sourcerpm"])

            # Check if package is already data structure
            src_pkg = packages.get(srpm_name)
            if src_pkg:
                pkg = src_pkg.get(raw["name"])
            else:
                pkg = None
            revision = "{}-{}".format(raw["version"], raw["release"])
            first_pkg_encounter = False

            # Register unknown packages.
            if pkg == None:
                pkg = Package(raw["name"])
                if not srpm_name in packages:
                    packages[srpm_name] = {}
                packages[srpm_name][pkg.name] = pkg
                first_pkg_encounter = True
                pkg.source = srpm_name
                packages_count += 1

            # Override package metadata with rawhide (= lastest) values.
            if first_pkg_encounter or release_branch == "rawhide":
                pkg.summary = raw["summary"]
                pkg.description = raw["description"]
                pkg.upstream = raw["url"]
                pkg.license = raw["rpm_license"]
                pkg.maintainers = maintainer_mapping["rpms"].get(srpm_name, [])

            # XXX: we do not resolve files and changelog here because storing
            # them in the packages hash would require multiple GBs of RAM
            # (roughly 1GB per repository).

            # Always register branch-specific metadata.
            (release, branch) = release_branch_pattern.findall(release_branch)[0]
            if branch == "":
                branch = "base"

            pkg.set_release(release, raw["pkgKey"], branch, raw["arch"], revision, release_mapping.get(release))

    print(">>> {} packages have been extracted.".format(packages_count))

    print("Sending data to Solr index...")

    # Create a tmp solr index
    tmp_idx = f"solr_{int(time.time())}"
    req = requests.get(f"{SOLR_URL}solr/admin/cores?action=CREATE&name={tmp_idx}&instanceDir=/var/solr/data/{tmp_idx}&configSet={SOLR_CONF_SET}")
    req.raise_for_status()

    # Start submitting to the index
    pkg_xml = Element('add')
    pkg_count = 0
    max_pkg_count = packages_count

    for src_pkg in packages.values():
        for pkg in src_pkg.values():
            # Submit packages to Solr index, 500 at a time.
            pkg_el = Element('doc')

            pkg_el_id = Element('field', { "name": "name" })
            pkg_el_id.text = pkg.name
            pkg_el.append(pkg_el_id)

            pkg_el_src_name = Element('field', { "name": "srcName" })
            pkg_el_src_name.text = pkg.source
            pkg_el.append(pkg_el_src_name)

            pkg_el_summary = Element('field', { "name": "summary" })
            pkg_el_summary.text = pkg.summary
            pkg_el.append(pkg_el_summary)

            for release in pkg.releases.values():
                pkg_el_release = Element('field', { "name": "releases" })
                pkg_el_release.text = release['human_name']
                pkg_el.append(pkg_el_release)

            pkg_xml.append(pkg_el)

            pkg_count += 1
            if (pkg_count % 500 == 0 or pkg_count == max_pkg_count):
                req = requests.post(f"{SOLR_URL}solr/{tmp_idx}/update?commit={str(pkg_count == max_pkg_count).lower()}&update.chain=uuid", data=tostring(pkg_xml), headers={'Content-Type': 'application/xml'})
                req.raise_for_status()
                pkg_xml.clear()
                # print("Submitted {}/{} packages.".format(pkg_count, max_pkg_count))
    
    # Create default core if it does not exist
    req = requests.get(f"{SOLR_URL}solr/admin/cores?action=STATUS&core={SOLR_CORE}")
    status = req.json()
    if len(status["status"]["packages"]) == 0:
        requests.get(f"{SOLR_URL}solr/admin/cores?action=CREATE&name={SOLR_CORE}&instanceDir=/var/solr/data/{SOLR_CORE}&configSet={SOLR_CONF_SET}")

    # Swap production core with our temporary core
    req = requests.get(f"{SOLR_URL}solr/admin/cores?action=SWAP&core={tmp_idx}&other={SOLR_CORE}")
    req.raise_for_status()

    # Delete the old core that was swapped out
    req = requests.get(f"{SOLR_URL}solr/admin/cores?action=UNLOAD&core={tmp_idx}&deleteInstanceDir=true&deleteDataDir=true&deleteIndex=true")
    req.raise_for_status()

    print("DONE.")
    print("> {} packages submitted to solr.".format(packages_count))

if __name__ == '__main__':
    defusedxml.defuse_stdlib()
    main()
