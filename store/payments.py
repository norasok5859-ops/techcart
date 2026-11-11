"""QR payments (KHQR / EMVCo merchant-presented QR) and receipts.

Demo mode: the QR is a correctly formatted KHQR payload for the order amount, but payment is
confirmed by the customer pressing "I have paid" (no bank callback). To take real payments, set
TECHCART_KHQR_ACCOUNT to your Bakong account ID and replace `confirm_payment` with a call to your
bank's / Bakong's transaction-check API before marking the order paid.
"""
import secrets
import time
from decimal import Decimal

import segno
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order

QR_VALID_MINUTES = 15


class PaymentError(Exception):
    pass


def _tlv(tag, value):
    value = str(value)
    return f"{tag}{len(value):02d}{value}"


def _crc16(data: str) -> str:
    """CRC-16/CCITT-FALSE, as required by EMVCo QR codes."""
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def khqr_payload(order: Order) -> str:
    """EMVCo / KHQR payload for this order's total (USD)."""
    account = settings.KHQR_ACCOUNT_ID
    merchant = settings.KHQR_MERCHANT_NAME[:25]
    city = settings.KHQR_MERCHANT_CITY[:15]
    amount = f"{Decimal(order.total):.2f}"
    payload = (
        _tlv("00", "01")                                   # payload format indicator
        + _tlv("01", "12")                                 # dynamic QR (one amount, one payment)
        + _tlv("29", _tlv("00", account))                  # Bakong account (individual)
        + _tlv("52", "5732")                               # merchant category: electronics stores
        + _tlv("53", "840")                                # currency: USD
        + _tlv("54", amount)
        + _tlv("58", "KH")
        + _tlv("59", merchant)
        + _tlv("60", city)
        + _tlv("62", _tlv("01", order.number) + _tlv("02", order.phone[:25] or "-"))  # bill no. + mobile
        + _tlv("99", _tlv("00", str(int(time.time() * 1000))))                        # creation timestamp
        + "6304"
    )
    return payload + _crc16(payload)


def qr_svg(data: str, scale=6) -> str:
    """Inline SVG of a QR code (no external service: the QR is drawn on the server)."""
    return segno.make(data, error="m").svg_inline(scale=scale, border=2, dark="#0b1020", light="#ffffff")


def payment_qr(order: Order) -> dict:
    if not order.awaiting_qr_payment:
        raise PaymentError("This order is not waiting for a QR payment.")
    payload = khqr_payload(order)
    return {"order": order.number, "amount": f"{order.total:.2f}", "currency": "USD",
            "payload": payload, "svg": qr_svg(payload), "expires_in_seconds": QR_VALID_MINUTES * 60,
            "merchant": settings.KHQR_MERCHANT_NAME, "account": settings.KHQR_ACCOUNT_ID}


@transaction.atomic
def confirm_payment(order: Order) -> Order:
    """Demo confirmation: mark the order paid and confirmed, with a transaction reference."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.awaiting_qr_payment:
        raise PaymentError("This order is not waiting for a QR payment.")
    order.payment_status = Order.PaymentStatus.PAID
    order.paid_at = timezone.now()
    order.payment_ref = f"KHQR-{order.pk:05d}-{secrets.token_hex(4).upper()}"
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.CONFIRMED
    order.save(update_fields=["payment_status", "paid_at", "payment_ref", "status"])
    return order


def receipt_data(order: Order) -> dict:
    """Everything a receipt shows (used by the receipt page and the API)."""
    items = [{"name": i.product_name, "price": f"{i.price:.2f}", "quantity": i.quantity,
              "subtotal": f"{i.subtotal:.2f}"} for i in order.items.all()]
    return {
        "receipt_number": order.receipt_number, "order_number": order.number,
        "date": order.paid_at or order.created_at, "customer": order.full_name, "phone": order.phone,
        "address": order.address, "items": items, "subtotal": f"{order.total:.2f}", "delivery": "0.00",
        "total": f"{order.total:.2f}", "currency": "USD",
        "payment_method": order.get_payment_method_display(), "payment_status": order.payment_status,
        "payment_ref": order.payment_ref, "paid_at": order.paid_at, "order_status": order.status,
    }
