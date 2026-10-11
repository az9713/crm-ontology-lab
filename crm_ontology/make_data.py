"""Generate sample CRM data: one CSV per dataset in ontology.json (x-local.datasets), columns taken from the
datasource property mappings. Deterministic (seed 7). Two planted defects, asserted at the end:
  1. Duplicate company: acct-019 'Northwind Traders' and acct-020 'Northwind Traders, Inc.' are one company
     (same website). Two leads were converted separately and convert-lead does not deduplicate (report section 4.1).
  2. Missing contract row: opp-025 is closedWon, but esign-contracts has no row for it.
Usage: python make_data.py"""
import csv, json, random, re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
ONT = json.loads((HERE / "ontology.json").read_text(encoding="utf-8"))
rnd = random.Random(7)
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
ts = lambda days_ago: (NOW - timedelta(days=days_ago, minutes=rnd.randint(0, 1439))).strftime("%Y-%m-%dT%H:%M:%SZ")
before = lambda iso, days: (datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
day = lambda days: (NOW + timedelta(days=days)).strftime("%Y-%m-%d")

# ---- sales reps (salesRepId = user ID in x-local.users)
reps = [dict(salesRepId=i, fullName=n, email=f"{i[4:]}@example.com", team=t, maxOpenLeads=m, openLeadCount=0)
        for i, n, t, m in [("rep-ana", "Ana Lopez", "East", 5), ("rep-ben", "Ben Okafor", "East", 5),
                           ("rep-eli", "Eli Novak", "West", 6), ("rep-fay", "Fay Chen", "West", 3)]]
rep_ids = [r["salesRepId"] for r in reps]

# ---- accounts: 18 distinct companies + the planted duplicate pair
names = ["Acme Robotics", "Blue Harbor Foods", "Cedar Health", "Delta Freight", "Evergreen Solar", "Fable Books",
         "Granite Bank", "Helix Biotech", "Iris Optics", "Juniper Retail", "Kestrel Aviation", "Lumen Energy",
         "Maple Insurance", "Nimbus Cloud", "Orchid Hotels", "Pioneer Steel", "Quartz Media", "Redwood Logistics"]
industries = ["Manufacturing", "Food", "Healthcare", "Logistics", "Energy", "Media", "Finance", "Biotech",
              "Retail", "Aviation", "Insurance", "Technology", "Hospitality"]
slug = lambda s: re.sub(r"[^a-z]", "", s.lower().split(",")[0])
accounts = [dict(accountId=f"acct-{i:03d}", name=n, industry=rnd.choice(industries), website=f"{slug(n)}.example.com",
                 annualRevenue=f"{rnd.randint(2, 500) * 1_000_000:.2f}", ownerId=rnd.choice(rep_ids),
                 createdAt=ts(rnd.randint(200, 700))) for i, n in enumerate(names, 1)]
for i, n, owner in [(19, "Northwind Traders", "rep-ana"), (20, "Northwind Traders, Inc.", "rep-eli")]:
    accounts.append(dict(accountId=f"acct-{i:03d}", name=n, industry="Retail", website="northwindtraders.example.com",
                         annualRevenue="85000000.00", ownerId=owner, createdAt=ts(rnd.randint(30, 120))))

# ---- contacts: 2 per account
first = ["Alex", "Bea", "Carl", "Dina", "Ed", "Fern", "Gus", "Hana", "Ivan", "Jo", "Kai", "Lena", "Max", "Nora",
         "Omar", "Pia", "Raj", "Sara", "Tom", "Uma"]
last = ["Adams", "Brooks", "Cruz", "Diaz", "Evans", "Ford", "Gray", "Hill", "Ito", "James", "Khan", "Lee"]
titles = ["CEO", "CFO", "VP Sales", "Head of Procurement", "IT Director", "Operations Manager"]
contacts = []
for a in accounts:
    for _ in range(2):
        f, l = rnd.choice(first), rnd.choice(last)
        n = len(contacts) + 1
        contacts.append(dict(contactId=f"cont-{n:03d}", fullName=f"{f} {l}", email=f"{f}.{l}@{a['website']}".lower(),
                             phone=f"+1-555-01{n:02d}", jobTitle=rnd.choice(titles), accountId=a["accountId"]))

# ---- leads: 10 new, 8 assigned, 8 converted, 4 disqualified
sources = ["web", "referral", "event", "outbound"]
new_cos = ["Atlas Mining", "Bright Dental", "Coral Travel", "Dune Apparel", "Echo Audio", "Falcon Security",
           "Glacier Water", "Harbor Legal", "Indigo Paints", "Jade Gardens", "Kite Games", "Lotus Spa", "Mesa Farms",
           "Nova Labs"]
converted_into = ["acct-003", "acct-007", "acct-011", "acct-014", "acct-016", "acct-018", "acct-019", "acct-020"]
plan = ([("new", None, None)] * 10
        + [("assigned", o, None) for o in ["rep-ana", "rep-ana", "rep-ben", "rep-ben", "rep-eli",
                                           "rep-fay", "rep-fay", "rep-fay"]]  # rep-fay at her limit of 3
        + [("converted", None, a) for a in converted_into]
        + [("disqualified", o, None) for o in ["rep-ana", "rep-ben", "rep-eli", "rep-fay"]])
acct_by_id = {a["accountId"]: a for a in accounts}
leads = []
for n, (status, owner, acct) in enumerate(plan, 1):
    f, l = rnd.choice(first), rnd.choice(last)
    co = acct_by_id[acct]["name"] if acct else new_cos[(n - 1) % len(new_cos)]
    leads.append(dict(leadId=f"lead-{n:03d}", fullName=f"{f} {l}", companyName=co,
                      email=f"{f}.{l}@{slug(co)}.example.com".lower(), leadSource=rnd.choice(sources), status=status,
                      ownerId=acct_by_id[acct]["ownerId"] if acct else owner, convertedAccountId=acct,
                      createdAt=before(acct_by_id[acct]["createdAt"], rnd.randint(3, 30)) if acct else ts(rnd.randint(5, 150)),
                      createdBy=rnd.choice(["mgr-cara", "rep-ana", "rep-ben"])))
open_leads = Counter(l["ownerId"] for l in leads if l["status"] == "assigned")
for r in reps:
    r["openLeadCount"] = open_leads[r["salesRepId"]]

# ---- opportunities: 4 prospecting, 4 qualification, 5 proposal, 5 negotiation, 2 closedLost, 5 closedWon
prob = {"prospecting": 0.1, "qualification": 0.25, "proposal": 0.5, "negotiation": 0.75, "closedWon": 1.0, "closedLost": 0.0}
stages = (["prospecting"] * 4 + ["qualification"] * 4 + ["proposal"] * 5 + ["negotiation"] * 5
          + ["closedLost"] * 2 + ["closedWon"] * 5)
opp_accts = [a["accountId"] for a in accounts[:18]] + ["acct-019", "acct-020", "acct-002", "acct-005", "acct-009",
                                                     "acct-012", "acct-015"]
rnd.shuffle(opp_accts)
products = ["Platform license", "Support renewal", "Pilot", "Expansion", "Onboarding package"]
opps = []
for n, (stage, acct) in enumerate(zip(stages, opp_accts), 1):
    closed = stage.startswith("closed")
    changed = ts(rnd.randint(1, 60))
    opps.append(dict(opportunityId=f"opp-{n:03d}", name=f"{acct_by_id[acct]['name']} - {rnd.choice(products)}",
                     accountId=acct, ownerId=acct_by_id[acct]["ownerId"], stage=stage,
                     amount=f"{rnd.randint(5, 400) * 1000:.2f}",
                     closeDate=day(-rnd.randint(1, 60) if closed else rnd.randint(10, 120)), probability=prob[stage],
                     discountPct=rnd.choice([0.0, 0.0, 5.0, 10.0, 15.0]), lastStageChangeAt=changed,
                     closedAt=changed if closed else None))

# ---- e-signature system rows: closedWon opp-021..024 signed (opp-025 planted missing);
#      negotiation opp-014, opp-015 signed (ready for close-opportunity-won), opp-016 sent but unsigned,
#      opp-017, opp-018 no row yet (normal: contract not sent).
opp_by_id = {o["opportunityId"]: o for o in opps}
esign = ([dict(opportunityId=f"opp-{n:03d}", contractSigned="true",  # signed before the deal closed
               contractSignedOn=before(opp_by_id[f"opp-{n:03d}"]["closedAt"], rnd.randint(1, 10))[:10]) for n in (21, 22, 23, 24)]
         + [dict(opportunityId=f"opp-{n:03d}", contractSigned="true", contractSignedOn=day(-rnd.randint(1, 9))) for n in (14, 15)]
         + [dict(opportunityId="opp-016", contractSigned="false", contractSignedOn=None)])

# ---- many-to-many Contact <-> Opportunity: 1 or 2 contacts of the opportunity's account
opp_contacts = []
for o in opps:
    cs = [c["contactId"] for c in contacts if c["accountId"] == o["accountId"]]
    for c in cs[:rnd.choice([1, 2])]:
        opp_contacts.append(dict(contactId=c, opportunityId=o["opportunityId"]))

# ---- write: columns from ontology.json datasource mappings
cols = {}
for ot in ONT["objectTypes"].values():
    for ds in ot["objectType"]["datasources"]:
        d = ds["definition"]
        if d["type"] == "dataset":
            cols[d["datasetRid"]] = [m["column"] for m in d["propertyMapping"].values()]
for ld in ONT["x-local"]["linkDatasources"].values():
    cols[ld["datasetRid"]] = list(ld["columns"].values())
rows = {"sales-reps": reps, "accounts": accounts, "contacts": contacts, "leads": leads, "opportunities": opps,
        "esign-contracts": esign, "opportunity-contacts": opp_contacts}
for rid, path in ONT["x-local"]["datasets"].items():
    data = rows[Path(path).stem]
    assert set(data[0]) == set(cols[rid]), (path, set(data[0]) ^ set(cols[rid]))
    (HERE / path).parent.mkdir(exist_ok=True)
    with open(HERE / path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols[rid])
        w.writeheader()
        w.writerows({k: ("" if v is None else v) for k, v in r.items()} for r in data)
    print(f"{path}: {len(data)} rows")

# ---- self-check: integrity everywhere except the two planted defects
ids = lambda rs, k: {r[k] for r in rs}
assert (len(reps), len(accounts), len(contacts), len(leads), len(opps)) == (4, 20, 40, 30, 25)
assert all(r[k] in set(rep_ids) for rs in (accounts, opps) for r in rs for k in ["ownerId"])
assert all(l["ownerId"] in set(rep_ids) for l in leads if l["status"] != "new")
assert all(not l["ownerId"] for l in leads if l["status"] == "new")
assert ids(contacts, "accountId") | ids(opps, "accountId") <= ids(accounts, "accountId")
assert {l["convertedAccountId"] for l in leads if l["convertedAccountId"]} <= ids(accounts, "accountId")
assert ids(opp_contacts, "contactId") <= ids(contacts, "contactId") and ids(esign, "opportunityId") <= ids(opps, "opportunityId")
assert all(r["openLeadCount"] <= r["maxOpenLeads"] for r in reps) and reps[3]["openLeadCount"] == reps[3]["maxOpenLeads"]
norm = lambda s: re.sub(r"[^a-z]", "", s.lower().replace(", inc.", ""))
dupes = [k for k, v in Counter(norm(a["name"]) for a in accounts).items() if v > 1]
assert dupes == ["northwindtraders"], dupes                                      # planted defect 1
won_no_contract = [o["opportunityId"] for o in opps if o["stage"] == "closedWon" and o["opportunityId"] not in ids(esign, "opportunityId")]
assert won_no_contract == ["opp-025"], won_no_contract                          # planted defect 2
assert all(l["createdAt"] < acct_by_id[l["convertedAccountId"]]["createdAt"] for l in leads if l["convertedAccountId"])
assert all(e["contractSignedOn"] <= opp_by_id[e["opportunityId"]]["closedAt"][:10] for e in esign if opp_by_id[e["opportunityId"]]["closedAt"])
print("OK integrity checks; planted defects present: duplicate 'northwindtraders' (acct-019, acct-020), closedWon without contract (opp-025)")

# ==== raw layer: what the two source systems export (data/raw/). clean_crm.py must turn it back into the files above.
# Own Random, so the clean files above stay byte-identical. Mess types and counts: README "Raw layer".
rr = random.Random(11)
E1, E2 = "2026-09-15T00:00:00.000+0000", "2026-10-01T00:00:00.000+0000"  # full extract, then incremental extract
crm = lambda iso: iso.replace("Z", ".000+0000")                        # CRM API timestamp format
old_mod = lambda: crm(f"2026-{rr.choice(['08', '09'])}-{rr.randint(1, 14):02d}T{rr.randint(0, 23):02d}:{rr.randint(0, 59):02d}:00Z")
new_mod = lambda: crm(f"2026-09-{rr.randint(16, 30):02d}T{rr.randint(0, 23):02d}:{rr.randint(0, 59):02d}:00Z")
raw = {}
def put(name, row, stale=None, extract=None):
    """One record. stale = field overrides for an older version that sits in the full extract (E1)."""
    rows_ = raw.setdefault(name, [])
    if stale is not None:
        rows_.append({**row, **stale, "IsDeleted": "false", "_extracted_at": E1})
    rows_.append({**row, "IsDeleted": row.get("IsDeleted", "false"),
                  "_extracted_at": E2 if stale is not None else (extract or E1)})

# CRM users: reps plus a manager, an integration user and a deactivated rep (all three must be filtered out)
region = {"rep-ana": "East", "rep-ben": "east", "rep-eli": "WEST ", "rep-fay": "West"}
for r in reps:
    put("crm_users", dict(Id=r["salesRepId"], Name=r["fullName"], Email=r["email"], Profile="Sales Rep", IsActive="true",
                          Region=region[r["salesRepId"]], MaxOpenLeads=r["maxOpenLeads"], LastModifiedDate=old_mod()))
for i, n, p, act in [("mgr-cara", "Cara Diaz", "Sales Manager", "true"), ("usr-sync", "Integration User", "System Integration", "true"),
                     ("rep-gil", "Gil Moss", "Sales Rep", "false")]:
    put("crm_users", dict(Id=i, Name=n, Email=f"{i[4:]}@example.com", Profile=p, IsActive=act, Region="East",
                          MaxOpenLeads="5" if p == "Sales Rep" else "", LastModifiedDate=old_mod()))

# CRM accounts: website variants, trailing spaces, integer revenue, 3 owner changes, 1 test account deleted in E2
for i, a in enumerate(accounts):
    w = a["website"]
    row = dict(Id=a["accountId"], Name=a["name"] + (" " if i % 5 == 0 else ""), Industry=a["industry"],
               Website=[w, f"https://www.{w}/", f"http://{w}", f"WWW.{w.upper()}"][i % 4],
               AnnualRevenue=str(int(float(a["annualRevenue"]))), OwnerId=a["ownerId"], CreatedDate=crm(a["createdAt"]))
    if a["accountId"] in ("acct-003", "acct-008", "acct-012"):  # reassigned after E1; the stale row has the old owner
        put("crm_accounts", {**row, "LastModifiedDate": new_mod()},
            stale=dict(OwnerId=rep_ids[(rep_ids.index(a["ownerId"]) + 1) % 4], LastModifiedDate=old_mod()))
    else:
        put("crm_accounts", {**row, "LastModifiedDate": old_mod()})
test = dict(Id="acct-900", Name="Test Account - DO NOT USE", Industry="", Website="test.example.com", AnnualRevenue="0",
            OwnerId="usr-sync", CreatedDate=crm(ts(100)))
put("crm_accounts", {**test, "LastModifiedDate": old_mod()})
put("crm_accounts", {**test, "LastModifiedDate": new_mod(), "IsDeleted": "true"}, extract=E2)

# CRM contacts: first/last split, email case + spaces, 4 phone formats, 4 job-title changes
for i, c in enumerate(contacts):
    f, l = c["fullName"].split(" ")
    p = c["phone"][-4:]
    row = dict(Id=c["contactId"], FirstName=f, LastName=l, Email=c["email"].upper() + " " if i % 3 == 0 else c["email"],
               Phone=[c["phone"], f"555-{p}", f"(555) {p}", f"1.555.{p}"][i % 4], Title=c["jobTitle"], AccountId=c["accountId"])
    if i in (4, 9, 14, 19):
        put("crm_contacts", {**row, "LastModifiedDate": new_mod()}, stale=dict(Title="Analyst", LastModifiedDate=old_mod()))
    else:
        put("crm_contacts", {**row, "LastModifiedDate": old_mod()})

# CRM leads: picklist labels, unassigned leads owned by a queue, two null tokens, assigned after E1 -> stale 'new' row
STATUS = {"new": "Open - Not Contacted", "assigned": "Working - Contacted", "converted": "Closed - Converted",
          "disqualified": "Closed - Not Converted"}
SOURCE = {"web": "Web", "referral": "Referral", "event": "Trade Show", "outbound": "Cold Call"}
for i, l in enumerate(leads):
    f, la = l["fullName"].split(" ")
    created = crm(l["createdAt"])
    row = dict(Id=l["leadId"], FirstName=f, LastName=la, Company=l["companyName"],
               Email=l["email"].upper() if i % 4 == 0 else l["email"], LeadSource=SOURCE[l["leadSource"]],
               Status=STATUS[l["status"]], OwnerId=l["ownerId"] or "queue-unassigned",
               ConvertedAccountId=l["convertedAccountId"] or ["", "NULL"][i % 2], CreatedDate=created,
               CreatedById=l["createdBy"])
    if l["status"] == "assigned" and created < E1:
        put("crm_leads", {**row, "LastModifiedDate": new_mod()},
            stale=dict(Status=STATUS["new"], OwnerId="queue-unassigned", LastModifiedDate=created))
    else:
        put("crm_leads", {**row, "LastModifiedDate": max(created, old_mod())}, extract=E2 if created > E1 else E1)

# CRM opportunities: stage labels, percent probability, integer amounts, closedAt not exported (derive it),
# stage changed after E1 -> stale row at the previous stage
STAGE = {"prospecting": "Prospecting", "qualification": "Qualification", "proposal": "Proposal/Price Quote",
         "negotiation": "Negotiation/Review", "closedWon": "Closed Won", "closedLost": "Closed Lost"}
PREV = {"qualification": "prospecting", "proposal": "qualification", "negotiation": "proposal",
        "closedWon": "negotiation", "closedLost": "negotiation"}
for o in opps:
    row = dict(Id=o["opportunityId"], Name=o["name"], AccountId=o["accountId"], OwnerId=o["ownerId"],
               StageName=STAGE[o["stage"]], Amount=str(int(float(o["amount"]))), CloseDate=o["closeDate"],
               Probability=str(round(o["probability"] * 100)), DiscountPercent=str(int(o["discountPct"])),
               LastStageChangeDate=crm(o["lastStageChangeAt"]), IsClosed=str(bool(o["closedAt"])).lower(),
               IsWon=str(o["stage"] == "closedWon").lower(), LastModifiedDate=crm(o["lastStageChangeAt"]))
    late = crm(o["lastStageChangeAt"]) > E1
    if late and o["stage"] in PREV:
        earlier = crm(before(o["lastStageChangeAt"], 20))
        put("crm_opportunities", row, stale=dict(StageName=STAGE[PREV[o["stage"]]], IsClosed="false", IsWon="false",
            Probability=str(round(prob[PREV[o["stage"]]] * 100)), LastStageChangeDate=earlier, LastModifiedDate=earlier))
    else:
        put("crm_opportunities", row, extract=E2 if late else E1)

# CRM contact roles: one row per (opportunity, contact, role); 1 pair in 5 has a second role; 1 deleted role
for n, oc in enumerate(opp_contacts):
    for k, role in enumerate([["Decision Maker", "Influencer", "Technical Buyer"][n % 3]] + (["Economic Buyer"] if n % 5 == 0 else [])):
        put("crm_opportunity_contact_roles", dict(Id=f"ocr-{n:03d}{'ab'[k]}", OpportunityId=oc["opportunityId"],
            ContactId=oc["contactId"], Role=role, IsPrimary=str(k == 0).lower(), LastModifiedDate=old_mod()))
single = next(o for o in opps if sum(oc["opportunityId"] == o["opportunityId"] for oc in opp_contacts) == 1)
other = next(c["contactId"] for c in contacts if c["accountId"] == single["accountId"]
             and dict(contactId=c["contactId"], opportunityId=single["opportunityId"]) not in opp_contacts)
put("crm_opportunity_contact_roles", dict(Id="ocr-del", OpportunityId=single["opportunityId"], ContactId=other,
    Role="Influencer", IsPrimary="false", LastModifiedDate=new_mod(), IsDeleted="true"), extract=E2)

# e-signature system: one row per envelope, its own date format and a free-text deal reference
us = lambda d, hhmm: f"{d[5:7]}/{d[8:10]}/{d[:4]} {hhmm}"
envs = []
for k, e in enumerate(esign):
    oid, signed = e["opportunityId"], e["contractSigned"] == "true"
    sent = before((e["contractSignedOn"] or day(-3)) + "T00:00:00Z", 2)[:10]
    envs.append(dict(deal_ref=[oid.upper(), oid, f" {oid}", f"Opp {int(oid[4:])}"][k % 4],
                     status="completed" if signed else "sent", sent_at=us(sent, "09:00"),
                     completed_at=us(e["contractSignedOn"], f"{rr.randint(10, 17)}:{rr.randint(10, 59)}") if signed else ""))
envs += [dict(deal_ref="opp-014", status="voided", sent_at=us(day(-40), "09:00"), completed_at=""),    # replaced by a resend
         dict(deal_ref="OPP-015", status="declined", sent_at=us(day(-35), "09:00"), completed_at=""),  # declined, then resent
         dict(deal_ref="opp-017", status="voided", sent_at=us(day(-20), "09:00"), completed_at=""),    # its only envelope, voided
         dict(deal_ref="OPP-031", status="completed", sent_at=us(day(-12), "09:00"),                   # deal unknown to the CRM
              completed_at=us(day(-11), "15:30"))]
raw["esign_envelopes"] = [dict(envelope_id=f"env-{1001 + k}", **e) for k, e in enumerate(envs)]

(HERE / "data" / "raw").mkdir(exist_ok=True)
for name, rows_ in raw.items():
    rr.shuffle(rows_)  # row order carries no meaning; the transform must not rely on it
    with open(HERE / "data" / "raw" / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows_[0]))
        w.writeheader()
        w.writerows(rows_)
    print(f"data/raw/{name}.csv: {len(rows_)} rows")
