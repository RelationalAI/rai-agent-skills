# NOTE: Design-only example (requires Snowflake tables) — demonstrates binary/pairwise
# properties, .ref() for same-type instance binding, and junction concepts.
# Pattern: binary property + .ref() pairwise binding + junction concept
# Key ideas: Concept.covar is a binary Property relating two instances of the same type;
# Concept.ref() creates a second independent iterator for pairwise binding;
# Junction concept connects two parent concepts; filter_by for FK resolution.

"""Pattern: binary property with `.ref()` for pairwise self-join + junction concept for many-to-many."""
from relationalai.semantics import Model, Date, DateTime, Float, Integer, String

model = Model("Entity Aggregation")

# -- Source Tables -----------------------------------------------------------
class Sources:
    class ops_db:
        class public:
            owners = model.Table("OPS_DB.PUBLIC.OWNERS")
            addresses = model.Table("OPS_DB.PUBLIC.ADDRESSES")
            transactions = model.Table("OPS_DB.PUBLIC.TRANSACTIONS")
            items = model.Table("OPS_DB.PUBLIC.ITEMS")
            covariance = model.Table("OPS_DB.PUBLIC.COVARIANCE")
            collections = model.Table("OPS_DB.PUBLIC.COLLECTIONS")
            accounts = model.Table("OPS_DB.PUBLIC.ACCOUNTS")
            allocations = model.Table("OPS_DB.PUBLIC.ALLOCATIONS")

# -- Concepts & Properties ---------------------------------------------------

# Address
Address = model.Concept("Address", identify_by={"id": Integer})
Address.street_address = model.Property(f"{Address} has {String:street_address}")
Address.city = model.Property(f"{Address} has {String:city}")
Address.state = model.Property(f"{Address} has {String:state}")
Address.zip_code = model.Property(f"{Address} has {Integer:zip_code}")

# Owner
Owner = model.Concept("Owner", identify_by={"id": Integer})
Owner.full_name = model.Property(f"{Owner} has {String:full_name}")
Owner.email = model.Property(f"{Owner} has {String:email}")
Owner.phone = model.Property(f"{Owner} has {String:phone}")
Owner.external_id = model.Property(f"{Owner} has {Integer:external_id}")
Owner.account_type = model.Property(f"{Owner} has {String:account_type}")
Owner.risk_score = model.Property(f"{Owner} has {Float:risk_score}")
Owner.signup_date = model.Property(f"{Owner} has {String:signup_date}")
Owner.address = model.Relationship(f"{Owner} lives at {Address}")

# Account
Account = model.Concept("Account", identify_by={"id": Integer})
Account.account_type = model.Property(f"{Account} has {String:account_type}")
Account.balance = model.Property(f"{Account} has {Float:balance}")
Account.opened_date = model.Property(f"{Account} has {String:opened_date}")
Account.owner = model.Property(f"{Account} owned by {Owner:owner}")

# Transaction
Transaction = model.Concept("Transaction", identify_by={"id": Integer})
Transaction.amount = model.Property(f"{Transaction} has {Float:amount}")
Transaction.merchant = model.Property(f"{Transaction} has {String:merchant}")
Transaction.category = model.Property(f"{Transaction} has {String:category}")
Transaction.timestamp = model.Property(f"{Transaction} has {String:timestamp}")
Transaction.is_flagged = model.Relationship(f"{Transaction} is flagged")
Transaction.owner = model.Property(f"{Transaction} belongs to {Owner:owner}")

# Item
Item = model.Concept("Item", identify_by={"id": Integer})
Item.code = model.Property(f"{Item} has {String:code}")
Item.category = model.Property(f"{Item} has {String:category}")
Item.expected_return = model.Property(f"{Item} has {Float:expected_return}")

# Binary property: covariance between two items (pairwise)
Item.covar = model.Property(f"{Item} and {Item} have {Float:covar}")

# Collection
Collection = model.Concept("Collection", identify_by={"id": Integer})
Collection.name = model.Property(f"{Collection} has {String:name}")
Collection.budget = model.Property(f"{Collection} has {Float:budget}")
Collection.min_return_target = model.Property(f"{Collection} has {Float:min_return_target}")

# Allocation (junction: Account <-> Item)
Allocation = model.Concept("Allocation", identify_by={"id": Integer})
Allocation.quantity = model.Property(f"{Allocation} has {Float:quantity}")
Allocation.unit_price = model.Property(f"{Allocation} has {Float:unit_price}")
Allocation.acquired_date = model.Property(f"{Allocation} has {String:acquired_date}")
Allocation.account = model.Relationship(f"{Allocation} in {Account}")
Allocation.item = model.Relationship(f"{Allocation} of {Item}")

# -- Data Loading ------------------------------------------------------------

# Address
src = Sources.ops_db.public.addresses
model.define(Address.new(
    id=src.ADDRESS_ID,
    street_address=src.STREET_ADDRESS,
    city=src.CITY,
    state=src.STATE,
    zip_code=src.ZIP_CODE,
))

# Owner
src = Sources.ops_db.public.owners
model.define(Owner.new(
    id=src.OWNER_ID,
    full_name=src.FULL_NAME,
    email=src.EMAIL,
    phone=src.PHONE,
    external_id=src.EXTERNAL_ID,
    account_type=src.ACCOUNT_TYPE,
    risk_score=src.RISK_SCORE,
    signup_date=src.SIGNUP_DATE,
    address=Address.filter_by(id=src.ADDRESS_ID),
))

# Account
src = Sources.ops_db.public.accounts
model.define(Account.new(
    id=src.ACCOUNT_ID,
    account_type=src.ACCOUNT_TYPE,
    balance=src.BALANCE,
    opened_date=src.OPENED_DATE,
    owner=Owner.filter_by(id=src.OWNER_ID),
))

# Transaction
src = Sources.ops_db.public.transactions
model.define(Transaction.new(
    id=src.TRANSACTION_ID,
    amount=src.AMOUNT,
    merchant=src.MERCHANT,
    category=src.CATEGORY,
    timestamp=src.TIMESTAMP,
    owner=Owner.filter_by(id=src.OWNER_ID),
))
# Unary relationship from boolean column (recommended over Boolean Property)
model.define(Transaction.is_flagged()).where(
    Transaction.filter_by(id=src.TRANSACTION_ID),
    src.IS_FLAGGED == True,
)

# Item
src = Sources.ops_db.public.items
model.define(Item.new(
    id=src.ITEM_ID,
    code=src.CODE,
    category=src.CATEGORY,
    expected_return=src.EXPECTED_RETURN,
))

# Covariance: binary property binding two Item instances via .ref()
src = Sources.ops_db.public.covariance
PairedItem = Item.ref()
model.where(Item.id(src.ITEM_I), PairedItem.id(src.ITEM_J)).define(
    Item.covar(Item, PairedItem, src.COVARIANCE)
)

# Collection
src = Sources.ops_db.public.collections
model.define(Collection.new(
    id=src.COLLECTION_ID,
    name=src.NAME,
    budget=src.BUDGET,
    min_return_target=src.MIN_RETURN_TARGET,
))

# Allocation
src = Sources.ops_db.public.allocations
model.define(Allocation.new(
    id=src.ALLOCATION_ID,
    quantity=src.QUANTITY,
    unit_price=src.UNIT_PRICE,
    acquired_date=src.ACQUIRED_DATE,
    account=Account.filter_by(id=src.ACCOUNT_ID),
    item=Item.filter_by(id=src.ITEM_ID),
))
