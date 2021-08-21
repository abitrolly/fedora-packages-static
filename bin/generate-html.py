#!/usr/bin/python3
#
# Naming conventions used in this script:
#   * product: fedora, epel
#   * release: fedora-31, epel-7, ...
#   * branch: base (= none), updates, updates-testing
#   * release_branch: fedora-31, fedora-31-updates, fedora-31-updates-testing, ...
import functools
import os
import re
import sys
import json
import shutil
import sqlite3
import argparse
import glob

from datetime import date
from collections import OrderedDict

from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_DIR='../templates'
DBS_DIR=os.environ.get('DB_DIR') or "repositories"
ASSETS_DIR='assets'
SCM_MAINTAINER_MAPPING=os.environ.get('MAINTAINER_MAPPING') or "pagure_owner_alias.json"
PRODUCT_VERSION_MAPPING=os.environ.get('PRODUCT_VERSION_MAPPING') or "product_version_mapping.json"
SITEMAP_URL = os.environ.get('SITEMAP_URL') or 'https://localhost:8080'
SEARCH_BACKEND = os.environ.get('SEARCH_BACKEND', False)

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

def gen_file_array(dir_representation, data=None):
    if not data:
        data = []
    for dir in sorted(dir_representation):
        if type(dir_representation[dir]) is str:
            data.append({ "name": dir, "control": "file" })
        else:
            data.append({ "name": dir, "control": "dir" })
            data = gen_file_array(dir_representation[dir], data)

    if len(data) != 0:
        data.append({ "control": "exit-list" })
    return data

def do_regex(pattern, string):
    (result) = pattern.findall(string)[0]
    return result

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
            autoescape=True
            )

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
    db_conns = {}
    packages = {}
    partial_update = False
    removed_packages = set()
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

        db_conns[release_branch] = {
            "filelist": filelist,
            "other": other,
            "primary": primary
        }

        # Check if this db has a changes table
        primary.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'changes'")
        partial_update = primary.fetchone() is not None

        partial_update_packages = []
        if partial_update:
            primary.execute('SELECT name, rpm_sourcerpm_name FROM changes')
            for row in primary.fetchall():
                partial_update_packages.append((row["rpm_sourcerpm_name"], row['name']))

        for raw in primary.execute('SELECT * FROM packages'):
            # Get source rpm name
            srpm_name = raw["rpm_sourcerpm_name"]

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

            # Override package metadata with rawhide (= lastest) values.
            if first_pkg_encounter or release_branch == "fedora-rawhide":
                pkg.summary = raw["summary"]
                pkg.description = raw["description"]
                pkg.upstream = raw["url"]
                pkg.license = raw["rpm_license"]
                pkg.maintainers = maintainer_mapping["rpms"].get(srpm_name, [])

            # Check if package should be updated during a partial update
            if partial_update and (srpm_name, pkg.name) in partial_update_packages:
                pkg.should_update = True
            elif first_pkg_encounter and partial_update:
                pkg.should_update = False

            # If a changes table does not exist, then the package should
            # always be updated.
            if not partial_update:
                pkg.should_update = True

            # XXX: we do not resolve files and changelog here because storing
            # them in the packages hash would require multiple GBs of RAM
            # (roughly 1GB per repository).

            # Always register branch-specific metadata.
            (release, branch) = release_branch_pattern.findall(release_branch)[0]
            if branch == "":
                branch = "base"

            pkg.set_release(release, raw["pkgKey"], branch, raw["arch"], revision, release_mapping.get(release))

        # Get removed packages to determine if folder needs to be deleted later
        if partial_update:
            for removed in primary.execute("SELECT name, rpm_sourcerpm_name FROM changes WHERE change = 'removed'"):
                removed_packages.add((removed["rpm_sourcerpm_name"], removed["name"]))

    # If a package was removed and it was not in any repository, attempt to
    # delete the folder from the target directory
    for removed_package in removed_packages:
        if removed_package not in packages:
            shutil.rmtree(os.path.join(output_dir, 'pkgs', removed_package[0], removed_package[1]), True)

    print(">>> {} packages have been extracted.".format(len(packages)))

    # Generate main user entrypoint.
    print("Generating index pages...")

    pkgs_list = []
    # {"aa": ["aaargh", ...]}
    prefix_index = {}

    for src_pkg in packages:
        for pkg_name in packages[src_pkg]:
            tmp_pkg = packages[src_pkg][pkg_name]
            pkgs_list.append((tmp_pkg.source, tmp_pkg.name))
            prefix_index.setdefault(tmp_pkg.name[:2].lower(), []).append((tmp_pkg.source, tmp_pkg.name))

    # Sort the indexes
    for prefix_group in prefix_index:
        prefix_index[prefix_group] = sorted(prefix_index[prefix_group], key=lambda x : x[1])

    static_index_html = env.get_template('index-static.html.j2').render(
            date=date.today().isoformat(),
            package_count=len(packages),
            prefix_index=prefix_index)
    save_to(os.path.join(output_dir, 'index-static.html'), static_index_html)

    search = env.get_template('index.html.j2')
    search_html = search.render(date=date.today().isoformat(),
                                package_count=len(packages),
                                prefix_index=prefix_index,
                                search_backend=SEARCH_BACKEND)
    save_to(os.path.join(output_dir, 'index.html'), search_html)

    index_tpl = env.get_template('index-prefix.html.j2')
    index_dir = os.path.join(output_dir, 'index')
    os.makedirs(index_dir, exist_ok=True)
    for prefix, names in prefix_index.items():
        html = index_tpl.render(prefix=prefix, packages=names,
                                search_backend=SEARCH_BACKEND)
        save_to(os.path.join(index_dir, f'{prefix}.html'), html)

    # Generate sitemaps
    sitemap_list = []
    sitemap_dir = os.path.join(output_dir, 'sitemaps')
    shutil.rmtree(sitemap_dir, ignore_errors=True)
    os.makedirs(sitemap_dir, exist_ok=True)
    i = 0
    # Number of pkgs in one sitemap. Should not be above 50,000
    # https://www.sitemaps.org/protocol.html#index
    sitemap_amount = 10000
    sitemap_pkgs = pkgs_list[i * sitemap_amount:(i + 1) * sitemap_amount]
    while sitemap_pkgs:
        crawler_sitemap = env.get_template('sitemap.xml.j2')
        crawler_sitemap_xml = crawler_sitemap.render(packages=sitemap_pkgs, url=SITEMAP_URL)
        save_to(os.path.join(sitemap_dir, 'sitemap{}.xml'.format(i)), crawler_sitemap_xml)
        sitemap_list.append('/sitemaps/sitemap{}.xml'.format(i))
        i = i + 1
        sitemap_pkgs = pkgs_list[i * sitemap_amount:(i + 1) * sitemap_amount]

    sitemap_sitemap = env.get_template('sitemap-index.xml.j2')
    sitemap_sitemap_xml = sitemap_sitemap.render(sitemaps=sitemap_list, url=SITEMAP_URL)
    save_to(os.path.join(output_dir, 'sitemap.xml'), sitemap_sitemap_xml)

    # Generate package pages from Rawhide.
    print("> Generating package pages...")

    page_count = 0
    max_page_count = len(pkgs_list)

    # Generate package index and version pages
    for src_pkg in packages:
        src_dir = os.path.join(output_dir, 'pkgs', src_pkg)
        related_pkg_list = []
        should_update_src = False
        for pkg in packages[src_pkg]:
            if not should_update_src and packages[src_pkg][pkg].should_update == True:
                should_update_src = True
            related_pkg_list.append(packages[src_pkg][pkg].name)
        related_pkg_list = sorted(related_pkg_list)

        # Generate source pkg index page if needed
        if should_update_src:
            os.makedirs(src_dir, exist_ok=True)

            source_package_index = env.get_template("source-package.html.j2")
            source_package_index_html = source_package_index.render(name=src_pkg, children=packages[src_pkg], search_backend=SEARCH_BACKEND)
            save_to(os.path.join(src_dir, 'index.html'), source_package_index_html)

        # Process subpackages
        for pkg in packages[src_pkg].values():
            if pkg.should_update == False:
                continue
            pkg_dir = os.path.join(src_dir, pkg.name)
            clean_dir(pkg_dir)
            os.makedirs(pkg_dir, exist_ok=True)

            html_path = os.path.join(pkg_dir, 'index.html')
            html_template = env.get_template('package.html.j2')
            html_content = html_template.render(pkg=pkg, related_pkgs=related_pkg_list, search_backend=SEARCH_BACKEND)
            save_to(html_path, html_content)

            # Simple way to display progress.
            page_count += 1
            if (page_count % 100 == 0 or page_count == max_page_count):
                print("Processed {}/{} package pages.".format(page_count, max_page_count))

            for release in pkg.releases.keys():
                for branch in pkg.get_release(release).keys():
                    if branch == "base":
                        release_branch = release
                    else:
                        release_branch = "{}-{}".format(release, branch)

                    pkg_key = pkg.get_release(release)[branch]['pkg_key']
                    revision = pkg.get_release(release)[branch]['revision']

                    filelist = db_conns[release_branch]["filelist"]
                    other = db_conns[release_branch]["other"]
                    primary = db_conns[release_branch]["primary"]

                    # Generate files page for pkg.
                    # Create a nested object to represent the file tree
                    files = {}
                    for entry in filelist.execute('SELECT * FROM filelist WHERE pkgKey = ?', (pkg_key,)):
                        filenames = entry["filenames"].split('/')
                        filetype_index = 0
                        for filename in filenames:
                            try:
                                filetype = entry["filetypes"][filetype_index]
                            except Exception:
                                filetype = '?'

                            current = files
                            for dir in entry["dirname"].split('/'):
                                if dir != "":
                                    if dir not in current or type(current[dir]) == str:
                                        current[dir] = {}
                                    current = current[dir]

                            if filetype == 'd' and not filename in current:
                                current[filename] = {}
                            elif filetype != 'd':
                                current[filename] = filetype
                            filetype_index += 1
                    # Flatten and sort the files structure for jinja
                    files = gen_file_array(files)

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

                    # Generate provides list for pkg.
                    provides = []
                    try:
                        for provide in primary.execute('SELECT name FROM provides where pkgkey = ? GROUP BY name', (pkg_key,)):
                            provides.append(provide["name"])
                    except Exception as e:
                        print(e)
                        print(databases[release_branch]["primary"])

                        primary.execute("PRAGMA database_list")
                        rows = primary.fetchall()

                        for row in rows:
                            print(row[0], row[1], row[2])

                        primary.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        print(primary.fetchall())
                        sys.exit(1)

                    # Generate dependencies for pkg
                    requires = []
                    for require in primary.execute("""
                        SELECT requires.flags, requires.version, requires.release, packages.rpm_sourcerpm_name, packages.name AS provides FROM requires
                        INNER JOIN provides ON requires.name=provides.name
                        INNER JOIN packages ON provides.pkgkey=packages.pkgkey
                        WHERE requires.pkgkey = ?
                        GROUP BY packages.name
                        """, (pkg_key,)):
                        flags = ""
                        if require["flags"] == "EQ":
                            flags = "="
                        elif require["flags"] == "GE":
                            flags = ">="
                        elif require["flags"] == "GT":
                            flags = ">"
                        elif require["flags"] == "LE":
                            flags = "<="
                        elif require["flags"] == "LT":
                            flags = "<"
                        require_srpm_name = require["rpm_sourcerpm_name"]
                        requires.append({ "requirement": require["provides"], "flags": flags, "version": require["version"], "release": require["release"], "can_link": bool(packages[require_srpm_name].get(require["provides"])), "srpm_name": require_srpm_name })

                    html_path = os.path.join(pkg_dir, release_branch + ".html")
                    html_template = env.get_template("package-details.html.j2")
                    html_content = html_template.render(pkg=pkg, release=release, branch=branch, changelog=changelog, files=files, provides=provides, requires=requires, search_backend=SEARCH_BACKEND)
                    save_to(html_path, html_content)

    print("DONE.")
    print("> {} packages processed.".format(page_count))

if __name__ == '__main__':
    main()
