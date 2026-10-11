"""Generate ontology.json in Palantir OntologyFullMetadata shape. Keys starting 'x-local' are local design.
Usage: python build_ontology.py [output.json]   (default: ontology.json next to this file)"""
import json, sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("ontology.json")
R = lambda kind, name: f"ri.ontology.local.{kind}.{name}"
DS = lambda name: f"ri.foundry.local.dataset.{name}"

def prop(ot, name, dtype, display, desc=None, nullable=True, **extra):
    p = {"displayName": display, "dataType": dtype if isinstance(dtype, dict) else {"type": dtype},
         "rid": R("property", f"{ot}.{name}"), "status": {"type": "active"}, "visibility": "NORMAL",
         "dataConstraints": {"nullability": "NULLABLE" if nullable else "NOT_NULLABLE"}}
    if desc: p["description"] = desc
    p.update(extra)
    return name, p

MONEY = {"type": "decimal", "precision": 18, "scale": 2}

# ---- object types: (apiName, display, plural, icon, pk, title, props, datasources, desc)
def col_map(names): return {n: {"type": "column", "column": n} for n in names}
OBJECTS = {}
LINKS = {}  # objectType -> [LinkTypeSideV2]

def obj(api, display, plural, icon, color, pk, title, props, datasources, desc):
    OBJECTS[api] = {
        "objectType": {"apiName": api, "displayName": display, "status": "ACTIVE", "description": desc,
                       "pluralDisplayName": plural, "icon": {"type": "blueprint", "name": icon, "color": color},
                       "primaryKey": pk, "properties": dict(props), "rid": R("object-type", api),
                       "titleProperty": title, "visibility": "NORMAL", "aliases": [], "datasources": datasources},
        "linkTypes": [], "implementsInterfaces": [], "implementsInterfaces2": {}, "sharedPropertyTypeMapping": {},
        "x-localConflictResolution": "APPLY_USER_EDITS",
    }

def dataset_ds(api, name, props):
    return {"rid": R("datasource", f"{api}.{name}"),
            "definition": {"type": "dataset", "datasetRid": DS(name), "propertyMapping": col_map(props)}}

rep_props = [prop("SalesRep", "salesRepId", "string", "Sales rep ID", "Same value as the user ID.", False),
             prop("SalesRep", "fullName", "string", "Full name", nullable=False),
             prop("SalesRep", "email", "string", "Email"),
             prop("SalesRep", "team", "string", "Team"),
             prop("SalesRep", "maxOpenLeads", "integer", "Maximum open leads", nullable=False),
             prop("SalesRep", "openLeadCount", "integer", "Open lead count",
                  "Guard counter. Every lead assignment and conversion writes it, so concurrent assignments conflict (report section 8.4).", False)]
obj("SalesRep", "Sales Rep", "Sales Reps", "people", "#4C90F0", "salesRepId", "fullName", rep_props,
    [dataset_ds("SalesRep", "sales-reps", [p[0] for p in rep_props])], "A person who owns leads, accounts and opportunities.")

acct_props = [prop("Account", "accountId", "string", "Account ID", nullable=False),
              prop("Account", "name", "string", "Name", nullable=False),
              prop("Account", "industry", "string", "Industry"),
              prop("Account", "website", "string", "Website"),
              prop("Account", "annualRevenue", MONEY, "Annual revenue", "Currency USD. JSON-encoded as a string."),
              prop("Account", "ownerId", "string", "Owner", "Foreign key to SalesRep."),
              prop("Account", "createdAt", "timestamp", "Created at")]
obj("Account", "Account", "Accounts", "office", "#238551", "accountId", "name", acct_props,
    [dataset_ds("Account", "accounts", [p[0] for p in acct_props])], "A company that is a customer or a possible customer.")

contact_props = [prop("Contact", "contactId", "string", "Contact ID", nullable=False),
                 prop("Contact", "fullName", "string", "Full name", nullable=False),
                 prop("Contact", "email", "string", "Email"),
                 prop("Contact", "phone", "string", "Phone"),
                 prop("Contact", "jobTitle", "string", "Job title"),
                 prop("Contact", "accountId", "string", "Account", "Foreign key to Account.")]
obj("Contact", "Contact", "Contacts", "person", "#7961DB", "contactId", "fullName", contact_props,
    [dataset_ds("Contact", "contacts", [p[0] for p in contact_props])], "A person at an account.")

lead_props = [prop("Lead", "leadId", "string", "Lead ID", nullable=False),
              prop("Lead", "fullName", "string", "Full name", nullable=False),
              prop("Lead", "companyName", "string", "Company name"),
              prop("Lead", "email", "string", "Email"),
              prop("Lead", "leadSource", "string", "Lead source"),
              prop("Lead", "status", "string", "Status", "new | assigned | converted | disqualified", False),
              prop("Lead", "ownerId", "string", "Owner", "Foreign key to SalesRep. Empty until assigned."),
              prop("Lead", "convertedAccountId", "string", "Converted account", "Foreign key to Account. Set by convert-lead."),
              prop("Lead", "createdAt", "timestamp", "Created at"),
              prop("Lead", "createdBy", "string", "Created by")]
obj("Lead", "Lead", "Leads", "new-person", "#C87619", "leadId", "fullName", lead_props,
    [dataset_ds("Lead", "leads", [p[0] for p in lead_props])], "A possible customer that nobody has qualified yet.")

opp_crm = [prop("Opportunity", "opportunityId", "string", "Opportunity ID", nullable=False),
           prop("Opportunity", "name", "string", "Name", nullable=False),
           prop("Opportunity", "accountId", "string", "Account", "Foreign key to Account.", False),
           prop("Opportunity", "ownerId", "string", "Owner", "Foreign key to SalesRep."),
           prop("Opportunity", "stage", "string", "Stage",
                "prospecting | qualification | proposal | negotiation | closedWon | closedLost", False),
           prop("Opportunity", "amount", MONEY, "Amount", "Currency USD. JSON-encoded as a string."),
           prop("Opportunity", "closeDate", "date", "Expected close date"),
           prop("Opportunity", "probability", "double", "Win probability",
                "A represented estimate between 0 and 1, not a fact about the customer (report section 4.3)."),
           prop("Opportunity", "discountPct", "double", "Discount percent"),
           prop("Opportunity", "lastStageChangeAt", "timestamp", "Last stage change"),
           prop("Opportunity", "closedAt", "timestamp", "Closed at")]
opp_contract = [prop("Opportunity", "contractSigned", "boolean", "Contract signed",
                     "From the e-signature system datasource. Empty when that system has no row for this opportunity (report section 2, multi-datasource)."),
                prop("Opportunity", "contractSignedOn", "date", "Contract signed on")]
obj("Opportunity", "Opportunity", "Opportunities", "dollar", "#29A634", "opportunityId", "name", opp_crm + opp_contract,
    [dataset_ds("Opportunity", "opportunities", [p[0] for p in opp_crm]),
     dataset_ds("Opportunity", "esign-contracts", ["opportunityId"] + [p[0] for p in opp_contract])],
    "A possible sale. Two datasources: the CRM table and the e-signature system, joined column-wise on opportunityId.")

act_props = [prop("Activity", "activityId", "string", "Activity ID", nullable=False),
             prop("Activity", "subject", "string", "Subject", nullable=False),
             prop("Activity", "activityType", "string", "Type", "call | email | meeting | note", False),
             prop("Activity", "notes", "string", "Notes"),
             prop("Activity", "occurredAt", "timestamp", "Occurred at", nullable=False),
             prop("Activity", "loggedBy", "string", "Logged by", "User ID from currentUser."),
             prop("Activity", "contactId", "string", "Contact", "Foreign key to Contact."),
             prop("Activity", "opportunityId", "string", "Opportunity", "Foreign key to Opportunity.")]
obj("Activity", "Activity", "Activities", "comment", "#738091", "activityId", "subject", act_props,
    [{"rid": R("datasource", "Activity.edits-only"), "definition": {"type": "editsOnly"}}],
    "A call, email, meeting or note. Edits-only: created only by actions, no source table.")

# ---- links: (rid name, sideA type, sideA apiName, sideA card, sideA fk, sideB type, sideB apiName, sideB card, sideB fk)
def link(ridname, a, a_api, a_card, a_fk, b, b_api, b_card, b_fk, display_a, display_b):
    rid = R("link-type", ridname)
    sa = {"apiName": a_api, "displayName": display_a, "status": "ACTIVE", "objectTypeApiName": b, "cardinality": a_card, "linkTypeRid": rid}
    sb = {"apiName": b_api, "displayName": display_b, "status": "ACTIVE", "objectTypeApiName": a, "cardinality": b_card, "linkTypeRid": rid}
    if a_fk: sa["foreignKeyPropertyApiName"] = a_fk
    if b_fk: sb["foreignKeyPropertyApiName"] = b_fk
    OBJECTS[a]["linkTypes"].append(sa); OBJECTS[b]["linkTypes"].append(sb)

link("contact-account", "Contact", "account", "ONE", "accountId", "Account", "contacts", "MANY", None, "Account", "Contacts")
link("opportunity-account", "Opportunity", "account", "ONE", "accountId", "Account", "opportunities", "MANY", None, "Account", "Opportunities")
link("account-owner", "Account", "owner", "ONE", "ownerId", "SalesRep", "accounts", "MANY", None, "Owner", "Accounts")
link("lead-owner", "Lead", "owner", "ONE", "ownerId", "SalesRep", "leads", "MANY", None, "Owner", "Leads")
link("opportunity-owner", "Opportunity", "owner", "ONE", "ownerId", "SalesRep", "opportunities", "MANY", None, "Owner", "Opportunities")
link("lead-converted-account", "Lead", "convertedAccount", "ONE", "convertedAccountId", "Account", "sourceLeads", "MANY", None, "Converted account", "Source leads")
link("activity-contact", "Activity", "contact", "ONE", "contactId", "Contact", "activities", "MANY", None, "Contact", "Activities")
link("activity-opportunity", "Activity", "opportunity", "ONE", "opportunityId", "Opportunity", "activities", "MANY", None, "Opportunity", "Activities")
link("contact-opportunity", "Contact", "opportunities", "MANY", None, "Opportunity", "contacts", "MANY", None, "Opportunities", "Contacts")

# ---- interface + shared property type
SPT = {"rid": R("shared-property-type", "recordOwnerId"), "apiName": "recordOwnerId", "displayName": "Record owner",
       "description": "The SalesRep that owns the record.", "dataType": {"type": "string"}}
ISPT = {**SPT, "required": True, "type": "interfaceSharedPropertyType"}
INTERFACE = {"rid": R("interface-type", "OwnedRecord"), "apiName": "OwnedRecord", "displayName": "Owned record",
             "description": "A record that one sales rep owns. Used for 'my records' views and owner checks.",
             "properties": {"recordOwnerId": ISPT}, "allProperties": {"recordOwnerId": ISPT},
             "propertiesV2": {"recordOwnerId": ISPT},
             "allPropertiesV2": {"recordOwnerId": {"rid": R("interface-property-type", "OwnedRecord.recordOwnerId"),
                                                   "apiName": "recordOwnerId", "displayName": "Record owner",
                                                   "description": SPT["description"], "dataType": {"type": "string"},
                                                   "requireImplementation": True}},
             "extendsInterfaces": [], "allExtendsInterfaces": [],
             "implementedByObjectTypes": ["Account", "Lead", "Opportunity"],
             "links": {"owner": {"rid": R("interface-link-type", "OwnedRecord.owner"), "apiName": "owner", "displayName": "Owner",
                                 "linkedEntityApiName": {"type": "objectTypeApiName", "apiName": "SalesRep"},
                                 "cardinality": "ONE", "required": True}}}
INTERFACE["allLinks"] = INTERFACE["links"]
for ot in ["Account", "Lead", "Opportunity"]:
    o = OBJECTS[ot]
    o["implementsInterfaces"] = ["OwnedRecord"]
    o["implementsInterfaces2"] = {"OwnedRecord": {"apiName": "OwnedRecord", "rid": INTERFACE["rid"],
                                                  "properties": {"recordOwnerId": "ownerId"},
                                                  "propertiesV2": {"recordOwnerId": {"type": "localPropertyImplementation", "propertyApiName": "ownerId"}},
                                                  "links": {"owner": ["owner"]}, "actionTypes": {}}}
    o["sharedPropertyTypeMapping"] = {"recordOwnerId": "ownerId"}

# ---- actions
def param(display, dtype, required=True, allowed=None, desc=None):
    p = {"displayName": display, "dataType": dtype if isinstance(dtype, dict) else {"type": dtype}, "required": required}
    if desc: p["description"] = desc
    if allowed: p["validation"] = {"defaultValidation": {"allowedValues": allowed}}
    return p
OBJ = lambda t: {"type": "object", "objectApiName": t, "objectTypeApiName": t}
oneof = lambda *vals: {"type": "oneOf", "otherValuesAllowed": False, "options": [{"displayName": v, "value": v} for v in vals]}
pid = lambda p: {"type": "parameterId", "parameterId": p}
opv = lambda p, prop_: {"type": "objectParameterPropertyValue", "parameterId": p, "propertyTypeApiName": prop_}
static = lambda v: {"type": "staticValue", "value": v}
NOW, ME, UUID = {"type": "currentTime"}, {"type": "currentUser"}, {"type": "uniqueIdentifier"}

# local submission-criteria vocabulary (Palantir publishes no schema; templates and operators follow the docs page)
user_in = lambda *groups: {"type": "currentUser", "field": "groupIds", "operator": "includesAny", "value": {"static": list(groups)}}
user_is_owner = lambda p: {"type": "currentUser", "field": "userId", "operator": "is", "value": {"parameterId": p, "property": "ownerId"}}
owner_or_manager = lambda p: {"operator": "any", "conditions": [user_is_owner(p), user_in("sales-manager")],
                              "failureMessage": "Only the record owner or a sales manager can do this."}
SALES = {"operator": "all", "conditions": [user_in("sales-rep", "sales-manager")], "failureMessage": "Only sales users can do this."}

ACTIONS = {}
def action(api, display, desc, params, rules, ops, criteria, side_effects=None, tool=None):
    at = {"apiName": api, "displayName": display, "description": desc, "status": "ACTIVE", "parameters": params,
          "rid": R("action-type", api), "operations": ops}
    if tool: at["toolDescription"] = tool
    full = {"actionType": at, "fullLogicRules": rules, "x-localSubmissionCriteria": criteria}
    if side_effects: full["x-localSideEffects"] = side_effects
    ACTIONS[api] = full

STAGES_OPEN = ("prospecting", "qualification", "proposal", "negotiation")
FN = lambda name, inputs: {"type": "function", "functionRid": f"ri.function-registry.local.function.{name}",
                           "functionVersion": "1.0.0", "functionInputValues": {k: pid(k) for k in inputs}}

action("create-lead", "Create lead", "Create an unassigned lead with status 'new'.",
       {"fullName": param("Full name", "string", allowed={"type": "text", "gte": 1, "lte": 200}),
        "companyName": param("Company name", "string"),
        "email": param("Email", "string", allowed={"type": "text", "regex": "[^@ ]+@[^@ ]+\\.[^@ ]+",
                                                   "configuredFailureMessage": "Enter a valid email address."}),
        "leadSource": param("Lead source", "string", allowed=oneof("web", "referral", "event", "outbound"))},
       [{"type": "createObject", "objectTypeApiName": "Lead", "structPropertyArguments": {},
         "propertyArguments": {"leadId": UUID, "fullName": pid("fullName"), "companyName": pid("companyName"),
                               "email": pid("email"), "leadSource": pid("leadSource"), "status": static("new"),
                               "createdAt": NOW, "createdBy": ME}}],
       [{"type": "createObject", "objectTypeApiName": "Lead"}], [SALES],
       tool="Create a new unassigned sales lead.")

action("assign-lead", "Assign lead", "Assign a new lead to a sales rep if the rep is under their open-lead limit.",
       {"lead": param("Lead", OBJ("Lead")), "rep": param("Sales rep", OBJ("SalesRep"))},
       [FN("assignLead", ["lead", "rep"])],
       [{"type": "modifyObject", "objectTypeApiName": "Lead"}, {"type": "modifyObject", "objectTypeApiName": "SalesRep"}],
       [{"operator": "all", "conditions": [user_in("sales-manager")], "failureMessage": "Only a sales manager can assign leads."},
        {"operator": "all", "conditions": [{"type": "parameter", "parameterId": "lead", "property": "status", "operator": "is", "value": {"static": "new"}}],
         "failureMessage": "Only a lead with status 'new' can be assigned."}],
       tool="Assign a new lead to a sales rep. Fails if the rep already has maxOpenLeads open leads.")

action("convert-lead", "Convert lead", "Turn an assigned lead into an Account, a Contact and an Opportunity.",
       {"lead": param("Lead", OBJ("Lead")), "opportunityName": param("Opportunity name", "string"),
        "amount": param("Amount (USD)", "decimal", allowed={"type": "range", "gt": {"type": "static", "value": "0"}}),
        "closeDate": param("Expected close date", "date")},
       [FN("convertLead", ["lead", "opportunityName", "amount", "closeDate"])],
       [{"type": "createObject", "objectTypeApiName": "Account"}, {"type": "createObject", "objectTypeApiName": "Contact"},
        {"type": "createObject", "objectTypeApiName": "Opportunity"}, {"type": "modifyObject", "objectTypeApiName": "Lead"},
        {"type": "modifyObject", "objectTypeApiName": "SalesRep"},
        {"type": "createLink", "linkTypeApiNameAtoB": "opportunities", "linkTypeApiNameBtoA": "contacts",
         "aSideObjectTypeApiName": "Contact", "bSideObjectTypeApiName": "Opportunity"}],
       [{"operator": "all", "conditions": [{"type": "parameter", "parameterId": "lead", "property": "status", "operator": "is", "value": {"static": "assigned"}}],
         "failureMessage": "Only an assigned lead can be converted."}, owner_or_manager("lead")],
       tool="Convert an assigned lead into an account, contact and opportunity.")

action("advance-opportunity-stage", "Advance opportunity stage", "Move an open opportunity to another open stage.",
       {"opportunity": param("Opportunity", OBJ("Opportunity")),
        "newStage": param("New stage", "string", allowed=oneof(*STAGES_OPEN))},
       [{"type": "modifyObject", "objectToModify": "opportunity", "structPropertyArguments": {},
         "propertyArguments": {"stage": pid("newStage"), "lastStageChangeAt": NOW}}],
       [{"type": "modifyObject", "objectTypeApiName": "Opportunity"}],
       [owner_or_manager("opportunity"),
        {"operator": "none", "conditions": [{"type": "parameter", "parameterId": "opportunity", "property": "stage",
                                             "operator": "isIncludedIn", "value": {"static": ["closedWon", "closedLost"]}}],
         "failureMessage": "A closed opportunity cannot change stage."}])

action("apply-discount", "Apply discount", "Set the discount on an opportunity. 20% or more needs a sales manager.",
       {"opportunity": param("Opportunity", OBJ("Opportunity")),
        "discountPct": param("Discount percent", "double", allowed={"type": "range", "gte": {"type": "static", "value": 0},
                                                                  "lte": {"type": "static", "value": 50}})},
       [{"type": "modifyObject", "objectToModify": "opportunity", "structPropertyArguments": {},
         "propertyArguments": {"discountPct": pid("discountPct")}}],
       [{"type": "modifyObject", "objectTypeApiName": "Opportunity"}],
       [owner_or_manager("opportunity"),
        {"operator": "any", "conditions": [{"type": "parameter", "parameterId": "discountPct", "operator": "isLessThan", "value": {"static": 20}},
                                           user_in("sales-manager")],
         "failureMessage": "A discount of 20% or more needs a sales manager."}])

action("close-opportunity-won", "Close opportunity as won", "Close a negotiated opportunity that has a signed contract.",
       {"opportunity": param("Opportunity", OBJ("Opportunity"))},
       [{"type": "modifyObject", "objectToModify": "opportunity", "structPropertyArguments": {},
         "propertyArguments": {"stage": static("closedWon"), "probability": static(1.0), "closedAt": NOW}}],
       [{"type": "modifyObject", "objectTypeApiName": "Opportunity"}],
       [owner_or_manager("opportunity"),
        {"operator": "all", "conditions": [{"type": "parameter", "parameterId": "opportunity", "property": "stage", "operator": "is", "value": {"static": "negotiation"}}],
         "failureMessage": "Only an opportunity in 'negotiation' can close as won."},
        {"operator": "all", "conditions": [{"type": "parameter", "parameterId": "opportunity", "property": "contractSigned", "operator": "is", "value": {"static": True}}],
         "failureMessage": "The e-signature system has no signed contract for this opportunity."}],
       side_effects=[{"type": "webhook", "name": "notifyBilling", "timing": "afterEdits",
                      "idempotencyKey": {"parameterId": "opportunity", "property": "opportunityId"},
                      "inputs": {"opportunityId": opv("opportunity", "opportunityId"), "amount": opv("opportunity", "amount")},
                      "note": "Runs after the edits commit. It can fail after the user sees success (report section 6.3); the key prevents a duplicate invoice on retry."}],
       tool="Close an opportunity as won. Billing is notified after the commit; check its status before telling the user billing is done.")

action("log-activity", "Log activity", "Record a call, email, meeting or note against a contact.",
       {"contact": param("Contact", OBJ("Contact")), "opportunity": param("Opportunity", OBJ("Opportunity"), required=False),
        "activityType": param("Type", "string", allowed=oneof("call", "email", "meeting", "note")),
        "subject": param("Subject", "string", allowed={"type": "text", "gte": 1, "lte": 200}),
        "notes": param("Notes", "string", required=False)},
       [{"type": "createObject", "objectTypeApiName": "Activity", "structPropertyArguments": {},
         "propertyArguments": {"activityId": UUID, "activityType": pid("activityType"), "subject": pid("subject"),
                               "notes": pid("notes"), "occurredAt": NOW, "loggedBy": ME,
                               "contactId": opv("contact", "contactId"), "opportunityId": opv("opportunity", "opportunityId")}}],
       [{"type": "createObject", "objectTypeApiName": "Activity"}], [SALES])

action("add-contact-to-opportunity", "Add contact to opportunity", "Link a contact to an opportunity (many-to-many).",
       {"contact": param("Contact", OBJ("Contact")), "opportunity": param("Opportunity", OBJ("Opportunity"))},
       [{"type": "createLink", "linkTypeApiName": "opportunities", "sourceObject": "contact", "targetObject": "opportunity"}],
       [{"type": "createLink", "linkTypeApiNameAtoB": "opportunities", "linkTypeApiNameBtoA": "contacts",
         "aSideObjectTypeApiName": "Contact", "bSideObjectTypeApiName": "Opportunity"}],
       [owner_or_manager("opportunity")])

doc = {
    "ontology": {"apiName": "crm", "displayName": "CRM", "rid": R("ontology", "crm"),
                 "description": "Local Palantir-style CRM ontology for learning. Not a Palantir artifact."},
    "objectTypes": OBJECTS,
    "actionTypes": {k: v["actionType"] for k, v in ACTIONS.items()},
    "actionTypesFullMetadata": ACTIONS,
    "queryTypes": {},
    "interfaceTypes": {"OwnedRecord": INTERFACE},
    "sharedPropertyTypes": {"recordOwnerId": SPT},
    "valueTypes": {},
    "x-local": {
        "note": "Every key that starts with 'x-local' is local design. Remove them all to get Palantir's OntologyFullMetadata shape. RIDs are local placeholders.",
        "datasets": {DS(n): f"data/{n}.csv" for n in ["sales-reps", "accounts", "contacts", "leads", "opportunities", "esign-contracts", "opportunity-contacts"]},
        "linkDatasources": {R("link-type", "contact-opportunity"): {"datasetRid": DS("opportunity-contacts"),
                                                                     "columns": {"Contact": "contactId", "Opportunity": "opportunityId"}}},
        "functions": {f"ri.function-registry.local.function.{n}": {"version": "1.0.0", "entryPoint": f"functions.py:{e}"}
                      for n, e in [("assignLead", "assign_lead"), ("convertLead", "convert_lead")]},
        "users": [{"userId": "rep-ana", "displayName": "Ana (rep)", "groupIds": ["sales-rep"]},
                  {"userId": "rep-ben", "displayName": "Ben (rep)", "groupIds": ["sales-rep"]},
                  {"userId": "rep-eli", "displayName": "Eli (rep)", "groupIds": ["sales-rep"]},
                  {"userId": "rep-fay", "displayName": "Fay (rep)", "groupIds": ["sales-rep"]},
                  {"userId": "mgr-cara", "displayName": "Cara (manager)", "groupIds": ["sales-manager"]},
                  {"userId": "viewer-dan", "displayName": "Dan (viewer)", "groupIds": ["viewer"]}],
    },
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

# self-check: names, keys, link symmetry, rule references
import re
for api, o in OBJECTS.items():
    ot = o["objectType"]; assert re.fullmatch(r"[A-Z][A-Za-z0-9]{0,99}", api)
    assert ot["primaryKey"] in ot["properties"] and ot["titleProperty"] in ot["properties"]
    assert ot["properties"][ot["primaryKey"]]["dataType"]["type"] in ("string", "integer", "short")
    for p in ot["properties"]: assert re.fullmatch(r"[a-z][A-Za-z0-9]{0,99}", p)
    for l in o["linkTypes"]:
        assert l["objectTypeApiName"] in OBJECTS and (not l.get("foreignKeyPropertyApiName") or l["foreignKeyPropertyApiName"] in ot["properties"])
        assert sum(x["linkTypeRid"] == l["linkTypeRid"] for x in OBJECTS[l["objectTypeApiName"]]["linkTypes"]) == 1
for api, a in ACTIONS.items():
    ps = a["actionType"]["parameters"]; rules = a["fullLogicRules"]
    if any(r["type"] == "function" for r in rules): assert len(rules) == 1, "function rule must be the only rule"
    for r in rules:
        for arg in list(r.get("propertyArguments", {}).values()) + list(r.get("functionInputValues", {}).values()):
            assert arg.get("parameterId") is None or arg["parameterId"] in ps, (api, arg)
        for k in ("objectToModify", "sourceObject", "targetObject"):
            assert r.get(k) is None or r[k] in ps
        if r["type"] == "createObject":
            props = OBJECTS[r["objectTypeApiName"]]["objectType"]["properties"]
            assert set(r["propertyArguments"]) <= set(props)
print("OK", len(OBJECTS), "object types,", sum(len(o["linkTypes"]) for o in OBJECTS.values()) // 2, "link types,", len(ACTIONS), "action types")
