# CRM ontology — Palantir-style schema

A local CRM ontology written in Palantir Foundry's public metadata shape (`OntologyFullMetadata`). It is a learning artifact, not a Palantir product file. Research behind every field: `../research/palantir-public-model.md`.

## Files

| File | Job |
|---|---|
| `build_ontology.py` | The editable source. Run it to regenerate `ontology.json`. It also runs structural self-checks. |
| `ontology.json` | The generated schema (6 object types, 9 link types, 8 action types, 1 interface). |
| `make_data.py` | Generates the sample data `data/*.csv` (one file per dataset in `x-local.datasets`; columns come from `ontology.json`). Deterministic. Asserts integrity and the two planted defects. Then writes the raw source exports `data/raw/*.csv` (see "Raw layer"). |
| `clean_crm.py` | The transform: raw exports → the 7 clean datasets, one pandas function per output. Run it to assert that its output equals `data/*.csv`. |
| `check_ontology.py` | Removes all `x-local*` keys and validates the rest against Palantir's own SDK models (`foundry-platform-sdk` 1.108.0). It also fails on any unknown key, because the SDK models otherwise accept extra keys silently. |

    python build_ontology.py
    pip install foundry-platform-sdk
    python check_ontology.py
    python make_data.py
    python clean_crm.py

## Rule: `x-local` keys

Every key that starts with `x-local` is local design. Palantir publishes no schema for these parts. Remove all `x-local*` keys and the rest is Palantir's public shape. The check script proves this on each run.

| `x-local` key | Why it is local |
|---|---|
| `x-localSubmissionCriteria` (per action) | No public schema. Condition templates (current user, parameter) and operators (`is`, `isLessThan`, `includesAny`, `isIncludedIn`, all/any/none) follow the docs page wording. |
| `x-localSideEffects` (per action) | Webhook rules are not in the public API. |
| `x-localConflictResolution` (per object type) | The docs describe "Apply user edits" as the default; the API has no field for it. |
| `x-local.datasets` | Maps local dataset RIDs to CSV paths under `data/`. |
| `x-local.linkDatasources` | The API has no join-table field for many-to-many links. |
| `x-local.functions` | Maps function RIDs to Python functions. In Foundry these are published TypeScript or Python functions. |
| `x-local.users` | Users and groups, for `currentUser` and the criteria. |

All RIDs are local placeholders in Palantir's `ri.<service>.<instance>.<type>.<locator>` form.

## The CRM model

**Object types:** `SalesRep`, `Account`, `Contact`, `Lead`, `Opportunity`, `Activity`.
- `Opportunity` has two datasources: the CRM table and an e-signature system. They join column-wise on `opportunityId`. `contractSigned` is empty when the e-signature system has no row.
- `Activity` has an `editsOnly` datasource. Only actions create activities.
- `Account`, `Lead` and `Opportunity` implement the `OwnedRecord` interface through the shared property `recordOwnerId` → `ownerId`.

**Link types:** eight foreign-key links (many-to-one) and one many-to-many link, `Contact.opportunities` ↔ `Opportunity.contacts`.

**Action types, and the report lesson each one shows:**

| Action | Rules | Lesson |
|---|---|---|
| `create-lead` | `createObject` with `uniqueIdentifier`, `currentTime`, `currentUser`, `staticValue` | Logic rules only copy values. |
| `assign-lead` | one `function` rule | The function counts the rep's assigned leads when it runs, and it also writes the `SalesRep` as a guard object. Two managers assigning at once must conflict (report §8.4, write skew). See "Raw layer" for the decision. |
| `convert-lead` | one `function` rule | One action edits five object types. The function does not deduplicate accounts — identity resolution is a separate obligation (§4.1). |
| `advance-opportunity-stage` | `modifyObject` | Criteria block changes to closed deals. |
| `apply-discount` | `modifyObject` | Parameter range 0–50; 20% or more needs a manager (authorization versus validation, §2). |
| `close-opportunity-won` | `modifyObject` + side-effect webhook | Billing runs after commit and can fail; an idempotency key prevents a double invoice (§6.3). Needs data from the second datasource. |
| `log-activity` | `createObject` on an edits-only type | `objectParameterPropertyValue` copies keys from object parameters. |
| `add-contact-to-opportunity` | `createLink` | `createLink` works only on many-to-many links. |

## Checked and not checked

- **Checked:** Palantir's SDK models accept the stripped schema with zero unknown keys. The build script checks naming patterns, primary-key types, foreign keys, link symmetry, parameter references, and the rule "a function rule must be the only rule".
- **Not checked:** the SDK does not validate RID format, so the placeholder RIDs are not tested against a real format rule.
- **Naming choice, confirmed 2026-10-11:** action API names use kebab-case (`create-lead`). Foundry accepted all 8 names.
- **Built in Foundry instead of locally (2026-10-11):** the two functions are TypeScript v1 edit functions in the Foundry repo `crm-functions` (`../foundry/functions/index.ts`), not `functions.py`.

## Built in Foundry, and not built

Built on the Foundry Developer Tier (global branch `crm-ontology-v1`, 2026-10-10 to 2026-10-11): 7 raw datasets, 7 clean datasets (repo `crm-transforms`), 6 object types, 9 link types, 8 action types, 2 TypeScript functions (repo `crm-functions`), and 2 groups (`sales-rep`, `sales-manager`).

Identity rules as built (the local `x-localSubmissionCriteria` say "current user is `<record>.ownerId`", but `ownerId` holds CRM ids such as `rep-ana`, not Foundry user ids):
- `SalesRep.foundryUserId` maps a rep to a Foundry user. The transform fills it (`FOUNDRY_USERS` in `../foundry/transforms/crm.py`); only `rep-ana` has a user.
- Criteria cannot follow links. So each owner-checked action has an optional object parameter `owner` (SalesRep) and the rule ANY( current user in `sales-manager`, ALL( `owner.foundryUserId` = current user id, `owner.salesRepId` = `<record>.ownerId` ) ). The second condition binds `owner` to the record, so a caller cannot pass someone else's rep.
- `assign-lead`: managers only. `convert-lead`, `advance-opportunity-stage`, `apply-discount`, `close-opportunity-won`, `add-contact-to-opportunity`: owner or manager. `create-lead`, `log-activity`: members of `sales-rep` or `sales-manager`.
- `apply-discount`: `discountPct` is required, range 0–50 inclusive (parameter constraint), and ANY( current user in `sales-manager`, `discountPct` < 20 ).

Tested 2026-10-11 on the branch (Platform API, validate-only). As a member of `sales-rep` only (the test user = `rep-ana`): own record with `owner` = `rep-ana` VALID; no `owner`, another rep's record, or `owner` = `rep-fay` INVALID "Only the record owner or a sales manager can do this."; discount 10 VALID, 25 INVALID "A discount of 20 or more needs a sales manager.", 60 also fails the 0–50 range; `assign-lead` INVALID "Only a sales manager can assign leads."; `create-lead` VALID. In no group: `create-lead` INVALID "Only a sales rep or a sales manager can do this." As a manager: all VALID except discount 60.

Not built, by decision on 2026-10-11:
| Item | Why |
|---|---|
| `OwnedRecord` interface | No action needs it. Learning value only. |
| Field checks: email regex, text length; `uniqueIdentifier` / current time / current user on `create-lead` and `log-activity` | Left out of this build. `leadId` and the `log-activity` values stay typed parameters. |
| Concurrency test of `assign-lead` | Needs two calls at the same moment. Snapshot isolation and the guard write are configured, but no test proves the conflict. |
| `notifyBilling` webhook on `close-opportunity-won` | No billing system exists to call. |

## Sample data and planted defects

`make_data.py` writes 4 sales reps, 20 accounts, 40 contacts, 30 leads (10 new, 8 assigned, 8 converted, 4 disqualified), 25 opportunities, 7 e-signature rows and 38 contact-opportunity link rows. `Activity` has no file: it is edits-only.

| Planted item | Where | Lesson |
|---|---|---|
| Duplicate company | `acct-019` "Northwind Traders" and `acct-020` "Northwind Traders, Inc.": same website, different owners. Leads `lead-025` and `lead-026` were converted separately. | `convert-lead` does not deduplicate; identity resolution is a separate job (§4.1). |
| Missing contract row (defect) | `opp-025` is `closedWon`, but `esign-contracts.csv` has no row, so `contractSigned` is empty. | A second datasource can disagree with the first; the ontology shows the gap. |
| Rep at limit (not a defect) | `rep-fay`: `openLeadCount` 3 = `maxOpenLeads` 3. | `assign-lead` to her must fail. |
| Contract states (not defects) | `opp-014`, `opp-015` negotiation + signed; `opp-016` negotiation + unsigned; `opp-017`, `opp-018` negotiation + no row. | Only `opp-014` and `opp-015` pass the `close-opportunity-won` criteria. |

## Raw layer

In Foundry, data does not go straight into the ontology. A source system exports raw data, a transform cleans it, and the object types read the clean output. `data/raw/` holds what two source systems export: a CRM (6 files) and an e-signature system (1 file). That is 201 raw rows. `clean_crm.py` turns them into the 164 clean rows in `data/*.csv`. The clean files are the known answer, and the script asserts an exact match.

The two CRM extracts overlap. `_extracted_at` is `2026-09-15T00:00:00.000+0000` (full extract) or `2026-10-01T00:00:00.000+0000` (incremental extract). A record changed after 15 September is in both, and the older row has old values. The raw row order is random, so position tells you nothing.

| Mess | Where (rows) | Cleaning rule | What breaks if you skip it |
|---|---|---|---|
| Overlapping extracts | 19 stale versions: 3 accounts (old owner), 4 contacts (old title), 7 leads (still `new`), 5 opportunities (previous stage) | Keep the newest `LastModifiedDate` per `Id` | Duplicate primary keys: the object type cannot use the dataset. If you keep the oldest version instead, `rep-fay` has 0 open leads, not 3, and `assign-lead` to her wrongly succeeds. |
| Soft delete | `acct-900` test account (live in the full extract, deleted in the incremental), 1 contact role | Dedupe first, *then* drop `IsDeleted = true` | Filter first and the older, undeleted `acct-900` row survives. |
| Users who are not reps | `mgr-cara` (manager), `usr-sync` (integration), `rep-gil` (inactive rep) | Keep `Profile = Sales Rep` and `IsActive = true` | Three false `SalesRep` objects. |
| Picklist labels | Lead `Status` and `LeadSource` (37 rows each), opportunity `StageName` (30) | Map labels to API values (`Closed Won` → `closedWon`) | Action criteria compare with API values and never match. |
| Queue as owner | 17 lead rows owned by `queue-unassigned` | Queue → empty `ownerId` | A link to a `SalesRep` that does not exist. |
| Null tokens | `ConvertedAccountId`: 15 `NULL`, 14 empty | Both → empty | A link to an account called `NULL`. |
| Derived columns | `fullName` (first + last), `closedAt` (7 closed deals), `probability` (percent → fraction), `openLeadCount` (counted from clean leads) | Compute in the transform | Missing or wrong properties. |
| Format noise | 18 websites, 4 names with trailing spaces, 15 + 9 emails in upper case or with spaces, 33 phones in 4 formats, 2 regions in the wrong case, integer money, CRM timestamps `…000+0000`, e-signature dates `MM/DD/YYYY HH:MM` | Normalize | Search, joins and the identity check do not match. |
| One row per role | 8 contact-opportunity pairs have a second role | Keep distinct (contact, opportunity) pairs | Duplicate rows in the many-to-many link table. |
| Second source system | Envelopes: 7 `deal_ref` values in free text (`OPP-014`, `Opp 14`), 2 voided, 1 declined then resent, 1 for a deal the CRM does not know (`OPP-031`) | Normalize the reference, drop voided and unknown, keep the latest envelope per deal | Wrong `contractSigned`. `opp-017` (only envelope voided) must get no row. |

**Not cleaned on purpose:** the Northwind duplicate (`acct-019`, `acct-020`) and the missing contract for `opp-025`. Cleaning fixes format and provenance. Deciding that two records are one company is identity resolution, a separate job (§4.1). `clean_crm.py` asserts both items pass through.

**Proof that the check works:** 8 deliberate bugs, one at a time, each make `clean_crm.py` fail: keep the oldest version, no dedupe, filter deletes before dedupe, keep voided envelopes, keep unknown deals, keep all users, keep the queue as owner, do not derive `closedAt`.

**Decision (2026-10-10, option 3): `openLeadCount` has one writer, the transform.** It is a read-only CRM view. The `assign-lead` function does not edit it. To check the limit, the function counts the rep's linked leads with status `assigned` when it runs; those leads already include the Foundry edits. Rejected: (1) the action does not update the count, so between builds the guard misses Foundry assignments; (2) the count is edit-only, so CRM changes never reach it. The old design had two writers. After a rebuild, the transform value and the action edit could differ, and Foundry's default ("Apply user edits") kept the edit over a newer CRM value.

**Consequence for write skew (§8.4), not tested on Foundry:** in snapshot mode Foundry checks conflicts only on objects that an action writes (report D18, [S20]). Two managers who assign two different leads to `rep-ben` at the same time write two different `Lead` objects, so neither action conflicts and Ben can go over his limit. The guard must also write the `SalesRep`, for example an edit-only property that each assignment changes. Then the second action conflicts and retries against the new count.
