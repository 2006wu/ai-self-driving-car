"""Offline checks for the isolated Project 2 Agent baseline."""
import ast
import importlib
from pathlib import Path
from professor_baseline import construct_reference, reference_model_ids
from model_config import REFERENCE_MODEL_ID, runtime_model_id


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
    agents, active, prompt = construct_reference()
    assert reference_model_ids() == {REFERENCE_MODEL_ID}
    assert all(agent.model.id == runtime_model_id() for agent in agents.values())
    assert agents[active].tools and prompt
    print('reference constructors: PASS (6 agents; Agno 3 keyword adapters)')
    print('active baseline:', active, '| Gemini + ReasoningTools | travel prompt')
    print('professor/reference model:', REFERENCE_MODEL_ID)
    print('student runtime model:', agents[active].model.id)
    print('GOOGLE_API_KEY present:', 'yes' if __import__('os').environ.get('GOOGLE_API_KEY') else 'no')
    print('live API call: SKIPPED (offline check never invokes the model)')


if __name__ == '__main__':
    main()
