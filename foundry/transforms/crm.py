"""Raw CRM and e-signature exports -> the 7 clean datasets that back the CRM ontology.
The cleaning logic is myproject/clean_crm.py, a copy of crm_ontology/clean_crm.py (tested locally against data/*.csv).
Each output gets an explicit Arrow schema, so the column types match the ontology property types."""
import pyarrow as pa
from transforms import expectations as E
from transforms.api import Check, Input, Output, transform

from myproject import clean_crm as c

P = "/<your-project-path>/CRM Ontology/"  # set to your Foundry project folder
S, TS, D = pa.string(), pa.timestamp("us", tz="UTC"), pa.date32()
# ponytail: money as double to match the double money properties of the object types.
# Exact for these amounts; switch to decimal(18,2) if the ontology uses a decimal type.
DEC = pa.float64()
SCHEMA = {
    "accounts": [("accountId", S), ("name", S), ("industry", S), ("website", S), ("annualRevenue", DEC),
                 ("ownerId", S), ("createdAt", TS)],
    "contacts": [("contactId", S), ("fullName", S), ("email", S), ("phone", S), ("jobTitle", S), ("accountId", S)],
    "leads": [("leadId", S), ("fullName", S), ("companyName", S), ("email", S), ("leadSource", S), ("status", S),
              ("ownerId", S), ("convertedAccountId", S), ("createdAt", TS), ("createdBy", S)],
    "sales-reps": [("salesRepId", S), ("fullName", S), ("email", S), ("team", S), ("maxOpenLeads", pa.int32()),
                   ("openLeadCount", pa.int32()), ("foundryUserId", S)],
    "opportunities": [("opportunityId", S), ("name", S), ("accountId", S), ("ownerId", S), ("stage", S),
                      ("amount", DEC), ("closeDate", D), ("probability", pa.float64()), ("discountPct", pa.float64()),
                      ("lastStageChangeAt", TS), ("closedAt", TS)],
    "opportunity-contacts": [("contactId", S), ("opportunityId", S)],
    "esign-contracts": [("opportunityId", S), ("contractSigned", pa.bool_()), ("contractSignedOn", D)],
}
# CRM rep -> Foundry user id, for the action owner checks (Foundry criteria compare the current user id).
# Only here, not in clean_crm.py: local data/*.csv has no Foundry users. Reps without a Foundry user stay empty.
# ponytail: one Foundry user exists; move this to an admin-maintained mapping dataset when there are more.
FOUNDRY_USERS = {"rep-ana": "<foundry-user-id>"}
PK = {"accounts": ["accountId"], "contacts": ["contactId"], "leads": ["leadId"], "sales-reps": ["salesRepId"],
      "opportunities": ["opportunityId"], "opportunity-contacts": ["contactId", "opportunityId"],
      "esign-contracts": ["opportunityId"]}


def out(stem):
    """Output dataset with a primary-key check: the build fails if a duplicate key survives the cleaning."""
    return Output(P + stem, checks=Check(E.primary_key(*PK[stem]), f"{stem} primary key", on_error="FAIL"))


def table(df, stem):
    schema = pa.schema(SCHEMA[stem])
    df = df.astype({f.name: float for f in schema if f.type == pa.float64()})  # Decimal -> float for money
    return pa.Table.from_pandas(df, schema=schema, preserve_index=False)


@transform.using(output=out("accounts"), raw=Input(P + "crm_accounts"))
def accounts(raw, output):
    output.write_table(table(c.clean_accounts(raw.pandas()), "accounts"))


@transform.using(output=out("contacts"), raw=Input(P + "crm_contacts"))
def contacts(raw, output):
    output.write_table(table(c.clean_contacts(raw.pandas()), "contacts"))


@transform.using(output=out("leads"), raw=Input(P + "crm_leads"))
def leads(raw, output):
    output.write_table(table(c.clean_leads(raw.pandas()), "leads"))


@transform.using(output=out("opportunities"), raw=Input(P + "crm_opportunities"))
def opportunities(raw, output):
    output.write_table(table(c.clean_opportunities(raw.pandas()), "opportunities"))


@transform.using(output=out("opportunity-contacts"), raw=Input(P + "crm_opportunity_contact_roles"))
def opportunity_contacts(raw, output):
    output.write_table(table(c.clean_opportunity_contacts(raw.pandas()), "opportunity-contacts"))


@transform.using(output=out("sales-reps"), raw=Input(P + "crm_users"), clean_leads=Input(P + "leads"))
def sales_reps(raw, clean_leads, output):  # reads the clean leads OUTPUT: lineage raw -> leads -> sales-reps
    df = c.clean_sales_reps(raw.pandas(), clean_leads.pandas())
    df["foundryUserId"] = df["salesRepId"].map(FOUNDRY_USERS)
    output.write_table(table(df, "sales-reps"))


@transform.using(output=out("esign-contracts"), raw=Input(P + "esign_envelopes"), clean_opps=Input(P + "opportunities"))
def esign_contracts(raw, clean_opps, output):  # reads the clean opportunities OUTPUT
    output.write_table(table(c.clean_esign_contracts(raw.pandas(), clean_opps.pandas()), "esign-contracts"))
