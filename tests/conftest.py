import uuid
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from src.db.models import Base, Customer, Order, OrderStatus, Refund, RefundStatus


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_customer_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_order_id():
    return "ORD-ABC123"


@pytest_asyncio.fixture
async def populated_db(db_session):
    """Seed the test database with a customer, order, and refund."""
    customer = Customer(
        id="cust-001",
        email="jane@example.com",
        name="Jane Doe",
        phone="+15551234567",
        notes="VIP customer",
    )
    order = Order(
        id="ORD-TEST01",
        customer_id="cust-001",
        status=OrderStatus.DELIVERED,
        total=Decimal("149.99"),
        item_summary="Wireless headphones x1, USB-C cable x2",
        tracking_number="TRACK123456",
    )
    refund = Refund(
        id="ref-001",
        order_id="ORD-TEST01",
        amount=Decimal("29.99"),
        reason="Defective USB-C cable",
        status=RefundStatus.PROCESSED,
        processed_at=datetime.utcnow(),
    )

    db_session.add_all([customer, order, refund])
    await db_session.commit()

    return {"customer": customer, "order": order, "refund": refund}
