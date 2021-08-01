#!/usr/bin/python3

import requests
import defusedxml.ElementTree as ET
import shutil
import tempfile
import sqlite3
import os
import argparse
import hashlib
import sys
from requests.models import HTTPError
import tqdm
from dnf.subject import Subject
import hawkey

repomd_xml_namespace = {
    'repo': 'http://linux.duke.edu/metadata/repo',
    'rpm': 'http://linux.duke.edu/metadata/rpm',
}
padding = 22

MIRROR = 'https://dl.fedoraproject.org'
KOJI_REPO = 'https://kojipkgs.fedoraproject.org/repos'
# Enforce, or not, checking the SSL certs
DL_VERIFY = True

def needs_update(local_file, remote_sha, sha_type):
    ''' Compare sha of a local and remote file.
    Return True if our local file needs to be updated.
    '''

    if not os.path.isfile(local_file):
        # If we have never downloaded this before, then obviously it has
        # "changed"
        return True

    # Old old epel5 doesn't even know which sha it is using..
    if sha_type == 'sha':
        sha_type = 'sha1'

    hash = getattr(hashlib, sha_type)()
    with open(local_file, 'rb') as f:
        hash.update(f.read())

    local_sha = hash.hexdigest()
    if local_sha != remote_sha:
        return True

    return False

def download_db(name, repomd_url, archive):
    print(f'{name.ljust(padding)} Downloading file: {repomd_url} to {archive}')
    response = requests.get(repomd_url, verify=DL_VERIFY, stream=True)
    response.raise_for_status()
    with tqdm.tqdm.wrapattr(
            open(archive, 'wb'),
            "write",
            desc=repomd_url.split('/')[-1],
            total=int(response.headers.get('content-length', 0))) as stream:
        for chunk in response.iter_content(chunk_size=1024*1024):
            stream.write(chunk)

def decompress_db(name, archive, location):
    ''' Decompress the given XZ archive at the specified location. '''
    print(f'{name.ljust(padding)} Extracting {archive} to {location}')
    if archive.endswith('.xz'):
        import lzma
        with lzma.open(archive) as inp, open(location, 'wb') as out:
            out.write(inp.read())
    elif archive.endswith('.tar.gz'):
        import tarfile
        with tarfile.open(archive) as tar:
            tar.extractall(path=location)
    elif archive.endswith('.gz'):
        import gzip
        with gzip.open(archive, 'rb') as inp, open(location, 'wb') as out:
            out.write(inp.read())
    elif archive.endswith('.bz2'):
        import bz2
        with bz2.open(archive) as inp, open(location, 'wb') as out:
            out.write(inp.read())
    else:
        raise NotImplementedError(archive)

def index_db(name, tempdb):
    print(f'{name.ljust(padding)} Indexing file: {tempdb}')

    if tempdb.endswith('primary.sqlite'):
        conn = sqlite3.connect(tempdb)
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE INDEX packageSource ON packages (rpm_sourcerpm)')
        conn.commit()
        # Insert source package name field for diff creation
        conn.execute('ALTER TABLE packages ADD rpm_sourcerpm_name TEXT')
        for package_info in conn.execute('SELECT * FROM packages'):
            subject = Subject(package_info["rpm_sourcerpm"])
            nevra = subject.get_nevra_possibilities(forms=hawkey.FORM_NEVRA)
            conn.execute("UPDATE packages SET rpm_sourcerpm_name = ? WHERE pkgKey = ?", [nevra[0].name, package_info["pkgKey"]])
        conn.commit()
        conn.close()

# Adds a table named 'changes' listing if certian packages were changed,
#  added, or deleted.
def gen_db_diff(name, new, old, regen_all):
    if not os.path.isfile(old) or not new.endswith('primary.sqlite'):
        return

    # If we want to regen all, then just don't make changes tables
    if regen_all:
        return

    print(f'{name.ljust(padding)} Creating diff for file: {old}')
    conn = sqlite3.connect(new)
    conn.execute(f'ATTACH DATABASE \'{old}\' as old')
    # changes table schema:
    # name - package name
    # arch - package arch
    # version (optional) - {epoch}:{package version}-{package release}
    # change - 'updated', 'removed', or 'added'
    conn.execute('''
        CREATE TABLE changes (
            name TEXT NOT NULL,
            arch TEXT NOT NULL,
            rpm_sourcerpm_name TEXT NOT NULL,
            version TEXT,
            change TEXT NOT NULL,
            UNIQUE(name, arch, rpm_sourcerpm_name) ON CONFLICT IGNORE
        )
        ''')
    # Insert added packages list to changes table
    conn.execute('''
        INSERT INTO changes (name, arch, rpm_sourcerpm_name, version, change)
        SELECT main.packages.name, main.packages.arch, main.packages.rpm_sourcerpm_name,
            IIF(main.packages.epoch IS NOT NULL, main.packages.epoch || ':', '') ||
                main.packages.version || '-' || main.packages.release || '.' || main.packages.arch,
            'added'
        FROM main.packages LEFT JOIN old.packages ON main.packages.name = old.packages.name
            AND main.packages.arch = old.packages.arch AND main.packages.rpm_sourcerpm_name = old.packages.rpm_sourcerpm_name
        WHERE old.packages.name IS NULL
        ''')
    # Insert removed packages list to changes table
    conn.execute('''
        INSERT INTO changes (name, arch, rpm_sourcerpm_name, version, change)
        SELECT old.packages.name, old.packages.arch, old.packages.rpm_sourcerpm_name,
            IIF(old.packages.epoch IS NOT NULL, old.packages.epoch || ':', '') ||
                old.packages.version || '-' || old.packages.release,
            'removed'
        FROM old.packages LEFT JOIN main.packages ON main.packages.name = old.packages.name
            AND main.packages.arch = old.packages.arch AND main.packages.rpm_sourcerpm_name = old.packages.rpm_sourcerpm_name
        WHERE main.packages.name IS NULL
        ''')
    # Insert changed packages list to changes table
    conn.execute('''
        INSERT INTO changes (name, arch, rpm_sourcerpm_name, change)
        SELECT name, arch, rpm_sourcerpm_name, 'updated' FROM
            (SELECT main.packages.name, main.packages.arch, main.packages.rpm_sourcerpm_name,
                IIF(main.packages.epoch IS NOT NULL, main.packages.epoch || ':', '') ||
                main.packages.version || '-' || main.packages.release || '.' || main.packages.arch
            FROM main.packages
            UNION
            SELECT old.packages.name, old.packages.arch, old.packages.rpm_sourcerpm_name,
                IIF(old.packages.epoch IS NOT NULL, old.packages.epoch || ':', '') ||
                old.packages.version || '-' || old.packages.release || '.' || old.packages.arch
            FROM old.packages)
        GROUP BY name, arch, rpm_sourcerpm_name
        HAVING COUNT(*) > 1
        ''')
    conn.commit()
    conn.close()

def clear_diff_table(db):
    conn = sqlite3.connect(db)
    result = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'changes'")
    if result.fetchone() is not None:
        conn.execute("DELETE FROM changes")
        conn.commit()
    conn.close()

def install_db(name, src, dest):
    print(f'{name.ljust(padding)} Installing {src} to {dest}.')
    shutil.move(src, dest)

def handle(repo, target_dir, db_removed):
    url, name = repo
    repomd_url = f'{url}/repomd.xml'
    response = requests.get(repomd_url, verify=DL_VERIFY)
    if not response:
        print(f'{name.ljust(padding)} !! Failed to get {repomd_url!r} {response!r}')
        return

    # Parse the xml doc and get a list of locations and their shasum.
    files = ((
        node.find('repo:location', repomd_xml_namespace),
        node.find('repo:open-checksum', repomd_xml_namespace),
    ) for node in ET.fromstring(response.text))

    # Extract out the attributes that we're really interested in.
    files = (
        (f.attrib['href'].replace('repodata/', ''), s.text, s.attrib['type'])
        for f, s in files if f is not None and s is not None
    )

    # Filter down to only sqlite dbs
    files = ((f, s, t) for f, s, t in files if '.sqlite' in f)

    # We need to ensure the primary db comes first so we can build a pkey cache
    primary_first = lambda item: 'primary' not in item[0]
    files = sorted(files, key=primary_first)

    # Primary-key caches built from the primary dbs so we can make sense
    # of the contents of the filelist and changelog dbs.
    cache1, cache2 = {}, {}

    if not files:
        print(f'No sqlite database could be found in {url}')

    for filename, shasum, shatype in files:
        repomd_url = f'{url}/{filename}'

        # First, determine if the file has changed by comparing hash
        db = None
        if 'primary.sqlite' in filename:
            db = f'{name}_primary.sqlite'
        elif 'filelists.sqlite' in filename:
            db = f'{name}_filelists.sqlite'
        elif 'other.sqlite' in filename:
            db = f'{name}_other.sqlite'

        # Have we downloaded this before?  Did it change?
        destfile = os.path.join(target_dir, db)
        if not needs_update(destfile, shasum, shatype):
            clear_diff_table(destfile)
            print(f'{name.ljust(padding)} No change of {repomd_url}')
            continue

        # If it has changed, then download it and move it into place.
        tempargs = dict(prefix='mdapi-')
        with tempfile.TemporaryDirectory(**tempargs) as working_dir:
            tempdb = os.path.join(working_dir, db)
            archive = os.path.join(working_dir, filename)

            try:
                download_db(name, repomd_url, archive)
            except HTTPError as err:
                print(f'{name.ljust(padding)} ERROR Downloading DB file: {err}')
                print(f'{name.ljust(padding)} will be skipped.')
                continue
            decompress_db(name, archive, tempdb)
            index_db(name, tempdb)
            gen_db_diff(name, tempdb, destfile, db_removed)
            install_db(name, tempdb, destfile)

def get_repository_urls_for(product, version):
    release = "{}-{}".format(product, version)
    if product == "fedora":
        if version == "rawhide":
            return [(f'{KOJI_REPO}/rawhide/latest/x86_64/repodata', release)]

        return [
                ('{}/pub/fedora/linux/releases/{}/Everything/x86_64/os/repodata'.format(MIRROR, version), release),
                ('{}/pub/fedora/linux/updates/{}/Everything/x86_64/repodata'.format(MIRROR, version), release + "-updates"),
                ('{}/pub/fedora/linux/updates/testing/{}/Everything/x86_64/repodata'.format(MIRROR, version), release + "-updates-testing"),
                ]
    elif product == "epel" and int(version) < 8:
        return [
                ('{}/pub/epel/{}/x86_64/repodata/'.format(MIRROR, version), release),
                ('{}/pub/epel/testing/{}/x86_64/repodata'.format(MIRROR, version), release + "-testing"),
                ]
    elif product == "epel" and int(version) >= 8:
        return [
                ('{}/pub/epel/{}/Everything/x86_64/repodata/'.format(MIRROR, version), release),
                ('{}/pub/epel/testing/{}/Everything/x86_64/repodata'.format(MIRROR, version), release + "-testing"),
                ]
    else:
        sys.exit("Unknown product: {}".format(product))

def main():
    # Handle command-line arguments.
    parser = argparse.ArgumentParser(
            description='Fetch SQL metadata databases of Fedora/EPEL repositories')
    parser.add_argument(
            '--target-dir', dest='target_dir', action='store', required=True)

    args = parser.parse_args()

    # Get active releases from PDC.
    print("Fetching active releases from PDC...")
    r = requests.get(
            "https://pdc.fedoraproject.org/rest_api/v1/product-versions/",
            params={'active': 'true'})
    if (r.status_code != 200):
        sys.exit("Failed to fetch active releases from PDC (request returned {})"
                .format(r.status_code))

    # Generate repository URLs.
    repositories = []
    active_releases = map(lambda e: (e["short"], e["version"]), r.json()["results"])

    for (product, version) in active_releases:
        repositories += get_repository_urls_for(product, version)

    print("Found: " + str(list(map(lambda p: p[1], repositories))))

    # Delete db files for inactive releases. If a db is deleted, all pages will be regenerated.
    db_removed = False
    for filename in os.listdir(args.target_dir):
        file_from_active_release = False
        for repo in repositories:
            if filename.find(repo[1]) != -1:
                file_from_active_release = True
                break

        if not file_from_active_release:
            os.remove(os.path.join(args.target_dir, filename))
            # this will trigger a full regen
            db_removed = True

    # Fetch repository databases.
    for repo in repositories:
        handle(repo, args.target_dir, db_removed)

if __name__ == '__main__':
    main()
