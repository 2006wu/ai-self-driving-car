"""Download pinned wheels concurrently, then let pip resolve/install them offline."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    requirements = Path(sys.argv[1])
    packages = [line.strip() for line in requirements.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')]
    with tempfile.TemporaryDirectory(prefix='wheels-') as destination:
        def download(package):
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'download', '--no-deps',
                 '--only-binary=:all:', '--dest', destination, package],
                capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            print('Downloaded ' + package, flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(download, packages))
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index',
                        '--find-links', destination, '-r', str(requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)


if __name__ == '__main__':
    main()
