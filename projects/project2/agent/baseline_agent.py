"""Minimal student-owned runner for the professor Agent baseline."""
import os

from professor_baseline import construct_reference


def main():
    if not os.environ.get('GOOGLE_API_KEY'):
        raise SystemExit('GOOGLE_API_KEY must be supplied at runtime; it is never stored in source.')
    agents, active, prompt = construct_reference()
    print('Student runtime model:', agents[active].model.id)
    agents[active].print_response(prompt, stream=True)


if __name__ == '__main__':
    main()
