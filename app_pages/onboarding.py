import streamlit as st

from portal import (
    DEMO_DOCUMENTS,
    DEMO_SELLER,
    REQUIRED_DOCUMENTS,
    make_seller_profile_pdf,
)

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def _cancel_profile_update():
    st.session_state.seller_profile_tabs = "Seller details"


seller = st.session_state.seller
for profile_field in ("lut_number", "rcmc", "icegate_profile"):
    seller.setdefault(profile_field, DEMO_SELLER[profile_field])
if seller.get("profile_source") == DEMO_SELLER["profile_source"]:
    documents = seller.get("documents_received", DEMO_DOCUMENTS)
    existing_types = {document["type"] for document in documents}
    seller["documents_received"] = [
        *documents,
        *[
            document
            for document in DEMO_DOCUMENTS
            if document["type"] not in existing_types
        ],
    ]
version = st.session_state.setdefault("onboarding_upload_version", 0)
existing_documents = {
    document["type"]: document
    for document in seller.get("documents_received", DEMO_DOCUMENTS)
}

details_tab, update_tab = st.tabs(
    ["Seller details", "Update profile"],
    key="seller_profile_tabs",
    on_change="rerun",
)
with details_tab:
    st.markdown("### Seller details")
    with st.container(border=True):
        profile_left, profile_right = st.columns(2)
        with profile_left:
            st.markdown(f"**Registered business name**  \n{seller['business_name']}")
            st.markdown(f"**Seller ID**  \n`{seller['seller_id']}`")
            st.markdown(f"**Importer Exporter Code (IEC)**  \n`{seller.get('iec', '—')}`")
            st.markdown(f"**PAN**  \n`{seller.get('pan', '—')}`")
            st.markdown(f"**GSTIN**  \n`{seller.get('gstin', '—')}`")
            st.markdown(f"**LUT number**  \n`{seller.get('lut_number', '—')}`")
            st.markdown(f"**RCMC**  \n`{seller.get('rcmc', '—')}`")
            st.markdown(f"**Registered address**  \n{seller.get('registered_address', '—')}")
        with profile_right:
            st.markdown(f"**Pickup address**  \n{seller.get('pickup_address', '—')}")
            st.markdown(
                f"**Pickup contact**  \n{seller.get('pickup_contact_name', '—')} · "
                f"{seller.get('pickup_contact_phone', '—')}"
            )
            st.markdown(f"**Bank**  \n{seller.get('bank_name', '—')}")
            st.markdown(f"**Account ending**  \n`{seller.get('bank_account_last4', '—')}`")
            st.markdown(f"**IFSC**  \n`{seller.get('ifsc', '—')}`")
            st.markdown(f"**ICEGATE profile**  \n{seller.get('icegate_profile', '—')}")
            st.markdown(f"**Profile source**  \n{seller.get('profile_source', 'Sample profile')}")

    st.caption(
        "Details are prefilled from the uploaded sample seller documents. "
        "Document extraction is simulated for this demo."
    )
    st.download_button(
        "Download seller profile",
        data=make_seller_profile_pdf(seller),
        file_name=f"{seller['seller_id']}-export-profile.pdf",
        mime="application/pdf",
        type="primary",
        icon=":material/download:",
        width="stretch",
    )
with update_tab:
    st.markdown("### Required documents")
    st.caption(
        "Upload a PDF, JPG, or PNG for each document. Each individual file "
        "must be 20 MB or smaller. Sample checkmarks are seeded mock documents."
    )
    uploaded_documents = dict(existing_documents)
    documents_valid = True
    for index, label in enumerate(REQUIRED_DOCUMENTS):
        with st.container(key=f"document_row_{index}", border=True):
            name_col, file_col, status_col = st.columns(
                [2.4, 3.4, 1],
                vertical_alignment="center",
            )
            name_col.markdown(f"**{label}**")
            uploaded = file_col.file_uploader(
                f"Upload {label}",
                type=sorted(ALLOWED_EXTENSIONS),
                key=f"onboarding_document_{version}_{index}",
                max_upload_size=20,
                label_visibility="collapsed",
            )
            prior_document = existing_documents.get(label)
            if uploaded is None and prior_document:
                status_text = (
                    "Sample"
                    if prior_document.get("source") == "Sample seller profile"
                    else "On file"
                )
                status_col.markdown(f":green[:material/check_circle:] {status_text}")
            elif uploaded is None:
                status_col.markdown(":red[:material/cancel:] Required")
                documents_valid = False
            elif uploaded.size > MAX_DOCUMENT_BYTES:
                status_col.markdown(":red[:material/cancel:] Over 20 MB")
                documents_valid = False
            else:
                uploaded_documents[label] = {
                    "type": label,
                    "filename": uploaded.name,
                    "size_bytes": uploaded.size,
                    "source": "Seller upload",
                    "status": "uploaded",
                }
                status_col.markdown(":green[:material/check_circle:] Uploaded")

    accepted = st.checkbox(
        "I confirm these seller details are accurate.",
        key=f"onboarding_confirmation_{version}",
    )
    cancel_col, save_col = st.columns([1, 1.3])
    cancel_col.button(
        "Cancel",
        key="cancel_profile_update",
        width="stretch",
        on_click=_cancel_profile_update,
    )
    if save_col.button(
        "Save updates",
        type="primary",
        key="save_profile_update",
        width="stretch",
        disabled=not documents_valid,
    ):
        if not accepted:
            st.error("Confirm that the displayed seller details are accurate.")
        else:
            seller["documents_received"] = list(uploaded_documents.values())
            seller["profile_source"] = "Seller submitted"
            st.session_state.seller = seller
            st.session_state.onboarding_complete = True
            st.session_state.onboarding_upload_version = version + 1
            st.session_state.success_message = (
                "Seller profile and documents updated successfully."
            )
            st.rerun()

success_message = st.session_state.pop("success_message", None)
if success_message:
    st.toast(success_message, icon=":material/task_alt:")
