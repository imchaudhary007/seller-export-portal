import base64

import streamlit as st

from portal import load_shipments, make_document_html


def _open_shipment_dialog(shipment_id):
    st.session_state.shipment_info_dialog_id = shipment_id


def _close_shipment_dialog():
    st.session_state.shipment_info_dialog_id = None


@st.dialog(
    "Shipment information",
    width="large",
    position="right",
    on_dismiss=_close_shipment_dialog,
)
def _show_shipment_details(shipment, seller):
    shipment_heading, challan_column, receipt_column = st.columns(
        [2.2, 1.1, 1.1],
        vertical_alignment="center",
    )
    shipment_heading.markdown(f"### `{shipment['shipment_id']}`")
    challan_data = make_document_html(shipment, seller, "challan")
    receipt_data = make_document_html(shipment, seller, "receipt")
    with challan_column:
        st.download_button(
            "Export challan",
            data=challan_data,
            file_name=f"{shipment['shipment_id']}-export-challan.html",
            mime="text/html",
            type="primary",
            width="stretch",
        )
    with receipt_column:
        st.download_button(
            "Pickup receipt",
            data=receipt_data,
            file_name=f"{shipment['shipment_id']}-pickup-receipt.html",
            mime="text/html",
            type="primary",
            width="stretch",
        )
    st.badge(
        shipment["status"],
        color={
            "Closed": "green",
            "In transit": "blue",
            "Pickup scheduled": "orange",
        }.get(shipment["status"], "gray"),
    )
    summary_columns = st.columns(3)
    summary_columns[0].metric(
        "Units",
        sum(item["quantity"] for item in shipment["items"]),
    )
    summary_columns[1].metric(
        "Chargeable weight",
        f"{shipment['estimate']['chargeable_weight_kg']:.2f} kg",
    )
    summary_columns[2].metric(
        "Approx. shipment cost",
        f"${shipment['estimate']['estimated_total_usd']:,.2f}",
    )
    st.write(f"**Route:** Mumbai, India → {shipment['destination_label']}")
    st.write(f"**Pickup address:** {shipment['pickup_address']}")
    st.write(
        f"**Pickup:** {shipment['pickup_date']} · "
        f"{shipment['pickup_slot']} · {shipment['pickup_contact']}"
    )
    st.write(f"**Consignee:** {shipment['consignee_name']}")
    st.write(f"**Destination address:** {shipment['consignee_address']}")
    st.write(f"**Seller reference:** {shipment.get('seller_reference') or '—'}")
    st.write(f"**Created:** {shipment['created_at']}")
    st.write(f"**Category:** {shipment['category']} · {shipment['subcategory']}")
    st.write(
        f"**Packages:** {shipment['package_count']} "
        f"{shipment['package_type'].lower()} · "
        f"{shipment['length_cm']} × {shipment['width_cm']} × "
        f"{shipment['height_cm']} cm"
    )
    st.write(f"**Tracking:** {shipment.get('tracking_number') or 'Not assigned'}")
    if shipment.get("payment_status"):
        st.write(f"**Payment:** {shipment['payment_status']}")
    st.markdown("#### Cargo")
    st.dataframe(
        [
            {
                "SKU": item["sku"],
                "Product": item["name"],
                "Category": item["category"],
                "HSN code": item["hs_code"],
                "Units": item["quantity"],
            }
            for item in shipment["items"]
        ],
        hide_index=True,
        width="stretch",
        alt="Products and quantities in the selected export shipment",
    )
    for index, document in enumerate(shipment.get("compliance_documents", [])):
        st.download_button(
            f"Download {document['filename']}",
            data=base64.b64decode(document["content_base64"]),
            file_name=document["filename"],
            mime=document.get("mime_type", "application/octet-stream"),
            type="primary",
            key=f"compliance_download_{shipment['shipment_id']}_{index}",
        )
    st.warning(
        "Operational mock only; confirm shipment data, taxes, classification, "
        "duties, and insurance with your customs broker and insurer.",
        title="Review before dispatch",
    )


if not st.session_state.onboarding_complete:
    st.warning("Complete seller onboarding before viewing shipment information.")
    st.stop()

seller = st.session_state.seller
shipments = load_shipments(seller["seller_id"])
if not shipments:
    st.info("Create a shipment to see its details and paperwork here.")
    st.stop()

status_options = ["All statuses", *sorted({item["status"] for item in shipments})]
destination_options = [
    "All destinations",
    *sorted({item["destination_label"] for item in shipments}),
]
with st.container(key="shipment_information_filters", border=True):
    search_col, destination_col, status_col = st.columns(3, vertical_alignment="bottom")
    with search_col:
        search_query = st.text_input(
            "Search by shipment",
            placeholder="Shipment ID, consignee, or reference",
            key="documents_shipment_search",
        )
    with destination_col:
        selected_destination_filter = st.selectbox(
            "Destination warehouse",
            destination_options,
            key="documents_destination_filter",
        )
    with status_col:
        selected_status_filter = st.segmented_control(
            "Status",
            status_options,
            default="All statuses",
            key="documents_status_filter",
        )

search_term = search_query.strip().casefold()
filtered_shipments = [
    shipment
    for shipment in shipments
    if (
        selected_status_filter in (None, "All statuses")
        or shipment["status"] == selected_status_filter
    )
    and (
        selected_destination_filter == "All destinations"
        or shipment["destination_label"] == selected_destination_filter
    )
    and (
        not search_term
        or search_term
        in " ".join(
            str(shipment.get(field, ""))
            for field in (
                "shipment_id",
                "status",
                "destination_label",
                "consignee_name",
                "seller_reference",
                "tracking_number",
            )
        ).casefold()
    )
]

if not filtered_shipments:
    st.info("No shipments match that search.")
    st.stop()

st.caption(
    "Select a shipment ID to view its full details."
)
with st.container(key="shipment_information_rows", gap="small"):
    column_widths = [2, 1.15, 1.6, 0.85, 0.5, 1.35, 0.95]
    header_columns = st.columns(column_widths)
    for column, label in zip(
        header_columns,
        (
            "Shipment ID",
            "Status",
            "Destination",
            "Pick-up date",
            "Units",
            "Seller reference",
            "Created date",
        ),
    ):
        column.markdown(f"**{label}**")

    for index, shipment in enumerate(filtered_shipments):
        with st.container(key=f"shipment_info_row_{index}"):
            columns = st.columns(column_widths)
            columns[0].button(
                shipment["shipment_id"],
                key=f"open_shipment_{shipment['shipment_id']}",
                type="tertiary",
                width="stretch",
                on_click=_open_shipment_dialog,
                args=(shipment["shipment_id"],),
            )
            columns[1].write(shipment["status"])
            columns[2].write(shipment["destination_label"])
            columns[3].write(shipment["pickup_date"])
            columns[4].write(sum(item["quantity"] for item in shipment["items"]))
            columns[5].write(shipment.get("seller_reference") or "—")
            columns[6].write(
                str(shipment.get("created_at") or "—").split("T", 1)[0]
            )

dialog_id = st.session_state.get("shipment_info_dialog_id")
dialog_shipment = next(
    (item for item in shipments if item["shipment_id"] == dialog_id),
    None,
)
if dialog_shipment:
    st.session_state.active_shipment_id = dialog_id
    st.session_state.documents_selected_shipment = dialog_id
    _show_shipment_details(dialog_shipment, seller)
