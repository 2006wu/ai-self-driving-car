"""Prerequisite checks for tests using external reference files."""
from functools import wraps
from pathlib import Path


def requires_file(path, obtain):
    """Check at test execution time so restored files enable the original checks."""
    path = Path(path)

    def decorate(test):
        @wraps(test)
        def run(self, *args, **kwargs):
            if not path.is_file():
                self.skipTest(f'Missing external file: {path}. {obtain}')
            return test(self, *args, **kwargs)
        return run
    return decorate
