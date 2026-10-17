import streamlit as st

st.markdown("### Seller support")
st.caption("Mock support landing page for the seller export workflow.")

with st.container(border=True):
    st.markdown("#### Shipment operations desk")
    st.write("Typical response window: one business day · Monday–Friday, 09:00–18:00 IST")
    st.write("Email: seller-support@example.com")
    st.write("Phone: +91 22 4000 2048")
    st.link_button(
        "Email seller support",
        "mailto:seller-support@example.com?subject=AMAZON%20EXPORT%20seller%20support",
        icon=":material/mail:",
    )

with st.container(border=True):
    st.markdown("#### What to include in a request")
    st.write(
        "Include your seller ID, shipment ID (if applicable), destination warehouse, "
        "and a short description. Do not email PAN, bank account details, or identity "
        "documents through this demo support channel."
    )
    st.info(
        "This is a demonstration contact page. It does not submit a real support ticket."
    )
