import base64
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import streamlit as st

from portal import (
    CATEGORY_SUBCATEGORIES,
    DEFAULT_CATALOG,
    WAREHOUSES,
    calculate_estimate,
    delete_shipment_draft,
    load_shipment_draft,
    load_shipment_drafts,
    load_shipments,
    make_demo_draft,
    make_document_html,
    save_shipment_draft,
    save_shipment,
)


def _encode_draft_value(value):
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__type__": "time", "value": value.isoformat()}
    if isinstance(value, dict):
        return {key: _encode_draft_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_draft_value(item) for item in value]
    return value


def _decode_draft_value(value):
    if isinstance(value, dict) and value.get("__type__") == "date":
        return date.fromisoformat(value["value"])
    if isinstance(value, dict) and value.get("__type__") == "time":
        return time.fromisoformat(value["value"])
    if isinstance(value, dict):
        return {key: _decode_draft_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_draft_value(item) for item in value]
    return value


def _request_draft_deletion(draft_id):
    st.session_state.delete_confirm_draft_id = draft_id


def _cancel_draft_deletion():
    st.session_state.delete_confirm_draft_id = None


def _confirm_draft_deletion(draft_id):
    seller_id = st.session_state.seller["seller_id"]
    delete_shipment_draft(draft_id, seller_id)
    if st.session_state.get("active_shipment_draft_id") == draft_id:
        st.session_state.active_shipment_draft_id = None
        st.session_state.loaded_shipment_draft_id = None
        st.session_state.shipment_flow_active = False
    st.session_state.delete_confirm_draft_id = None
    st.session_state.export_shipment_tabs = "Pending Completion"


def _resume_shipment_draft(draft_id):
    st.session_state.active_shipment_draft_id = draft_id
    st.session_state.loaded_shipment_draft_id = None
    st.session_state.shipment_flow_active = True
    st.session_state.shipment_success_message = ""
    st.session_state.export_shipment_tabs = "New Shipment"


def _start_shipment_flow():
    version = st.session_state.get("shipment_form_version", 0) + 1
    draft_id = f"DRAFT-{uuid4().hex[:12].upper()}"
    seller_id = st.session_state.seller["seller_id"]
    base_reference = st.session_state.demo_shipment_draft["seller_reference"]
    used_references = {
        item.get("seller_reference")
        for item in load_shipments(seller_id)
    }
    used_references.update(
        item.get("seller_reference")
        for item in load_shipment_drafts(seller_id)
    )
    seller_reference = base_reference
    suffix = 2
    while seller_reference in used_references:
        seller_reference = f"{base_reference}-{suffix}"
        suffix += 1

    st.session_state.shipment_form_version = version
    st.session_state.shipment_flow_step = 1
    st.session_state.shipment_flow_active = True
    st.session_state.export_shipment_tabs = "New Shipment"
    st.session_state.active_shipment_draft_id = draft_id
    st.session_state.loaded_shipment_draft_id = draft_id
    st.session_state.current_seller_reference = seller_reference
    st.session_state.shipment_working_data = {}
    st.session_state.shipment_selected_items = {
        item["sku"]: 0 for item in st.session_state.catalog
    }
    st.session_state.shipment_success_message = ""
    st.session_state.last_created_shipment_id = None
    save_shipment_draft(
        {
            "draft_id": draft_id,
            "seller_id": seller_id,
            "seller_reference": seller_reference,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "flow_step": 1,
            "progress_percent": 0,
            "items": [],
            "form_state": {
                "form_version": version,
                "flow_step": 1,
                "selected_items": st.session_state.shipment_selected_items,
                "working_data": {},
                "widget_values": {},
            },
        }
    )


def _save_active_draft_snapshot(seller, draft):
    active_draft_id = st.session_state.get("active_shipment_draft_id")
    if not active_draft_id:
        return

    version = st.session_state.shipment_form_version
    widget_prefix = f"wizard_{version}_"
    widget_values = {
        key: value
        for key, value in st.session_state.items()
        if key.startswith(widget_prefix)
        and not key.endswith("_compliance_documents")
    }
    selected_items = dict(st.session_state.get("shipment_selected_items", {}))
    for product in st.session_state.catalog:
        quantity_key = f"{widget_prefix}qty_{product['sku']}"
        if quantity_key in widget_values:
            selected_items[product["sku"]] = int(widget_values[quantity_key])

    step = int(st.session_state.shipment_flow_step)
    progress_percent = max(0, (step - 1) * 25)
    if step == 1 and any(selected_items.values()):
        progress_percent = 10
    save_shipment_draft(
        {
            "draft_id": active_draft_id,
            "seller_id": seller["seller_id"],
            "seller_reference": draft["seller_reference"],
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "flow_step": step,
            "progress_percent": progress_percent,
            "items": [
                {
                    "sku": product["sku"],
                    "name": product["name"],
                    "quantity": int(selected_items.get(product["sku"], 0)),
                }
                for product in st.session_state.catalog
                if int(selected_items.get(product["sku"], 0)) > 0
            ],
            "destination_label": st.session_state.get(
                "shipment_working_data", {}
            ).get("destination_label", "Destination not selected"),
            "form_state": {
                "form_version": version,
                "flow_step": step,
                "selected_items": selected_items,
                "working_data": st.session_state.get(
                    "shipment_working_data", {}
                ),
                "widget_values": _encode_draft_value(widget_values),
            },
        }
    )
    st.session_state.shipment_selected_items = selected_items


def _render_wip_shipments(saved_drafts):
    st.markdown("### Pending Completion")
    if not saved_drafts:
        st.info("Partially completed shipments will appear here.")
    for saved_draft in saved_drafts:
        with st.container(border=True):
            st.markdown(f"#### `{saved_draft['seller_reference']}`")
            st.write(
                f"{len(saved_draft.get('items', []))} product lines · "
                f"{saved_draft.get('destination_label', 'Destination not selected')}"
            )
            progress = int(saved_draft.get("progress_percent", 0))
            st.progress(
                progress / 100,
                text=(
                    f"Step {saved_draft.get('flow_step', 1)} of 4 · "
                    f"{progress}% complete"
                ),
            )
            st.caption(f"Autosaved · {saved_draft['updated_at']}")
            resume_col, delete_col = st.columns([1, 1])
            with resume_col:
                st.button(
                    "Resume",
                    key=f"resume_draft_{saved_draft['draft_id']}",
                    type="primary",
                    width="stretch",
                    on_click=_resume_shipment_draft,
                    args=(saved_draft["draft_id"],),
                )
            with delete_col:
                draft_id = saved_draft["draft_id"]
                if st.session_state.delete_confirm_draft_id == draft_id:
                    st.button(
                        "Confirm delete",
                        key=f"confirm_delete_draft_{draft_id}",
                        type="secondary",
                        width="stretch",
                        on_click=_confirm_draft_deletion,
                        args=(draft_id,),
                    )
                else:
                    st.button(
                        "Delete",
                        key=f"request_delete_draft_{draft_id}",
                        width="stretch",
                        on_click=_request_draft_deletion,
                        args=(draft_id,),
                    )
            if st.session_state.delete_confirm_draft_id == saved_draft["draft_id"]:
                st.warning("Delete this saved shipment draft? This cannot be undone.")
                st.button(
                    "Cancel",
                    key=f"cancel_delete_draft_{saved_draft['draft_id']}",
                    on_click=_cancel_draft_deletion,
                )


def _render_shipment_status(shipments, status):
    if not shipments:
        st.info("There are no shipments in this status.")
    for shipment in shipments:
        shipment_id = shipment["shipment_id"]
        with st.container(border=True):
            st.markdown(f"#### `{shipment_id}`")
            if status == "Scheduled for pick-up":
                st.badge("Pickup scheduled", color="orange")
                st.write(
                    f"{shipment['destination_label']} · {shipment['pickup_date']} · "
                    f"{shipment['pickup_slot']}"
                )
                st.caption(
                    f"{sum(item['quantity'] for item in shipment['items'])} units · "
                    f"{shipment['shipping_mode']} · "
                    f"Seller reference {shipment.get('seller_reference', '—')}"
                )
                if st.button(
                    "Shipment details",
                    key=f"scheduled_documents_{shipment_id}",
                ):
                    st.session_state.active_shipment_id = shipment_id
                    st.session_state.documents_selected_shipment = shipment_id
                    st.switch_page("app_pages/shipment_documents.py")
            elif status == "In-transit":
                st.badge("In transit", color="blue")
                st.write(
                    f"{shipment['destination_label']} · {shipment['shipping_mode']} · "
                    f"{sum(item['quantity'] for item in shipment['items'])} units"
                )
                st.caption(
                    f"Last update · {shipment.get('updated_at', shipment['created_at'])} · "
                    f"{shipment.get('current_milestone', 'International transit')} · "
                    f"Tracking {shipment.get('tracking_number', 'Assigned')}"
                )
                if st.button(
                    "Tracking details",
                    key=f"export_track_{shipment_id}",
                    type="primary",
                ):
                    st.session_state.active_shipment_id = shipment_id
                    st.session_state.tracking_expanded_id = shipment_id
                    st.session_state.tracking_selected_id = shipment_id
                    st.session_state.tracking_show_milestones = True
                    st.switch_page("app_pages/tracking.py")
            else:
                st.badge("Delivered", color="green")
                st.write(
                    f"{shipment['destination_label']} · "
                    f"{shipment['closed_at'][:10]} · "
                    f"{sum(item['quantity'] for item in shipment['items'])} units"
                )
                st.write(
                    f"**Category:** {shipment['category']} · "
                    f"**Mode:** {shipment['shipping_mode']} · "
                    f"**Payment:** {shipment.get('payment_status', 'Pending')} · "
                    f"**Shipment cost:** "
                    f"${shipment['estimate']['estimated_total_usd']:,.2f}"
                )
                st.caption(
                    f"Seller Central ref · {shipment.get('seller_reference', '—')} · "
                    f"Tracking · {shipment.get('tracking_number', '—')} · "
                    f"Consignee · {shipment['consignee_name']}"
                )
                if st.button(
                    "Shipment details",
                    key=f"closed_documents_{shipment_id}",
                ):
                    st.session_state.active_shipment_id = shipment_id
                    st.session_state.documents_selected_shipment = shipment_id
                    st.switch_page("app_pages/shipment_documents.py")


if not st.session_state.onboarding_complete:
    st.warning("Complete seller onboarding before creating an export shipment.")
    st.stop()

seller = st.session_state.seller
saved_shipments = load_shipments(seller["seller_id"])
demo_draft = st.session_state.setdefault("demo_shipment_draft", make_demo_draft(seller))
st.session_state.setdefault("current_seller_reference", demo_draft["seller_reference"])
draft = {**demo_draft, "seller_reference": st.session_state.current_seller_reference}
st.session_state.setdefault("export_shipment_tabs", "New Shipment")
st.session_state.setdefault("shipment_flow_step", 1)
st.session_state.setdefault("shipment_form_version", 0)
st.session_state.setdefault("shipment_flow_active", False)
st.session_state.setdefault("delete_confirm_draft_id", None)

active_draft_id = st.session_state.get("active_shipment_draft_id")
if active_draft_id and (
    st.session_state.get("loaded_shipment_draft_id") != active_draft_id
):
    active_draft = load_shipment_draft(active_draft_id, seller["seller_id"])
    if active_draft:
        form_state = active_draft.get("form_state", {})
        st.session_state.current_seller_reference = active_draft.get(
            "seller_reference", demo_draft["seller_reference"]
        )
        version = int(form_state.get("form_version", 0))
        st.session_state.shipment_form_version = version
        st.session_state.shipment_flow_step = int(
            form_state.get("flow_step", active_draft.get("flow_step", 1))
        )
        st.session_state.shipment_selected_items = form_state.get(
            "selected_items", {}
        )
        st.session_state.shipment_working_data = form_state.get(
            "working_data", {}
        )
        for key, value in form_state.get("widget_values", {}).items():
            st.session_state[key] = _decode_draft_value(value)
        st.session_state.shipment_flow_active = True
        st.session_state.export_shipment_tabs = "New Shipment"
        st.session_state.loaded_shipment_draft_id = active_draft_id
    else:
        st.session_state.active_shipment_draft_id = None
        st.session_state.loaded_shipment_draft_id = None
        st.session_state.shipment_flow_active = False

draft = {
    **demo_draft,
    "seller_reference": st.session_state.current_seller_reference,
}

_save_active_draft_snapshot(seller, draft)

saved_drafts = load_shipment_drafts(seller["seller_id"])
in_transit_shipments = [
    item for item in saved_shipments if item["status"] == "In transit"
]
pickup_scheduled_shipments = [
    item for item in saved_shipments if item["status"] == "Pickup scheduled"
]
closed_shipments = [item for item in saved_shipments if item["status"] == "Closed"]

status_options = [
    ("Pending Completion", len(saved_drafts)),
    ("Scheduled for pick-up", len(pickup_scheduled_shipments)),
    ("In-transit", len(in_transit_shipments)),
    ("Closed", len(closed_shipments)),
]
st.space("small")
st.title("Export Shipment")
with st.container(key="shipment_summary_table", gap=None, border=True):
    for index, (status, count) in enumerate(status_options):
        row_key = f"shipment_summary_row_{index}"
        with st.container(key=row_key):
            status_cell, metric_cell = st.columns([1, 1], vertical_alignment="center")
            status_cell.markdown(f"**{status}**")
            metric_cell.markdown(
                f"<div style='text-align:center;font-weight:700'>{count}</div>",
                unsafe_allow_html=True,
            )

new_shipment_tab, wip_tab, scheduled_tab, transit_tab, closed_tab = st.tabs(
    [
        "New Shipment",
        "Pending Completion",
        "Scheduled for pick-up",
        "In-transit",
        "Closed",
    ],
    key="export_shipment_tabs",
    default="New Shipment",
)

with new_shipment_tab:
    if not st.session_state.shipment_flow_active:
        st.markdown("### Create a new shipment")
        st.caption(
            "Start a shipment from your Seller Central catalogue. Your progress "
            "will be autosaved as you work through the steps."
        )
        st.button(
            "Start new shipment",
            key="start_new_shipment",
            type="primary",
            icon=":material/add_box:",
            on_click=_start_shipment_flow,
        )
    if st.session_state.shipment_flow_active:
        with st.container(key="shipment_workspace"):
            imported_shipment = next(
                (
                    item
                    for item in saved_shipments
                    if item.get("seller_reference") == draft["seller_reference"]
                ),
                None,
            )
            if imported_shipment:
                with st.container(border=True):
                    st.success(
                        f"Seller Central order {draft['seller_reference']} was booked as "
                        f"{imported_shipment['shipment_id']}."
                    )
                    st.write("The original order remains in the catalog import for reference.")
                    if st.button("Start another shipment", key="reset_new_shipment"):
                        _start_shipment_flow()
                        st.rerun()
            else:
                step = st.session_state.shipment_flow_step
                version = st.session_state.shipment_form_version
                st.progress(step / 4, text=f"Step {step} of 4 · " + [
                    "Import items",
                    "Pickup and destination",
                    "Shipment details",
                    "Review and create",
                ][step - 1])

                if step == 1:
                    st.markdown("#### 1 · Import items from Seller Central")
                    st.info(
                        f"Seller Central order `{draft['seller_reference']}` · "
                        f"Sample order import for seller `{seller['seller_id']}`. "
                        "No live account connection is configured.",
                        icon=":material/sync:",
                    )
                    st.caption(
                        ":material/info: Product category and HSN codes are imported "
                        "from the Seller Central catalogue and are read-only here."
                    )
                    with st.expander("Add an item to the imported product catalogue"):
                        with st.form("add_shipment_catalog_item", clear_on_submit=True):
                            add_col1, add_col2 = st.columns(2)
                            with add_col1:
                                new_name = st.text_input("Product name")
                                new_sku = st.text_input("Seller SKU")
                                new_category = st.selectbox(
                                    "Category",
                                    list(CATEGORY_SUBCATEGORIES),
                                )
                                new_subcategory = st.text_input("Subcategory")
                            with add_col2:
                                new_hsn = st.text_input("HSN code")
                                new_origin = st.text_input("Country of origin", value="India")
                                new_value = st.number_input(
                                    "Unit value (USD)",
                                    min_value=0.01,
                                    value=25.0,
                                    step=1.0,
                                )
                                new_weight = st.number_input(
                                    "Unit weight (kg)",
                                    min_value=0.01,
                                    value=0.5,
                                    step=0.05,
                                )
                            add_product = st.form_submit_button("Add catalogue item")
                        if add_product:
                            new_sku = new_sku.strip().upper()
                            if not new_name.strip() or not new_sku or not new_subcategory.strip():
                                st.error("Enter a product name, SKU, and subcategory.")
                            elif any(
                                product["sku"].upper() == new_sku
                                for product in st.session_state.catalog
                            ):
                                st.error("That seller SKU already exists.")
                            else:
                                st.session_state.catalog.append(
                                    {
                                        "sku": new_sku,
                                        "name": new_name.strip(),
                                        "category": new_category,
                                        "subcategory": new_subcategory.strip(),
                                        "hs_code": new_hsn.strip() or "Seller to confirm",
                                        "country_of_origin": new_origin.strip() or "India",
                                        "unit_value_usd": float(new_value),
                                        "unit_weight_kg": float(new_weight),
                                    }
                                )
                                st.rerun()
                    draft_quantities = {
                        item["sku"]: item["quantity"] for item in draft["items"]
                    }
                    use_sample_order = st.checkbox(
                        "Use the preloaded Seller Central sample order",
                        value=st.session_state.get("use_sample_seller_order", True),
                        key=f"wizard_{version}_use_sample_order",
                    )
                    st.session_state.use_sample_seller_order = use_sample_order
                    items = st.session_state.setdefault(
                        "shipment_selected_items",
                        {item["sku"]: 0 for item in st.session_state.catalog},
                    )
                    for item in st.session_state.catalog:
                        if item["sku"] not in items:
                            items[item["sku"]] = 0
                    last_applied_version = st.session_state.get(
                        "sample_order_applied_version"
                    )
                    last_applied_value = st.session_state.get(
                        "sample_order_applied_value"
                    )
                    if (
                        last_applied_version != version
                        or last_applied_value != use_sample_order
                    ):
                        for product in st.session_state.catalog:
                            quantity_key = f"wizard_{version}_qty_{product['sku']}"
                            quantity = (
                                draft_quantities.get(product["sku"], 0)
                                if use_sample_order
                                else 0
                            )
                            st.session_state[quantity_key] = quantity
                            items[product["sku"]] = quantity
                        st.session_state.sample_order_applied_version = version
                        st.session_state.sample_order_applied_value = use_sample_order
                    for product in st.session_state.catalog:
                        quantity_key = f"wizard_{version}_qty_{product['sku']}"
                        if quantity_key not in st.session_state:
                            st.session_state[quantity_key] = int(items.get(product["sku"], 0))
                        with st.container(border=True):
                            product_col, details_col, quantity_col = st.columns(
                                [2, 2, 1],
                                vertical_alignment="center",
                            )
                            product_col.markdown(f"**{product['name']}**")
                            product_col.caption(f"{product['sku']} · {product['category']}")
                            details_col.write(
                                f"{product['subcategory']} · HS {product['hs_code']}"
                            )
                            details_col.caption(
                                f"${product['unit_value_usd']:.2f} per unit · "
                                f"{product['unit_weight_kg']:.2f} kg"
                            )
                            items[product["sku"]] = quantity_col.number_input(
                                f"Quantity · {product['sku']}",
                                min_value=0,
                                max_value=1000,
                                step=1,
                                key=quantity_key,
                                label_visibility="collapsed",
                            )
                    chosen = [
                        (product, int(items.get(product["sku"], 0)))
                        for product in st.session_state.catalog
                        if int(items.get(product["sku"], 0)) > 0
                    ]
                    item_total = sum(quantity for _, quantity in chosen)
                    st.metric("Selected units", item_total)
                    _, next_col = st.columns([4, 1])
                    with next_col:
                        if st.button(
                            "Next · pickup",
                            key="wizard_to_pickup",
                            type="primary",
                            width="stretch",
                        ):
                            if not chosen:
                                st.error("Choose a quantity for at least one catalog item.")
                            else:
                                st.session_state.shipment_selected_items = items
                                st.session_state.shipment_flow_step = 2
                                st.rerun()

                elif step == 2:
                    st.markdown("#### 2 · Pick up details and destination")
                    st.caption("Confirm how this shipment will be collected and routed.")
                    with st.container(border=True):
                        st.markdown("##### Pick up details")
                        pickup_col, contact_col = st.columns(2)
                        pickup_col.markdown(
                            f"**Pickup address**  \n{seller['pickup_address']}"
                        )
                        pickup_col.caption(
                            ":material/info: From seller profile · Pickup address proof"
                        )
                        pickup_contact_name = contact_col.text_input(
                            "Pickup contact name",
                            value=seller.get("pickup_contact_name", ""),
                            key=f"wizard_{version}_pickup_contact_name",
                        )
                        pickup_contact_phone = contact_col.text_input(
                            "Pickup contact phone",
                            value=seller.get("pickup_contact_phone", ""),
                            key=f"wizard_{version}_pickup_contact_phone",
                        )

                        india_timezone = ZoneInfo("Asia/Kolkata")
                        local_now = datetime.now(timezone.utc).astimezone(india_timezone)
                        earliest_pickup = local_now + timedelta(hours=36)
                        default_pickup = earliest_pickup.replace(
                            minute=0, second=0, microsecond=0
                        ) + timedelta(hours=1)
                        date_col, time_col = st.columns([1, 1])
                        selected_date = date_col.date_input(
                            "Pickup date",
                            value=default_pickup.date(),
                            min_value=earliest_pickup.date(),
                            key=f"wizard_{version}_pickup_date",
                        )
                        selected_time = time_col.time_input(
                            "Pickup time · IST",
                            value=default_pickup.time(),
                            key=f"wizard_{version}_pickup_time",
                        )
                        st.caption(
                            "Pickup must be booked at least 36 hours in advance. "
                            "Date and time are shown in India local time."
                        )

                    with st.container(border=True):
                        st.markdown("##### Destination Warehouse")
                        route_col, consignee_col = st.columns(2)
                        destination = route_col.selectbox(
                            "Destination warehouse",
                            list(WAREHOUSES),
                            key=f"wizard_{version}_destination",
                        )
                        shipping_mode = route_col.selectbox(
                            "Shipping mode",
                            ["Air freight", "Ocean consolidated freight"],
                            key=f"wizard_{version}_shipping_mode",
                        )
                        warehouse_details = WAREHOUSES[destination]
                        consignee_name = warehouse_details["consignee_name"]
                        consignee_address = warehouse_details["consignee_address"]
                        consignee_col.markdown(
                            f"**Consignee / receiving account**  \n{consignee_name}"
                        )
                        consignee_col.markdown(
                            f"**Consignee address**  \n{consignee_address}"
                        )
                        consignee_col.caption(
                            ":material/info: Receiving address is prefilled from the "
                            "selected warehouse listing and cannot be edited here."
                        )

                    with st.container(border=True):
                        st.markdown("##### Export and delivery declarations")
                        regulatory_left, regulatory_right = st.columns(2)
                        port_of_loading = regulatory_left.selectbox(
                            "Port / airport of loading",
                            [
                                "Nhava Sheva (JNPT), Maharashtra",
                                "Mundra, Gujarat",
                                "Chennai, Tamil Nadu",
                                "Kolkata, West Bengal",
                                "Delhi Air Cargo",
                                "Bengaluru Air Cargo",
                                "Hyderabad Air Cargo",
                            ],
                            key=f"wizard_{version}_port",
                        )
                        incoterm = regulatory_left.selectbox(
                            "Delivery terms / Incoterm",
                            ["To be agreed with buyer", "FCA", "FOB", "CPT", "CIP", "DAP", "DDP"],
                            key=f"wizard_{version}_incoterm",
                        )
                        export_tax_treatment = regulatory_right.selectbox(
                            "Export GST / LUT",
                            [
                                "To be confirmed with tax advisor",
                                "LUT / bond (exporter to confirm)",
                                "IGST paid at export (exporter to confirm)",
                            ],
                            key=f"wizard_{version}_gst",
                        )
                        commercial_invoice_number = regulatory_right.text_input(
                            "Commercial invoice number (optional)",
                            key=f"wizard_{version}_invoice",
                        )

                    nav_back, _, nav_next = st.columns([1, 3, 1])
                    with nav_back:
                        if st.button("← Previous", key="wizard_back_to_items"):
                            st.session_state.shipment_flow_step = 1
                            st.rerun()
                    with nav_next:
                        if st.button(
                            "Next · shipment details",
                            type="primary",
                            key="wizard_to_details",
                            width="stretch",
                        ):
                            pickup_datetime = datetime.combine(
                                selected_date,
                                selected_time,
                                tzinfo=india_timezone,
                            )
                            errors = []
                            if pickup_datetime < earliest_pickup:
                                errors.append("Choose a pickup date and time at least 36 hours from now.")
                            if not pickup_contact_name.strip() or not pickup_contact_phone.strip():
                                errors.append("Enter a pickup contact name and phone.")
                            if not consignee_name.strip() or not consignee_address.strip():
                                errors.append("Enter the US consignee and destination address.")
                            if errors:
                                st.error("\n\n".join(errors))
                            else:
                                selected_quantities = st.session_state.get(
                                    "shipment_selected_items", {}
                                )
                                chosen_items = [
                                    (product, int(selected_quantities.get(product["sku"], 0)))
                                    for product in st.session_state.catalog
                                    if int(selected_quantities.get(product["sku"], 0)) > 0
                                ]
                                if not chosen_items:
                                    st.error(
                                        "Return to Import items and choose at least one "
                                        "product before continuing."
                                    )
                                    st.stop()
                                st.session_state.shipment_working_data = {
                                    "destination_label": destination,
                                    "destination": WAREHOUSES[destination],
                                    "shipping_mode": shipping_mode,
                                    "consignee_name": consignee_name.strip(),
                                    "consignee_address": consignee_address.strip(),
                                    "pickup_city": seller.get("pickup_city", "Mumbai"),
                                    "pickup_address": seller["pickup_address"],
                                    "pickup_contact": (
                                        f"{pickup_contact_name.strip()} · "
                                        f"{pickup_contact_phone.strip()}"
                                    ),
                                    "pickup_date": selected_date.isoformat(),
                                    "pickup_time": selected_time.strftime("%H:%M"),
                                    "port_of_loading": port_of_loading,
                                    "incoterm": incoterm,
                                    "export_tax_treatment": export_tax_treatment,
                                    "commercial_invoice_number": commercial_invoice_number.strip(),
                                    "seller_reference": draft["seller_reference"],
                                    "items": [
                                        {
                                            **product,
                                            "quantity": int(quantity),
                                            "category": product["category"],
                                            "subcategory": product["subcategory"],
                                        }
                                        for product, quantity in chosen_items
                                    ],
                                }
                                st.session_state.shipment_flow_step = 3
                                st.rerun()

                elif step == 3:
                    st.markdown("#### 3 · Shipment Details")
                    shipment_data = st.session_state.get("shipment_working_data", {})
                    if not shipment_data:
                        st.warning("Start with the Seller Central items, then continue through pickup details.")
                        st.session_state.shipment_flow_step = 1
                        st.stop()

                    with st.container(border=True):
                        st.markdown("##### Selected catalogue line items")
                        st.dataframe(
                            [
                                {
                                    "SKU": item["sku"],
                                    "Product": item["name"],
                                    "Category": item["category"],
                                    "Subcategory": item["subcategory"],
                                    "HSN code": item["hs_code"],
                                    "Units": item["quantity"],
                                    "Unit value (USD)": item["unit_value_usd"],
                                }
                                for item in shipment_data["items"]
                            ],
                            hide_index=True,
                            width="stretch",
                            alt="Selected imported catalogue items and quantities",
                        )

                    default_declared = sum(
                        item["unit_value_usd"] * item["quantity"]
                        for item in shipment_data["items"]
                    )
                    with st.container(border=True):
                        st.markdown("##### Shipment value and insurance")
                        value_col, insurance_col = st.columns(2)
                        declared_value = value_col.number_input(
                            "Declared shipment cost / goods value (USD)",
                            min_value=1.0,
                            value=float(
                                st.session_state.get(
                                    f"wizard_{version}_declared_value",
                                    default_declared,
                                )
                            ),
                            step=10.0,
                            key=f"wizard_{version}_declared_value",
                            help="Seller-declared value used as the indicative cargo insurance basis.",
                        )
                        insurance_estimate = max(12.0, declared_value * 0.008)
                        insurance_col.metric(
                            "Firm-arranged insurance estimate",
                            f"${insurance_estimate:,.2f} USD",
                            help="Illustrative estimate: 0.8% of declared value, minimum $12.",
                        )

                    with st.container(border=True):
                        st.markdown("##### Packages and volumetric weight")
                        package_col1, package_col2, package_col3, package_col4 = st.columns(4)
                        package_type = package_col1.selectbox(
                            "Package type",
                            ["Cartons", "Crates", "Pallets"],
                            key=f"wizard_{version}_package_type",
                        )
                        package_count = package_col2.number_input(
                            "Number of packages",
                            min_value=1,
                            max_value=100,
                            value=3,
                            step=1,
                            key=f"wizard_{version}_package_count",
                        )
                        length_cm = package_col3.number_input(
                            "Length (cm)",
                            min_value=1.0,
                            max_value=300.0,
                            value=60.0,
                            step=1.0,
                            key=f"wizard_{version}_length",
                        )
                        width_cm = package_col4.number_input(
                            "Width (cm)",
                            min_value=1.0,
                            max_value=300.0,
                            value=45.0,
                            step=1.0,
                            key=f"wizard_{version}_width",
                        )
                        height_cm = st.number_input(
                            "Height per package (cm)",
                            min_value=1.0,
                            max_value=300.0,
                            value=40.0,
                            step=1.0,
                            key=f"wizard_{version}_height",
                        )
                        packaging_weight = st.number_input(
                            "Total packaging weight (kg)",
                            min_value=0.0,
                            max_value=500.0,
                            value=4.5,
                            step=0.1,
                            key=f"wizard_{version}_packaging_weight",
                        )
                        package_marks = st.text_input(
                            "Package marks / labels",
                            value="AARAV / US-EAST / CARTON 1-3",
                            key=f"wizard_{version}_marks",
                        )

                    with st.container(border=True):
                        st.markdown("##### Destination compliance documents")
                        st.caption(
                            f"Upload product and destination-specific compliance "
                            f"documents for {shipment_data['destination_label']}, such "
                            "as test reports, certificates, or permits. Requirements "
                            "depend on product classification; confirm them with your "
                            "customs broker. PDF, JPG, or PNG files up to 20 MB each."
                        )
                        compliance_uploads = st.file_uploader(
                            "Compliance documents",
                            type=["pdf", "jpg", "jpeg", "png"],
                            accept_multiple_files=True,
                            key=f"wizard_{version}_compliance_documents",
                            max_upload_size=20,
                        )
                        compliance_documents = [
                            {
                                "filename": uploaded.name,
                                "mime_type": uploaded.type or "application/octet-stream",
                                "size_bytes": uploaded.size,
                                "content_base64": base64.b64encode(
                                    uploaded.getvalue()
                                ).decode("ascii"),
                            }
                            for uploaded in compliance_uploads
                        ] or shipment_data.get("compliance_documents", [])

                    selected_items = [
                        {**item, "unit_value_usd": float(item["unit_value_usd"])}
                        for item in shipment_data["items"]
                    ]
                    estimate = calculate_estimate(
                        selected_items,
                        int(package_count),
                        float(length_cm),
                        float(width_cm),
                        float(height_cm),
                        shipment_data["shipping_mode"],
                        float(packaging_weight),
                        declared_value_override=float(declared_value),
                    )
                    shipment_data.update(
                        {
                            "declared_shipment_cost_usd": float(declared_value),
                            "package_type": package_type,
                            "package_count": int(package_count),
                            "length_cm": float(length_cm),
                            "width_cm": float(width_cm),
                            "height_cm": float(height_cm),
                            "packaging_weight_kg": float(packaging_weight),
                            "package_marks": package_marks,
                            "compliance_documents": compliance_documents,
                            "estimate": estimate,
                        }
                    )
                    st.session_state.shipment_working_data = shipment_data

                    item_col, weight_col, freight_col, insurance_col = st.columns(4)
                    item_col.metric("Units", sum(item["quantity"] for item in selected_items))
                    weight_col.metric(
                        "Volumetric weight",
                        f"{estimate['volumetric_weight_kg']:.2f} kg",
                    )
                    freight_col.metric(
                        "Estimated export service cost",
                        f"${estimate['freight_usd'] + estimate['handling_usd']:,.2f}",
                    )
                    insurance_col.metric(
                        "Insurance estimate",
                        f"${estimate['insurance_usd']:,.2f}",
                    )
                    previous, _, review = st.columns([1, 3, 1])
                    with previous:
                        if st.button("← Previous", key="wizard_back_to_pickup"):
                            st.session_state.shipment_flow_step = 2
                            st.rerun()
                    with review:
                        if st.button(
                            "Review estimate →",
                            key="wizard_to_review",
                            type="primary",
                            width="stretch",
                        ):
                            st.session_state.shipment_flow_step = 4
                            st.rerun()

                else:
                    st.markdown("#### Review estimate")
                    shipment_data = st.session_state.get("shipment_working_data", {})
                    if not shipment_data:
                        st.warning("Start with the Seller Central items to review a shipment.")
                        st.session_state.shipment_flow_step = 1
                        st.stop()
                    estimate = shipment_data["estimate"]
                    summary_col, route_col = st.columns(2)
                    with summary_col:
                        with st.container(border=True):
                            st.markdown("##### Cargo and declared value")
                            st.write(f"**Order:** {shipment_data['seller_reference']}")
                            st.write(
                                f"**Units / SKUs:** "
                                f"{sum(item['quantity'] for item in shipment_data['items'])} / "
                                f"{len(shipment_data['items'])}"
                            )
                            st.write(
                                f"**Declared shipment cost:** "
                                f"${shipment_data['declared_shipment_cost_usd']:,.2f} USD"
                            )
                            st.write(
                                f"**Approx. insurance:** "
                                f"${estimate['insurance_usd']:,.2f} USD"
                            )
                            st.write(
                                f"**Freight + handling estimate:** "
                                f"${estimate['freight_usd'] + estimate['handling_usd']:,.2f} USD"
                            )
                            st.write(
                                f"**Approx. export service total:** "
                                f"${estimate['estimated_total_usd']:,.2f} USD"
                            )
                            st.write(
                                f"**Actual / volumetric / chargeable weight:** "
                                f"{estimate['actual_weight_kg']:.2f} / "
                                f"{estimate['volumetric_weight_kg']:.2f} / "
                                f"{estimate['chargeable_weight_kg']:.2f} kg"
                            )
                    with route_col:
                        with st.container(border=True):
                            st.markdown("##### Route and pickup")
                            st.write(f"**Pickup:** {shipment_data['pickup_address']}")
                            st.write(f"**Contact:** {shipment_data['pickup_contact']}")
                            st.write(
                                f"**Pickup date and slot:** {shipment_data['pickup_date']} · "
                                f"{shipment_data['pickup_time']} IST"
                            )
                            st.write(
                                f"**Destination:** {shipment_data['destination_label']}"
                            )
                            st.write(
                                f"**Consignee:** {shipment_data['consignee_name']} · "
                                f"{shipment_data['consignee_address']}"
                            )
                            st.write(
                                f"**Mode / port:** {shipment_data['shipping_mode']} · "
                                f"{shipment_data['port_of_loading']}"
                            )
                            st.write(
                                f"**Delivery terms:** {shipment_data['incoterm']} · "
                                f"**GST / LUT:** {shipment_data['export_tax_treatment']}"
                            )

                    st.dataframe(
                        [
                            {
                                "SKU": item["sku"],
                                "Description": item["name"],
                                "Category / subcategory": (
                                    f"{item['category']} / {item['subcategory']}"
                                ),
                                "HSN code": item["hs_code"],
                                "Units": item["quantity"],
                                "Unit value (USD)": item["unit_value_usd"],
                            }
                            for item in shipment_data["items"]
                        ],
                        hide_index=True,
                        width="stretch",
                        alt="Reviewed items in the new export shipment",
                    )
                    st.warning(
                        "All costs and insurance are indicative demo estimates. Verify "
                        "customs, tax, classification, and cover before dispatch."
                    )
                    previous, _, create = st.columns([1, 3, 1.2])
                    with previous:
                        if st.button("← Previous", key="wizard_back_to_details"):
                            st.session_state.shipment_flow_step = 3
                            st.rerun()
                    with create:
                        if st.button(
                            "Create Shipment",
                            type="primary",
                            key="wizard_create_shipment",
                            width="stretch",
                        ):
                            now = datetime.now(timezone.utc).isoformat(timespec="minutes")
                            shipment = {
                                **shipment_data,
                                "shipment_id": (
                                    f"MER-{datetime.now():%y%m%d}-{uuid4().hex[:6].upper()}"
                                ),
                                "seller_id": seller["seller_id"],
                                "created_at": now,
                                "updated_at": now,
                                "status": "Pickup scheduled",
                                "pickup_slot": shipment_data["pickup_time"] + " IST",
                                "category": shipment_data["items"][0]["category"],
                                "subcategory": shipment_data["items"][0]["subcategory"],
                                "seller_reference": draft["seller_reference"],
                                "tracking_number": "",
                            }
                            save_shipment(shipment)
                            active_draft_id = st.session_state.get(
                                "active_shipment_draft_id"
                            )
                            if active_draft_id:
                                delete_shipment_draft(
                                    active_draft_id, seller["seller_id"]
                                )
                            st.session_state.active_shipment_draft_id = None
                            st.session_state.loaded_shipment_draft_id = None
                            st.session_state.shipment_flow_active = False
                            st.session_state.active_shipment_id = shipment["shipment_id"]
                            st.session_state.documents_selected_shipment = shipment[
                                "shipment_id"
                            ]
                            st.session_state.shipment_info_dialog_id = shipment[
                                "shipment_id"
                            ]
                            st.session_state.shipment_flow_step = 1
                            st.session_state.shipment_form_version += 1
                            st.session_state.shipment_working_data = {}
                            st.session_state.shipment_selected_items = {
                                item["sku"]: 0 for item in st.session_state.catalog
                            }
                            st.session_state.last_created_shipment_id = shipment[
                                "shipment_id"
                            ]
                            st.session_state.shipment_success_message = (
                                f"Shipment {shipment['shipment_id']} created. "
                                "Your pickup receipt is ready."
                            )
                            st.switch_page("app_pages/shipment_documents.py")

                if step in (2, 3, 4):
                    st.caption("Use Previous to return to the prior step without losing your entries.")


with wip_tab:
    _render_wip_shipments(saved_drafts)

with scheduled_tab:
    st.markdown("### Scheduled for pick-up")
    _render_shipment_status(pickup_scheduled_shipments, "Scheduled for pick-up")

with transit_tab:
    st.markdown("### In-transit shipments")
    success_message = st.session_state.get("shipment_success_message")
    if success_message:
        with st.container(border=True):
            st.success(success_message)
            st.write("Your pickup receipt is ready in Shipment information.")
            st.button(
                "Start another shipment",
                key="start_another_shipment",
                type="primary",
                on_click=_start_shipment_flow,
            )
    _render_shipment_status(in_transit_shipments, "In-transit")

with closed_tab:
    st.markdown("### Closed shipments")
    _render_shipment_status(closed_shipments, "Closed")

_save_active_draft_snapshot(seller, draft)
