"""Synthetic scope matrix for the sample data (loaded as the tblScopeMatrix query).

Columns: L3 Commodity, Category, Scope Tier, Proposed Route, Lead, Practical solution.
BASE covers the 22 random-sample commodities; SCENARIO covers the scripted scenario commodities
(see docs/scenarios.md). "Laboratory Supplies" and the two "Lab Testing" rows are deliberately
left out so the "not classified" and "ambiguous" scenarios can be tested.
"""

BASE = [
    ('Media Buying - Digital and TV', 'Media', 'B. Co-managed', 'Blanket PO per brand per quarter (or per campaign) against the media agency MSA. No catalogue.', 'Co-managed', '1) Confirm one media agency MSA per country/region and load it in Ariba Contracts. 2) Replace many small POs with one blanket PO per brand per quarter. 3) Reconcile agency invoices to approved estimates. 4) Route direct publisher, social and influencer buys through a guided-buying form linked to the MSA. 5) Schedule an annual media contract-compliance audit.'),
    ('Market Research and Consumer Insights', 'Media', 'B. Co-managed', 'Syndicated data: contract + annual PO. Custom projects: roster MSA + SOW per project. DIY survey tools: catalogue item.', 'Co-managed', '1) Split spend into syndicated data, custom projects and DIY tools. 2) Syndicated data -> contract + annual blanket PO. 3) Custom projects -> roster MSA + SOW, 3 quotes above agreed threshold. 4) DIY survey-tool licences -> catalogue item.'),
    ('Events and Sponsorship', 'Activation', 'B. Co-managed', 'Sponsorship: contract-linked PO with milestone payments. Event services: roster contract + SOW per event; standard AV/staging as rate-card items.', 'Co-managed', '1) Tag spend as sponsorship rights vs event services. 2) Sponsorship -> contract-linked PO with milestone payments and Legal review. 3) Event services -> roster contract + SOW per event; standard items as rate-card catalogue lines. 4) Venues via the venue programme (CM0019).'),
    ('Promotional and POS Materials', 'Activation', 'A. Procurement-led', 'Static catalogue with quantity-break prices for repeat items; bespoke displays via quote request (3 suppliers).', 'Procurement Led', '1) Identify top repeat SKUs (shelf strips, wobblers, posters, branded merchandise). 2) Build catalogue with quantity-break prices per country. 3) Bespoke displays -> Ariba quote request. 4) Consolidate to 1-2 suppliers per country.'),
    ('Spare Parts - Production Equipment', 'MRO Materials', 'B. Co-managed', 'OEM frame agreement (discount off list price) + contract-linked PO; OEM punch-out where available.', 'Co-managed', '1) Rank spend by OEM. 2) Top OEMs -> contract with % discount off list; contract-linked PO. 3) Enable OEM punch-out where offered. 4) Check whether plant maintenance (ERP/MRP) already raises these POs - if yes, exclude from the Ariba gap.'),
    ('Industrial Consumables', 'MRO Materials', 'A. Procurement-led', 'Punch-out catalogue from one integrated MRO distributor per country; free text blocked.', 'Procurement Led', '1) One MRO distributor per country with punch-out. 2) Block free-text for this commodity. 3) Pilot vending at high-volume sites.'),
    ('Equipment Maintenance Services', 'MRO Services', 'B. Co-managed', 'Annual service contract + blanket PO per site; call-outs against rate card; shutdowns via SOW.', 'Co-managed', '1) Annual service contract + blanket PO per site. 2) Call-out rate card; call-offs against the contract. 3) Shutdown/project work -> SOW with 3 quotes. 4) Bundle sites per supplier.'),
    ('Cleaning Services', 'Soft Services', 'A. Procurement-led', 'Contract + monthly blanket PO per site; extras (deep clean, windows) as fixed-price service catalogue items.', 'Procurement Led', '1) Contract + monthly blanket PO per site. 2) Extras as fixed-price service catalogue items. 3) Evaluate a soft-FM bundle (cleaning + security + laundry).'),
    ('Security Services', 'Soft Services', 'A. Procurement-led', 'Contract + blanket PO per site; man-hour rate card for extra hours.', 'Procurement Led', '1) Contract + blanket PO per site. 2) Rate card for extra hours. 3) Labour-law and licence compliance clauses. 4) Include in soft-FM bundle review.'),
    ('Uniforms and Laundry', 'Soft Services', 'A. Procurement-led', 'Uniforms: catalogue by role and size with entitlement limits. Laundry: contract + blanket PO.', 'Procurement Led', '1) Catalogue of standard uniforms/PPE by role. 2) Laundry -> contract + blanket PO. 3) Annual entitlement per role.'),
    ('Freight Forwarding', 'Logistics', 'D. Outside Ariba buying channel', 'Production/outbound freight: rates in TMS, paid via freight audit or self-billing. Indirect courier: contract with rate card.', 'Procurement Led', '1) Confirm freight ownership per country. 2) Production/outbound freight -> exclude from indirect catalogue base; report separately. 3) Indirect courier/ad-hoc freight -> contract with courier rate card.'),
    ('Third-party Warehousing', 'Logistics', 'B. Co-managed', 'Multi-year 3PL contract + monthly blanket PO; invoices matched to activity reports.', 'Co-managed', '1) Contract + monthly blanket PO. 2) Match invoices to activity reports. 3) Annual rate review.'),
    ('Software Licences and SaaS', 'IT', 'B. Co-managed', 'Enterprise: contract + annual PO. Standard software: reseller punch-out catalogue. New SaaS: intake form with IT security review.', 'Co-managed', '1) Build renewal calendar for top 20 contracts. 2) Enterprise -> contract + annual PO. 3) Standard titles -> reseller punch-out. 4) New SaaS -> guided-buying intake form with IT approval.'),
    ('IT Hardware and Peripherals', 'IT', 'A. Procurement-led', 'Standard device bundles in reseller punch-out catalogue; non-standard needs IT approval + quote.', 'Procurement Led', '1) Standard bundles in catalogue. 2) Non-standard -> IT approval + quote. 3) Annual price refresh.'),
    ('Mobile and Fixed Telecom', 'Telecom', 'B. Co-managed', 'Contract + annual blanket PO per carrier; devices via catalogue.', 'Co-managed', '1) Contract + annual blanket PO per carrier. 2) Devices via catalogue. 3) Quarterly bill review for unused lines.'),
    ('Management Consulting', 'Advisory', 'B. Co-managed', 'Panel MSA with day rates + SOW per engagement; milestone-based POs; competition above threshold.', 'Co-managed', '1) Agree threshold for procurement engagement. 2) Panel MSAs with day rates. 3) SOW per engagement with milestone POs. 4) Above threshold: 2-3 panel proposals.'),
    ('Legal Services', 'Advisory', 'C. Business-led with guardrails', 'Legal-owned panel; PO per matter or blanket per firm with non-confidential description.', 'Business Led', '1) Legal-owned panel with agreed rates. 2) PO per matter or blanket per firm. 3) Procurement joins panel renewal only. 4) Annual spend review with GC.'),
    ('Hotels and Accommodation', 'Travel', 'D. Outside Ariba buying channel', 'Booked via travel agency / online booking tool with negotiated rates; paid by corporate card or central billing.', 'Procurement Led', '1) Route via TMC/booking tool; exclude from non-catalogue base. 2) Negotiate hotel programme in top cities. 3) Hotel lines in Ariba = channel leakage; fix the channel. 4) Group bookings for events -> Venues.'),
    ('Meeting Venues', 'Meetings', 'A. Procurement-led', 'Preferred venue list with rates; PO per event with standard terms.', 'Procurement Led', '1) Preferred venue list per city. 2) Book via meetings desk or quote request. 3) PO per event with standard terms. 4) Link to Events (CM0003).'),
    ('Contingent Labour', 'Workforce', 'B. Co-managed', 'Agency panel with fixed mark-ups; services requisition with timesheets, or VMS if volume justifies.', 'Co-managed', '1) Agency panel with fixed mark-up per role. 2) Services requisition with timesheets (VMS if volume justifies). 3) Track tenure to manage misclassification risk. 4) No catalogue.'),
    ('Training and Development', 'Workforce', 'B. Co-managed', 'Open courses: catalogue with per-seat price. Bespoke programmes: contract + SOW. E-learning: contract + annual PO.', 'Co-managed', '1) Open/public courses -> catalogue with per-seat price. 2) Bespoke programmes -> contract + SOW. 3) E-learning platform -> contract + annual PO.'),
    ('Office Supplies and Stationery', 'Office Supplies', 'A. Procurement-led', 'Punch-out catalogue, one supplier per country; free text blocked.', 'Procurement Led', '1) One punch-out supplier per country. 2) Block free-text. 3) Monthly leakage report.'),
]

TA, TB, TC, TE = "A. Procurement-led", "B. Co-managed", "C. Business-led with guardrails", "E. Out of scope (non-addressable)"
SCENARIO = [
    ("Protective Workwear", "Workwear", TA, "Catalogue (distributor punch-out)", "Procurement Led",
     "1) Distributor punch-out per country. 2) Block free-text. 3) Vending at high-use sites."),
    ("Courier Services", "Courier & Postal", TA, "Contract with account billing", "Procurement Led",
     "1) Contract per country with rate card. 2) Monthly consolidated invoice on blanket PO."),
    ("Pest Control Services", "Hygiene", TA, "Contract + monthly blanket PO; extras as fixed-price service items",
     "Procurement Led", "1) Contract + monthly blanket PO per site. 2) Consider a soft-FM bundle."),
    ("Digital Analytics Services", "Digital Marketing", TB, "Contract: agency roster + SOW per project",
     "Co-managed (Marketing + Procurement)",
     "1) Roster of 2-3 analytics agencies. 2) MSA with rate cards. 3) SOW + PO per project."),
    ("Translation Services", "Language Services", TA, "Contract: rate card (per word/hour)", "Procurement Led",
     "1) Rate-card contract with 1-2 language providers. 2) PO per job against the rate card."),
    ("Corporate Strategy Advisory", "Strategy Advisory", TC, "Engagement letter + PO; procurement commercial review",
     "Business Led (Leadership / CFO)",
     "1) Engagement letter + PO per mandate. 2) Procurement commercial review above threshold."),
    ("Customer Rebates", "Trade Investment", TE, "Out of procurement scope: trade terms, credit notes or customer claims",
     "Sales / Revenue Management",
     "1) Exclude from addressable spend. 2) Move off requisitions to the trade-claims process."),
    ("Office Rent", "Leases", TE, "Non-PO lease payments under signed lease", "Real Estate / Finance",
     "1) Exclude from addressable spend. 2) Pay via lease schedule (non-PO)."),
]

ROWS = BASE + SCENARIO
