"""
Jira Ticket Number(s): DEV-5121

    The original ticket was to delete FABS records that still incorrectly live in USAspending, however,
    this script does a wee bit more than that by performing a general synchronization between Broker
    and USAspending:

        - Delete FABS/FPDS records that live in USAspending that should not
        - Load FABS/FPDS records that are missing from USAspending

    This updates both the USAspending source_*_transaction and transaction_F*S tables.

    Note that this script does NOT compare records nor does it attempt to find missing updates.  It ONLY
    looks for primary key differences.

Expected CLI:

    $ ./manage.py resynchronize_fabs_and_fpds

Life expectancy:

    Theoretically this script can go away once it has been run all the way through to production, however,
    data quality is an ongoing concern.  It might be a good idea to keep this thing around indefinitely,
    update it as necessary, and run it on occasion should USAspending and Broker desynchronize again.

"""
import logging

from datetime import date
from django.core.management import BaseCommand, call_command
from django.db import connections, transaction
from usaspending_api.common.helpers.sql_helpers import execute_sql, execute_dml_sql, execute_sql_return_single_value
from usaspending_api.common.helpers.timing_helpers import ScriptTimer as Timer
from usaspending_api.etl.transaction_loaders.fpds_loader import load_fpds_transactions

logger = logging.getLogger("script")


TEMP_TABLE_PREFIX = "temp_dev_5121"

FABS_ID_COLUMN = "published_award_financial_assistance_id"
FPDS_ID_COLUMN = "detached_award_procurement_id"

BROKER_FABS_TABLE = "published_award_financial_assistance"
BROKER_FPDS_TABLE = "detached_award_procurement"

GET_BROKER_FABS_IDS_SQL = f"select {FABS_ID_COLUMN} from {BROKER_FABS_TABLE} where is_active is true"
GET_BROKER_FPDS_IDS_SQL = f"select {FPDS_ID_COLUMN} from {BROKER_FPDS_TABLE}"

VALIDATE_BROKER_FABS_DELETE_IDS_SQL = (
    f"select {FABS_ID_COLUMN} from {BROKER_FABS_TABLE} where is_active is true and {FABS_ID_COLUMN} in %s"
)
VALIDATE_BROKER_FPDS_DELETE_IDS_SQL = f"select {FPDS_ID_COLUMN} from {BROKER_FPDS_TABLE} where {FPDS_ID_COLUMN} in %s"

TEMP_FABS_ID_TABLE = f"{TEMP_TABLE_PREFIX}_broker_active_fabs_ids"
TEMP_FPDS_ID_TABLE = f"{TEMP_TABLE_PREFIX}_broker_active_fpds_ids"

LOCAL_FABS_SOURCE_TABLE = "source_assistance_transaction"
LOCAL_FABS_TRANSACTION_TABLE = "transaction_fabs"
LOCAL_FPDS_SOURCE_TABLE = "source_procurement_transaction"
LOCAL_FPDS_TRANSACTION_TABLE = "transaction_fpds"

TEMP_SOURCE_FABS_DELETE_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FABS_SOURCE_TABLE}_delete_ids"
TEMP_SOURCE_FABS_ADD_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FABS_SOURCE_TABLE}_add_ids"
TEMP_TRANSACTION_FABS_DELETE_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FABS_TRANSACTION_TABLE}_delete_ids"
TEMP_TRANSACTION_FABS_ADD_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FABS_TRANSACTION_TABLE}_add_ids"

TEMP_SOURCE_FPDS_DELETE_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FPDS_SOURCE_TABLE}_delete_ids"
TEMP_SOURCE_FPDS_ADD_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FPDS_SOURCE_TABLE}_add_ids"
TEMP_TRANSACTION_FPDS_DELETE_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FPDS_TRANSACTION_TABLE}_delete_ids"
TEMP_TRANSACTION_FPDS_ADD_IDS_TABLE = f"{TEMP_TABLE_PREFIX}_{LOCAL_FPDS_TRANSACTION_TABLE}_add_ids"

TASKS = [
    {
        "run_me": "transfer_ids_from_broker",
        "broker_sql": GET_BROKER_FABS_IDS_SQL,
        "destination_table": TEMP_FABS_ID_TABLE,
        "key_column": FABS_ID_COLUMN,
    },
    {
        "run_me": "transfer_ids_from_broker",
        "broker_sql": GET_BROKER_FPDS_IDS_SQL,
        "destination_table": TEMP_FPDS_ID_TABLE,
        "key_column": FPDS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": LOCAL_FABS_SOURCE_TABLE,
        "subtrahend_table": TEMP_FABS_ID_TABLE,
        "destination_table": TEMP_SOURCE_FABS_DELETE_IDS_TABLE,
        "key_column": FABS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": TEMP_FABS_ID_TABLE,
        "subtrahend_table": LOCAL_FABS_SOURCE_TABLE,
        "destination_table": TEMP_SOURCE_FABS_ADD_IDS_TABLE,
        "key_column": FABS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": LOCAL_FABS_TRANSACTION_TABLE,
        "subtrahend_table": TEMP_FABS_ID_TABLE,
        "destination_table": TEMP_TRANSACTION_FABS_DELETE_IDS_TABLE,
        "key_column": FABS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": TEMP_FABS_ID_TABLE,
        "subtrahend_table": LOCAL_FABS_TRANSACTION_TABLE,
        "destination_table": TEMP_TRANSACTION_FABS_ADD_IDS_TABLE,
        "key_column": FABS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": LOCAL_FPDS_SOURCE_TABLE,
        "subtrahend_table": TEMP_FPDS_ID_TABLE,
        "destination_table": TEMP_SOURCE_FPDS_DELETE_IDS_TABLE,
        "key_column": FPDS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": TEMP_FPDS_ID_TABLE,
        "subtrahend_table": LOCAL_FPDS_SOURCE_TABLE,
        "destination_table": TEMP_SOURCE_FPDS_ADD_IDS_TABLE,
        "key_column": FPDS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": LOCAL_FPDS_TRANSACTION_TABLE,
        "subtrahend_table": TEMP_FPDS_ID_TABLE,
        "destination_table": TEMP_TRANSACTION_FPDS_DELETE_IDS_TABLE,
        "key_column": FPDS_ID_COLUMN,
    },
    {
        "run_me": "subtract_table",
        "minuend_table": TEMP_FPDS_ID_TABLE,
        "subtrahend_table": LOCAL_FPDS_TRANSACTION_TABLE,
        "destination_table": TEMP_TRANSACTION_FPDS_ADD_IDS_TABLE,
        "key_column": FPDS_ID_COLUMN,
    },
    {
        "run_me": "validate_deletions",
        "source_temp_table": TEMP_SOURCE_FABS_DELETE_IDS_TABLE,
        "transaction_temp_table": TEMP_TRANSACTION_FABS_DELETE_IDS_TABLE,
        "key_column": FABS_ID_COLUMN,
        "broker_sql": VALIDATE_BROKER_FABS_DELETE_IDS_SQL,
    },
    {
        "run_me": "validate_deletions",
        "source_temp_table": TEMP_SOURCE_FPDS_DELETE_IDS_TABLE,
        "transaction_temp_table": TEMP_TRANSACTION_FPDS_DELETE_IDS_TABLE,
        "key_column": FPDS_ID_COLUMN,
        "broker_sql": VALIDATE_BROKER_FPDS_DELETE_IDS_SQL,
    },
]


class OneLineTimer(Timer):
    def log_starting_message(self):
        pass

    def log_success_message(self):
        pass

    def log_message(self, rows_affected=None):
        msg = f" - {rows_affected:,} rows affected" if rows_affected not in (-1, None) else ""
        self.success_logger(f"[{self.message}] finished successfully after {self}{msg}")


def table_exists(table_name):
    return execute_sql_return_single_value(
        f"""
            select exists(
                select from information_schema.tables where table_schema = 'public' and table_name = '{table_name}'
            );
        """
    )


def get_ids(*temp_table_names):
    sql = " union ".join(f"select * from {t}" for t in temp_table_names)
    return [row[0] for row in execute_sql(sql)]


def get_row_count(table_name):
    row_count = execute_sql_return_single_value(f"select count(*) from {table_name}")
    logger.info(f"Found {row_count:,} rows in {table_name}")
    return row_count


def run_sql(timer_message, sql):
    with OneLineTimer(timer_message) as t:
        rows_affected = execute_dml_sql(sql)
    t.log_message(rows_affected)
    return rows_affected


def drop_table(table_name):
    run_sql(f"Drop {table_name}", f"drop table if exists {table_name}")


class Command(BaseCommand):
    apply_corrections = False
    do_not_recreate_temp_tables = False
    nuke_temp_tables = False
    do_not_create_fabs_delete_files = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply-corrections",
            action="store_true",
            help=(
                "If this switch is not supplied, no changes will be made to USAspending tables.  Temporary "
                "tables WILL be created, though.  Read below for a fun usage tip."
            ),
        )
        # This is intentionally a negative so the default behavior isn't to work with stale data.
        parser.add_argument(
            "--do-not-recreate-temp-tables",
            action="store_true",
            help=(
                "This is primarily for testing and debugging, but if this switch is supplied none of "
                "the temporary tables will be recreated if they already exist.  Read below for a fun "
                "usage tip."
            ),
        )
        parser.add_argument(
            "--nuke-temp-tables",
            action="store_true",
            help=(
                "If --apply-corrections is also supplied, will remove all temporary tables at the "
                "end of processing.  Does nothing if --apply-corrections is not also supplied."
            ),
        )
        parser.add_argument(
            "--do-not-create-fabs-delete-files",
            action="store_true",
            help="For FABS deletes, do not create delete files for deleted transactions.",
        )
        parser.epilog = (
            "Switches can be coordinated in such a way so as to provide a stopping point in the "
            "process which allows for data sanity checking.  For example, let's say you suspect "
            "there are data issues.  Run this script without any switches.  This will create a whole "
            "mess of temporary tables that you can use to verify corrections before applying them.  "
            "Once you're satisfied with the corrections, run the script again with the "
            "--do-not-recreate-temp-tables and --apply-corrections (and optionally --nuke-temp-tables) "
            "switches to have the corrections you just vetted applied to the appropriate USAspending "
            "tables.  Neat, eh?"
        )

    def handle(self, *args, **options):
        self.apply_corrections = options["apply_corrections"]
        self.do_not_recreate_temp_tables = options["do_not_recreate_temp_tables"]
        self.nuke_temp_tables = options["nuke_temp_tables"]
        self.do_not_create_fabs_delete_files = options["do_not_create_fabs_delete_files"]

        with Timer("Re-synchronize FABS and FPDS transactions"):
            for task in TASKS:
                getattr(self, task["run_me"])(**task)

            self.document_artifacts()

            if not self.apply_corrections:
                logger.info("--apply-corrections switch not supplied.  Bailing before any data are harmed.")
                return

            self.delete_fabs_source_records()
            self.add_fabs_source_records()

            self.delete_fpds_source_records()
            self.add_fpds_source_records()

            with transaction.atomic():
                self.delete_and_add_fabs_transaction_records()
                self.delete_and_add_fpds_transaction_records()

            if self.nuke_temp_tables:
                self.drop_temp_tables()

    def transfer_ids_from_broker(self, broker_sql, destination_table, key_column, **kwargs):
        if self.do_not_recreate_temp_tables and table_exists(destination_table):
            logger.info(f"{destination_table} exists and --do-not-recreate-temp-tables was supplied.  Not recreating.")
            return get_row_count(destination_table)

        run_sql(f"Drop {destination_table}", f"drop table if exists {destination_table}")

        rows_affected = run_sql(
            f"Pull active {key_column}s from Broker",
            f"""
                create
                table   {destination_table} as
                select  bs.{key_column}
                from    dblink('broker_server', '{broker_sql}') as bs ({key_column} integer)
            """,
        )

        run_sql(
            f"Index {destination_table}",
            f"""
                alter table {destination_table}
                add constraint pk_{destination_table}
                primary key ({key_column})
            """,
        )

        run_sql(f"Analyze {destination_table}", f"analyze {destination_table}")

        return rows_affected

    def subtract_table(self, minuend_table, subtrahend_table, destination_table, key_column, **kwargs):
        """
        We're finding all IDS in the minuend_table that do not exist in the subtrahend_table table
        so if you think of it like set math, it's pretty much minuend_table - subtrahend_table.
        """
        if self.do_not_recreate_temp_tables and table_exists(destination_table):
            logger.info(f"{destination_table} exists and --do-not-recreate-temp-tables was supplied.  Not recreating.")
            return get_row_count(destination_table)

        run_sql(f"Drop {destination_table}", f"drop table if exists {destination_table}")

        return run_sql(
            f"Create {destination_table}",
            f"""
                create
                table   {destination_table} as
                select  m.{key_column}
                from    {minuend_table} m
                        left outer join {subtrahend_table} s on s.{key_column} = m.{key_column}
                where   s.{key_column} is null
            """,
        )

    @staticmethod
    def validate_deletions(source_temp_table, transaction_temp_table, key_column, broker_sql, **kwargs):
        """
        This is probably unnecessary, but let's double check our deletions just in case a record
        didn't get copied over for whatever reason.  It shouldn't take very long.
        """
        with OneLineTimer(f"Validate {key_column}s deletions") as t:
            ids = tuple(
                row[0]
                for row in execute_sql(
                    f"""
                    select {key_column} from {source_temp_table}
                    union
                    select {key_column} from {transaction_temp_table}
                """
                )
            )
            if not ids:
                return
            sql = broker_sql % (str(ids) if len(ids) > 1 else f"({ids[0]})")

            connection = connections["data_broker"]
            with connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()

            ids = tuple(row[0] for row in results)
            if ids:
                raise RuntimeError(
                    f"ERROR!  Somehow we managed to identify {key_column}s that should not be "
                    f"deleted!  {ids if len(ids) < 1000 else 'There are too many to list.'}"
                )

        t.log_message()

    @staticmethod
    def document_artifacts():
        messages = [
            'These are the "temp" tables that were generated as a result of this script.  If the '
            "--nuke-temp-tables option was provided, they will be removed at the end of processing.  "
            "If the script crashes, they will remain for your debugging pleasure:"
        ]

        for task in TASKS:
            if task["run_me"] == "transfer_ids_from_broker":
                messages.append(f"  {task['destination_table']}: All active {task['key_column']}s from Broker")
            elif task["run_me"] == "subtract_table":
                messages.append(
                    f"  {task['destination_table']}: All {task['key_column']}s in {task['minuend_table']} "
                    f"that are not in {task['subtrahend_table']}"
                )
            else:
                # This task type generates no artifact.
                pass

        logger.info("\n".join(messages))

    def delete_fabs_source_records(self):
        ids = get_ids(TEMP_SOURCE_FABS_DELETE_IDS_TABLE)
        if not ids:
            logger.info("No FABS source records to delete")
            return

        command = ["delete_assistance_records"]
        if self.do_not_create_fabs_delete_files:
            command.append("--skip-upload")
        command.append("--ids")

        call_command(*command, *ids)

    @staticmethod
    def add_fabs_source_records():
        ids = get_ids(TEMP_SOURCE_FABS_ADD_IDS_TABLE)
        if ids:
            call_command("transfer_assistance_records", "--ids", *ids)
        else:
            logger.info("No FABS source records to add")

    @staticmethod
    def delete_fpds_source_records():
        ids = get_ids(TEMP_SOURCE_FPDS_DELETE_IDS_TABLE)
        if ids:
            call_command("delete_procurement_records", "--ids", *ids)
        else:
            logger.info("No FPDS source records to delete")

    @staticmethod
    def add_fpds_source_records():
        ids = get_ids(TEMP_SOURCE_FPDS_ADD_IDS_TABLE)
        if ids:
            call_command("transfer_procurement_records", "--ids", *ids)
        else:
            logger.info("No FPDS source records to add")

    @staticmethod
    def delete_and_add_fabs_transaction_records():
        from usaspending_api.broker.helpers.delete_fabs_transactions import delete_fabs_transactions
        from usaspending_api.broker.helpers.upsert_fabs_transactions import upsert_fabs_transactions

        with Timer("Insert/delete FABS transactions"):
            delete_ids = get_ids(TEMP_TRANSACTION_FABS_DELETE_IDS_TABLE)
            add_ids = get_ids(TEMP_TRANSACTION_FABS_ADD_IDS_TABLE)
            if not delete_ids and not add_ids:
                logger.info("No FABS transaction records to add or delete")
                return

            update_award_ids = delete_fabs_transactions(delete_ids)
            upsert_fabs_transactions(add_ids, update_award_ids)

    @staticmethod
    def delete_and_add_fpds_transaction_records():
        from usaspending_api.broker.management.commands.load_fpds_transactions import Command as FPDSCommand
        from usaspending_api.etl.transaction_loaders.fpds_loader import delete_stale_fpds

        with Timer("Insert/delete FPDS transactions"):
            delete_ids = get_ids(TEMP_TRANSACTION_FPDS_DELETE_IDS_TABLE)
            add_ids = get_ids(TEMP_TRANSACTION_FPDS_ADD_IDS_TABLE)
            if not delete_ids and not add_ids:
                logger.info("No FPDS transaction records to add or delete")
                return

            # Structure necessary for deletes.
            delete_ids = {date.today().strftime("%Y-%m-%d"): delete_ids}

            fpds_command = FPDSCommand()
            stale_awards = delete_stale_fpds(delete_ids)
            stale_awards.extend(load_fpds_transactions(add_ids))
            fpds_command.update_award_records(awards=stale_awards, skip_cd_linkage=False)

    @staticmethod
    def drop_temp_tables():
        for task in TASKS:
            if "destination_table" in task:
                drop_table(task["destination_table"])
