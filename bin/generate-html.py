#!/usr/bin/python3

import os
import sqlite3
import sys
import argparse
import shutil
import json
import re
from datetime import date
from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_DIR='../templates'
DBS_DIR='repositories'
ASSETS_DIR='assets'
SCM_MAINTAINER_MAPPING='pagure_owner_alias.json'

class Package:
    def __init__(self, name):
        self.name = name
        self.summary = "No summary specified."
        self.description = "No description specified."

        self.license = "unknown"
        self.upstream = ""
        self.maintainers = []
        self.branches = {}
        self.subpackage_of = None
        self.subpackages = []

    def set_branch(self, name, revision):
        self.branches[name] = revision

    def get_branch(self, name):
        return self.branches[name]

    def source(self):
        if self.subpackage_of == None:
            return self.name
        else:
            return self.subpackage_of

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
    db = os.path.join(DBS_DIR, "koji-primary.sqlite")
    env = Environment(
            loader=PackageLoader('generate-html', TEMPLATE_DIR),
            autoescape=select_autoescape(['html'])
            )

    # Load maintainer mapping (imported from dist-git).
    # TODO: check that mapping exist / error.
    print("Loading maintainer mapping...")
    with open(SCM_MAINTAINER_MAPPING) as raw:
        maintainer_mapping = json.load(raw)

    # Build internal package metadata structure / cache.
    packages = {}

    for db in os.listdir(DBS_DIR):
        print("> Processing database file {}.".format(db))
        pattern = re.compile('^(fedora|epel)-([\w|-]+)_(primary|filelists|other).sqlite$')
        match = pattern.match(db)

        if (not match):
            sys.exit("Invalid object in {}: {}".format(DBS_DIR, db))

        (product, branch, db_type) = pattern.findall(db)[0]

        conn = sqlite3.connect(os.path.join(DBS_DIR, db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        srpm_pattern = re.compile("^(.+)-.+-.+.src.rpm$")
        if db_type == "primary":
            for raw in c.execute('SELECT * FROM packages'):
                pkg = packages.get(raw["name"])
                revision = "{}-{}".format(raw["version"], raw["release"])
                release = "{}-{}".format(product, branch)
                first_pkg_encounter = False

                # Register unknown packages.
                if pkg == None:
                    pkg = Package(raw["name"])
                    packages[pkg.name] = pkg
                    first_pkg_encounter = True

                # Override package metadata with rawhide (= lastest) values.
                if first_pkg_encounter or branch == "rawhide":
                    pkg.summary = raw["summary"]
                    pkg.description = raw["description"]
                    pkg.upstream = raw["url"]
                    pkg.license = raw["rpm_license"]
                    pkg.maintainers = maintainer_mapping["rpms"].get(pkg.name, [])

                # Handle subpackage specific case.
                (srpm_name) = srpm_pattern.findall(raw["rpm_sourcerpm"])[0]
                if pkg.name != srpm_name:
                    pkg.subpackage_of = srpm_name

                # Always register branch-specific metadata.
                pkg.set_branch(release, revision)

    # Set license and maintainers for subpackages. We have to wait for all
    # packages to have been processed since subpackage might have been
    # processed before its parent.
    print("Syncing subpackages...")
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
    shutil.copytree(ASSETS_DIR, os.path.join(output_dir, 'assets'))

    # Generate indexing system entrypoint.
    crawler_entrypoint = env.get_template('crawler_entrypoint.html.j2')
    crawler_entrypoint_html = crawler_entrypoint.render(packages=packages)
    save_to(os.path.join(output_dir, 'crawler-entrypoint.html'), crawler_entrypoint_html)

    # Generate package pages from Rawhide.
    print("Generating package pages...")

    count = 0
    for pkg in packages.values():
        pkg_dir = os.path.join(output_dir, 'pkgs', pkg.name)
        os.makedirs(pkg_dir, exist_ok=True)

        html_path = os.path.join(pkg_dir, 'index.html')
        html_template = env.get_template('package.html.j2')
        html_content = html_template.render(pkg=pkg)
        save_to(html_path, html_content)
        count += 1

        if (count % 100 == 0):
            print("Processed {}/{} packages.".format(count, len(packages)))


if __name__ == '__main__':
    main()
