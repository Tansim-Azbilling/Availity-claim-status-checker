"""Persist UI discovery results (remittance paths, line columns) across runs."""
import json
import os
import threading

_CACHE_VERSION = 1
_CACHE_FILENAME = '.availity_cache.json'
_lock = threading.Lock()


def cache_file_path(output_folder):
    """Return the path to the discovery cache file for an output folder."""
    if not output_folder:
        return None
    return os.path.join(output_folder, _CACHE_FILENAME)


def _load_full_cache(output_folder):
    path = cache_file_path(output_folder)
    if not path or not os.path.isfile(path):
        return {'version': _CACHE_VERSION, 'payers': {}}
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {'version': _CACHE_VERSION, 'payers': {}}
        data.setdefault('payers', {})
        return data
    except (OSError, json.JSONDecodeError):
        return {'version': _CACHE_VERSION, 'payers': {}}


def _write_full_cache(output_folder, data):
    path = cache_file_path(output_folder)
    if not path:
        return
    data['version'] = _CACHE_VERSION
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp_path = path + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(temp_path, path)
    except OSError:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def load_payer_discovery(output_folder, payer_name):
    """Return cached discovery dict for a payer, or empty dict."""
    if not output_folder or not payer_name:
        return {}
    with _lock:
        cache = _load_full_cache(output_folder)
    return dict(cache.get('payers', {}).get(payer_name, {}))


def save_payer_discovery(output_folder, payer_name, section, value):
    """Merge ``value`` into ``section`` for ``payer_name`` and persist."""
    if not output_folder or not payer_name or not section:
        return
    with _lock:
        cache = _load_full_cache(output_folder)
        payers = cache.setdefault('payers', {})
        entry = payers.setdefault(payer_name, {})
        entry[section] = value
        _write_full_cache(output_folder, cache)


def hydrate_remit_amount_paths(output_folder, payer_name, session_paths):
    """Load disk cache into the in-memory remittance path dict."""
    if not payer_name:
        return
    disk = load_payer_discovery(output_folder, payer_name)
    cached = disk.get('remit_amount_paths')
    if not isinstance(cached, dict):
        return
    for key, path in cached.items():
        if key not in session_paths and isinstance(path, dict):
            session_paths[key] = path


def persist_remit_amount_paths(output_folder, payer_name, session_paths):
    """Write all session remittance paths to disk."""
    if not session_paths:
        return
    save_payer_discovery(
        output_folder, payer_name, 'remit_amount_paths', dict(session_paths),
    )


def get_line_table_columns(output_folder, payer_name):
    """Return cached line-table column map, or None."""
    disk = load_payer_discovery(output_folder, payer_name)
    cols = disk.get('line_table_col_defaults')
    return dict(cols) if isinstance(cols, dict) else None


def persist_line_table_columns(output_folder, payer_name, columns):
    """Persist resolved line-table column indices."""
    if not columns:
        return
    save_payer_discovery(
        output_folder, payer_name, 'line_table_col_defaults', dict(columns),
    )
