"""Streamlit utilities."""


def in_streamlit() -> bool:
    """Return True when the current process is running inside a Streamlit app."""
    try:
        import logging

        from streamlit.runtime.scriptrunner import get_script_run_ctx

        for name in logging.Logger.manager.loggerDict:
            if name.startswith("streamlit"):
                logging.getLogger(name).setLevel(logging.ERROR)

        return get_script_run_ctx() is not None
    except ImportError:
        return False
