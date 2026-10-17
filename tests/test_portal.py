import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portal import (
    DEMO_DOCUMENTS,
    DEMO_SELLER,
    REQUIRED_DOCUMENTS,
    calculate_estimate,
    load_shipment,
    load_shipment_draft,
    load_shipment_drafts,
    load_shipments,
    make_demo_draft,
    make_document_html,
    make_seller_profile_pdf,
    delete_shipment_draft,
    save_shipment_draft,
    save_shipment,
    seed_demo_shipments,
)


class SellerProfileTests(unittest.TestCase):
    def test_compliance_documents_and_registered_seller_details_are_seeded(self):
        expected_documents = {
            "LUT Number (Letter of Undertaking)",
            "RCMC",
            "ICEGATE Profile",
        }

        self.assertTrue(expected_documents.issubset(REQUIRED_DOCUMENTS))
        self.assertTrue(
            expected_documents.issubset(
                {document["type"] for document in DEMO_DOCUMENTS}
            )
        )
        self.assertTrue(DEMO_SELLER["lut_number"])
        self.assertTrue(DEMO_SELLER["rcmc"])
        self.assertTrue(DEMO_SELLER["icegate_profile"])


class EstimateTests(unittest.TestCase):
    def test_dimensional_weight_drives_estimate_and_insurance_has_minimum(self):
        items = [
            {
                "unit_value_usd": 10.0,
                "unit_weight_kg": 1.25,
                "quantity": 2,
            }
        ]

        result = calculate_estimate(
            items,
            package_count=1,
            length_cm=40,
            width_cm=30,
            height_cm=25,
            shipping_mode="Air freight",
        )

        self.assertEqual(result["declared_value_usd"], 20.0)
        self.assertEqual(result["actual_weight_kg"], 2.5)
        self.assertEqual(result["volumetric_weight_kg"], 5.0)
        self.assertEqual(result["chargeable_weight_kg"], 5.0)
        self.assertEqual(result["insurance_usd"], 12.0)
        self.assertEqual(result["estimated_total_usd"], 66.0)

    def test_insurance_scales_with_declared_value_and_ocean_mode_is_estimated(self):
        items = [{"unit_value_usd": 10_000.0, "unit_weight_kg": 1.0, "quantity": 1}]

        result = calculate_estimate(
            items,
            package_count=1,
            length_cm=10,
            width_cm=10,
            height_cm=10,
            shipping_mode="Ocean consolidated freight",
        )

        self.assertEqual(result["insurance_usd"], 80.0)
        self.assertEqual(result["chargeable_weight_kg"], 1.0)
        self.assertEqual(result["freight_usd"], 2.85)
        self.assertEqual(result["estimated_total_usd"], 127.85)

    def test_seller_declared_shipment_value_controls_insurance_basis(self):
        result = calculate_estimate(
            [{"unit_value_usd": 10.0, "unit_weight_kg": 1.0, "quantity": 1}],
            package_count=1,
            length_cm=10,
            width_cm=10,
            height_cm=10,
            shipping_mode="Air freight",
            declared_value_override=2_500,
        )

        self.assertEqual(result["declared_value_usd"], 2_500)
        self.assertEqual(result["insurance_usd"], 20)


class ShipmentStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "shipments.db"
        self.database_patch = patch("portal.DATABASE_PATH", self.database)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_shipments_are_scoped_to_seller_and_updates_replace_existing_record(self):
        shipment = {
            "shipment_id": "MER-TEST-001",
            "seller_id": "SELLER-1",
            "created_at": "2026-10-16T12:00+00:00",
            "status": "Pickup scheduled",
            "note": "Original",
        }
        save_shipment(shipment)
        shipment["note"] = "Updated"
        save_shipment(shipment)

        self.assertEqual(load_shipment("MER-TEST-001", "SELLER-1")["note"], "Updated")
        self.assertIsNone(load_shipment("MER-TEST-001", "SELLER-2"))
        self.assertEqual(len(load_shipments("SELLER-1")), 1)

    def test_seeded_demo_shipment_is_in_transit_and_seed_is_idempotent(self):
        seller = {**DEMO_SELLER, "pickup_address": "Mumbai demo address"}

        seed_demo_shipments(seller)
        seed_demo_shipments(seller)

        shipments = load_shipments(seller["seller_id"])
        self.assertEqual(len(shipments), 4)
        by_id = {shipment["shipment_id"]: shipment for shipment in shipments}
        transit = by_id["MER-DEMO-2026-001"]
        closed = by_id["MER-DEMO-2026-0008"]
        self.assertEqual(transit["status"], "In transit")
        self.assertEqual(transit["current_milestone"], "International transit")
        self.assertTrue(transit["tracking_number"].startswith("DEMO-"))
        self.assertEqual(closed["status"], "Closed")
        self.assertEqual(closed["payment_status"], "Paid")
        self.assertEqual(
            sum(shipment["status"] == "In transit" for shipment in shipments),
            2,
        )
        self.assertEqual(
            sum(shipment["status"] == "Closed" for shipment in shipments),
            2,
        )

    def test_existing_transit_demo_does_not_skip_closed_demo(self):
        seller = {**DEMO_SELLER, "pickup_address": "Mumbai demo address"}
        save_shipment(
            {
                "shipment_id": "MER-DEMO-2026-001",
                "seller_id": seller["seller_id"],
                "created_at": "2026-10-12T12:00+00:00",
                "status": "In transit",
            }
        )

        seed_demo_shipments(seller)

        shipments = load_shipments(seller["seller_id"])
        self.assertEqual(len(shipments), 4)
        self.assertEqual(
            load_shipment("MER-DEMO-2026-001", seller["seller_id"])["status"],
            "In transit",
        )
        closed = load_shipment("MER-DEMO-2026-0008", seller["seller_id"])
        self.assertEqual(closed["status"], "Closed")
        self.assertEqual(closed["payment_status"], "Paid")

    def test_seller_central_demo_draft_has_items_and_estimate(self):
        draft = make_demo_draft(
            {**DEMO_SELLER, "pickup_address": "Mumbai demo address"}
        )

        self.assertTrue(draft["is_demo_draft"])
        self.assertEqual(draft["status"], "Ready to create")
        self.assertEqual(draft["seller_reference"], "SC-ORDER-784216")
        self.assertGreater(len(draft["items"]), 0)
        self.assertGreater(draft["estimate"]["estimated_total_usd"], 0)

    def test_incomplete_shipment_drafts_are_saved_seller_scoped_and_removable(self):
        draft = {
            "draft_id": "DRAFT-TEST-001",
            "seller_id": "SELLER-1",
            "seller_reference": "SC-ORDER-TEST",
            "updated_at": "2026-10-16T12:00:00+00:00",
            "flow_step": 2,
            "progress_percent": 25,
            "items": [{"sku": "TEST-1", "quantity": 2}],
            "form_state": {"flow_step": 2},
        }
        save_shipment_draft(draft)
        draft["progress_percent"] = 50
        save_shipment_draft(draft)

        self.assertEqual(
            load_shipment_draft("DRAFT-TEST-001", "SELLER-1")["progress_percent"],
            50,
        )
        self.assertIsNone(load_shipment_draft("DRAFT-TEST-001", "SELLER-2"))
        self.assertEqual(len(load_shipment_drafts("SELLER-1")), 1)

        delete_shipment_draft("DRAFT-TEST-001", "SELLER-1")
        self.assertEqual(load_shipment_drafts("SELLER-1"), [])


class DocumentTests(unittest.TestCase):
    def test_seller_profile_pdf_is_downloadable_pdf_data(self):
        content = make_seller_profile_pdf(
            {**DEMO_SELLER, "documents_received": []}
        )

        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 500)

    def test_printable_challan_escapes_seller_and_product_content(self):
        shipment = {
            "shipment_id": "MER-TEST-002",
            "created_at": "2026-10-16T12:00+00:00",
            "destination": {"code": "US-EAST", "gateway": "JFK"},
            "destination_label": "US East",
            "estimate": {
                "actual_weight_kg": 1.0,
                "goods_weight_kg": 1.0,
                "packaging_weight_kg": 0.0,
                "volumetric_weight_kg": 2.0,
                "chargeable_weight_kg": 2.0,
                "declared_value_usd": 25.0,
                "freight_usd": 10.0,
                "handling_usd": 28.0,
                "insurance_usd": 12.0,
                "estimated_total_usd": 50.0,
            },
            "category": "Other",
            "subcategory": "Demo",
            "shipping_mode": "Air freight",
            "port_of_loading": "Nhava Sheva",
            "incoterm": "To be agreed with buyer",
            "export_tax_treatment": "To be confirmed with tax advisor",
            "package_count": 1,
            "package_type": "Cartons",
            "length_cm": 40,
            "width_cm": 30,
            "height_cm": 20,
            "consignee_name": "Buyer",
            "consignee_address": "New York",
            "pickup_address": "Mumbai",
            "pickup_date": "2026-10-17",
            "pickup_slot": "09:00–12:00 IST",
            "seller_reference": "",
            "items": [
                {
                    "sku": "A-1",
                    "name": "<script>alert(1)</script>",
                    "category": "Other",
                    "subcategory": "Demo",
                    "hs_code": "000000",
                    "quantity": 1,
                    "unit_value_usd": 25.0,
                }
            ],
        }
        seller = {
            "business_name": "<b>Seller</b>",
            "seller_id": "SELLER-1",
            "iec": "AABCT1234F",
            "gstin": "27AABCT1234F1Z5",
        }

        document = make_document_html(shipment, seller, "challan")

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", document)
        self.assertIn("&lt;b&gt;Seller&lt;/b&gt;", document)
        self.assertNotIn("<script>alert(1)</script>", document)


if __name__ == "__main__":
    unittest.main()
