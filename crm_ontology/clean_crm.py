"""Clean the raw source exports (data/raw/) into the 7 ontology datasets (data/*.csv).
Each clean_* function takes raw pandas DataFrames (every column a string) and returns one typed DataFrame.
In Foundry, a lightweight transform calls the same function, e.g. output.write_table(clean_accounts(raw.pandas())).
The cleaning fixes format and provenance only. It never merges records: the Northwind duplicate stays (identity is
a separate job, report section 4.1), and opp-025 still has no contract row.
Usage: python clean_crm.py   -> asserts that the output equals data/*.csv, the known answer."""
import re
from decimal import Decimal

import pandas as pd

NULLS = ["", "NULL", "N/A"]
STATUS = {"Open - Not Contacted": "new", "Working - Contacted": "assigned", "Closed - Converted": "converted",
          "Closed - Not Converted": "disqualified"}
SOURCE = {"Web": "web", "Referral": "referral", "Trade Show": "event", "Cold Call": "outbound"}
STAGE = {"Prospecting": "prospecting", "Qualification": "qualification", "Proposal/Price Quote": "proposal",
         "Negotiation/Review": "negotiation", "Closed Won": "closedWon", "Closed Lost": "closedLost"}

crm_ts = lambda s: pd.to_datetime(s, format="%Y-%m-%dT%H:%M:%S.%f%z", utc=True)
money = lambda s: Decimal(s).quantize(Decimal("0.01"))
nulls = lambda s: s.str.strip().replace(NULLS, None)
email = lambda s: s.str.strip().str.lower()


def latest(df):
    """Two extracts overlap, so a record can appear twice. Keep its newest version, THEN drop soft-deletes.
    Dropping deletes first would let the older, undeleted version of a deleted record survive."""
    df = df.assign(_mod=crm_ts(df.LastModifiedDate)).sort_values(["_mod", "_extracted_at"])
    df = df.drop_duplicates("Id", keep="last")
    return df[df.IsDeleted != "true"]


def phone(s):  # ponytail: North American numbers only; use the phonenumbers library if other countries appear
    d = re.sub(r"\D", "", s)
    d = d if d.startswith("1") else "1" + d
    return f"+{d[0]}-{d[1:4]}-{d[4:]}"


def clean_accounts(raw):
    a = latest(raw)
    site = (a.Website.str.strip().str.lower().str.replace(r"^https?://", "", regex=True)
            .str.replace(r"^www\.", "", regex=True).str.rstrip("/"))
    return pd.DataFrame({"accountId": a.Id, "name": a.Name.str.strip(), "industry": a.Industry.str.strip(),
                         "website": site, "annualRevenue": a.AnnualRevenue.map(money), "ownerId": a.OwnerId,
                         "createdAt": crm_ts(a.CreatedDate)})


def clean_contacts(raw):
    c = latest(raw)
    return pd.DataFrame({"contactId": c.Id, "fullName": c.FirstName.str.strip() + " " + c.LastName.str.strip(),
                         "email": email(c.Email), "phone": c.Phone.map(phone), "jobTitle": c.Title.str.strip(),
                         "accountId": c.AccountId})


def clean_leads(raw):
    l = latest(raw)
    return pd.DataFrame({"leadId": l.Id, "fullName": l.FirstName.str.strip() + " " + l.LastName.str.strip(),
                         "companyName": l.Company.str.strip(), "email": email(l.Email),
                         "leadSource": l.LeadSource.map(SOURCE), "status": l.Status.map(STATUS),
                         "ownerId": l.OwnerId.replace("queue-unassigned", None),  # a queue is not a sales rep
                         "convertedAccountId": nulls(l.ConvertedAccountId), "createdAt": crm_ts(l.CreatedDate),
                         "createdBy": l.CreatedById})


def clean_sales_reps(raw_users, leads):
    """Only active users with the Sales Rep profile. openLeadCount is not in the CRM: count it from the clean leads."""
    u = latest(raw_users)
    u = u[(u.Profile == "Sales Rep") & (u.IsActive == "true")]
    open_leads = leads[leads.status == "assigned"].groupby("ownerId").size()
    return pd.DataFrame({"salesRepId": u.Id, "fullName": u.Name.str.strip(), "email": email(u.Email),
                         "team": u.Region.str.strip().str.title(), "maxOpenLeads": u.MaxOpenLeads.astype(int),
                         "openLeadCount": u.Id.map(open_leads).fillna(0).astype(int)})


def clean_opportunities(raw):
    """The CRM exports no closedAt. A closed deal closed at its last stage change."""
    o = latest(raw)
    changed = crm_ts(o.LastStageChangeDate)
    return pd.DataFrame({"opportunityId": o.Id, "name": o.Name.str.strip(), "accountId": o.AccountId,
                         "ownerId": o.OwnerId, "stage": o.StageName.map(STAGE), "amount": o.Amount.map(money),
                         "closeDate": pd.to_datetime(o.CloseDate, format="%Y-%m-%d").dt.date,
                         "probability": o.Probability.astype(float) / 100,
                         "discountPct": o.DiscountPercent.astype(float), "lastStageChangeAt": changed,
                         "closedAt": changed.where(o.IsClosed == "true")})


def clean_opportunity_contacts(raw_roles):
    """The CRM has one row per role. The link needs one row per (contact, opportunity) pair."""
    r = latest(raw_roles)
    return (r[["ContactId", "OpportunityId"]].drop_duplicates()
            .rename(columns={"ContactId": "contactId", "OpportunityId": "opportunityId"}))


def clean_esign_contracts(raw_envelopes, opportunities):
    """One row per deal from the e-signature system: drop voided envelopes and deals the CRM does not know,
    then keep the latest envelope. A deal whose only envelope was voided gets no row."""
    e = raw_envelopes.assign(opportunityId=raw_envelopes.deal_ref.str.extract(r"(\d+)")[0].astype(int).map("opp-{:03d}".format),
                             _sent=pd.to_datetime(raw_envelopes.sent_at, format="%m/%d/%Y %H:%M"))
    e = e[(e.status != "voided") & e.opportunityId.isin(opportunities.opportunityId)]
    e = e.sort_values("_sent").drop_duplicates("opportunityId", keep="last")
    signed = e.status == "completed"
    return pd.DataFrame({"opportunityId": e.opportunityId, "contractSigned": signed,
                         "contractSignedOn": pd.to_datetime(e.completed_at.where(signed), format="%m/%d/%Y %H:%M").dt.date})


def clean_all(raw):
    out = {"accounts": clean_accounts(raw["crm_accounts"]), "contacts": clean_contacts(raw["crm_contacts"]),
           "leads": clean_leads(raw["crm_leads"]), "opportunities": clean_opportunities(raw["crm_opportunities"]),
           "opportunity-contacts": clean_opportunity_contacts(raw["crm_opportunity_contact_roles"])}
    out["sales-reps"] = clean_sales_reps(raw["crm_users"], out["leads"])
    out["esign-contracts"] = clean_esign_contracts(raw["esign_envelopes"], out["opportunities"])
    return out


if __name__ == "__main__":
    from pathlib import Path
    D = Path(__file__).parent / "data"
    raw = {p.stem: pd.read_csv(p, dtype=str, keep_default_na=False) for p in (D / "raw").glob("*.csv")}
    out = clean_all(raw)

    def fmt(v):  # typed value -> the string form used in data/*.csv
        if v is None or (not isinstance(v, (str, Decimal)) and pd.isna(v)):
            return ""
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(v, Decimal):
            return f"{v:.2f}"
        return str(v).lower() if str(v) in ("True", "False") else str(v)

    for stem, df in out.items():
        want = pd.read_csv(D / f"{stem}.csv", dtype=str, keep_default_na=False)
        got = [tuple(fmt(v) for v in row) for row in df.itertuples(index=False)]
        assert list(df.columns) == list(want.columns), (stem, list(df.columns))
        assert len(got) == len(set(got)) == len(want), (stem, len(got), len(want))  # no duplicate keys survive
        assert set(got) == set(map(tuple, want.values)), (stem, set(got) ^ set(map(tuple, want.values)))
        print(f"{stem}: {len(df)} rows, equal to data/{stem}.csv")
    # the planted items pass through the cleaning untouched
    assert set(out["accounts"].query("website == 'northwindtraders.example.com'").accountId) == {"acct-019", "acct-020"}
    assert "opp-025" not in set(out["esign-contracts"].opportunityId)
    fay = out["sales-reps"].set_index("salesRepId").loc["rep-fay"]
    assert fay.openLeadCount == fay.maxOpenLeads == 3
    print("OK clean(raw) == data/*.csv for all 7 datasets; planted items intact")
