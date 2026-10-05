"""Minimal student-owned runner for the professor Agent baseline."""
import os

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.reasoning import ReasoningTools


def main():
    if not os.environ.get('GOOGLE_API_KEY'):
        raise SystemExit('GOOGLE_API_KEY must be supplied at runtime; it is never stored in source.')
    agent = Agent(
        model=Gemini(id='gemini-2.5-flash'),
        tools=[ReasoningTools(add_instructions=True)],
        instructions='Use tables to display data.',
        markdown=True,
    )
    agent.print_response(
        'Explain how AI agents differ from a single language-model completion in a short table.',
        stream=True,
    )


if __name__ == '__main__':
    main()
