import html
import json
import sqlite3
from io import BytesIO
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "data" / "seller_portal.db"

DEMO_SELLER = {
    "seller_id": "SLR-IN-2048",
    "business_name": "Aarav Living Co.",
    "login_email": "seller.demo@example.com",
    "iec": "AABCT1234F",
    "gstin": "27AABCT1234F1Z5",
    "lut_number": "LUT-27-2026-004812",
    "rcmc": "FIEO/RCMC/2026/118204",
    "icegate_profile": "Active · ICEGATE ID AABCT1234F",
    "pan": "AABCT1234F",
    "registered_address": "14 Export House, Andheri East, Mumbai, Maharashtra 400069",
    "pickup_address": "14 Export House, Andheri East, Mumbai, Maharashtra 400069",
    "bank_name": "HDFC Bank · Mumbai Export Branch",
    "bank_account_last4": "4821",
    "ifsc": "HDFC0001234",
    "pickup_contact_name": "Aarav Export Desk",
    "pickup_contact_phone": "+91 22 4000 2048",
    "last_login": "16 Oct 2026 · 09:42 IST",
    "profile_source": "DEMO PROFILE · SAMPLE DATA",
}

DEFAULT_CATALOG = [
    {
        "sku": "AL-LIN-014",
        "name": "Hand-block linen cushion cover",
        "category": "Home & kitchen",
        "subcategory": "Soft furnishings",
        "hs_code": "630492",
        "country_of_origin": "India",
        "unit_value_usd": 24.00,
        "unit_weight_kg": 0.45,
    },
    {
        "sku": "AL-BRS-022",
        "name": "Hammered brass candle holder",
        "category": "Handicrafts & decor",
        "subcategory": "Metal decor",
        "hs_code": "830629",
        "country_of_origin": "India",
        "unit_value_usd": 38.00,
        "unit_weight_kg": 0.90,
    },
    {
        "sku": "AL-COT-031",
        "name": "Handwoven cotton throw",
        "category": "Apparel & textiles",
        "subcategory": "Home textiles",
        "hs_code": "630130",
        "country_of_origin": "India",
        "unit_value_usd": 58.00,
        "unit_weight_kg": 1.20,
    },
    {
        "sku": "AL-CER-009",
        "name": "Studio ceramic serving bowl",
        "category": "Home & kitchen",
        "subcategory": "Tableware",
        "hs_code": "691200",
        "country_of_origin": "India",
        "unit_value_usd": 32.00,
        "unit_weight_kg": 1.15,
    },
    {
        "sku": "AL-WOD-018",
        "name": "Neem wood chopping board",
        "category": "Home & kitchen",
        "subcategory": "Kitchen accessories",
        "hs_code": "441990",
        "country_of_origin": "India",
        "unit_value_usd": 27.00,
        "unit_weight_kg": 0.75,
    },
]

WAREHOUSES = {
    "US East · Avenel, New Jersey": {
        "city": "Avenel",
        "state": "New Jersey",
        "country": "United States",
        "postal_code": "07001",
        "code": "US-EAST-AVN",
        "gateway": "Port Newark / JFK cargo gateway",
        "consignee_name": "Amazon US FBA · Avenel receiving",
        "consignee_address": "1000 Riverside Drive, Avenel, NJ 07001, United States",
    },
    "US West · Ontario, California": {
        "city": "Ontario",
        "state": "California",
        "country": "United States",
        "postal_code": "91761",
        "code": "US-WEST-ONT",
        "gateway": "Port of Los Angeles / LAX cargo gateway",
        "consignee_name": "Amazon US FBA · Ontario receiving",
        "consignee_address": "2400 E Airport Drive, Ontario, CA 91761, United States",
    },
    "US Central · Dallas, Texas": {
        "city": "Dallas",
        "state": "Texas",
        "country": "United States",
        "postal_code": "75247",
        "code": "US-CENTRAL-DAL",
        "gateway": "Dallas Fort Worth cargo gateway",
        "consignee_name": "Amazon US FBA · Dallas receiving",
        "consignee_address": "1515 E 30th Street, Dallas, TX 75247, United States",
    },
}

CATEGORY_SUBCATEGORIES = {
    "Apparel & textiles": ["Apparel", "Home textiles", "Accessories"],
    "Home & kitchen": ["Tableware", "Soft furnishings", "Kitchen accessories"],
    "Handicrafts & decor": ["Metal decor", "Woodcraft", "Artisan decor"],
    "Beauty & wellness": ["Personal care", "Wellness products"],
    "Other": ["General merchandise"],
}

TRACKING_STAGES = [
    "Shipment created",
    "Pickup and origin processing",
    "Export clearance",
    "International transit",
    "US import clearance",
    "Delivered to destination warehouse",
]

REQUIRED_DOCUMENTS = [
    "IEC / exporter registration certificate",
    "GST registration certificate",
    "PAN card or PAN allotment letter",
    "Cancelled cheque or bank confirmation",
    "Pickup address proof",
    "LUT Number (Letter of Undertaking)",
    "RCMC",
    "ICEGATE Profile",
]

DEMO_DOCUMENTS = [
    {
        "type": name,
        "filename": f"demo_{index + 1}_{name.split('/')[0].strip().lower().replace(' ', '_')}.pdf",
        "source": "Sample seller profile",
        "status": "uploaded",
    }
    for index, name in enumerate(REQUIRED_DOCUMENTS)
]


def ensure_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shipments (
                    shipment_id TEXT PRIMARY KEY,
                    seller_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shipment_drafts (
                    draft_id TEXT PRIMARY KEY,
                    seller_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )


def load_shipments(seller_id: str) -> list[dict[str, Any]]:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            "SELECT payload FROM shipments WHERE seller_id = ? ORDER BY created_at DESC",
            (seller_id,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def load_shipment(shipment_id: str, seller_id: str) -> dict[str, Any] | None:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        row = connection.execute(
            "SELECT payload FROM shipments WHERE shipment_id = ? AND seller_id = ?",
            (shipment_id, seller_id),
        ).fetchone()
    return json.loads(row[0]) if row else None


def save_shipment(shipment: dict[str, Any]) -> None:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO shipments (shipment_id, seller_id, created_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(shipment_id) DO UPDATE SET
                    seller_id = excluded.seller_id,
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (
                    shipment["shipment_id"],
                    shipment["seller_id"],
                    shipment["created_at"],
                    json.dumps(shipment),
                ),
            )


def load_shipment_drafts(seller_id: str) -> list[dict[str, Any]]:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT payload FROM shipment_drafts
            WHERE seller_id = ?
            ORDER BY updated_at DESC
            """,
            (seller_id,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def load_shipment_draft(draft_id: str, seller_id: str) -> dict[str, Any] | None:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        row = connection.execute(
            """
            SELECT payload FROM shipment_drafts
            WHERE draft_id = ? AND seller_id = ?
            """,
            (draft_id, seller_id),
        ).fetchone()
    return json.loads(row[0]) if row else None


def save_shipment_draft(draft: dict[str, Any]) -> None:
    required_fields = ("draft_id", "seller_id", "updated_at")
    if any(not draft.get(field) for field in required_fields):
        raise ValueError("A shipment draft requires an ID, seller ID, and update time.")

    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO shipment_drafts (draft_id, seller_id, updated_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET
                    seller_id = excluded.seller_id,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    draft["draft_id"],
                    draft["seller_id"],
                    draft["updated_at"],
                    json.dumps(draft),
                ),
            )


def delete_shipment_draft(draft_id: str, seller_id: str) -> None:
    ensure_database()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                "DELETE FROM shipment_drafts WHERE draft_id = ? AND seller_id = ?",
                (draft_id, seller_id),
            )


def make_demo_draft(seller: dict[str, Any]) -> dict[str, Any]:
    catalog = DEFAULT_CATALOG
    items = [
        {**catalog[0], "quantity": 24},
        {**catalog[1], "quantity": 12},
        {**catalog[4], "quantity": 10},
    ]
    estimate = calculate_estimate(
        items,
        package_count=3,
        length_cm=60,
        width_cm=45,
        height_cm=40,
        shipping_mode="Air freight",
        packaging_weight_kg=4.5,
    )
    destination_label = "US East · Avenel, New Jersey"
    return {
        "shipment_id": "DRAFT-SELLER-CENTRAL-02",
        "seller_id": seller["seller_id"],
        "created_at": "",
        "status": "Ready to create",
        "is_demo_draft": True,
        "items": items,
        "destination_label": destination_label,
        "destination": WAREHOUSES[destination_label],
        "shipping_mode": "Air freight",
        "category": "Home & kitchen",
        "subcategory": "Mixed home goods",
        "consignee_name": "Amazon US FBA · Avenel receiving",
        "consignee_address": "1000 Riverside Drive, Avenel, NJ 07001, United States",
        "pickup_city": "Mumbai",
        "pickup_address": seller["pickup_address"],
        "pickup_contact": "Aarav Export Desk · +91 22 4000 2048",
        "pickup_date": (date.today() + timedelta(days=2)).isoformat(),
        "pickup_slot": "09:00–12:00 IST",
        "package_type": "Cartons",
        "package_count": 3,
        "length_cm": 60.0,
        "width_cm": 45.0,
        "height_cm": 40.0,
        "seller_reference": "SC-ORDER-784216",
        "commercial_invoice_number": "INV-2026-104",
        "port_of_loading": "Nhava Sheva (JNPT), Maharashtra",
        "incoterm": "FCA",
        "export_tax_treatment": "LUT / bond (exporter to confirm)",
        "package_marks": "AARAV / US-EAST / CARTON 1-3",
        "packaging_weight_kg": 4.5,
        "estimate": estimate,
    }


def seed_demo_closed_shipment(seller: dict[str, Any]) -> None:
    closed_id = "MER-DEMO-2026-0008"
    if load_shipment(closed_id, seller["seller_id"]):
        return

    closed_items = [
        {**DEFAULT_CATALOG[0], "quantity": 20},
        {**DEFAULT_CATALOG[4], "quantity": 12},
    ]
    closed_estimate = calculate_estimate(
        closed_items,
        package_count=2,
        length_cm=48,
        width_cm=38,
        height_cm=32,
        shipping_mode="Air freight",
        packaging_weight_kg=3.0,
    )
    closed_destination = "US East · Avenel, New Jersey"
    closed_at = datetime.now(timezone.utc) - timedelta(days=8)
    closed_shipment = {
        "shipment_id": closed_id,
        "seller_id": seller["seller_id"],
        "created_at": (closed_at - timedelta(days=16)).isoformat(timespec="minutes"),
        "updated_at": closed_at.isoformat(timespec="minutes"),
        "closed_at": closed_at.isoformat(timespec="minutes"),
        "status": "Closed",
        "payment_status": "Paid",
        "tracking_number": "DEMO-TRK-US-771008",
        "current_milestone": "Delivered to destination warehouse",
        "milestone_index": 5,
        "items": closed_items,
        "destination_label": closed_destination,
        "destination": WAREHOUSES[closed_destination],
        "shipping_mode": "Air freight",
        "category": "Home & kitchen",
        "subcategory": "Soft furnishings and kitchen accessories",
        "consignee_name": "Amazon US FBA · Avenel receiving",
        "consignee_address": "1000 Riverside Drive, Avenel, NJ 07001, United States",
        "pickup_city": "Mumbai",
        "pickup_address": seller["pickup_address"],
        "pickup_contact": (
            f"{seller['pickup_contact_name']} · {seller['pickup_contact_phone']}"
        ),
        "pickup_date": (date.today() - timedelta(days=24)).isoformat(),
        "pickup_slot": "09:00–12:00 IST",
        "package_type": "Cartons",
        "package_count": 2,
        "length_cm": 48.0,
        "width_cm": 38.0,
        "height_cm": 32.0,
        "seller_reference": "SC-ORDER-740008",
        "commercial_invoice_number": "INV-2026-072",
        "port_of_loading": "Nhava Sheva (JNPT), Maharashtra",
        "incoterm": "FCA",
        "export_tax_treatment": "LUT / bond (exporter to confirm)",
        "package_marks": "AARAV / US-EAST / CARTON 1-2",
        "packaging_weight_kg": 3.0,
        "estimate": closed_estimate,
    }
    save_shipment(closed_shipment)


def seed_additional_demo_shipments(seller: dict[str, Any]) -> None:
    transit = load_shipment("MER-DEMO-2026-001", seller["seller_id"])
    if transit and not load_shipment("MER-DEMO-2026-002", seller["seller_id"]):
        second_transit_items = [
            {**DEFAULT_CATALOG[0], "quantity": 28},
            {**DEFAULT_CATALOG[1], "quantity": 8},
        ]
        second_destination = "US Central · Dallas, Texas"
        second_transit = {
            **transit,
            "shipment_id": "MER-DEMO-2026-002",
            "created_at": (
                datetime.now(timezone.utc) - timedelta(days=2)
            ).isoformat(timespec="minutes"),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "items": second_transit_items,
            "destination_label": second_destination,
            "destination": WAREHOUSES[second_destination],
            "shipping_mode": "Air freight",
            "category": "Home & kitchen",
            "subcategory": "Soft furnishings and metal decor",
            "consignee_name": "Amazon US FBA · Dallas receiving",
            "consignee_address": "1515 E 30th Street, Dallas, TX 75247, United States",
            "pickup_date": (date.today() - timedelta(days=2)).isoformat(),
            "seller_reference": "SC-ORDER-771905",
            "commercial_invoice_number": "INV-2026-097",
            "package_count": 3,
            "length_cm": 48.0,
            "width_cm": 38.0,
            "height_cm": 35.0,
            "tracking_number": "DEMO-TRK-US-884202",
            "current_milestone": "Export clearance",
            "milestone_index": 2,
        }
        second_transit["estimate"] = calculate_estimate(
            second_transit_items,
            package_count=3,
            length_cm=48,
            width_cm=38,
            height_cm=35,
            shipping_mode="Air freight",
            packaging_weight_kg=4.0,
        )
        save_shipment(second_transit)

    closed = load_shipment("MER-DEMO-2026-0008", seller["seller_id"])
    if closed and not load_shipment("MER-DEMO-2026-0009", seller["seller_id"]):
        second_closed_items = [
            {**DEFAULT_CATALOG[2], "quantity": 16},
            {**DEFAULT_CATALOG[3], "quantity": 14},
        ]
        second_closed_at = datetime.now(timezone.utc) - timedelta(days=15)
        second_destination = "US West · Ontario, California"
        second_closed = {
            **closed,
            "shipment_id": "MER-DEMO-2026-0009",
            "created_at": (
                second_closed_at - timedelta(days=12)
            ).isoformat(timespec="minutes"),
            "updated_at": second_closed_at.isoformat(timespec="minutes"),
            "closed_at": second_closed_at.isoformat(timespec="minutes"),
            "items": second_closed_items,
            "destination_label": second_destination,
            "destination": WAREHOUSES[second_destination],
            "category": "Apparel & textiles",
            "subcategory": "Home textiles and tableware",
            "consignee_name": "Amazon US FBA · Ontario receiving",
            "consignee_address": "2400 E Airport Drive, Ontario, CA 91761, United States",
            "pickup_date": (date.today() - timedelta(days=27)).isoformat(),
            "seller_reference": "SC-ORDER-740009",
            "commercial_invoice_number": "INV-2026-073",
            "tracking_number": "DEMO-TRK-US-771009",
            "package_count": 3,
            "length_cm": 55.0,
            "width_cm": 42.0,
            "height_cm": 36.0,
        }
        second_closed["estimate"] = calculate_estimate(
            second_closed_items,
            package_count=3,
            length_cm=55,
            width_cm=42,
            height_cm=36,
            shipping_mode="Ocean consolidated freight",
            packaging_weight_kg=4.0,
        )
        save_shipment(second_closed)


def seed_demo_shipments(seller: dict[str, Any]) -> None:
    shipment_id = "MER-DEMO-2026-001"
    if load_shipment(shipment_id, seller["seller_id"]):
        seed_demo_closed_shipment(seller)
        seed_additional_demo_shipments(seller)
        return

    created_at = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(
        timespec="minutes"
    )
    items = [
        {**DEFAULT_CATALOG[2], "quantity": 36},
        {**DEFAULT_CATALOG[3], "quantity": 18},
    ]
    estimate = calculate_estimate(
        items,
        package_count=4,
        length_cm=55,
        width_cm=45,
        height_cm=40,
        shipping_mode="Ocean consolidated freight",
        packaging_weight_kg=6.0,
    )
    destination_label = "US West · Ontario, California"
    shipment = {
        "shipment_id": shipment_id,
        "seller_id": seller["seller_id"],
        "created_at": created_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "status": "In transit",
        "tracking_number": "DEMO-TRK-US-884201",
        "current_milestone": "International transit",
        "milestone_index": 3,
        "items": items,
        "destination_label": destination_label,
        "destination": WAREHOUSES[destination_label],
        "shipping_mode": "Ocean consolidated freight",
        "category": "Apparel & textiles",
        "subcategory": "Home textiles and tableware",
        "consignee_name": "Amazon US FBA · Ontario receiving",
        "consignee_address": "2400 E Airport Drive, Ontario, CA 91761, United States",
        "pickup_city": "Mumbai",
        "pickup_address": seller["pickup_address"],
        "pickup_contact": "Aarav Export Desk · +91 22 4000 2048",
        "pickup_date": (date.today() - timedelta(days=4)).isoformat(),
        "pickup_slot": "09:00–12:00 IST",
        "package_type": "Cartons",
        "package_count": 4,
        "length_cm": 55.0,
        "width_cm": 45.0,
        "height_cm": 40.0,
        "seller_reference": "SC-ORDER-771904",
        "commercial_invoice_number": "INV-2026-096",
        "port_of_loading": "Nhava Sheva (JNPT), Maharashtra",
        "incoterm": "FCA",
        "export_tax_treatment": "LUT / bond (exporter to confirm)",
        "package_marks": "AARAV / US-WEST / CARTON 1-4",
        "packaging_weight_kg": 6.0,
        "estimate": estimate,
    }
    save_shipment(shipment)
    seed_demo_closed_shipment(seller)
    seed_additional_demo_shipments(seller)


def make_seller_profile_pdf(seller: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AMAZON EXPORT seller profile",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ProfileTitle",
            parent=styles["Title"],
            textColor=colors.HexColor("#123b49"),
            alignment=TA_LEFT,
            fontSize=22,
            leading=27,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ProfileSection",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#087f72"),
            fontSize=13,
            leading=17,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
        )
    )
    story = [
        Paragraph("AMAZON EXPORT", styles["Heading3"]),
        Paragraph("Seller export profile", styles["ProfileTitle"]),
        Paragraph("Sample profile · generated for reference", styles["Italic"]),
        Spacer(1, 5 * mm),
        Paragraph("Account details", styles["ProfileSection"]),
    ]

    def add_table(rows: list[tuple[str, str]]) -> None:
        if not rows:
            story.append(Paragraph("No document records on file.", styles["BodyText"]))
            return
        safe_rows = [
            [
                Paragraph(html.escape(label), styles["BodyText"]),
                Paragraph(html.escape(value or "—"), styles["BodyText"]),
            ]
            for label, value in rows
        ]
        table = Table(safe_rows, colWidths=[52 * mm, 118 * mm], repeatRows=0)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf4f1")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#17363b")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d5e0dc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(table)

    add_table(
        [
            ("Business name", seller["business_name"]),
            ("Seller ID", seller["seller_id"]),
            ("Login email", seller["login_email"]),
            ("Last login", seller.get("last_login", "Demo session")),
            ("IEC", seller.get("iec", "")),
            ("GSTIN", seller.get("gstin", "")),
            ("LUT number", seller.get("lut_number", "")),
            ("RCMC", seller.get("rcmc", "")),
            ("ICEGATE profile", seller.get("icegate_profile", "")),
            ("PAN", seller.get("pan", "")),
            ("Registered address", seller.get("registered_address", "")),
            ("Pickup address", seller.get("pickup_address", "")),
            ("Pickup contact", seller.get("pickup_contact_name", "")),
            ("Pickup phone", seller.get("pickup_contact_phone", "")),
            ("Bank", seller.get("bank_name", "")),
            ("Account ending", seller.get("bank_account_last4", "")),
            ("IFSC", seller.get("ifsc", "")),
        ]
    )
    story.append(Paragraph("Documents on file", styles["ProfileSection"]))
    docs = seller.get("documents_received", DEMO_DOCUMENTS)
    add_table(
        [
            (
                item["type"],
                f"{item['filename']} · {item.get('status', 'uploaded')}",
            )
            for item in docs
        ]
    )
    story.extend(
        [
            Spacer(1, 7 * mm),
            Paragraph(
                "Demo profile only. Verify all details before using for export, "
                "customs, tax, banking, or logistics activity.",
                styles["Italic"],
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()

def calculate_estimate(
    items: list[dict[str, Any]],
    package_count: int,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    shipping_mode: str,
    packaging_weight_kg: float = 0.0,
    declared_value_override: float | None = None,
) -> dict[str, float]:
    declared_value = (
        declared_value_override
        if declared_value_override is not None
        else sum(item["unit_value_usd"] * item["quantity"] for item in items)
    )
    goods_weight = sum(item["unit_weight_kg"] * item["quantity"] for item in items)
    actual_weight = goods_weight + packaging_weight_kg
    volumetric_weight = (
        length_cm * width_cm * height_cm * package_count / 6000
    )
    chargeable_weight = max(actual_weight, volumetric_weight)
    rate_per_kg = 5.20 if shipping_mode == "Air freight" else 2.85
    handling_fee = 28.00 if shipping_mode == "Air freight" else 45.00
    freight = chargeable_weight * rate_per_kg
    insurance = max(12.00, declared_value * 0.008)
    return {
        "declared_value_usd": round(declared_value, 2),
        "goods_weight_kg": round(goods_weight, 2),
        "packaging_weight_kg": round(packaging_weight_kg, 2),
        "actual_weight_kg": round(actual_weight, 2),
        "volumetric_weight_kg": round(volumetric_weight, 2),
        "chargeable_weight_kg": round(chargeable_weight, 2),
        "freight_usd": round(freight, 2),
        "handling_usd": round(handling_fee, 2),
        "insurance_usd": round(insurance, 2),
        "estimated_total_usd": round(freight + handling_fee + insurance, 2),
    }


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _money(value: float) -> str:
    return f"${value:,.2f} USD"


def make_document_html(
    shipment: dict[str, Any],
    seller: dict[str, Any],
    document_type: str,
) -> str:
    challan = document_type == "challan"
    title = "Export shipment challan" if challan else "Seller pickup receipt"
    warehouse = shipment["destination"]
    estimate = shipment["estimate"]
    item_rows = "".join(
        "<tr>"
        f"<td>{_e(item['sku'])}</td>"
        f"<td>{_e(item['name'])}</td>"
        f"<td>{_e(item['category'])} / {_e(item['subcategory'])}</td>"
        f"<td>{_e(item['hs_code'])}</td>"
        f"<td>{_e(item.get('country_of_origin', 'Seller to declare'))}</td>"
        f"<td>{item['quantity']}</td>"
        f"<td>{_money(item['unit_value_usd'])}</td>"
        f"<td>{_money(item['unit_value_usd'] * item['quantity'])}</td>"
        "</tr>"
        for item in shipment["items"]
    )
    if challan:
        detail_rows = [
            ("Shipment category", shipment["category"]),
            ("Shipment subcategory", shipment["subcategory"]),
            ("Shipping mode", shipment["shipping_mode"]),
            ("Country of export", "India"),
            (
                "Port / airport of loading",
                shipment.get("port_of_loading", "Seller to confirm"),
            ),
            ("US entry gateway", warehouse.get("gateway", "To be confirmed")),
            (
                "Incoterms / delivery term",
                shipment.get("incoterm", "To be agreed with buyer"),
            ),
            (
                "Export GST / LUT declaration",
                shipment.get("export_tax_treatment", "Seller to confirm with tax advisor"),
            ),
            (
                "Commercial invoice reference",
                shipment.get("commercial_invoice_number") or "Seller to provide",
            ),
            ("Shipping bill number / date", "To be assigned after customs filing"),
            ("Air waybill / bill of lading", "To be assigned by carrier"),
            ("E-way bill", "Exporter to arrange if applicable"),
            ("Packages", f"{shipment['package_count']} {shipment['package_type']}"),
            (
                "Outer package dimensions",
                f"{shipment['length_cm']} × {shipment['width_cm']} × "
                f"{shipment['height_cm']} cm",
            ),
            (
                "Net goods / packaging / gross weight",
                f"{estimate.get('goods_weight_kg', estimate['actual_weight_kg'])} / "
                f"{estimate.get('packaging_weight_kg', 0)} / "
                f"{estimate['actual_weight_kg']} kg (estimated)",
            ),
            ("Volumetric weight", f"{estimate['volumetric_weight_kg']} kg"),
            ("Chargeable weight", f"{estimate['chargeable_weight_kg']} kg"),
            ("Declared goods value", _money(estimate["declared_value_usd"])),
            ("Estimated freight", _money(estimate["freight_usd"])),
            ("Export handling estimate", _money(estimate["handling_usd"])),
            ("Firm-arranged cargo insurance estimate", _money(estimate["insurance_usd"])),
            ("Approximate shipment cost", _money(estimate["estimated_total_usd"])),
            ("Consignee", shipment["consignee_name"]),
            ("Consignee address", shipment["consignee_address"]),
            ("Destination warehouse", shipment["destination_label"]),
            ("Warehouse code", warehouse["code"]),
            ("Pickup address", shipment["pickup_address"]),
            ("Pickup date and slot", f"{shipment['pickup_date']} · {shipment['pickup_slot']}"),
            ("Seller reference", shipment.get("seller_reference") or "—"),
        ]
    else:
        detail_rows = [
            ("Seller", seller["business_name"]),
            ("Seller ID", seller["seller_id"]),
            ("Pickup address", shipment["pickup_address"]),
            ("Pickup date", shipment["pickup_date"]),
            ("Pickup window", shipment["pickup_slot"]),
            ("Pickup contact", shipment["pickup_contact"]),
            ("Destination warehouse", shipment["destination_label"]),
            ("Warehouse code", warehouse["code"]),
            ("Packages", f"{shipment['package_count']} {shipment['package_type']}"),
            ("Shipment weight", f"{estimate['chargeable_weight_kg']} kg chargeable"),
            ("Status", shipment["status"]),
        ]
    details = "".join(
        f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>"
        for label, value in detail_rows
    )
    exporter = (
        f"<p><strong>Exporter:</strong> {_e(seller['business_name'])} · "
        f"Seller ID {_e(seller['seller_id'])}<br>"
        f"<strong>IEC:</strong> {_e(seller.get('iec', 'Pending'))} · "
        f"<strong>GSTIN:</strong> {_e(seller.get('gstin', 'Pending'))}</p>"
    )
    disclaimer = (
        "<p class=\"notice\"><strong>Operational draft only.</strong> Estimates are "
        "indicative, not a carrier/insurer quote or government-issued customs document. "
        "The exporter and customs broker must verify the HS classification, export "
        "declarations, tax treatment and any product-specific permissions before dispatch. "
        "US duties/taxes and destination charges are excluded. Final insurance cover is "
        "subject to the firm/insurer's review and written confirmation.</p>"
        if challan
        else "<p class=\"notice\">Pickup is a seller-portal booking request. Confirmed "
        "carrier assignment and live tracking require an operational carrier integration.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} · {_e(shipment['shipment_id'])}</title>
<style>
body{{font:15px/1.5 Arial,sans-serif;color:#172b31;max-width:900px;margin:36px auto;padding:0 24px}}
h1{{margin-bottom:4px}}.muted{{color:#52676b}}table{{border-collapse:collapse;width:100%;margin:18px 0}}
th,td{{border:1px solid #cbd7d5;padding:9px;text-align:left;vertical-align:top}}
th{{background:#eef4f1}}.notice{{background:#f4f7f5;border-left:4px solid #248b72;padding:12px}}
.print{{margin:16px 0;padding:10px 16px}}@media print{{.print{{display:none}}body{{margin:0;max-width:none}}}}
</style></head><body>
<button class="print" onclick="window.print()">Print / save as PDF</button>
<p class="muted">AMAZON EXPORT · INDIA TO UNITED STATES · DEMO DOCUMENT</p>
<h1>{_e(title)}</h1>
<p class="muted">Shipment ID <strong>{_e(shipment['shipment_id'])}</strong> ·
Created {_e(shipment['created_at'])}</p>
{exporter}
<table><tbody>{details}</tbody></table>
<h2>Goods declaration</h2>
<table><thead><tr><th>SKU</th><th>Description</th><th>Category / subcategory</th>
<th>HS code (seller supplied)</th><th>Country of origin (seller supplied)</th><th>Qty</th>
<th>Unit value</th><th>Line value</th></tr>
</thead><tbody>{item_rows}</tbody></table>
{disclaimer}
</body></html>"""
