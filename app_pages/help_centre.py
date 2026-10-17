import streamlit as st

st.markdown("### Seller help centre")
st.caption("Quick answers for preparing your India-to-US export shipment mock.")

faqs = [
    (
        "Which documents should I keep ready?",
        "IEC/exporter registration, GST registration, PAN, bank confirmation, "
        "and pickup address proof are shown in the onboarding checklist. Requirements "
        "vary by goods and filing route; confirm with your customs broker.",
    ),
    (
        "How does the pickup booking work?",
        "Select a pickup date and time at least 36 hours in advance. The mock uses "
        "your saved seller pickup address and the contact details supplied on the "
        "shipment page. Live carrier assignment is not connected.",
    ),
    (
        "How are volumetric weight and insurance estimated?",
        "Volumetric weight is estimated from package dimensions and count. Chargeable "
        "weight uses the greater of gross actual weight and volumetric weight. The "
        "illustrative insurance estimate is 0.8% of seller-declared shipment value, "
        "subject to a $12 minimum.",
    ),
    (
        "Can I use this challan to file customs?",
        "No. The generated challan is an operational mock document. The exporter and "
        "customs broker must verify classification, invoice values, origin, tax "
        "treatment, permits, declarations, and filing requirements.",
    ),
    (
        "Are Seller Central orders and tracking live?",
        "No. The orders, product catalogue, tracking IDs, and shipment milestones "
        "are seeded mock data for a product walkthrough.",
    ),
]
for question, answer in faqs:
    with st.expander(question):
        st.write(answer)
