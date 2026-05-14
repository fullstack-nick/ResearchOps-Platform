from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    azure_keys: tuple[str, ...]
    value_type: str
    display_order: int
    extractor: str = "text"


@dataclass(frozen=True)
class NormalizedField:
    field_key: str
    label: str
    value: str | None
    value_type: str
    confidence: float | None
    source_page: int | None
    source_regions: list[dict[str, Any]]
    raw_value: dict[str, Any] | None
    is_missing: bool
    display_order: int


@dataclass(frozen=True)
class NormalizedLineItem:
    item_index: int
    description: str | None
    quantity: float | None
    unit_price: float | None
    amount: float | None
    currency: str | None
    confidence: float | None
    source_page: int | None
    source_regions: list[dict[str, Any]]
    raw_value: dict[str, Any] | None


@dataclass(frozen=True)
class NormalizedInvoice:
    fields: list[NormalizedField]
    line_items: list[NormalizedLineItem]
    missing_fields: list[str]
    model_id: str | None


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("vendor_name", "Vendor name", ("VendorName",), "string", 10),
    FieldSpec("invoice_number", "Invoice number", ("InvoiceId",), "string", 20),
    FieldSpec("issue_date", "Issue date", ("InvoiceDate",), "date", 30),
    FieldSpec("due_date", "Due date", ("DueDate",), "date", 40),
    FieldSpec(
        "currency",
        "Currency",
        ("InvoiceTotal", "SubTotal", "TotalTax", "AmountDue"),
        "currency_code",
        50,
        "currency",
    ),
    FieldSpec("net_amount", "Net amount", ("SubTotal",), "currency", 60, "amount"),
    FieldSpec("vat_amount", "VAT/tax amount", ("TotalTax",), "currency", 70, "amount"),
    FieldSpec("gross_total", "Gross total", ("InvoiceTotal",), "currency", 80, "amount"),
    FieldSpec("purchase_order_number", "Purchase order number", ("PurchaseOrder",), "string", 90),
    FieldSpec("payment_terms", "Payment terms", ("PaymentTerm",), "string", 100),
    FieldSpec("vendor_tax_id", "Vendor tax ID", ("VendorTaxId",), "string", 110),
)

REQUIRED_FIELD_KEYS = {
    "vendor_name",
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "net_amount",
    "vat_amount",
    "gross_total",
    "purchase_order_number",
}


def normalize_invoice_result(result: Any) -> NormalizedInvoice:
    fields_by_name = _first_document_fields(result)
    normalized_fields: list[NormalizedField] = []

    for spec in FIELD_SPECS:
        source_field = _first_field(fields_by_name, spec.azure_keys)
        value = _extract_field_value(source_field, spec.extractor)
        source_regions = _source_regions(source_field)
        normalized_fields.append(
            NormalizedField(
                field_key=spec.key,
                label=spec.label,
                value=value,
                value_type=spec.value_type,
                confidence=_field_confidence(source_field),
                source_page=_first_source_page(source_regions),
                source_regions=source_regions,
                raw_value=_raw_field(source_field),
                is_missing=spec.key in REQUIRED_FIELD_KEYS and _is_blank(value),
                display_order=spec.display_order,
            )
        )

    line_items = _line_items(fields_by_name.get("Items"))
    missing_fields = [
        field.field_key
        for field in normalized_fields
        if field.field_key in REQUIRED_FIELD_KEYS and field.is_missing
    ]
    if not line_items:
        missing_fields.append("line_items")

    return NormalizedInvoice(
        fields=normalized_fields,
        line_items=line_items,
        missing_fields=missing_fields,
        model_id=_get_str(result, "model_id", "modelId"),
    )


def _first_document_fields(result: Any) -> dict[str, Any]:
    documents = _get(result, "documents")
    if not documents:
        return {}
    first = documents[0]
    fields = _get(first, "fields")
    if isinstance(fields, Mapping):
        return {str(key): value for key, value in cast(Mapping[Any, Any], fields).items()}
    return {}


def _line_items(items_field: Any) -> list[NormalizedLineItem]:
    values = _array_values(items_field)
    items: list[NormalizedLineItem] = []
    for index, item in enumerate(values):
        item_fields = _object_values(item)
        description_field = item_fields.get("Description")
        quantity_field = item_fields.get("Quantity")
        unit_price_field = item_fields.get("UnitPrice")
        amount_field = item_fields.get("Amount")
        item_source_regions = _source_regions(item) or _source_regions(description_field)
        currency = _extract_currency(amount_field) or _extract_currency(unit_price_field)
        items.append(
            NormalizedLineItem(
                item_index=index,
                description=_extract_field_value(description_field, "text"),
                quantity=_extract_number(quantity_field),
                unit_price=_extract_number(unit_price_field, prefer_amount=True),
                amount=_extract_number(amount_field, prefer_amount=True),
                currency=currency,
                confidence=_field_confidence(item),
                source_page=_first_source_page(item_source_regions),
                source_regions=item_source_regions,
                raw_value=_raw_field(item),
            )
        )
    return items


def _first_field(fields_by_name: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        field = fields_by_name.get(name)
        if field is not None:
            return field
    return None


def _extract_field_value(field: Any, extractor: str) -> str | None:
    if field is None:
        return None
    if extractor == "amount":
        amount = _extract_number(field, prefer_amount=True)
        return None if amount is None else f"{amount:.2f}"
    if extractor == "currency":
        return _extract_currency(field)

    for attr in ("value_string", "valueString"):
        value = _get(field, attr)
        if value is not None:
            return str(value)
    for attr in ("value_date", "valueDate"):
        value = _get(field, attr)
        if value is not None:
            return _stringify(value)
    value_number = _get(field, "value_number", "valueNumber")
    if value_number is not None:
        return _stringify(value_number)
    content = _get(field, "content")
    return None if content is None else str(content).strip() or None


def _extract_number(field: Any, prefer_amount: bool = False) -> float | None:
    if field is None:
        return None
    if prefer_amount:
        amount = _currency_amount(field)
        if amount is not None:
            return amount
    number = _get(field, "value_number", "valueNumber")
    if number is not None:
        try:
            return float(number)
        except (TypeError, ValueError):
            return None
    if not prefer_amount:
        amount = _currency_amount(field)
        if amount is not None:
            return amount
    return None


def _extract_currency(field: Any) -> str | None:
    currency = _currency_value(field)
    for attr in ("currency_code", "currencyCode", "code"):
        value = _get(currency, attr)
        if value:
            return str(value)
    for attr in ("currency_symbol", "currencySymbol", "symbol"):
        value = _get(currency, attr)
        if value:
            return str(value)
    return None


def _currency_amount(field: Any) -> float | None:
    currency = _currency_value(field)
    amount = _get(currency, "amount")
    if amount is None:
        return None
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


def _currency_value(field: Any) -> Any:
    return _get(field, "value_currency", "valueCurrency", "value") if field is not None else None


def _array_values(field: Any) -> list[Any]:
    value = _get(field, "value_array", "valueArray", "value")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(cast(Sequence[Any], value))
    return []


def _object_values(field: Any) -> dict[str, Any]:
    value = _get(field, "value_object", "valueObject", "value")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in cast(Mapping[Any, Any], value).items()}
    return {}


def _source_regions(field: Any) -> list[dict[str, Any]]:
    regions = _get(field, "bounding_regions", "boundingRegions")
    if not regions:
        return []
    normalized: list[dict[str, Any]] = []
    for region in regions:
        page_number = _get(region, "page_number", "pageNumber")
        polygon = _get(region, "polygon")
        normalized.append(
            {
                "page_number": page_number,
                "polygon": list(polygon) if polygon is not None else [],
            }
        )
    return normalized


def _first_source_page(source_regions: list[dict[str, Any]]) -> int | None:
    if not source_regions:
        return None
    value = source_regions[0].get("page_number")
    return int(value) if value is not None else None


def _field_confidence(field: Any) -> float | None:
    value = _get(field, "confidence")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _raw_field(field: Any) -> dict[str, Any] | None:
    if field is None:
        return None
    raw: dict[str, Any] = {}
    for key in (
        "type",
        "content",
        "confidence",
        "value_string",
        "valueString",
        "value_number",
        "valueNumber",
        "value_date",
        "valueDate",
    ):
        value = _get(field, key)
        if value is not None:
            raw[key] = _jsonable(value)
    currency = _currency_value(field)
    if currency is not None:
        raw["value_currency"] = _jsonable(currency)
    return raw or None


def _jsonable(value: Any) -> Any:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in cast(Mapping[Any, Any], value).items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in cast(Sequence[Any], value)]
    return {
        key: _jsonable(_get(value, key))
        for key in ("amount", "currency_code", "currencyCode", "currency_symbol", "currencySymbol")
        if _get(value, key) is not None
    } or str(value)


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _stringify(value: Any) -> str:
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value).strip()


def _get_str(value: Any, *names: str) -> str | None:
    raw = _get(value, *names)
    return None if raw is None else str(raw)


def _get(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        for name in names:
            if name in mapping:
                return mapping[name]
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None
