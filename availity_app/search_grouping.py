"""Group consecutive rows that share the same claim-search criteria."""
from availity_app.utils import (
    normalize_dob,
    normalize_patient_names,
    resolve_service_search_dates,
    row_has_valid_dob,
    safe_alt_patient_id,
    safe_field,
    safe_invoice_number,
)


def supports_search_grouping(payer_config):
    """Return True when this payer may reuse one search for multiple rows."""
    if not payer_config:
        return False
    return payer_config.get('supports_search_grouping', True)


def search_group_key(df, row_index, safe_field_fn=safe_field):
    """Normalized tuple identifying the claim-search form for a row."""
    row = df.iloc[row_index]
    member_id = safe_alt_patient_id(row, 'AltPatientID')
    last_name, first_name = normalize_patient_names(
        safe_field_fn(row, 'Last_Name'),
        safe_field_fn(row, 'First_Name'),
    )
    dob = normalize_dob(safe_field_fn(row, 'DOB'))
    start_date, end_date = resolve_service_search_dates(row, safe_field_fn)
    return (member_id, last_name, first_name, dob, start_date, end_date)


def row_eligible_for_grouping(df, row_index, safe_field_fn=safe_field):
    """Rows need invoice + valid DOB to participate in a shared search."""
    row = df.iloc[row_index]
    if not safe_invoice_number(row, 'InvoiceNumber'):
        return False
    if not row_has_valid_dob(row, safe_field_fn):
        return False
    key = search_group_key(df, row_index, safe_field_fn)
    if not key[0] or not key[1]:
        return False
    if not key[4] and not key[5]:
        return False
    return True


def build_consecutive_search_groups(work_queue, df, payer_config):
    """Split ``work_queue`` into consecutive index groups with the same search key.

    Returns a list of lists of dataframe row indices.  Ineligible rows are
    always placed in single-item groups.
    """
    if not work_queue:
        return []
    if not supports_search_grouping(payer_config):
        return [[idx] for idx in work_queue]

    groups = []
    current = []
    current_key = None

    for idx in work_queue:
        if not row_eligible_for_grouping(df, idx):
            if current:
                groups.append(current)
                current = []
                current_key = None
            groups.append([idx])
            continue

        key = search_group_key(df, idx)
        if current and key == current_key:
            current.append(idx)
        else:
            if current:
                groups.append(current)
            current = [idx]
            current_key = key

    if current:
        groups.append(current)
    return groups
