# The AI Diligence Scorecard

## A pre-acquisition assessment of AI readiness and value-creation potential

This scorecard answers the question a deal team actually has: if we buy this company, how
much value can AI-enabled operations create, how fast, and what will get in the way. It is
designed to run in two to three weeks, during diligence or in the first month of
ownership, using artifacts the target can produce without heroics. It pairs with the
[Enterprise AI Playbook](ENTERPRISE_AI_PLAYBOOK.md): the scorecard decides whether and
where to deploy the FDE pod; the playbook governs what the pod does once deployed.

Two rules keep the output honest. First, every score must cite evidence: a document
reviewed, a system inspected, a query run, a person interviewed. A score based on what
management said in a pitch meeting is marked *claimed*, not *verified*, and claimed scores
are capped at 3 until verified. Second, the assessor must put hands on the systems. Ask
for a schema dump and read it. Pull a hundred customer records and count the duplicates.
Request an API token and attempt the export yourself. In my experience the gap between
the architecture diagram and the database is where diligence findings live.

---

## How to run it: the two-to-three-week engagement

**Week 1 — the data room and the interviews.** Request the artifact list below on day
one. While it arrives, run sixty-minute interviews: CTO or VP Engineering, the most senior
individual-contributor engineer (not the same conversation), the support leader, the
professional-services or delivery leader, a GTM operations owner, and the CFO or
controller for unit-cost data. Interview the senior IC separately because the org chart
answers and the codebase answers usually differ, and the difference is itself a finding.

Artifact request list:

| Artifact | What it reveals |
|---|---|
| Schema dumps or ERDs for the top 3 operational databases | Fragmentation, homegrown compensation layers, where the truth lives |
| List of production systems (CRM, billing, ticketing, PSA, data warehouse) with owner and record counts | Integration surface, shadow systems |
| API documentation, or evidence of export paths per system | Whether data is reachable without a rescue project |
| Last 6–12 months of ticketing/support metrics | Volume, categories, resolution time; also data quality of the ticket system itself |
| Engineering metrics as they exist (deploy logs, sprint history) | DORA-ish baseline feasibility; what instrumentation already exists |
| Current AI tool inventory and spend (seats, usage reports if available) | Adoption reality vs. procurement theater |
| Org chart for engineering, support, PS, and RevOps with tenure | Key-person concentration, capacity |
| Any data processing agreements / customer contracts' data clauses | Rights to process customer data with AI at all |

**Week 2 — hands-on verification.** Sample records across two systems and attempt to
join them (the entity-resolution reality check). Run the export paths. Read twenty
recent support tickets end to end. Watch one PS delivery task and one engineering task
being done, with a stopwatch mentality: where do minutes actually go. Score sections A
through D as you go.

**Week 3 — scoring, opportunity sizing, and the one-page output.** Complete the leverage
map, apply the rubric, size the top three opportunities, write the red flags, and deliver
the one-pager plus this scored workbook as backup.

For a pre-LOI setting with no system access, run weeks 1 and 3 only, mark everything
*claimed*, and treat the output as a screening view to be verified post-close.

---

## Scoring conventions

Every item scores 1 to 5 against the anchors given. Anchors describe observable states,
not sentiments. Half points are allowed; gut feel is not. Each section averages its items,
and section scores feed the rubric at the end. Red flags are recorded separately and can
cap the overall tier regardless of scores, because a deal-breaker buried in an average is
how diligence fails.

---

## Section A: Data readiness

The single best predictor of AI value-creation speed. Models are rented; the data estate
is what you actually bought.

### A1. Schema fragmentation

How many places does the same business fact live, and do they agree?

| Score | Observable state |
|---|---|
| 1 | The same customer/product/transaction exists in 4+ systems with no shared key; reconciliation is a human's job title |
| 2 | 3+ systems of record, joins possible only through exported spreadsheets |
| 3 | 2–3 systems with partial shared keys; joins work for ~80% of records, the rest is tribal knowledge |
| 4 | Clear system of record per domain; other systems sync from it, with known lag and documented exceptions |
| 5 | Single source of truth per domain, enforced keys, documented lineage |

Verification: pick one customer and trace them through every system. Count the name
variants, the ID formats, the conflicting fields. Twenty minutes of this outperforms any
interview answer. Note that a low score here is not a kill signal; it is a costing
signal. The reference implementation in this repository exists precisely because
mid-market data looks like a 2, and an interoperability layer can normalize around it.
But the effort must be priced into the value-creation plan.

### A2. Integration surface

Can software get to the data without a rescue project?

| Score | Observable state |
|---|---|
| 1 | Core data locked in a vendor system with no API and no export, or in a homegrown system only one person understands |
| 2 | Exports exist but are manual (someone downloads CSVs monthly); no API access to the operational core |
| 3 | APIs or scheduled exports exist for most systems, undocumented or rate-crippled; a warehouse exists but is stale |
| 4 | Documented APIs or reliable replication for all major systems; warehouse refreshed daily |
| 5 | Governed warehouse or lakehouse as the analytical spine, near-real-time, with access controls that would survive an audit |

Verification: request read credentials and pull data yourself during week 2. The time it
takes the company to provision safe access is itself a measurement.

### A3. Data quality

Duplicates, staleness, free-text sprawl, and missing values in the fields that matter.

| Score | Observable state |
|---|---|
| 1 | Sampled records show >20% duplicates or critical-field nulls; free text hides structured facts everywhere; nobody is surprised |
| 2 | 10–20% defect rate in sampled critical fields; known-bad legacy segments nobody has cleaned |
| 3 | 5–10% defect rate; quality issues known, listed, and worked around consistently |
| 4 | <5% defects in critical fields; validation at entry; periodic cleanup actually happens |
| 5 | Quality metrics monitored on dashboards someone looks at; defects have owners and SLAs |

Verification: sample 100+ records from the two most important tables and count. Report
the number, not an adjective.

### A4. Data ownership and rights

Can this company legally and contractually run AI over the data it holds?

| Score | Observable state |
|---|---|
| 1 | Customer contracts silent or prohibitive on data processing; regulated data (PHI, PCI, PII) handled without corresponding controls |
| 2 | Rights unclear; DPAs inconsistent across the customer base; legal review never done |
| 3 | Rights exist for most of the base; a known list of restrictive contracts; regulated data identified and segregated |
| 4 | Standard contracts permit processing including via subprocessors; vendor DPAs in place; a human owns this question |
| 5 | Clean rights across the base, documented subprocessor chain, and a working approval path for new processing purposes |

This item is scored with counsel, not instead of counsel. In healthcare and financial
verticals, a 2 here reshapes the entire plan toward local or private-deployment models,
which is an architecture decision with real cost implications, not a footnote.

---

## Section B: The AI leverage map

Section A says whether AI can run; Section B says where it pays. Inventory the candidate
workflows in each function, then score each candidate on ROI potential and implementation
risk. The output is a ranked shortlist, and the top of that list becomes the FDE pod's
Day-30 workflow selection if the deal proceeds.

### Where to look, by function

**Engineering SDLC.** Test generation and coverage expansion, boilerplate and scaffold
generation, code review assistance, migration and upgrade work, documentation, incident
summarization. Ask: what fraction of engineering time goes to work an experienced engineer
would call mechanical? In most 20–40 person teams the honest answer is 30–50%.

**Professional services and delivery.** Customer onboarding, data migration into the
product, configuration, report building. This is frequently the highest-EBITDA target in
vertical SaaS because PS is labor sold at a loss or break-even to protect ARR, and every
hour removed is margin or capacity. Look for: repetitive migrations from the same handful
of legacy competitor systems, template-able configuration, and backlog (if onboarding is
the bottleneck to revenue recognition, automation is revenue acceleration, not just cost).

**Support.** Triage and routing, draft responses grounded in the actual knowledge base,
known-issue detection, deflection via self-serve answers. Score the knowledge base
separately: AI-drafted support answers are only as good as the corpus behind them, and a
stale KB turns this opportunity from a quarter into a year. Also inspect ticket
categories: if 40% of volume is "how do I," that is deflectable; if 40% is "your product
is broken," the opportunity is in engineering, not support tooling.

**GTM.** Lead enrichment and routing, call summarization into the CRM, proposal and
security-questionnaire drafting, renewal-risk signals from usage and support data. GTM
scores high on feasibility and low on differentiation; it is rarely the first workflow
but often the easy second one once the data layer exists.

### Scoring each candidate workflow

Score ROI potential and implementation risk separately, 1–5 each.

**ROI potential** considers: annual labor hours in the workflow × loaded rate; error and
rework cost; revenue effect if the workflow gates revenue (onboarding backlog, quote
turnaround); and scalability (does the saving grow with the business or is it a fixed
pool).

**Implementation risk** considers: data readiness of the specific systems this workflow
touches (inherit from Section A); nondeterminism tolerance (is a wrong answer cheap, or
must every output be human-gated, and does a human gate still leave positive economics);
integration complexity; and change-management load (how many people must alter daily
habits for the value to appear).

Plot the candidates on the 2×2. The plan writes itself from the quadrants:

| | Low implementation risk | High implementation risk |
|---|---|---|
| **High ROI** | Do first (pod's Day-30 selection) | Do second, after the rails exist |
| **Low ROI** | Quick wins for trust-building only; time-box them | Do not do; revisit at next annual review |

A note from operating experience: the first workflow should also pass the trust test from
the playbook — boring, frequent, and human-gated. A high-ROI workflow that terrifies the
team is a second workflow, not a first one.

---

## Section C: Tech debt versus AI leverage

Every target has tech debt, and every management team will tell you AI must wait until
the replatform ships. Sometimes true. Usually a stall. This section makes the call
analytically.

Ask four questions about the specific debt in question:

**1. Does the debt block data access, or just offend engineers?** A monolith with an
ugly codebase but a reachable database does not block AI enablement at all; the
interoperability layer reads the data regardless of how unfashionable the code is.
Debt blocks AI only when it blocks *data*: no export path, no API, a datastore that
cannot be queried safely in production hours.

**2. Does the debt amplify errors?** When I took over IBM API Connect, the product ran
on Cassandra with a homegrown compensation layer that could not maintain transaction
integrity, and it corrupted customer data badly enough that engineers spent multi-hour
calls walking customers through manual fixes. Automating workflows *on top of* a storage
layer like that would have multiplied the corruption at machine speed. That is plumbing
you fix first, and we did (the move to Postgres). The test: if the underlying system
silently produces wrong state, automation amplifies the damage; if it merely produces
slow or ugly state, automation can proceed in parallel with the cleanup.

**3. Is there a route around?** Fragmented and messy data is routable: deterministic
entity resolution plus a normalization layer handles the mess at read time, which is
exactly what the [reference implementation](../src) demonstrates. A missing system of
record is not routable; you cannot normalize data that was never captured.

**4. What does sequencing cost?** Price both paths over 18 months: replatform-then-AI
versus AI-on-a-normalization-layer with replatforming in parallel. The second path is
usually 2–3x faster to first value, and the normalization layer's schema mapping becomes
a design input for the eventual replatform rather than throwaway work.

| Score | Observable state |
|---|---|
| 1 | Debt blocks data access AND amplifies errors; core datastore integrity is suspect (fix plumbing first, and price it into the deal) |
| 2 | Debt blocks access to the highest-value workflow's data specifically; routes exist for lesser workflows |
| 3 | Debt is real but routable; normalization layer required; replatform can run in parallel |
| 4 | Debt is cosmetic to AI purposes; data reachable and trustworthy despite it |
| 5 | No debt materially relevant to the leverage map |

---

## Section D: Team readiness

Technology diligence is table stakes; the engagements that fail, fail on people.

### D1. Skills

| Score | Observable state |
|---|---|
| 1 | No engineer has shipped anything with an LLM API; no internal experimentation visible in the codebase or Slack |
| 2 | Isolated tinkering by 1–2 engineers, nothing in production; skills concentrated in people who look likely to leave |
| 3 | Copilot-class tools in real use by a third of the team; one internal AI feature or tool shipped, however small |
| 4 | Multiple engineers comfortable with LLM APIs, prompting, and basic evaluation; an internal workflow already automated |
| 5 | The team has production AI features with monitoring and evals, and could critique this scorecard's methodology |

### D2. Culture and appetite

The trust problem is the adoption problem. Probe for it directly in interviews: ask an
engineer what they think of AI code tools and listen for whether the answer is curiosity,
fear for their job, or contempt. All three are workable, but each needs a different
opening move, and contempt from the *most respected* senior engineer is a real project
risk because teams follow their strongest IC, not their org chart.

| Score | Observable state |
|---|---|
| 1 | Open hostility or fear at the senior IC level; leadership mandates tools top-down without using them |
| 2 | Polite compliance, no pull; "we bought seats" is the whole story; utilization data (if any) shows <20% weekly active |
| 3 | Genuine curiosity in pockets; at least one credible internal champion; leadership talks about it more than uses it |
| 4 | Broad willingness, visible experiments, leaders who have personally used the tools on real work |
| 5 | Team already treats AI as ordinary tooling with appropriate skepticism; asks about evals and cost before being prompted |

### D3. Key-person risk

| Score | Observable state |
|---|---|
| 1 | One person holds the schema knowledge, the integration credentials, or the homegrown system; they are also the most likely departure |
| 2 | 2–3 single points of failure across data, infra, and the core product |
| 3 | Key knowledge concentrated but documented enough that a strong hire could absorb it in a quarter |
| 4 | Redundancy on all critical systems; documentation maintained; onboarding a new senior engineer takes weeks, not quarters |
| 5 | No individual whose departure would stall the AI plan by more than a sprint |

Flag specifically: the person who "owns the data" in a 1 or 2 is either the future named
owner of the first workflow or the future bottleneck that kills it. Diligence should form
a view on which, because the difference is worth real money.

### D4. Leadership engagement

| Score | Observable state |
|---|---|
| 1 | Executive sponsor cannot describe a single workflow in their own operation that could be automated; delegates the whole topic |
| 2 | Enthusiastic but abstract; no personal tool use; expects a vendor to "bring AI" |
| 3 | Has used the tools personally at least somewhat; can name 2–3 candidate workflows; willing to protect team time |
| 4 | Hands-on enough to have opinions grounded in use; will commit named people and time in writing |
| 5 | Already operating a measured AI initiative and looking for acceleration, not conversion |

---

## The scoring rubric

Compute section scores (average of items), then the weighted composite:

| Section | Weight |
|---|---|
| A. Data readiness | 35% |
| B. Leverage map (average ROI-potential score of the top 3 candidates) | 25% |
| C. Tech debt vs. leverage | 15% |
| D. Team readiness | 25% |

**Maturity tiers:**

| Composite | Tier | Meaning for the deal team |
|---|---|---|
| ≥ 4.0 | **Tier 1 — Ready** | FDE pod deploys at close; first-value inside 90 days per the playbook; AI plan can be underwritten in the model |
| 3.0–3.9 | **Tier 2 — Ready with paving** | Deploy the pod with a data-normalization first phase; first value 90–150 days; underwrite conservatively |
| 2.0–2.9 | **Tier 3 — Plumbing first** | 1–2 quarters of targeted foundation work (led by a fractional data engineer, not the full pod) before the playbook starts; AI upside is real but back-half of the hold |
| < 2.0 | **Tier 4 — Not now** | AI enablement is not a value-creation lever for this asset in the next 12 months; if the thesis depends on it, that is a price conversation |

**Red flags (recorded regardless of scores; each caps the tier as noted):**

| Red flag | Cap |
|---|---|
| Data rights do not permit AI processing for a material customer segment (A4 ≤ 2 in a regulated vertical) | Tier 3 until cured |
| Core datastore integrity is suspect (the Cassandra test: C = 1) | Tier 3; fix priced into the deal |
| Single point of failure who is a flight risk holds the data estate (D3 = 1) | Tier 2 max; retention package before close |
| Most-respected senior IC is openly hostile and leadership will not engage the problem | Tier 2 max |
| No executive will commit named people and protected time in writing | Tier 3; this is the "sponsorship without ownership" anti-pattern pre-detected |
| Material AI-washing: product marketed as AI-powered but diligence finds rules or offshore labor | Not a tier cap; a rep-and-warranty conversation |

### Sizing the top three opportunities

For each of the top three candidates from the leverage map, estimate annual EBITDA
impact as a range, built bottom-up and deliberately conservative:

1. Baseline the workflow's annual cost: hours × loaded rate, plus error/rework cost,
   from the CFO's numbers, not the vendor's calculator.
2. Apply an automation fraction consistent with a human-in-the-loop design (rarely above
   60% for a first-year estimate, whatever the demo suggested).
3. Apply an adoption haircut (50–75% of theoretical in year one).
4. Subtract run costs: tokens/API, tooling, and the review time the guardrails require.
5. Only count labor that is actually redeployed or avoided (hiring deferrals, backlog
   conversion, overtime elimination). Capacity that just becomes slack is not EBITDA.

State every range with its assumptions attached. A deal team that can recompute your
number will trust it; one that can't, won't, and shouldn't.

### The one-page output

The deliverable is one page: tier and composite score with the section bars; the top
three opportunities, each with its EBITDA range and first-90-days feasibility note; red
flags with their caps; and the recommended motion (deploy pod now / pave first / plumbing
first / pass). Everything behind it is this workbook, filled in, with evidence citations.

---

# Worked example: "Kestrel Systems" (fictional)

*Vertical SaaS for specialty equipment rental operators. $20M ARR, ~2,400 customers, 145
employees: 32 engineering, 22 support, 14 professional services, 11 sales/marketing.
EBITDA ~$2.8M. Every company, person, and number below is invented; the pattern is not.*

## Section scores

### A. Data readiness — 2.6

**A1 Schema fragmentation: 2.5** *(verified)*. Customer truth lives in four places:
the product's Postgres database, Salesforce, a Zendesk instance, and QuickBooks for
billing. Salesforce and Postgres share an account ID for customers onboarded after 2021;
the ~900 older accounts joined by company name, and week-2 sampling found the same
operator as "Blue Ridge Equipment Rental," "Blue Ridge Eqpt," and "BRER LLC" across
systems. Support tickets link by contact email, which fails for multi-location operators.

**A2 Integration surface: 3.0** *(verified)*. Product Postgres is reachable (read
replica provisioned for us in two days, a good sign). Salesforce and Zendesk have
standard APIs. QuickBooks data reaches the warehouse via a manual monthly CSV export
performed by the controller. The "warehouse" is a BigQuery project one data engineer
built; refreshed nightly for product data, monthly for finance.

**A3 Data quality: 2.5** *(verified)*. Sampled 150 accounts: 12% duplicates, 18% missing
or stale primary-contact fields. Equipment catalog entries are free-text in ways that
break reporting ("CAT 320", "Caterpillar 320 excavator", "320 CAT EXC"). Support ticket
categorization abandoned in 2023; 60% of tickets tagged "general."

**A4 Data ownership: 3.5** *(claimed, counsel review pending)*. Standard MSA permits
processing and subprocessors; 14 enterprise contracts have custom data clauses needing
individual review; no regulated data classes beyond ordinary PII.

### B. Leverage map — top candidates scored

| Candidate workflow | Function | ROI potential | Impl. risk | Quadrant |
|---|---|---|---|---|
| Onboarding data migration (competitor system → Kestrel) | PS | 4.5 | 2.5 | Do first |
| Support triage + drafted responses | Support | 3.5 | 2.5 | Do first/second |
| Test coverage expansion + boilerplate generation | Eng SDLC | 3.0 | 2.0 | Quick win |
| Quote/proposal drafting for enterprise deals | GTM | 2.5 | 2.0 | Quick win |
| Automated equipment-catalog normalization | Product | 3.0 | 3.5 | Second wave |

The PS finding is the headline. Kestrel onboards ~320 new customers a year; each requires
migrating rental history, customer lists, and equipment catalogs from one of five legacy
competitor systems. The migration is done by hand in spreadsheets by the 14-person PS
team, takes 3–6 weeks per customer, and is the stated bottleneck on new-logo revenue
recognition (sales confirms a ~7-week onboarding queue). Five source systems, high
volume, same transformation every time: this is a paved-road candidate, and it is the
Day-30 selection if the pod deploys. Support is the second wave: 4,100 tickets/month,
but the knowledge base was last curated in 2023, so drafted-response quality would
plateau fast without a KB rebuild running alongside (priced into the range below).

**Section B score (avg ROI potential of top 3): 3.7**

### C. Tech debt vs. leverage — 3.5

The product is a 10-year-old Django monolith the engineers apologize for. It does not
matter for this purpose: the database is sane Postgres, reachable, and transactionally
trustworthy (passes the Cassandra test). The genuinely blocking debt is narrow: the
QuickBooks manual export makes billing data monthly-stale, which degrades any workflow
touching unit economics; fixing that integration is a two-week task that should precede
the pod. Route-around exists for everything else via a normalization layer.

### D. Team readiness — 2.9

**D1 Skills: 2.5** *(verified)*. Two engineers have Copilot seats they use daily; one
built an internal ticket-summarizer prototype nobody productionized. No eval experience.

**D2 Culture: 3.0** *(verified)*. Genuine curiosity in the majority; the senior platform
engineer (11-year tenure, the codebase's memory) is skeptical but engaged — his stated
objection is reliability, not ideology, which is workable; he is a future ally if the
first workflow ships with real evals, and the pod should pair with him first.

**D3 Key-person risk: 2.0** *(verified)*. The BigQuery warehouse, the QuickBooks export
knowledge, and the Salesforce admin credentials all concentrate in one data engineer,
who is also the only person who understands the legacy account-ID history. She is
engaged and has no stated flight intent, but there is no redundancy. Retention package
recommended before close; she is also the obvious named owner for the data layer.

**D4 Leadership: 4.0** *(verified)*. The CTO uses Claude and Copilot personally, named
three candidate workflows unprompted (two matched our leverage map), and offered in
writing to allocate two engineers half-time. The CEO defers to the CTO credibly.

## Composite and tier

| Section | Score | Weight | Contribution |
|---|---|---|---|
| A. Data readiness | 2.6 | 35% | 0.91 |
| B. Leverage map | 3.7 | 25% | 0.93 |
| C. Debt vs. leverage | 3.5 | 15% | 0.53 |
| D. Team readiness | 2.9 | 25% | 0.73 |
| **Composite** | | | **3.1** |

**Tier 2 — Ready with paving.** No tier-capping red flags, one conditional: D3
key-person concentration (cap Tier 2, already the outcome; retention package required).

## Top three opportunities (annual EBITDA impact at steady state)

**1. Onboarding migration automation — $520k–$880k.** Baseline: 14 PS FTEs at ~$118k
loaded, ~55% of PS time on manual migration ≈ $910k/yr, plus a 7-week onboarding queue
gating revenue. Assume 60% automation of migration labor with human review of every
migrated dataset, 65% year-one adoption, minus ~$40k run and review costs: ~$320k labor
effect. Add queue compression: pulling onboarding from 7 weeks toward 3 accelerates
recognition of ~$2.1M in queued first-year ARR by ~1 month and lifts PS capacity for
billable configuration work (~$200k–$560k range depending on backlog persistence).
First 90 days: yes, this is the Day-30 selection.

**2. Support triage and drafted responses — $260k–$430k.** Baseline: 22 support FTEs at
~$74k loaded ≈ $1.63M; 4,100 tickets/month with 60% uncategorized. Triage + routing +
KB-grounded drafts on the "how do I" majority, human-sent always. Assume 20–30% handle-
time reduction after the KB rebuild, 60% adoption year one, minus run costs and the KB
curation investment (~$60k one-time, netted out of year one). Deflects the next two
support hires. First 90 days: partial (triage yes; drafts follow the KB rebuild).

**3. Engineering test generation and boilerplate — $210k–$380k.** Baseline: 32 engineers;
interview + repo analysis puts mechanical work (tests, scaffolds, migrations, docs) at
~35% of time. Target the test gap specifically (coverage is 31%, and low coverage is the
CTO's stated blocker on release cadence). Assume tooling + workflow redesign recovers
15–25% of mechanical time across the team in year one; expressed as two deferred backfill
hires plus measurable lead-time reduction. First 90 days: yes as a workshop track,
per the playbook's enablement cadence.

Aggregate: **$1.0M–$1.7M annual EBITDA effect at steady state** against $2.8M current
EBITDA, with roughly $350k–$450k first-year program cost (pod allocation, tooling,
retention package excluded). Ranges assume human-in-the-loop designs throughout and
year-one adoption haircuts as stated per item.

## Red flags and conditions

1. **Key-person concentration (D3):** one data engineer holds the warehouse, the billing
   export, and the ID-history knowledge. Retention package before close; pair her with
   the pod from day one; she is the natural data-layer owner.
2. **Fourteen enterprise contracts** need counsel review for AI-processing clauses before
   any customer data flows through a hosted model; if unfavorable, those tenants route to
   the local-model path, which the architecture supports but at higher setup cost.
3. **Support opportunity is gated on the knowledge base**, not on AI. Fund the KB rebuild
   or re-rank the opportunity honestly.
4. **QuickBooks integration** (two weeks) precedes the pod, or every unit-economics
   number the pod reports will be a month stale.

## Recommended motion

Proceed. Deploy the FDE pod at close with a two-week paving phase (QuickBooks
integration, read-path normalization layer over the four customer systems), then run the
playbook with onboarding-migration automation as the Day-30 workflow selection.
Underwrite $700k of the $1.0M–$1.7M range in the model; treat the rest as upside. Gate
reviews at Days 30, 60, and 90 per the playbook, with the Day-90 attribution deck
presented at the first post-close board meeting.

---

*Method notes for the assessor: keep every sampled dataset, query, and interview note as
appendix material; the one-pager earns trust only because the workbook behind it can be
audited. And resist the urge to score generously in a competitive process. A Tier 3 asset
bought with a Tier 1 AI thesis becomes the operating partner's problem, and then the
playbook's anti-patterns chapter, and eventually a write-down memo.*
