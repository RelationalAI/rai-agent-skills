# NOTE: Design-only example (requires Snowflake tables) — demonstrates binary/pairwise
# properties, .ref() for same-type instance binding, and junction concepts.
# Pattern: binary property + .ref() pairwise binding + junction concept
# Key ideas: Concept.covar is a binary Property relating two instances of the same type;
# Concept.ref() creates a second independent iterator for pairwise binding;
# Junction concept connects two parent concepts; filter_by for FK resolution.

"""Financial Services — Users, accounts, transactions, stocks, portfolios.

Patterns: Binary property (Stock.covar between two Stock instances),
.ref() for pairwise data binding, portfolio/holdings junction,
filter_by for FK resolution, Sources class with Snowflake tables.
"""
from relationalai.semantics import Model, Date, DateTime, Float, Integer, String

model = Model("Financial Services")

# -- Source Tables -----------------------------------------------------------
class Sources:
    class financial_services:
        class public:
            users = model.Table("FINANCIAL_SERVICES.PUBLIC.USERS")
            addresses = model.Table("FINANCIAL_SERVICES.PUBLIC.ADDRESSES")
            transactions = model.Table("FINANCIAL_SERVICES.PUBLIC.TRANSACTIONS")
            stocks = model.Table("FINANCIAL_SERVICES.PUBLIC.STOCKS")
            covariance = model.Table("FINANCIAL_SERVICES.PUBLIC.COVARIANCE")
            portfolios = model.Table("FINANCIAL_SERVICES.PUBLIC.PORTFOLIOS")
            accounts = model.Table("FINANCIAL_SERVICES.PUBLIC.ACCOUNTS")
            holdings = model.Table("FINANCIAL_SERVICES.PUBLIC.HOLDINGS")

# -- Concepts & Properties ---------------------------------------------------

# Address
Address = model.Concept("Address", identify_by={"id": Integer})
Address.street_address = model.Property(f"{Address} has {String:street_address}")
Address.city = model.Property(f"{Address} has {String:city}")
Address.state = model.Property(f"{Address} has {String:state}")
Address.zip_code = model.Property(f"{Address} has {Integer:zip_code}")

# User
User = model.Concept("User", identify_by={"id": Integer})
User.full_name = model.Property(f"{User} has {String:full_name}")
User.email = model.Property(f"{User} has {String:email}")
User.phone = model.Property(f"{User} has {String:phone}")
User.credit_card_number = model.Property(f"{User} has {Integer:credit_card_number}")
User.account_type = model.Property(f"{User} has {String:account_type}")
User.risk_score = model.Property(f"{User} has {Float:risk_score}")
User.signup_date = model.Property(f"{User} has {String:signup_date}")
User.address = model.Relationship(f"{User} lives at {Address}")

# Account
Account = model.Concept("Account", identify_by={"id": Integer})
Account.account_type = model.Property(f"{Account} has {String:account_type}")
Account.balance = model.Property(f"{Account} has {Float:balance}")
Account.opened_date = model.Property(f"{Account} has {String:opened_date}")
Account.owner = model.Property(f"{Account} owned by {User:owner}")

# Transaction
Transaction = model.Concept("Transaction", identify_by={"id": Integer})
Transaction.amount = model.Property(f"{Transaction} has {Float:amount}")
Transaction.merchant = model.Property(f"{Transaction} has {String:merchant}")
Transaction.category = model.Property(f"{Transaction} has {String:category}")
Transaction.timestamp = model.Property(f"{Transaction} has {String:timestamp}")
Transaction.is_flagged = model.Relationship(f"{Transaction} is flagged")
Transaction.user = model.Property(f"{Transaction} belongs to {User:user}")

# Stock
Stock = model.Concept("Stock", identify_by={"id": Integer})
Stock.ticker = model.Property(f"{Stock} has {String:ticker}")
Stock.sector = model.Property(f"{Stock} has {String:sector}")
Stock.expected_return = model.Property(f"{Stock} has {Float:expected_return}")

# Binary property: covariance between two stocks (pairwise)
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")

# Portfolio
Portfolio = model.Concept("Portfolio", identify_by={"id": Integer})
Portfolio.name = model.Property(f"{Portfolio} has {String:name}")
Portfolio.budget = model.Property(f"{Portfolio} has {Float:budget}")
Portfolio.min_return_target = model.Property(f"{Portfolio} has {Float:min_return_target}")

# Holding (junction: Account <-> Stock)
Holding = model.Concept("Holding", identify_by={"id": Integer})
Holding.quantity = model.Property(f"{Holding} has {Float:quantity}")
Holding.purchase_price = model.Property(f"{Holding} has {Float:purchase_price}")
Holding.purchase_date = model.Property(f"{Holding} has {String:purchase_date}")
Holding.account = model.Relationship(f"{Holding} in {Account}")
Holding.stock = model.Relationship(f"{Holding} of {Stock}")

# -- Data Loading ------------------------------------------------------------

# Address
src = Sources.financial_services.public.addresses
model.define(Address.new(
    id=src.ADDRESS_ID,
    street_address=src.STREET_ADDRESS,
    city=src.CITY,
    state=src.STATE,
    zip_code=src.ZIP_CODE,
))

# User
src = Sources.financial_services.public.users
model.define(User.new(
    id=src.USER_ID,
    full_name=src.FULL_NAME,
    email=src.EMAIL,
    phone=src.PHONE,
    credit_card_number=src.CREDIT_CARD_NUMBER,
    account_type=src.ACCOUNT_TYPE,
    risk_score=src.RISK_SCORE,
    signup_date=src.SIGNUP_DATE,
    address=Address.filter_by(id=src.ADDRESS_ID),
))

# Account
src = Sources.financial_services.public.accounts
model.define(Account.new(
    id=src.ACCOUNT_ID,
    account_type=src.ACCOUNT_TYPE,
    balance=src.BALANCE,
    opened_date=src.OPENED_DATE,
    owner=User.filter_by(id=src.USER_ID),
))

# Transaction
src = Sources.financial_services.public.transactions
model.define(Transaction.new(
    id=src.TRANSACTION_ID,
    amount=src.AMOUNT,
    merchant=src.MERCHANT,
    category=src.CATEGORY,
    timestamp=src.TIMESTAMP,
    user=User.filter_by(id=src.USER_ID),
))
# Unary relationship from boolean column (recommended over Boolean Property)
model.define(Transaction.is_flagged()).where(
    Transaction.filter_by(id=src.TRANSACTION_ID),
    src.IS_FLAGGED == True,
)

# Stock
src = Sources.financial_services.public.stocks
model.define(Stock.new(
    id=src.STOCK_ID,
    ticker=src.TICKER,
    sector=src.SECTOR,
    expected_return=src.EXPECTED_RETURN,
))

# Covariance: binary property binding two Stock instances via .ref()
src = Sources.financial_services.public.covariance
PairedStock = Stock.ref()
model.where(Stock.id(src.STOCK_I), PairedStock.id(src.STOCK_J)).define(
    Stock.covar(Stock, PairedStock, src.COVARIANCE)
)

# Portfolio
src = Sources.financial_services.public.portfolios
model.define(Portfolio.new(
    id=src.PORTFOLIO_ID,
    name=src.NAME,
    budget=src.BUDGET,
    min_return_target=src.MIN_RETURN_TARGET,
))

# Holding
src = Sources.financial_services.public.holdings
model.define(Holding.new(
    id=src.HOLDING_ID,
    quantity=src.QUANTITY,
    purchase_price=src.PURCHASE_PRICE,
    purchase_date=src.PURCHASE_DATE,
    account=Account.filter_by(id=src.ACCOUNT_ID),
    stock=Stock.filter_by(id=src.STOCK_ID),
))
