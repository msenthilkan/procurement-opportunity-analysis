"""Generate synthetic sample input files with the same layout as the real exports.

All suppliers, people, emails and amounts are invented. Run:
    python scripts/generate_sample_data.py
Files are written to sample-data/.
"""
import datetime as dt
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "sample-data"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- taxonomy
# (L1 family, L2 category, L3 long, L3 short, led by, mean line value, lines weight, catalogue share)
TAXONOMY = [
    ("Sales, Communication & Marketing", "Media", "Media Buying - Digital and TV", "Media buying", "Business Led", 45000, 6, 0.0),
    ("Sales, Communication & Marketing", "Media", "Market Research and Consumer Insights", "Market research", "Business Led", 18000, 3, 0.0),
    ("Sales, Communication & Marketing", "Activation", "Events and Sponsorship", "Events", "Business Led", 22000, 3, 0.0),
    ("Sales, Communication & Marketing", "Activation", "Promotional and POS Materials", "POS materials", "Procurement Led", 2500, 10, 0.25),
    ("Maintenance, Repairs & Operations", "MRO Materials", "Spare Parts - Production Equipment", "Spare parts", "Business Led", 1800, 12, 0.25),
    ("Maintenance, Repairs & Operations", "MRO Materials", "Industrial Consumables", "Consumables", "Procurement Led", 350, 14, 0.45),
    ("Maintenance, Repairs & Operations", "MRO Services", "Equipment Maintenance Services", "Maintenance services", "Business Led", 6500, 5, 0.0),
    ("Facilities Management", "Soft Services", "Cleaning Services", "Cleaning", "Procurement Led", 4200, 5, 0.0),
    ("Facilities Management", "Soft Services", "Security Services", "Security", "Procurement Led", 5200, 3, 0.0),
    ("Facilities Management", "Soft Services", "Uniforms and Laundry", "Uniforms", "Procurement Led", 600, 8, 0.40),
    ("Transport, Logistics, Warehousing", "Logistics", "Freight Forwarding", "Freight", "Procurement Led", 9500, 6, 0.0),
    ("Transport, Logistics, Warehousing", "Logistics", "Third-party Warehousing", "Warehousing", "Procurement Led", 12000, 3, 0.0),
    ("Information & Communications Technology", "IT", "Software Licences and SaaS", "Software", "Business Led", 8000, 4, 0.0),
    ("Information & Communications Technology", "IT", "IT Hardware and Peripherals", "IT hardware", "Procurement Led", 900, 9, 0.50),
    ("Information & Communications Technology", "Telecom", "Mobile and Fixed Telecom", "Telecom", "Business Led", 3000, 3, 0.0),
    ("Professional Services", "Advisory", "Management Consulting", "Consulting", "Business Led", 25000, 2, 0.0),
    ("Professional Services", "Advisory", "Legal Services", "Legal", "Business Led", 9000, 2, 0.0),
    ("Travel, Meetings & Events", "Travel", "Hotels and Accommodation", "Hotels", "Procurement Led", 700, 9, 0.0),
    ("Travel, Meetings & Events", "Meetings", "Meeting Venues", "Venues", "Procurement Led", 3500, 3, 0.0),
    ("HR Services", "Workforce", "Contingent Labour", "Contingent labour", "Procurement Led", 7000, 4, 0.0),
    ("HR Services", "Workforce", "Training and Development", "Training", "Business Led", 2500, 3, 0.0),
    ("Office", "Office Supplies", "Office Supplies and Stationery", "Office supplies", "Procurement Led", 150, 16, 0.65),
]
UNMAPPED = ["Miscellaneous Services", "Other Goods"]  # appear in spend, not in taxonomy

COUNTRIES = {"US01": 30, "AE01": 14, "DE01": 10, "TR01": 10, "ZA01": 7, "CA01": 6, "ID01": 5, "JP01": 2}

FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn",
         "Drew", "Rowan", "Parker", "Reese", "Hayden", "Emerson", "Skyler", "Finley", "Kai", "Logan"]
LAST = ["Smith", "Khan", "Garcia", "Okafor", "Novak", "Tanaka", "Silva", "Meyer", "Yilmaz", "Patel",
        "Dubois", "Rossi", "Nguyen", "Cohen", "Larsen"]


def bold_header(ws):
    for c in ws[1]:
        c.font = Font(bold=True)


def save(name, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = name
    ws.append(headers)
    for r in rows:
        ws.append(r)
    bold_header(ws)
    wb.save(OUT / f"{name}.xlsx")


def us_date(d):
    return f"{d.month}/{d.day}/{d.year}"


# ---------------------------------------------------------------- taxonomy file
tax_rows = []
for i, (l1, l2, l3, short, led, *_rest) in enumerate(TAXONOMY, start=1):
    tax_rows.append(["Indirect", f"F{i:02d}", l1, f"C{i:03d}", l2, f"CM{i:04d}", short, l3,
                     f"Synthetic description for {short.lower()}", led,
                     "Centre-led" if led.startswith("Procurement") else "Local",
                     "Strategic" if i % 3 == 0 else "Tactical",
                     "Contract" if i % 2 else "Catalogue"])
save("qTaxonomy",
     ["Level 0 (Group)", "Purchasing Family number", "Level 1 (Family)", "Purchasing Category number",
      "Level 2 (Category)", "Purchasing Commodity number", "Level 3 (Commodity) - Short",
      "Level 3 (Commodity) - Long", "Description", "Procurement Or Business Led",
      "Operating Model Types", "Procurement Category Classification", "Execution Strategy"],
     tax_rows)

# ---------------------------------------------------------------- people
people = []
used = set()
while len(people) < 60:
    n = f"{random.choice(FIRST)} {random.choice(LAST)}"
    if n in used:
        continue
    used.add(n)
    people.append(n)
procurement = people[:10]
email = {p: p.lower().replace(" ", ".") + "@example.com" for p in people}

um_rows = []
for i, p in enumerate(people, start=1):
    um_rows.append(["No", f"U{i:04d}", p, "Employee", "Yes", "Yes", "2026-09-30", "", "Chrome", email[p]])
# an inactive duplicate account to show the "active first" rule
um_rows.append(["Yes", "U9999", people[12], "Employee", "No", "No", "2023-01-15", "", "Edge", "old." + email[people[12]]])
save("qUserMaster",
     ["Locked", "User ID", "Name", "Type", "Active", "Has Password", "Last Login", "Delegatee",
      "Last Browser Used", "Business Email Address"], um_rows)
save("tblProcurementGroup", ["Email"], [[email[p]] for p in procurement])

# ---------------------------------------------------------------- spend + approvals
spend_rows, appr_rows = [], []
weights = [t[6] for t in TAXONOMY]
start = dt.date(2025, 10, 1)
req_no = 1000
suppliers = {t[2]: [f"Supplier {random.randint(100, 999)}" for _ in range(random.randint(2, 12))] for t in TAXONOMY}

for _ in range(1400):
    req_no += 1
    rid = f"PR{req_no}"
    country = random.choices(list(COUNTRIES), weights=list(COUNTRIES.values()))[0]
    d = start + dt.timedelta(days=random.randint(0, 364))
    po_d = d + dt.timedelta(days=random.randint(0, 6))
    unmapped = random.random() < 0.03
    t = random.choices(TAXONOMY, weights=weights)[0]
    l3, short, led, mean, cat_share = t[2], t[3], t[4], t[5], t[7]
    commodity = random.choice(UNMAPPED) if unmapped else random.choice([l3, short])  # short or long name
    supplier = random.choice(suppliers[l3])
    n_lines = random.randint(1, 4)

    led_proc = led.startswith("Procurement")
    approvers = random.sample(people[10:], random.randint(1, 2))
    if (led_proc and random.random() < 0.55) or random.random() < 0.15:
        approvers.append(random.choice(procurement))
    if random.random() < 0.02:
        approvers.append("Former Employee")  # not in user master

    line_types = []
    for ln in range(n_lines):
        catalog = random.random() < cat_share
        contract = "" if catalog else (f"CW{random.randint(1000, 9999)}" if random.random() < 0.12 else "")
        amt = round(max(20, random.lognormvariate(0, 0.8) * mean), 2)
        line_type = "Catalog Item" if catalog else ("Non-Catalog Item" if random.random() > 0.02 else "Service Item")
        line_types.append(line_type)
        spend_rows.append([rid, supplier, us_date(d), country, contract, line_type, "Ordered",
                           f"GL {short.title()}", line_type, f"PO{req_no}", f"UNSPSC-{random.randint(10, 99)}",
                           commodity, f"ERP-{random.randint(100, 999)}", us_date(po_d),
                           round(random.uniform(0.5, 72), 1), 1, amt, amt, len(approvers)])
        for a in approvers:  # approver export: each line repeated per approver
            appr_rows.append([rid, us_date(d), country, commodity, line_type, contract, a, amt])

save("qSpend",
     ["[REQ] Requisition ID", "[REQ]Supplier (Common Supplier)", "[REQ]Requisition Date (Date)",
      "[REQ]Purchasing Company (Purchase Organization Id)", "[REQ]Contract (Contract)", "[REQ] Line Type",
      "[REQ] Requisition Status", "[REQ]GL Account (GL Account Name)", "[PO-P&I] Line Type", "[REQ] PO Id",
      "[REQ]Commodity (UNSPSC (L3))", "[REQ]Commodity (Commodity (L3))", "[REQ]ERP Commodity (ERP Commodity)",
      "[PO-P&I]Ordered Date (Date)", "max(Approval Time)", "sum(Line Count)", "sum(Requisition Spend)",
      "sum(PO Spend)", "sum(Approver Count)"], spend_rows)
save("qApproverRaw",
     ["[REQ] Requisition ID", "[REQ]Requisition Date (Date)", "[REQ]Purchasing Company (Purchase Organization Id)",
      "[REQ]Commodity (Commodity)", "[REQ] Line Type", "[REQ]Contract (Contract)",
      "[APS]Approved by User (User)", "sum(Requisition Spend)"], appr_rows)

print(f"Wrote {len(spend_rows)} spend lines and {len(appr_rows)} approver rows to {OUT}")
