"""Student runtime model selection; the API key stays in the environment."""
import os

DEFAULT_MODEL_ID = 'gemini-3.8-flash'
REFERENCE_MODEL_ID = 'gemini-2.5-flash'


def runtime_model_id():
    """Read the optional override at construction time, including offline checks."""
    model_id = os.environ.get('GEMINI_MODEL_ID', DEFAULT_MODEL_ID).strip()
    if not model_id:
        raise ValueError('GEMINI_MODEL_ID must be a nonempty model ID')
    return model_id
