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
import glob

from datetime import date
from collections import defaultdict

from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_DIR='../templates'
DBS_DIR=os.environ.get('DB_DIR') or "repositories"
ASSETS_DIR='assets'
SCM_MAINTAINER_MAPPING=os.environ.get('MAINTAINER_MAPPING') or "pagure_owner_alias.json"
SITEMAP_URL = os.environ.get('SITEMAP_URL') or 'https://localhost:8080'

class Package:
    def __init__(self, name):
        self.name = name
        self.summary = "No summary specified."
        self.description = "No description specified."

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

def clean_dir(path):
    files = glob.glob(os.path.join(path, '*.html'))
    for file in files:
        try:
            os.remove(file)
        except:
            print("Error cleaning directory!")
            print(sys.exc_info()[0])

def save_to(path, content):
    with open(path, 'w') as fh:
        fh.write(content)

def main():
    # Handle command-line arguments.
    parser = argparse.ArgumentParser(
            description='Generate static pages for Fedora packages')
    parser.add_argument(
            '--target-dir', dest='target_dir', action='store', required=True)

    args = parser.parse_args()

    # Make sure output directory exists.
    output_dir = args.target_dir
    os.makedirs(output_dir, exist_ok=True)

    # Initialize templating system.
    env = Environment(
            loader=PackageLoader('generate-html', TEMPLATE_DIR),
            autoescape=select_autoescape(['html'])
            )

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
    partial_update = False
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

        if not partial_update:
            primary.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'changes'")
            partial_update = primary.fetchone() is not None

        partial_update_packages = []
        if partial_update:
            primary.execute('SELECT name FROM changes')
            for row in primary.fetchall():
                partial_update_packages.append(row['name'])

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

            # Check if package should be updated during a partial update
            if partial_update and pkg.name in partial_update_packages:
                pkg.should_update = True
            elif first_pkg_encounter and partial_update:
                pkg.should_update = False

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
    # Generate main user entrypoint.
    print("Generating generic pages...")
    search = env.get_template('search.html.j2')
    search_html = search.render(date=date.today().isoformat(), package_count=len(packages))
    save_to(os.path.join(output_dir, 'index.html'), search_html)

    # Import assets.
    assets_output = os.path.join(output_dir, 'assets')
    if not os.path.exists(assets_output):
        shutil.copytree(ASSETS_DIR, os.path.join(output_dir, 'assets'))

    # Generate sitemaps
    pkgs_list = list(packages.keys())
    sitemap_list = []
    sitemap_dir = os.path.join(output_dir, 'sitemaps')
    shutil.rmtree(sitemap_dir, ignore_errors=True)
    os.makedirs(sitemap_dir, exist_ok=True)
    i = 0
    # Number of pkgs in one sitemap. Should not be above 50,000
    # https://www.sitemaps.org/protocol.html#index
    sitemap_amount = 10000
    while True:
        sitemap_pkgs = pkgs_list[i * sitemap_amount:(i + 1) * sitemap_amount]
        if not sitemap_pkgs:
            break
        crawler_sitemap = env.get_template('sitemap.xml.j2')
        crawler_sitemap_xml = crawler_sitemap.render(packages=sitemap_pkgs, url=SITEMAP_URL)
        save_to(os.path.join(sitemap_dir, 'sitemap{}.xml'.format(i)), crawler_sitemap_xml)
        sitemap_list.append('/sitemaps/sitemap{}.xml'.format(i))
        i = i + 1 
        
    sitemap_sitemap = env.get_template('sitemap-index.xml.j2')
    sitemap_sitemap_xml = sitemap_sitemap.render(sitemaps=sitemap_list, url=SITEMAP_URL)
    save_to(os.path.join(output_dir, 'sitemap.xml'), sitemap_sitemap_xml)

    # Generate package pages from Rawhide.
    print("> Generating package pages...")

    page_count = 0
    max_page_count = len(packages)

    # Generate main pages.
    print(">>> Index pages...")
    for pkg in packages.values():
        if pkg.should_update == False:
            continue
        pkg_dir = os.path.join(output_dir, 'pkgs', pkg.name)
        clean_dir(pkg_dir)
        os.makedirs(pkg_dir, exist_ok=True)

        html_path = os.path.join(pkg_dir, 'index.html')
        html_template = env.get_template('package.html.j2')
        html_content = html_template.render(pkg=pkg)
        save_to(html_path, html_content)

        # Simple way to display progress.
        page_count += 1
        if (page_count % 100 == 0 or page_count == max_page_count):
            print("Processed {}/{} pages.".format(page_count, max_page_count))

    # Generate files and changelog pages.
    print(">>> Files and changelog pages...")
    db_conns = {}
    detailed_page_count = 0
    for pkg in packages.values():
      if pkg.should_update == False:
        continue
      pkg_dir = os.path.join(output_dir, 'pkgs', pkg.name)
      for release in pkg.releases.keys():
        for branch in pkg.get_release(release).keys():
            if branch == "base":
                release_branch = release
            else:
                release_branch = "{}-{}".format(release, branch)

            pkg_key = pkg.get_release(release)[branch]['pkg_key']
            revision = pkg.get_release(release)[branch]['revision']

            # Cache DB connections.
            if release_branch in db_conns:
                filelist = db_conns[release_branch]["filelist"]
                other = db_conns[release_branch]["other"]
            else:
                (_, filelist) = open_db(databases[release_branch]["filelists"])
                (_, other) = open_db(databases[release_branch]["other"])

                db_conns[release_branch] = {
                        "filelist": filelist,
                        "other": other,
                        }

            # Generate files page for pkg.
            files = []
            for entry in filelist.execute('SELECT * FROM filelist WHERE pkgKey = ?', (pkg_key,)):
                filenames = entry["filenames"].split('/')
                filetype_index = 0
                for filename in filenames:
                    try:
                      filetype = entry["filetypes"][filetype_index]
                    except Exception:
                      filetype = '?'

                    files += [{
                        "type": filetype,
                        "path": os.path.join(entry["dirname"], filename),
                    }]
                    filetype_index += 1

            # Generate changelog page for pkg.
            changelog = []
            for change in other.execute('SELECT * FROM changelog WHERE pkgKey = ?', (pkg_key,)):
                # Make addresses less obvious to spot for spam bots.
                author = change["author"]
                if changelog_mail_pattern.search(change["author"]):
                    addr = changelog_mail_pattern.findall(change["author"])[0]
                    obfuscated_addr = addr.replace('@', ' at ').replace('.', ' dot ').replace('-', ' dash ')
                    author = author.replace(addr, obfuscated_addr)

                changelog += [{
                    "author": author,
                    "timestamp": change["date"],
                    "date": date.fromtimestamp(change["date"]),
                    "change": change["changelog"]
                    }]
            html_path = os.path.join(pkg_dir, release_branch + ".html")
            html_template = env.get_template("package-details.html.j2")
            html_content = html_template.render(pkg=pkg, release=release, changelog=changelog, files=files)
            save_to(html_path, html_content)

      detailed_page_count += 1
      if (detailed_page_count % 100 == 0) or (detailed_page_count == max_page_count):
          print("Processed {}/{} pages.".format(detailed_page_count, max_page_count))

    print("DONE.")
    print("> {} packages processed.".format(page_count))

if __name__ == '__main__':
    main()
