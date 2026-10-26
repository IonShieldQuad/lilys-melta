"""Stage an exact commit of lilys-melta as a loadable mod directory.

Why python: on this box `git archive <rev> | tar -x` fails because the MSYS tar on PATH
is bsdtar and tries to read the pipe as a tape device. tarfile reads the same stream in
process, so the staged tree is byte-for-byte what the commit holds -- which is the only
way to prove "this commit loads" rather than "my working tree loads".

Usage: python stage_rev.py <rev> <dest>      e.g. python stage_rev.py 7615d38 C:/.../mods/lilys-melta
"""
import subprocess
import sys
import tarfile


def main():
    rev = sys.argv[1]
    dest = sys.argv[2]
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                          text=True, check=True).stdout.strip()
    archive = subprocess.run(["git", "-C", repo, "archive", "--format=tar", rev],
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=__import__("io").BytesIO(archive)) as tar:
        tar.extractall(dest)
    print("staged %s into %s" % (rev, dest))


if __name__ == "__main__":
    main()
