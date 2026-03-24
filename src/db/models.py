import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class RefundStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSED = "processed"
    DENIED = "denied"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20))
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    orders = relationship("Order", back_populates="customer", lazy="selectin")

    def __repr__(self):
        return f"<Customer {self.id} ({self.email})>"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_status", "customer_id", "status"),
    )

    id = Column(String(36), primary_key=True)
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    status = Column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )
    total = Column(Numeric(10, 2), nullable=False)
    item_summary = Column(Text, nullable=False)
    tracking_number = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="orders")
    refunds = relationship("Refund", back_populates="order", lazy="selectin")

    def __repr__(self):
        return f"<Order {self.id} status={self.status}>"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String(36), primary_key=True)
    order_id = Column(
        String(36), ForeignKey("orders.id"), nullable=False, index=True
    )
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        Enum(RefundStatus), nullable=False, default=RefundStatus.REQUESTED
    )
    processed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="refunds")

    def __repr__(self):
        return f"<Refund {self.id} amount={self.amount} status={self.status}>"
