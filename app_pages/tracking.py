import streamlit as st

from portal import TRACKING_STAGES, load_shipments

SHORT_STAGES = ["Created", "Pickup", "Export", "Transit", "US entry", "Delivered"]
STATUS_COLORS = {
    "Closed": "green",
    "In transit": "blue",
    "Pickup scheduled": "orange",
}


def _open_tracking_dialog(shipment_id):
    st.session_state.tracking_dialog_id = shipment_id


def _close_tracking_dialog():
    st.session_state.tracking_dialog_id = None


def _toggle_milestones(key):
    st.session_state[key] = not st.session_state[key]


def _select_tracking_milestone(key, index):
    st.session_state[key] = index


def _open_shipment_information(shipment_id):
    st.session_state.active_shipment_id = shipment_id
    st.session_state.documents_selected_shipment = shipment_id
    st.session_state.shipment_info_dialog_id = shipment_id
    st.session_state.tracking_dialog_id = None
    st.switch_page("app_pages/shipment_documents.py")


@st.dialog(
    "Shipment tracking",
    width="large",
    position="right",
    on_dismiss=_close_tracking_dialog,
)
def _show_tracking_details(shipment):
    shipment_id = shipment["shipment_id"]
    stage_index = max(
        0,
        min(
            int(
                shipment.get(
                    "milestone_index",
                    1 if shipment["status"] == "Pickup scheduled" else 0,
                )
            ),
            len(TRACKING_STAGES) - 1,
        ),
    )
    st.markdown(f"### `{shipment_id}`")
    st.badge(
        f"Current status · {shipment['status']}",
        color=STATUS_COLORS.get(shipment["status"], "gray"),
    )
    st.progress(
        stage_index / (len(TRACKING_STAGES) - 1),
        text=(
            f"Current milestone · "
            f"{shipment.get('current_milestone', TRACKING_STAGES[stage_index])}"
        ),
    )
    if shipment.get("tracking_number"):
        st.caption(
            f"Demo tracking reference · {shipment['tracking_number']} · "
            "not a live carrier scan."
        )
    st.write(
        f"**Route:** {shipment['pickup_city']}, India → "
        f"{shipment['destination_label']}"
    )
    st.write(f"**Pick up:** {shipment['pickup_date']} · {shipment['pickup_slot']}")
    st.write(
        f"**Cargo:** {sum(item['quantity'] for item in shipment['items'])} units · "
        f"{shipment['estimate']['chargeable_weight_kg']:.2f} kg"
    )
    milestones_key = f"tracking_milestones_open_{shipment_id}"
    if st.session_state.pop("tracking_show_milestones", False):
        st.session_state[milestones_key] = True
    st.session_state.setdefault(milestones_key, False)
    st.button(
        "Track shipment"
        if not st.session_state[milestones_key]
        else "Hide tracking milestones",
        key=f"track_shipment_link_{shipment_id}",
        type="tertiary",
        icon=":material/route:",
        on_click=_toggle_milestones,
        args=(milestones_key,),
    )
    if st.session_state[milestones_key]:
        st.markdown("#### Shipment milestones")
        selected_milestone_key = f"tracking_milestone_{shipment_id}"
        st.session_state.setdefault(selected_milestone_key, stage_index)
        milestone_columns = st.columns(len(TRACKING_STAGES), gap="small")
        for index, (column, short_label, stage) in enumerate(
            zip(milestone_columns, SHORT_STAGES, TRACKING_STAGES)
        ):
            marker = "✓" if index < stage_index else "●" if index == stage_index else "○"
            with column:
                st.button(
                    f"{marker} {short_label}",
                    key=f"milestone_select_{shipment_id}_{index}",
                    type=(
                        "primary"
                        if st.session_state[selected_milestone_key] == index
                        else "secondary"
                    ),
                    width="stretch",
                    help=stage,
                    on_click=_select_tracking_milestone,
                    args=(selected_milestone_key, index),
                )
        selected_milestone = st.session_state[selected_milestone_key]
        milestone_events = shipment.get("milestone_events", {})
        milestone_event = milestone_events.get(
            str(selected_milestone),
            milestone_events.get(TRACKING_STAGES[selected_milestone]),
        )
        if milestone_event:
            event_date = milestone_event.get("timestamp", "Date not recorded")
            event_status = milestone_event.get("status", "Recorded")
        elif selected_milestone == 0:
            event_date = shipment.get("created_at", "Date not recorded")
            event_status = "Shipment booked"
        elif selected_milestone == stage_index:
            event_date = shipment.get(
                "updated_at",
                shipment.get("pickup_date", "Date not recorded"),
            )
            event_status = "Current milestone"
        elif selected_milestone < stage_index:
            event_date = "Date not recorded in this demo shipment"
            event_status = "Completed"
        else:
            event_date = "Pending"
            event_status = "Upcoming"
        event_text = (
            f"**{TRACKING_STAGES[selected_milestone]}** · "
            f"{event_status} · {event_date}"
        )
        if selected_milestone < stage_index:
            st.success(event_text)
        elif selected_milestone == stage_index:
            st.info(event_text)
        else:
            st.caption(event_text)
    st.markdown("#### Cargo details")
    st.dataframe(
        [
            {
                "SKU": item["sku"],
                "Product": item["name"],
                "Units": item["quantity"],
                "Category": item["category"],
                "HSN code": item["hs_code"],
            }
            for item in shipment["items"]
        ],
        hide_index=True,
        width="stretch",
        alt="Products included in the selected shipment",
    )
    with st.container(border=True):
        st.markdown("#### Booking summary")
        st.write(f"**Consignee:** {shipment['consignee_name']}")
        st.write(
            f"**Packages:** {shipment['package_count']} "
            f"{shipment['package_type'].lower()}"
        )
        st.write(
            f"**Approx. shipment cost:** "
            f"${shipment['estimate']['estimated_total_usd']:,.2f} USD"
        )
        if shipment.get("payment_status"):
            st.write(f"**Payment:** {shipment['payment_status']}")
        st.write(f"**Created:** {shipment['created_at']}")
        st.button(
            "Shipment details",
            key=f"tracking_docs_{shipment_id}",
            type="tertiary",
            icon=":material/open_in_new:",
            on_click=_open_shipment_information,
            args=(shipment_id,),
        )


if not st.session_state.onboarding_complete:
    st.warning("Complete seller onboarding to view shipment tracking.")
    st.stop()

seller = st.session_state.seller
shipments = load_shipments(seller["seller_id"])
if not shipments:
    st.info("No shipments are available yet. Create a shipment to see it here.")
    st.stop()

status_options = ["All statuses", *sorted({item["status"] for item in shipments})]
destination_options = [
    "All destinations",
    *sorted({item["destination_label"] for item in shipments}),
]
with st.container(key="tracking_shipment_filters", border=True):
    search_col, destination_col, status_col = st.columns(
        3,
        vertical_alignment="bottom",
    )
    with search_col:
        search_query = st.text_input(
            "Search by shipment",
            placeholder="Shipment ID, consignee, or reference",
            key="tracking_shipment_search",
        )
    with destination_col:
        destination_filter = st.selectbox(
            "Destination warehouse",
            destination_options,
            key="tracking_destination_filter",
        )
    with status_col:
        status_filter = st.segmented_control(
            "Status",
            status_options,
            default="All statuses",
            key="tracking_status_filter",
        )
query = search_query.strip().casefold()
filtered_shipments = [
    shipment
    for shipment in shipments
    if (status_filter in (None, "All statuses") or shipment["status"] == status_filter)
    and (
        destination_filter == "All destinations"
        or shipment["destination_label"] == destination_filter
    )
    and (
        not query
        or query
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
    "Select a shipment ID to view its tracking details."
)
with st.container(key="tracking_shipment_rows", gap="small"):
    column_widths = [2.2, 1.4, 1.7, 1, 1.5, 1.3]
    header_columns = st.columns(column_widths)
    for column, label in zip(
        header_columns,
        (
            "Shipment ID",
            "Status",
            "Destination",
            "Pick-up date",
            "Current milestone",
            "Tracking number",
        ),
    ):
        column.markdown(f"**{label}**")

    for index, shipment in enumerate(filtered_shipments):
        with st.container(key=f"tracking_row_{index}"):
            columns = st.columns(column_widths)
            columns[0].button(
                shipment["shipment_id"],
                key=f"open_tracking_{shipment['shipment_id']}",
                type="tertiary",
                width="stretch",
                on_click=_open_tracking_dialog,
                args=(shipment["shipment_id"],),
            )
            columns[1].write(shipment["status"])
            columns[2].write(shipment["destination_label"])
            columns[3].write(shipment["pickup_date"])
            columns[4].write(
                shipment.get("current_milestone", "Shipment created")
            )
            columns[5].write(shipment.get("tracking_number") or "Not assigned")

dialog_id = st.session_state.get("tracking_dialog_id")
dialog_shipment = next(
    (item for item in shipments if item["shipment_id"] == dialog_id),
    None,
)
if dialog_shipment:
    _show_tracking_details(dialog_shipment)
