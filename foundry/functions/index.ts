import { Double, Edits, LocalDate, OntologyEditFunction, Timestamp, UserFacingError } from "@foundry/functions-api";
import { Account, Contact, Lead, Objects, Opportunity, SalesRep } from "@foundry/ontology-api";

// Edit functions behind the assign-lead and convert-lead actions (crm_ontology/ontology.json).
export class CrmFunctions {

    // Counts the rep's assigned leads when it runs (openLeadCount is a transform snapshot, never edited).
    // Writes rep.lastLeadAssignedAt as a guard: two concurrent assignments to one rep edit the same object and conflict.
    @Edits(Lead, SalesRep)
    @OntologyEditFunction()
    public async assignLead(lead: Lead, rep: SalesRep): Promise<void> {
        if (lead.status !== "new") {
            throw new UserFacingError(`Only a lead with status 'new' can be assigned. ${lead.leadId} is '${lead.status}'.`);
        }
        const open = await Objects.search().lead()
            .filter(l => l.ownerId.exactMatch(rep.salesRepId))
            .filter(l => l.status.exactMatch("assigned"))
            .count();
        const max = rep.maxOpenLeads ?? 0;
        if ((open ?? 0) >= max) {
            throw new UserFacingError(`${rep.salesRepId} already has ${open} of ${max} open leads.`);
        }
        lead.ownerId = rep.salesRepId;
        lead.status = "assigned";
        rep.lastLeadAssignedAt = Timestamp.now();
    }

    // One lead becomes an Account, a Contact and an Opportunity. No account deduplication (identity resolution is separate).
    // ponytail: ids derive from the lead id; a lead converts once, so they cannot collide.
    // owner is read only by the action criteria (owner.salesRepId is lead.ownerId, current user is owner.foundryUserId).
    @Edits(Lead, Account, Contact, Opportunity)
    @OntologyEditFunction()
    public convertLead(lead: Lead, opportunityName: string, amount: Double, closeDate: LocalDate, owner?: SalesRep): void {
        if (lead.status !== "assigned") {
            throw new UserFacingError(`Only an assigned lead can be converted. ${lead.leadId} is '${lead.status}'.`);
        }
        if (!(amount > 0)) {
            throw new UserFacingError("Amount must be greater than 0.");
        }
        const now = Timestamp.now();

        const account = Objects.create().account(`acct-${lead.leadId}`);
        account.name = lead.companyName;
        account.ownerId = lead.ownerId;
        account.createdAt = now;

        const contact = Objects.create().contact(`ct-${lead.leadId}`);
        contact.fullName = lead.fullName;
        contact.email = lead.email;
        contact.accountId = account.accountId;

        const opp = Objects.create().opportunity(`opp-${lead.leadId}`);
        opp.name = opportunityName;
        opp.accountId = account.accountId;
        opp.ownerId = lead.ownerId;
        opp.stage = "prospecting";
        opp.probability = 0.1;
        opp.amount = amount;
        opp.closeDate = closeDate;
        opp.discountPct = 0;
        opp.lastStageChangeAt = now;
        opp.contacts.add(contact);

        lead.status = "converted";
        lead.convertedAccountId = account.accountId;
    }
}
