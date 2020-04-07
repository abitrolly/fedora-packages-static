#!/usr/bin/python3

import os
import sqlite3
from jinja2 import Environment, PackageLoader, select_autoescape

OUTPUT_DIR='output/'

def save_to(path, content):
    with open(path, 'w') as fh:
        fh.write(content)

def main():
    db = "koji-primary.sqlite"

    env = Environment(
            loader=PackageLoader('generate-html', 'templates'),
            autoescape=select_autoescape(['html'])
            )
    index = env.get_template('index.html.j2')


    os.makedirs(os.path.join(OUTPUT_DIR, "pkgs"), exist_ok=True)
    save_to(os.path.join(OUTPUT_DIR, 'index.html'), index.render())

    conn = sqlite3.connect('koji-primary.sqlite')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM packages')
    package_count = c.fetchone()[0]
    print("Found {} packages in Rawhide.".format(package_count))

    count = 0
    for pkg in c.execute('SELECT * FROM packages'):
        html_path = os.path.join(OUTPUT_DIR, 'pkgs', pkg["name"] + ".html")
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
