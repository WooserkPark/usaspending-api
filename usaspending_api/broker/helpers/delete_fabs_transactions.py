import logging

from django.db import connections
from usaspending_api.broker.helpers.delete_stale_fabs import delete_stale_fabs
from usaspending_api.common.helpers.timing_helpers import timer


logger = logging.getLogger("console")


def delete_fabs_transactions(ids_to_delete):
    """ids_to_delete are published_award_financial_assistance_ids"""
    if ids_to_delete:
        with timer(f"deleting {len(ids_to_delete)} stale FABS data", logger.info):
            update_award_ids = delete_stale_fabs(ids_to_delete)

    else:
        update_award_ids = []
        logger.info("Nothing to delete...")

    return update_award_ids


def get_delete_pks_for_afa_keys(afa_ids_to_delete):
    """
    When we read from FABS delete files, we are only reading in afa_generated_unique keys (AFA).  Unfortunately,
    AFAs on their own do not give us enough information to delete records since AFAs are reused in Broker.  This
    function converts AFAs into a list of published_award_financial_assistance_id primary keys that should no
    longer exist in USAspending for the supplied set of AFAs.  Notice that published_award_financial_assistance
    records marked as is_active will not be deleted since they are the current, active, non-deleted version of
    the FABS record for that AFA.
    """
    if not afa_ids_to_delete:
        return []

    uppercased = tuple(afa.upper() for afa in afa_ids_to_delete)

    sql = """
    select  published_award_financial_assistance_id
    from    published_award_financial_assistance
    where   upper(afa_generated_unique) in %s and
            is_active is not true
    """

    with connections["data_broker"].cursor() as cursor:
        cursor.execute(sql, [uppercased])
        rows = cursor.fetchall()

    return [row[0] for row in rows]
