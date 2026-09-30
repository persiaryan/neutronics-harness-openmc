"""Acquire only the pin-cell tables from the official public OpenMC archive.

Never publishes nuclear data. The full stream is hashed; only ten HDF5 files
are retained in an operator-selected directory outside the checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

URL = "https://anl.app.box.com/public/static/6qr7jezzihkj9p9esl5jn19qgpujyjyz.xz"
TABLES = {n: "neutron" for n in ("H1", "O16", "U235", "U238", "Zr90", "Zr91", "Zr92", "Zr94", "Zr96")}
TABLES["c_H_in_H2O"] = "thermal"
ROOT = Path(__file__).resolve().parents[1]


class HashedReader:
    def __init__(self, stream):
        self.stream, self.sha, self.count = stream, hashlib.sha256(), 0

    def read(self, size=-1):
        raw = self.stream.read(size)
        self.sha.update(raw)
        self.count += len(raw)
        if self.count > 12_000_000_000:
            raise ValueError("Archive exceeds download limit")
        return raw


def prepare(source, output, expected=None):
    output = Path(output).absolute()
    if output.exists() or output == Path.home() or ROOT == output or ROOT in output.parents:
        raise ValueError("Use a new data directory outside the checkout")
    output.mkdir(parents=True)
    found = {}
    with (urllib.request.urlopen(URL, timeout=120) if source == "download" else Path(source).open("rb")) as stream:
        incoming = HashedReader(stream)
        with tarfile.open(fileobj=incoming, mode="r|xz") as archive:
            for member in archive:
                name = Path(member.name).name
                if name not in {n + ".h5" for n in TABLES}:
                    continue
                if name in found or not member.isfile() or not 0 < member.size <= 3_000_000_000:
                    raise ValueError("Duplicate, linked or oversized required library")
                sha = hashlib.sha256()
                with archive.extractfile(member) as src, (output / name).open("xb") as dst:
                    while raw := src.read(1024 * 1024):
                        sha.update(raw)
                        dst.write(raw)
                found[name] = dict(sha256=sha.hexdigest(), bytes=member.size,
                                   tables=[[TABLES[name[:-3]], name[:-3]]])
                print("Retained " + name, flush=True)
        while incoming.read(1024 * 1024):
            pass
    if set(found) != {n + ".h5" for n in TABLES}:
        raise ValueError("Missing required tables")
    root = ET.Element("cross_sections")
    for table, kind in sorted(TABLES.items()):
        ET.SubElement(root, "library", materials=table, path=table + ".h5", type=kind)
    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    (output / "cross_sections.xml").write_bytes(raw)
    result = dict(index_sha256=hashlib.sha256(raw).hexdigest(), files=found,
                  snapshot="read_only_host_mount_with_before_after_hash_checks")
    provenance = dict(source_url=URL, dataset="ENDF/B-VIII.1", processor="NJOY2016.78",
                      archive_bytes=incoming.count, archive_sha256=incoming.sha.hexdigest(), data=result)
    if expected is not None and provenance != expected:
        raise ValueError("Public data identity mismatch; retain directory for diagnosis")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="'download' or the official local .tar.xz archive")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path, help="New JSON receipt outside the flat data directory")
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()
    if args.receipt.exists() or args.output.absolute() in args.receipt.absolute().parents:
        parser.error("receipt must be new and outside the data directory")
    expected = json.loads(args.expected.read_bytes()) if args.expected else None
    result = prepare(args.source, args.output, expected)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
