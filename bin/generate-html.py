#!/usr/bin/python3

import os
import sqlite3
import sys
import argparse
import shutil
import json
import re
from collections import defaultdict
from datetime import date
from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_DIR='../templates'
DBS_DIR='repositories'
ASSETS_DIR='assets'
SCM_MAINTAINER_MAPPING='pagure_owner_alias.json'

class Package:
    def __init__(self, name, pkg_key):
        self.name = name
        self.key = pkg_key
        self.summary = "No summary specified."
        self.description = "No description specified."

        self.license = "unknown"
        self.upstream = ""
        self.maintainers = []
        self.branches = {}
        self.subpackage_of = None
        self.subpackages = []

    def set_branch(self, name, revision, changelog, files):
        self.branches[name] = {
                "revision": revision,
                "changelog": changelog,
                "files": files
                }

    def get_branch(self, name):
        return self.branches[name]

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

    # Group databases files.
    databases = {}
    db_pattern = re.compile('^(fedora|epel)-([\w|-]+)_(primary|filelists|other).sqlite$')
    for db in os.listdir(DBS_DIR):
        if (not db_pattern.match(db)):
            sys.exit("Invalid object in {}: {}".format(DBS_DIR, db))

        (product, branch, db_type) = db_pattern.findall(db)[0]
        release = "{}-{}".format(product, branch)
        if release in databases:
            databases[release][db_type] = db
        else:
            databases[release] = {db_type: db }

    # Build internal package metadata structure / cache.
    packages = {}
    srpm_pattern = re.compile("^(.+)-.+-.+.src.rpm$")
    changelog_mail_pattern = re.compile("<(.+@.+)>")
    for release in databases.keys():
        print("> Processing database files for {}.".format(release))

        for db_type in ["primary", "filelists", "other"]:
            if db_type not in databases[release]:
                sys.exit("No {} database for {}.".format(db_type, release))

        (_, primary) = open_db(databases[release]["primary"])
        (_, filelist) = open_db(databases[release]["filelists"])
        (_, other) = open_db(databases[release]["other"])

        for raw in primary.execute('SELECT * FROM packages'):
            pkg = packages.get(raw["name"])
            revision = "{}-{}".format(raw["version"], raw["release"])
            first_pkg_encounter = False

            # Register unknown packages.
            if pkg == None:
                pkg = Package(raw["name"], raw["pkgKey"])
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

            # Extract changelog from '-other' db.
            changelog = []
            for change in other.execute('SELECT * FROM changelog WHERE pkgKey = ?', (pkg.key,)):
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

            # Extract file list from '-filelists' db.
            files = []
            for entry in filelist.execute('SELECT * FROM filelist WHERE pkgKey = ?', (pkg.key,)):
                files += [{
                    "dirname": entry["dirname"],
                    "filenames": entry["filenames"],
                    "filetypes": entry["filetypes"]
                    }]

            # Always register branch-specific metadata.
            pkg.set_branch(release, revision, changelog, files)

    # Set license and maintainers for subpackages. We have to wait for all
    # packages to have been processed since subpackage might have been
    # processed before its parent.
    print("Handling subpackages...")
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

        for branch in pkg.branches.keys():
            os.makedirs(os.path.join(pkg_dir, branch), exist_ok=True)

            pages = [
                ('changelog.html', 'package-changelog.html'),
                ('files.html', 'package-files.html')
                ]
            for output_filename, template in pages:
                html_path = os.path.join(pkg_dir, branch, output_filename)
                html_template = env.get_template(template)
                html_content = html_template.render(pkg=pkg, branch=branch)
                save_to(html_path, html_content)

        # Simple way to display progress.
        count += 1
        if (count % 1000 == 0) or (count == len(packages)):
            print("Processed {}/{} packages.".format(count, len(packages)))


if __name__ == '__main__':
    main()
