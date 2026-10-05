"""Fetch the exact Python 3.8 amd64 TF wheel with resumable verified ranges.

Run from the repository root with:
  python3 projects/project2/modelb6/fetch_tensorflow_wheel.py

The wheel and partial chunks live in a Git-ignored wheelhouse. The PyPI URL is
looked up at runtime; only the expected filename, size and SHA-256 are pinned.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request


FILENAME = "tensorflow_cpu-2.13.1-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
EXPECTED_SIZE = 186523151
EXPECTED_SHA256 = "ba6eec4d9a1e86d36fd7e7d010e07ce69702bb3cb68bc33a02a668b1928772a9"
CHUNK_SIZE = 1024 * 1024
WHEELHOUSE = Path(__file__).resolve().parent / "wheelhouse"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_chunk(url, start, end):
    chunk = WHEELHOUSE / f"{FILENAME}.{start:09d}-{end:09d}.part"
    expected_length = end - start + 1
    if chunk.is_file() and chunk.stat().st_size == expected_length:
        return chunk
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    for attempt in range(1, 9):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content_range = response.headers.get("Content-Range")
                expected_range = f"bytes {start}-{end}/{EXPECTED_SIZE}"
                if response.status != 206 or content_range != expected_range:
                    raise RuntimeError(f"unexpected range response: {response.status} {content_range}")
                payload = response.read()
            if len(payload) != expected_length:
                raise RuntimeError(f"short range {start}-{end}: {len(payload)} bytes")
            chunk.write_bytes(payload)
            return chunk
        except (OSError, RuntimeError) as error:
            if attempt == 8:
                raise RuntimeError(f"range {start}-{end} failed after 8 attempts") from error
            time.sleep(min(attempt * 2, 10))
    raise AssertionError("unreachable")


def main():
    WHEELHOUSE.mkdir(parents=True, exist_ok=True)
    wheel = WHEELHOUSE / FILENAME
    if wheel.is_file() and wheel.stat().st_size == EXPECTED_SIZE and sha256(wheel) == EXPECTED_SHA256:
        print(f"verified cached wheel: {wheel} SHA-256 {EXPECTED_SHA256}", flush=True)
        return

    metadata_url = "https://pypi.org/pypi/tensorflow-cpu/2.13.1/json"
    with urllib.request.urlopen(metadata_url, timeout=30) as response:
        metadata = json.load(response)
    release = next(item for item in metadata["urls"] if item["filename"] == FILENAME)
    if release["size"] != EXPECTED_SIZE or release["digests"]["sha256"] != EXPECTED_SHA256:
        raise RuntimeError("PyPI wheel metadata differs from the pinned size or SHA-256")
    url = release["url"]
    ranges = [(start, min(start + CHUNK_SIZE, EXPECTED_SIZE) - 1)
              for start in range(0, EXPECTED_SIZE, CHUNK_SIZE)]
    print(f"fetching {len(ranges)} verified-size ranges into {WHEELHOUSE}", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_chunk, url, start, end): (start, end)
                   for start, end in ranges}
        for completed, future in enumerate(as_completed(futures), 1):
            future.result()
            if completed % 16 == 0 or completed == len(ranges):
                print(f"ranges complete: {completed}/{len(ranges)}", flush=True)

    assembled = WHEELHOUSE / (FILENAME + ".assembling")
    with assembled.open("wb") as output:
        for start, end in ranges:
            chunk = WHEELHOUSE / f"{FILENAME}.{start:09d}-{end:09d}.part"
            with chunk.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
    actual_size = assembled.stat().st_size
    actual_hash = sha256(assembled)
    if actual_size != EXPECTED_SIZE or actual_hash != EXPECTED_SHA256:
        assembled.unlink()
        for start, end in ranges:
            (WHEELHOUSE / f"{FILENAME}.{start:09d}-{end:09d}.part").unlink(missing_ok=True)
        raise RuntimeError(f"wheel integrity failed: size={actual_size}, SHA-256={actual_hash}")
    assembled.replace(wheel)
    print(f"verified wheel: {wheel} SHA-256 {actual_hash}", flush=True)


if __name__ == "__main__":
    main()
