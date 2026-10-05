"""Offline checks for the isolated Project 2 Agent baseline."""
import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / 'external' / 'aJLL' / 'Agent' / 'agent.py'
REQUIRED_IMPORTS = ('agno.agent', 'agno.models.google', 'agno.tools.yfinance',
                    'agno.tools.duckduckgo', 'agno.tools.reasoning', 'agno.media')
REQUIRED_NAMES = ('Agent', 'Gemini', 'YFinanceTools', 'DuckDuckGoTools',
                  'ReasoningTools', 'Image')


def main():
    if not REFERENCE.is_file():
        raise FileNotFoundError(REFERENCE)
    tree = ast.parse(REFERENCE.read_text(), filename=str(REFERENCE))
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
               for alias in node.names}
    froms = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    expected_froms = {'agno.agent', 'agno.models.google', 'agno.tools.yfinance',
                      'agno.tools.duckduckgo', 'agno.tools.reasoning', 'agno.media'}
    missing_source = sorted(expected_froms - froms)
    if missing_source:
        raise AssertionError('reference imports missing: ' + repr(missing_source))
    for module in REQUIRED_IMPORTS:
        importlib.import_module(module)
    namespace = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            namespace.update(alias.asname or alias.name for alias in node.names)
    missing_names = sorted(set(REQUIRED_NAMES) - namespace)
    if missing_names:
        raise AssertionError('reference names missing: ' + repr(missing_names))
    print('python imports: PASS')
    print('reference source: PASS')
    print('GOOGLE_API_KEY present:', 'yes' if __import__('os').environ.get('GOOGLE_API_KEY') else 'no')
    print('live API call: SKIPPED (no key is read or stored by this check)')


if __name__ == '__main__':
    main()
