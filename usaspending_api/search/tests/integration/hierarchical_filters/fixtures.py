import pytest
from model_mommy import mommy
from datetime import datetime

from usaspending_api.accounts.models import TreasuryAppropriationAccount

# ensures that tests aren't failing for having the wrong TAS. We trust functionality of tas_rendering_label_to_component_dictionary because it is tested elsewhere
TAS_STRINGS = ["000-X-0126-000", "010-024-X-8445-002", "012-2000/2000-1231-000", "020-012-2000/2000-1231-000"]
TAS_DICTIONARIES = [
    TreasuryAppropriationAccount.tas_rendering_label_to_component_dictionary(tas) for tas in TAS_STRINGS
]


@pytest.fixture
def award_with_tas(db):
    award(db, 1)
    tas(db, 1, 0)


@pytest.fixture
def award_with_bpoa_tas(db):
    award(db, 1)
    tas(db, 1, 2)


@pytest.fixture
def award_with_ata_tas(db):
    award(db, 1)
    tas(db, 1, 3)


@pytest.fixture
def award_with_multiple_tas(db):
    award(db, 1)
    tas(db, 1, 0)
    tas(db, 1, 1)


@pytest.fixture
def award_without_tas(db):
    award(db, 2)


@pytest.fixture
def multiple_awards_with_tas(db):
    award(db, 1)
    tas(db, 1, 0)
    award(db, 2)
    tas(db, 2, 1)


def award(db, id):
    # most values are just defined in order to match on all the default filters; we aren't testing those here
    award = mommy.make(
        "awards.Award",
        id=id,
        generated_unique_award_id=f"AWARD_{id}",
        type="D",
        date_signed=datetime(2017, 1, 1),
        category="contracts",
        latest_transaction_id=1000 + id,
        piid="abcdefg",
        fain="xyz",
        uri="abcxyx",
    )
    mommy.make("awards.TransactionNormalized", id=1000 + id, award=award, action_date=datetime(2017, 12, 1))


def tas(db, award_id, index):
    mommy.make("accounts.FederalAccount", id=index + 1)
    mommy.make(
        "accounts.TreasuryAppropriationAccount",
        treasury_account_identifier=index + 1,
        agency_id=TAS_DICTIONARIES[index]["aid"],
        main_account_code=TAS_DICTIONARIES[index]["main"],
        sub_account_code=TAS_DICTIONARIES[index]["sub"],
        availability_type_code=TAS_DICTIONARIES[index]["a"],
        federal_account_id=index + 1,
    )
    mommy.make("awards.FinancialAccountsByAwards", award_id=award_id, treasury_account_id=1)
