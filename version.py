# Authors: Douglas Creager <dcreager@dcreager.net>
#          Calum Lind <calumlind@gmail.com>
#          Dariusz Rybi <jiivanq@gmail.com>
#
# This file is placed into the public domain.
#
# Calculates the current version number by first checking output of
# “git describe”, modified to conform to PEP 386 versioning scheme.
# If “git describe” fails (likely due to using release tarball rather
# than git working copy), then fall back on reading the contents of
# the RELEASE-VERSION file.
#
# Usage: Import in setup.py, and use result of get_version() as package
# version:
#
# from version import get_version
#
# setup(
#     ...
#     version=get_version(),
#     ...
# )
#
# Script will automatically update the RELEASE-VERSION file, if needed.
# Note that  RELEASE-VERSION file should *not* be checked into git; please add
# it to your top-level .gitignore file.
#
# You'll probably want to distribute the RELEASE-VERSION file in your
# sdist tarballs; to do this, just create a MANIFEST.in file that
# contains the following line:
#
#   include RELEASE-VERSION
#

__all__ = ("get_version")

import argparse
import pathlib
import subprocess
VERSION_FILE = "RELEASE-VERSION"


def call_git_describe(prefix='', cwd='.'):
    version_cmd = 'git describe --tags --match %s[0-9]*' % prefix
    last_tag_cmd = 'git describe --tags --match %s[0-9]* --abbrev=0' % prefix
    version = subprocess.run(
        version_cmd.split(),
        stdout=subprocess.PIPE,
        check=True,
        shell=False,
    ).stdout.decode()

    last_tag = subprocess.run(
        last_tag_cmd.split(),
        stdout=subprocess.PIPE,
        check=True,
        shell=False,
    ).stdout.decode()

    assert ' ' not in prefix
    assert version.strip().startswith(prefix)
    assert last_tag.strip().startswith(prefix)

    version = version.strip()[len(prefix):]
    last_tag = last_tag.strip()[len(prefix):]

    assert version.startswith(last_tag)
    if version != last_tag:
        # `version` does not match the last tag so we must be on an untagged commit.
        # In that case `version` is that tag with a suffix consisting of the number of commits and a commit ID.
        # To make this very clear, we want to insert `+dev` between the tag and the suffix. Also, replace the
        # hyphen in the suffix with a dot but without mangling any hyphens that might be in the tag.
        # In effect something like 0.5.3-rc5-post1-5-78df3e12 becomes 0.5.3-rc5-post1+dev5.78df3e12.
        version = f"{last_tag}+dev{version[len(last_tag) + 1:].replace('-', '.')}"
    return version


def get_version(prefix='', cwd='.', no_update_version_file=False):
    path = pathlib.Path(cwd) / VERSION_FILE
    try:
        with path.open("r") as f:
            release_version = f.read()
    except FileNotFoundError:
        release_version = None

    version = call_git_describe(prefix, cwd)

    if no_update_version_file:
        return version

    if version is None:
        raise ValueError("Cannot find the version number!")

    if version != release_version:
        with path.open("w") as f:
            f.write(version)

    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-update-version-file', action='store_true', default=False)
    args = parser.parse_args()
    print(get_version(prefix='v', no_update_version_file=args.no_update_version_file))
