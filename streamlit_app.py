import streamlit as st

from portal import (
    DEFAULT_CATALOG,
    DEMO_DOCUMENTS,
    DEMO_SELLER,
    ensure_database,
    seed_demo_shipments,
)

st.set_page_config(
    page_title="AMAZON EXPORT",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(
    """
    <style>
    [data-testid="stMainBlockContainer"] {
        max-width: 1680px;
        padding: 0.35rem 2rem 2rem;
    }
    [data-testid="stMainBlockContainer"] h1,
    [data-testid="stMainBlockContainer"] h2 {
        background: linear-gradient(95deg, #123b49 0%, #087f72 56%, #e78328 100%);
        background-clip: text;
        -webkit-background-clip: text;
        color: transparent;
        letter-spacing: -0.035em;
    }
    [data-testid="stLayoutWrapper"]:has(> .st-key-workflow_navigation) {
        position: sticky;
        top: 3.75rem;
        z-index: 1000;
    }
    .st-key-workflow_navigation {
        margin: 0 0 1.5rem;
        padding: 0.35rem;
        border: 1px solid #d8e5e1;
        border-radius: 18px;
        background: linear-gradient(100deg, #f0f7f4 0%, #ffffff 50%, #fff6e9 100%);
        box-shadow: 0 5px 20px rgba(18, 59, 73, 0.07);
    }
    .st-key-workflow_navigation [data-testid="stPageLink"] a {
        min-height: 3.4rem;
        padding: 0.7rem 0.8rem;
        border-radius: 12px;
        font-weight: 700;
        font-size: 0.98rem;
        color: #17363b;
        transition: background-color 160ms ease, color 160ms ease;
    }
    .st-key-workflow_navigation [data-testid="stPageLink"] a:hover {
        color: #087f72;
        background-color: #e1f1eb;
    }
    .st-key-workflow_navigation a[href$="/new_shipment"] {
        background-color: #eaf3fb;
    }
    .st-key-workflow_navigation a[href$="/shipment_documents"] {
        background-color: #f5effa;
    }
    .st-key-workflow_navigation a[href$="/tracking"] {
        background-color: #fff2e3;
    }
    .st-key-shipment_workspace [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0.65rem 0.9rem;
    }
    .st-key-shipment_summary_table [class*="shipment_summary_row_"] {
        margin: 0;
        padding: 0.05rem 0.55rem;
        border: 0;
        background: #ffffff;
    }
    .st-key-shipment_summary_table {
        width: min(58%, 640px);
        margin: 0 0 1rem;
    }
    .st-key-shipment_summary_table [class*="shipment_summary_row_"] + [class*="shipment_summary_row_"] {
        border-top: 1px solid #d7dcdf;
    }
    .st-key-shipment_summary_table p {
        color: #171a1d;
    }
    .st-key-shipment_information_rows [class*="shipment_info_row_"],
    .st-key-tracking_shipment_rows [class*="tracking_row_"] {
        padding: 0.2rem 0;
        border-bottom: 1px solid #e1e9e7;
    }
    .st-key-shipment_information_rows [data-testid="stBaseButton-tertiary"],
    .st-key-tracking_shipment_rows [data-testid="stBaseButton-tertiary"] {
        justify-content: flex-start;
        padding: 0;
    }
    .st-key-shipment_information_rows [data-testid="stBaseButton-tertiary"] p,
    .st-key-tracking_shipment_rows [data-testid="stBaseButton-tertiary"] p {
        width: 100%;
        text-align: left;
        color: #087f72;
        font-weight: 700;
        text-decoration: underline;
    }
    .st-key-export_shipment_tabs [role="tablist"] {
        gap: 0.45rem;
        border-bottom: 2px solid #a9c8bf;
    }
    .st-key-export_shipment_tabs [role="tablist"] [role="tab"] {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 3.35rem;
        padding: 0.65rem 1rem;
        border: 1px solid #b8ccc6;
        border-bottom: 0;
        border-radius: 12px 12px 0 0;
        background: #edf4f1;
        color: #25443e;
        font-size: 0.98rem;
        font-weight: 750;
    }
    .st-key-export_shipment_tabs [role="tablist"] [role="tab"][aria-selected="true"] {
        border-color: #087f72;
        background: #087f72;
        color: #ffffff;
        box-shadow: 0 -2px 0 #087f72;
    }
    .st-key-export_shipment_tabs [role="tablist"] [role="tab"] p {
        font-size: 0.98rem;
        font-weight: 750;
    }
    .st-key-seller_profile_tabs [role="tablist"] {
        gap: 0.6rem;
        border-bottom: 2px solid #a9c8bf;
    }
    .st-key-seller_profile_tabs [role="tablist"] [role="tab"] {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 3.5rem;
        padding: 0.7rem 1.35rem;
        border: 1px solid #b8ccc6;
        border-bottom: 0;
        border-radius: 12px 12px 0 0;
        background: #edf4f1;
        color: #25443e;
        font-size: 1.05rem;
        font-weight: 750;
    }
    .st-key-seller_profile_tabs [role="tablist"] [role="tab"][aria-selected="true"] {
        border-color: #087f72;
        background: #087f72;
        color: #ffffff;
        box-shadow: 0 -2px 0 #087f72;
    }
    .st-key-seller_profile_tabs [role="tablist"] [role="tab"] p {
        font-size: 1.05rem;
        font-weight: 750;
    }
    .st-key-document_row_0 [data-testid="stFileUploaderDropzone"],
    .st-key-document_row_1 [data-testid="stFileUploaderDropzone"],
    .st-key-document_row_2 [data-testid="stFileUploaderDropzone"],
    .st-key-document_row_3 [data-testid="stFileUploaderDropzone"],
    .st-key-document_row_4 [data-testid="stFileUploaderDropzone"] {
        min-height: 3.2rem;
        padding: 0.3rem 0.6rem;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid #d8e5e1;
    }
    </style>
    """
)

ensure_database()
st.session_state.setdefault("seller", DEMO_SELLER.copy())
if not st.session_state.get("demo_profile_seeded"):
    st.session_state.seller = {**DEMO_SELLER, "documents_received": DEMO_DOCUMENTS}
    st.session_state.onboarding_complete = True
    st.session_state.demo_profile_seeded = True
st.session_state.setdefault("onboarding_complete", True)
st.session_state.setdefault("catalog", [item.copy() for item in DEFAULT_CATALOG])
st.session_state.setdefault("active_shipment_id", None)
st.session_state.setdefault("editing_shipment", None)
st.session_state.setdefault("onboarding_editing", False)
seed_demo_shipments(st.session_state.seller)

profile_page = st.Page(
    "app_pages/onboarding.py",
    title="Seller profile",
    icon=":material/person:",
)
shipment_page = st.Page(
    "app_pages/new_shipment.py",
    title="Export Shipment",
    icon=":material/inventory_2:",
)
documents_page = st.Page(
    "app_pages/shipment_documents.py",
    title="Shipment information",
    icon=":material/description:",
)
tracking_page = st.Page(
    "app_pages/tracking.py",
    title="Tracking",
    icon=":material/local_shipping:",
)
help_page = st.Page(
    "app_pages/help_centre.py",
    title="Help centre",
    icon=":material/help:",
    visibility="hidden",
)
support_page = st.Page(
    "app_pages/seller_support.py",
    title="Seller support",
    icon=":material/support_agent:",
    visibility="hidden",
)

workflow_pages = [
    profile_page,
    shipment_page,
    documents_page,
    tracking_page,
]

page = st.navigation(
    [
        *workflow_pages,
        help_page,
        support_page,
    ],
    position="hidden",
)

with st.sidebar:
    st.markdown("## AMAZON EXPORT")
    st.caption("INDIA → UNITED STATES")
    st.divider()
    st.markdown(f"**{st.session_state.seller['business_name']}**")
    st.caption(f"Seller ID · `{st.session_state.seller['seller_id']}`")
    st.caption(f"Last login · {st.session_state.seller.get('last_login', 'Demo session')}")
    st.success("Demo seller profile ready", icon=":material/task_alt:")
    st.divider()
    st.page_link(help_page, label="Help centre", icon=":material/help:")
    st.page_link(support_page, label="Seller support", icon=":material/support_agent:")
    st.link_button(
        "Open Seller Central",
        "https://sellercentral.amazon.in",
        icon=":material/open_in_new:",
        width="stretch",
    )
    st.divider()
    st.caption("Seller Central, shipment milestones, and profile documents are mock data.")

with st.container(key="workflow_navigation"):
    columns = st.columns(len(workflow_pages), gap="small")
    for column, workflow_page in zip(columns, workflow_pages):
        with column:
            st.page_link(
                workflow_page,
                label=workflow_page.title,
                icon=workflow_page.icon,
                width="stretch",
            )

current_page_title = page.title
if (
    current_page_title == "Export Shipment"
    and st.session_state.get("last_workflow_page") != current_page_title
):
    st.session_state.export_shipment_tabs = "New Shipment"
    st.session_state.shipment_flow_active = False
st.session_state.last_workflow_page = current_page_title

if page.title != "Export Shipment":
    st.title("Seller Profile" if page.title == "Seller profile" else page.title)
page.run()
