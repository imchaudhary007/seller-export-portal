# AMAZON EXPORT

A Streamlit prototype for Indian sellers preparing export shipments to US
consolidation warehouses. It includes seller onboarding, a sample Seller Central
catalog, shipment estimates, printable challan and pickup receipt drafts, and a
shipment tracking workspace.

## Run on Windows

The project has an isolated `.venv` environment. From this folder, run:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

Or run it without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

To recreate the environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Mock walkthrough

The four workflow links stay fixed below the app header while page content
scrolls in a single main pane.

1. Open **Seller profile**. **Seller details** is the default tab and includes a
   profile PDF download at the bottom. Switch to **Update profile** to review
   and upload required documents; each file can be up to 20 MB. Documents
   include IEC, GST, PAN, bank and pickup details, LUT, RCMC, and ICEGATE
   profile documentation.
2. Open **Export Shipment**. The compact boxed status/count summary sits
   immediately below the page heading, which serves as its section title; it
   uses only part of the page width. The
   five tabs are **New Shipment**, **Pending Completion**, **Scheduled for pick-up**,
   **In-transit**, and **Closed**. Incomplete orders can be resumed or deleted
   in the **Pending Completion** tab. The
   **New Shipment** tab starts with a CTA; start the workflow to import a sample
   Seller Central order and proceed through four steps: select items, enter
   pickup and destination details, add product compliance documents and
   shipment/package details, then review and create. A successful booking
   opens its shipment information directly. Incomplete work is autosaved.
   Pickup must be at least 36 hours ahead in India time.
3. Open **Shipment information**. The shipment ID/consignee/reference search,
   destination warehouse dropdown, and status buttons sit in three columns
   inside one filter box. The table includes seller reference and shipment
   creation date. Click a shipment ID to open its side
   drawer with route, cargo, and estimates. Download the export challan or
   pickup receipt from the top-right of the drawer.
4. Open **Tracking**. Search, destination warehouse, and status use the same
   three-column filter box. Click a shipment ID to open its tracking side drawer.
   Its status is color-coded; use **Track shipment** to reveal the horizontal
   milestones. Select a milestone to see its available event date and status.
   Use **Shipment details** to open this shipment directly in the Shipment
   Information drawer. Returning to Tracking opens the default shipment list
   instead of reopening the previous shipment.

The seeded seller includes two in-transit shipments, two closed shipments with
payment marked paid, and a separate sample Seller Central order ready to create.
All records are mock data for interviewer walkthroughs. See
the workflow PDFs for visual mocks:

- [`New shipment creation workflow`](docs/new-shipment-creation-workflow.pdf)
- [`Shipment information and tracking workflow`](docs/shipment-information-and-tracking-workflow.pdf)
- [`Help centre and seller support workflow`](docs/help-centre-and-seller-support-workflow.pdf)
- [`All workflows (combined)`](docs/shipment-user-journey.pdf)

## Publish on GitHub and Streamlit Community Cloud

1. Create an empty GitHub repository. Choose **Public** if recruiters should be
   able to browse the source; choose **Private** if you only want to share the
   deployed app URL. Do not add a README or license during creation because
   this project already has a README.
2. From this project folder, initialize Git, commit the project, and push it to
   the new repository. Replace `<username>` and `<repository>` with your values:

   ```powershell
   git init -b main
   git add .
   git status --short
   git commit -m "Prepare seller export portal demo"
   git remote add origin https://github.com/<username>/<repository>.git
   git push -u origin main
   ```

   Confirm `.venv`, the local SQLite database, temporary screenshots, and
   `.streamlit/secrets.toml` are not staged. The `.gitignore` excludes them.
3. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) using the
   GitHub account that can access the repository. Select **Create app**, then
   choose the repository, `main` branch, and `streamlit_app.py` as the entry
   point. Select **Deploy**.
4. Wait for the build to finish, open the generated `*.streamlit.app` URL, and
   test the onboarding, shipment creation, filters, tracking, and support pages.
   Share that URL with the recruiter. The app does not require Streamlit
   secrets.
5. For later changes, push commits to the selected GitHub branch; Community
   Cloud deploys updates from that branch.

This is a public-facing demo with no authentication. Keep real seller documents
and personal or commercial data out of it. Its SQLite store is demo-only and
is not a production persistence service.

## Prototype boundaries

- The seller login, seller ID, catalog import, warehouse locations, carrier
  milestones, freight tariffs, insurance rates, and support contacts are
  demonstration data.
  There is no live Seller Central, identity, carrier, customs, warehouse, or
  insurer integration.
- Sample documents and seller fields are mock data. Each new upload is limited
  to 20 MB; files are not parsed by OCR or retained by a backend.
  IEC/GSTIN values stay in the current Streamlit session. Use secure
  authentication, real document extraction, and encrypted, access-controlled
  document storage before handling real seller records.
- Shipment records are saved locally in `data\seller_portal.db` for this demo.
  Do not expose the prototype or its local database as a production service.
- Estimates are illustrative, not binding quotes. US duties, taxes, and
  destination charges are excluded. The challan is an operational draft, not a
  government-issued shipping bill, tax invoice, or customs declaration. The
  exporter and customs broker must verify classification, origin, tax treatment,
  permits, and filing requirements; insurance requires written confirmation.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
