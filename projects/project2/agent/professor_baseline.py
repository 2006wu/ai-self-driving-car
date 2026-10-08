"""Construct the reference examples offline with explicit Agno 3 API adapters."""
import ast
from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.yfinance import YFinanceTools
from model_config import runtime_model_id

REFERENCE = Path(__file__).resolve().parents[3] / 'external/aJLL/Agent/agent.py'
FACTORIES = dict(Agent=Agent, Gemini=Gemini, DuckDuckGoTools=DuckDuckGoTools,
                 ReasoningTools=ReasoningTools, YFinanceTools=YFinanceTools)


def value(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [value(item) for item in node.elts]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FACTORIES:
        name = node.func.id
        kwargs = {item.arg: value(item.value) for item in node.keywords}
        if None in kwargs or node.args:
            raise ValueError('unrecognized reference call')
        if name == 'Gemini':
            # Reference ID is historical; student calls use the current API model.
            kwargs['id'] = runtime_model_id()
        if name == 'YFinanceTools':
            for old in ('stock_price', 'analyst_recommendations', 'company_info', 'company_news'):
                if old in kwargs:
                    kwargs['enable_' + old] = kwargs.pop(old)
        if name == 'Agent':
            if 'agent_id' in kwargs:
                kwargs['id'] = kwargs.pop('agent_id')
            if 'add_datetime_to_instructions' in kwargs:
                kwargs['add_datetime_to_context'] = kwargs.pop('add_datetime_to_instructions')
            # Removed display-only flag; does not affect the active reasoning example.
            kwargs.pop('show_tool_calls', None)
        return FACTORIES[name](**kwargs)
    raise ValueError('unsupported reference expression: ' + type(node).__name__)


def construct_reference():
    """Adapt reference constructors to student runtime; never call the API here."""
    tree = ast.parse(REFERENCE.read_text(), filename=str(REFERENCE))
    agents, requests = {}, []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'Agent'):
            agents[node.targets[0].id] = value(node.value)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Attribute)
              and node.value.func.attr == 'print_response'):
            call = node.value
            requests.append((call.func.value.id, ast.literal_eval(call.args[0])))
    if len(agents) != 6 or len(requests) != 1:
        raise ValueError('reference baseline structure changed; inspect it before running')
    name, prompt = requests[0]
    return agents, name, prompt


def reference_model_ids():
    """Inspect historical IDs without changing the professor-owned source."""
    tree = ast.parse(REFERENCE.read_text(), filename=str(REFERENCE))
    return {ast.literal_eval(item.value)
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == 'Gemini'
            for item in node.keywords if item.arg == 'id'}
