#!/usr/bin/python3

import os
import sqlite3
import argparse
import shutil
from datetime import date
from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_DIR='../templates'
DBS_DIR='repositories'
ASSETS_DIR='assets'

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

    # 
    output_dir = args.target_dir
    db = os.path.join(DBS_DIR, "koji-primary.sqlite")

    env = Environment(
            loader=PackageLoader('generate-html', TEMPLATE_DIR),
            autoescape=select_autoescape(['html'])
            )
    index = env.get_template('index.html.j2')


    os.makedirs(os.path.join(output_dir, "pkgs"), exist_ok=True)
    shutil.copytree(ASSETS_DIR, os.path.join(output_dir, 'assets'))

    index_html = index.render(date=date.today().isoformat())
    save_to(os.path.join(output_dir, 'index.html'), index_html)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM packages')
    package_count = c.fetchone()[0]
    print("Found {} packages in Rawhide.".format(package_count))

    count = 0
    for pkg in c.execute('SELECT * FROM packages'):
        html_path = os.path.join(output_dir, 'pkgs', pkg["name"] + ".html")
        html_template = env.get_template('package.html.j2')
        html_content = html_template.render(
                name=pkg["name"],
                summary=pkg["description"],
                description=pkg["description"],
                )
        save_to(html_path, html_content)
        count += 1

        if (count % 100 == 0):
            print("Processed {}/{} packages.".format(count, package_count))


if __name__ == '__main__':
    main()
