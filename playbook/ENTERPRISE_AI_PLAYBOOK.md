# The Enterprise AI Playbook

## A 30/60/90 operating model for embedding a forward-deployed engineering pod in a portfolio company

---

## Executive summary

Most AI initiatives in mid-market companies fail the same way: a pilot gets built, a demo
impresses a steering committee, and six months later nothing in the P&L has changed. The
failure is rarely the technology. It is that the pilot was never tied to a business
workflow, nobody instrumented a baseline before starting, and nobody was named to own the
thing after the consultants left.

This playbook describes a different model: a small forward-deployed engineering (FDE) pod,
funded at the fund level and embedded inside a portfolio company for roughly ninety days.
The pod is two to four hands-on engineers, not a strategy team. It writes production code,
pairs daily with the portco's own engineers, and is judged against three proof gates that
a deal team can verify without taking anyone's word for it:

**Day 30: a measured baseline.** Engineering throughput, unit cost of the target
workflow, cycle times, and current AI tool utilization, all instrumented from systems the
company already trusts. No baseline, no credible ROI claim later. This gate exists to
protect the fund from its own optimism.

**Day 60: one workflow in production with a named internal owner.** Not a demo. A
workflow that touches the company's real systems, runs inside cost and safety guardrails,
and has a specific employee whose name is on the runbook. One workflow deep beats five
pilots wide.

**Day 90: board-deck-ready ROI attribution.** Velocity change, unit cost per automated
transaction, and quality metrics, each reported against the Day-30 baseline with a
counterfactual method a CFO can interrogate. Ranges, not point estimates. Full cost
accounting, including the pod itself.

The pod's exit is defined by a self-sufficiency test, not a date. The engagement is over
when the portco team ships its second AI workflow without the pod writing the code. If
that takes seventy days, exit early. If the test fails at ninety, the honest conversation
is about why, not about extending by default.

The economics for the fund: one pod, amortized across the portfolio, converting a
technology trend into measured EBITDA effects one company at a time, and leaving behind
teams that keep compounding after the pod moves on. The rest of this document is the
operating detail: what to instrument, how to pick the first workflow, how the pairing and
handover work, how the numbers survive finance scrutiny, and the anti-patterns that kill
these engagements.

---

## How to read this document

If you are an investment partner or operating partner, read the executive summary above
and the three gate-review sections (Day 30, Day 60, Day 90 deliverables), plus the
anti-patterns. That is enough to govern an engagement.

If you are a portco CTO or engineering leader, the whole document is for you, and the
[reference implementation](../README.md) in this repository is the working demonstration
of the architecture patterns the pod brings: a data interoperability layer, a
cost-governed orchestration engine, and an evaluation harness. Clone it and run it before
the pod arrives; it will make the first week faster.

A note on voice: where this playbook asserts something, it comes from operating
experience, mostly from running IBM API Connect, a $280M product line I grew past $350M
with a team that scaled from 35 to 70+ engineers across four countries, and from building
clinical AI systems where the tolerance for error was zero. Where the playbook is
opinionated, that is the point.

---

## The operating model

### What the pod is

A fund-level FDE pod is two to four engineers who embed inside one portfolio company at a
time. They sit in the portco's repositories, its Slack, its incident channel, and its
sprint cadence. They are not advisors. The distinction matters because advisory
engagements produce decks, and decks do not change unit economics.

When I needed to turn around customer experience across API Connect and DataPower at IBM,
I did not hire a consultancy. I designated a task force of four people, two managers and
two QA engineers, picked for relentless energy and deep product knowledge, gave them a
mandate to analyze the escalation patterns and propose actions, and required that
everything they built be scalable and run on tools we already had. Customer escalations
fell 60% over the following quarters, and a sister product team (IBM Cloud Pak for
Integration) adopted the process wholesale. The FDE pod is that task force pattern,
applied to AI enablement: small, senior, hands-on, instrumented, and designed from day
one to be adopted by the host team rather than depended on.

### The paved road principle

Beneath any single workflow, the pod's engineering objective is to replace fragmented
tooling with one paved road. At IBM Aspera, the migration experience was a pile of files
and tools that had to be run in a particular order, and feature gaps were being closed
piecemeal, customer by customer, including for JPMorgan Chase's data-center buildout. The
fix I drove was a migration service that tied those scripts into a single product
experience: one road for cloud-to-cloud moves where the driver was cost, and one for
on-prem-to-cloud moves for healthcare companies that wanted their data where AI could
reach it. Same road, different verticals.

The pod applies that principle inside a portco. The first workflow is deliberately built
as rails: the data adapters, the model routing table, the guardrails, the evaluation
harness, the runbook template. The second workflow then travels a paved road instead of
mounting a fresh expedition, which is why the exit test in this playbook hinges on the
portco team shipping that second workflow themselves. It is also why the pod refuses
one-off scripts that only the pod can run; every artifact is judged by whether the next
team can drive on it.

### Who is in it

The pod needs one lead who has operated at executive level and still writes code, one or
two engineers strong in data plumbing and evaluation, and, in regulated industries, access
to someone who has shipped software under compliance constraints. Every member must be
hands-on with current AI tooling personally. A leader who has not used the tools cannot
identify the opportunities, and engineers detect that instantly.

### What the portco must commit

Three things, secured before day one: an executive sponsor who controls engineering
priorities (usually the CTO or CEO, and it must be the person who can protect the team's
time), two to three portco engineers allocated at half-time or better for the pairing
work, and read access to the systems of record in the first week. An engagement that
cannot secure these three is an engagement to decline; see anti-patterns.

---

## Days 0–30: The baseline

**Proof gate one: a measured KPI baseline the CFO would accept as evidence.**

### Why baseline first

Every ROI number the fund will ever see from this engagement is a delta against what gets
measured in these thirty days. Skip this and the Day-90 conversation becomes an argument
about anecdotes. The discipline here is the same one I used at IBM: before the task force
proposed a single fix, we built telemetry on the existing Salesforce instance, new
dashboards that classified every customer case by squad, form factor, product version, and
issue area. Capturing those identifiers was a turnkey decision, and it was what made every
later claim about improvement defensible. The instrument came before the intervention.

### Instrument from systems the company already trusts

Do not stand up a new metrics platform in week one. Wire the baseline out of the systems
of record that already exist: the CI/CD pipeline, the ticketing system, the CRM, the
billing system, the support queue. Numbers from systems the leadership already believes
are numbers nobody re-litigates at day ninety.

The baseline covers four areas:

| Area | Metrics | Typical source |
|---|---|---|
| Engineering throughput (DORA) | Deployment frequency; change lead time (commit to production); change failure rate; mean time to restore | CI/CD history, incident tracker |
| Unit economics of the target workflow | Fully loaded cost per transaction (per invoice processed, per ticket resolved, per contract reviewed): labor minutes × loaded rate + error/rework cost | Finance, ops systems, time sampling |
| Cycle time | Intake-to-done per work item class, engineering and back-office both | Ticketing, PSA, workflow tools |
| Current AI utilization | Seats active weekly; where in the SDLC tools are actually used; spend on AI tooling to date | Vendor dashboards, expense reports |

Two practical notes. First, pull six to twelve months of history where the systems allow
it, not a two-week snapshot. Trend context is what lets you separate the pod's effect from
seasonality later. Second, publish the baseline internally at day 30, in writing, with the
measurement method attached. A baseline nobody saw until day 90 looks like it was
reverse-engineered from the result, because it usually was.

### What not to measure

Refuse to baseline lines of code, story points, or any individual-level output metric.
They invite gaming, they poison the pairing relationship, and no CFO respects them anyway.
Copilot suggestion-acceptance rate is a diagnostic, not a headline; a team can accept 40%
of suggestions and ship nothing faster. Measure outcomes at the workflow level and leave
individuals out of the telemetry.

### Selecting the first workflow

The other Day-30 deliverable is the choice of the first production workflow, and this
choice determines whether the engagement succeeds. The selection criteria, in order:

1. **Boring and frequent.** Boilerplate generation, reconciliation, data entry,
   triage, first-draft documents. The mundane daily work is where trust gets built,
   because the cost of an individual error is low and the volume makes the win measurable.
2. **Nondeterminism-tolerant, or gateable.** AI is nondeterministic by nature. Pick a
   workflow where a wrong answer is cheap, or where every consequential output can pass
   through a human approval step. In fintech, healthcare, and other regulated spaces there
   is no appetite for silent errors, so the human gate is not a training wheel to remove
   later; it is part of the production design.
3. **Data within reach.** The inputs live in systems the pod got access to in week one,
   not in a system that needs a six-month integration project first.
4. **An owner exists.** Someone in the building already cares about this workflow's
   output and will plausibly own the automated version. If no candidate owner comes to
   mind, pick a different workflow.

One workflow. The temptation at day 30 is to greenlight three, because three sponsors are
excited. Spreading across multiple workflows, or multiple LLM strategies, before one is
working end-to-end is how engagements dissipate. Go deep on one, then let the second one
ride on the rails the first one built.

### Day-30 gate review

The pod presents to the sponsor and the deal team: the written baseline with methods, the
selected workflow with the scoring behind the selection, the named candidate owner, and
the guardrail budget for the build (token spend caps and review requirements agreed in
advance). Thirty minutes. If the baseline is not defensible, the engagement pauses until
it is; building on an unmeasured foundation wastes everyone's ninety days.

---

## Days 31–60: One workflow in production

**Proof gate two: a production workflow with a named internal owner.**

### Production means production

The workflow runs against the company's real systems of record, on real data, inside the
company's deployment process, with monitoring, a rollback path, and a cost budget enforced
in code. A Streamlit demo on a laptop does not clear this gate, and neither does a
workflow running on the pod's cloud account.

The architecture the pod deploys follows the patterns in this repository's reference
implementation, and they are non-negotiable in spirit even where the specific stack
differs:

- **State in a database, not in memory.** Every agent step is a logged, replayable state
  transition. I learned the cost of unreliable state the expensive way at IBM: API
  Connect's original Cassandra layer, with a homegrown compensation scheme on top, could
  not maintain transaction integrity, and my engineers spent multi-hour calls walking
  customers like Deutsche Bahn through database corruption fixes by hand. Moving that
  product to Postgres was one of the two architectural decisions that saved it. An AI
  workflow whose intermediate state cannot be audited or replayed will eventually produce
  a result nobody can explain, and in a portco that moment kills the program.
- **Deterministic model routing with a cost ceiling.** Cheap models for extraction,
  mid-tier for reasoning, the expensive tier only on documented escalation criteria, and a
  per-run token budget that halts gracefully at a resumable checkpoint. Model choice is
  modular by design: when a better or cheaper model releases, it gets swapped in behind
  the adapter and evaluated before it ever touches production traffic.
- **Human review where confidence is low.** Low-confidence outputs land in a review
  queue, and disagreement between automated checks escalates to a person. Never silent
  override. This is what makes the "humans are the architects of the system" pitch true
  rather than a slogan, and it is what converts skeptical engineers.
- **An evaluation suite with known ground truth**, run on every change, so "is it still
  right" is a CI gate rather than a feeling.

### The enablement track: watch me, do it with me, I watch you

The pod's second product, as important as the workflow, is the portco team's capability.
The transfer runs as a deliberate progression across these four weeks:

**Watch me (week 5).** The pod builds in the open: shared screens, running commentary,
architecture decisions written up as short ADRs the same day. The portco engineers'
job this week is to interrupt with questions.

**Do it with me (weeks 6–7).** Pairing rotations, portco engineer at the keyboard, pod
engineer navigating. Each rotation owns a real slice: a data connector, an eval case, a
guardrail rule. This middle step is the one that gets skipped when schedules compress,
and skipping it is fatal. A team that watched but never drove will operate the system
until the first surprise, then call for help, and the dependency becomes permanent.

**I watch you (week 8).** The named owner and their teammates extend the workflow
themselves, with the pod reviewing rather than writing. The concrete test: the portco
team makes a change end-to-end (new field, new rule, new eval case) and ships it through
their own pipeline while the pod keeps its hands off the keyboard.

Alongside the pairing, the pod runs two 90-minute working sessions per week, open to any
engineer in the company. Working sessions, not lectures: attendees bring a task from
their own backlog and apply the tooling to it. This is also where the mental resistance
gets addressed directly. The pitch that works is honest: the technology is
nondeterministic, you are making the decisions, humans are the architects of the system,
and we are starting with the boring work on purpose.

### The named owner

By day 60 there is one person whose name is on the workflow, in writing, and that person
opted in rather than being volunteered. The owner has time formally carved out by the
sponsor, was in the pairing rotations from the start, and by the gate review can answer
operational questions about the workflow without the pod in the room. Ownership assigned
without protected time is theater; the sponsor's willingness to carve the time out is the
real test of whether the company wants this.

### Handover artifacts

Clearing the gate requires the boring documents to exist, because they are what makes
week twenty look like week eight:

1. A runbook: how to operate, monitor, roll back, and pause the workflow, including what
   to do when the cost guardrail halts a run.
2. The architecture document and dated ADRs, including the model routing table and the
   reasoning behind escalation criteria.
3. The evaluation suite, wired into CI, with its golden dataset and instructions for
   extending it.
4. The cost dashboard: per-run and per-transaction spend against budget, visible to the
   owner and the sponsor.
5. A severity and escalation guide: which failures page a human immediately and which
   wait for business hours. At IBM, reiterating consistent severity classification to
   every partner and customer was one of the highest-return fixes the task force shipped,
   because it made every downstream response predictable. The same is true here.

### Day-60 gate review

The owner, not the pod, demos the workflow to the sponsor and deal team, live against
production systems. The pod presents utilization and early outcome trends against the
baseline. If the workflow is in production but the owner cannot demo it alone, the gate
is not cleared; the fix is another two weeks of the enablement track, not a waiver.

---

## Days 61–90: Attribution

**Proof gate three: ROI numbers that survive the CFO.**

### The weekly loop

The final month runs the cadence I ran through the IBM transformation: a weekly checkpoint
against the dashboards, where emerging trends add or adjust actions and completed ones get
closed out. Week over week the escalation and issue counts fell, and when an individual
area fluctuated upward we doubled down on that area specifically. The same loop applies
here: the workflow's metrics get reviewed weekly with the owner, tuning happens in small
increments, and by day 90 the numbers have a visible trajectory rather than a single
before/after snapshot. A trajectory is far harder to dismiss than a two-point comparison.

### What gets measured

| Claim | Metric | Method |
|---|---|---|
| Shipping velocity compression | Change lead time (commit to production), median and p85, vs. baseline | Same CI/CD instrumentation as Day 30; report percentage reduction |
| Throughput | Deployment frequency; work items completed per week in the affected area | Same sources, trend-adjusted |
| Unit cost per automated transaction | (Human minutes remaining × loaded rate + token/API spend + amortized review time) per transaction, vs. baseline manual cost | Token accounting is native to the orchestration layer; labor by time sampling |
| Quality scaling | Test coverage percentage and eval-suite pass rates over time; error/rework rate in the workflow | CI history; eval harness reports; ops error logs |
| Adoption | Weekly active usage of the workflow and of AI tooling across the team, vs. Day-30 utilization | Tool dashboards |

Report cost the way finance will recompute it anyway: include the pod's own cost, tooling
subscriptions, token spend, and the human review time the guardrails require. A number
that omits the program's own cost gets one meeting; a fully loaded number gets renewed.

### The counterfactual, stated plainly

"Velocity went up" is not attribution. The Day-90 deck states what would have happened
without the intervention and how that estimate was constructed:

**Pre-registered baseline.** The Day-30 baseline, published before the build started, is
the primary counterfactual. It was measured over months of history, so the trend line,
not just the level, is the comparator. If lead time was already improving 2% monthly
before the pod arrived, the claim is the improvement beyond that trend.

**A comparison group where one exists.** Most portcos have a team, a product area, or a
work-item class the pod did not touch. Report its movement over the same window. If the
treated workflow improved 40% while the untouched area improved 5%, the attribution
argument mostly makes itself. Where no clean comparison exists, say so in the deck rather
than inventing one.

**Ranges with stated sensitivity.** Point estimates invite sniping. Report "unit cost
down 30–45%, where the low end assumes all review-time estimates are doubled" and the
conversation moves from whether the number is real to which end of the range to plan on.

**What is explicitly not claimed.** List the improvements that coincided but are not
attributable (a hiring change, a seasonal lull, a deprecated feature). Volunteering this
list is what makes the rest of the deck credible. Every escalation-reduction claim I put
in front of IBM leadership survived because the telemetry behind it classified every case
by area and cause; claims tied to instrumented segments survive scrutiny, aggregate
claims do not.

### The board deck

One page, four blocks: the workflow in one sentence and its owner's name; the fully
loaded unit-economics delta with the range; the velocity and quality deltas against
trend; and the forward plan, meaning the second workflow the portco team will ship
themselves and the projected EBITDA effect at portfolio scale if the pattern repeats.
Everything else is appendix.

---

## Engagement anti-patterns

These are the ways this engagement dies. Most were learned by watching them happen.

**The pilot that touches nothing.** If the workflow does not read from or write to a
system of record, it is a demo, and demos produce steering-committee applause and zero
EBITDA. The test at every review: what production system did this touch today?

**Sponsorship without ownership.** A CEO who is excited but will not carve out protected
time for a named owner is buying a story, not a capability. The engagement fails at day
75 when the owner's day job reabsorbs them. Secure the time commitment in writing at day
zero or do not start.

**Seats confused with adoption.** "We bought Copilot for everyone" is a procurement
event, not an enablement outcome. Utilization data usually shows a third of seats active
weekly and usage concentrated in autocomplete. Tooling changes outcomes only when paired
with workflow redesign and measurement, which is the entire reason the pod exists.

**Spreading thin.** Three workflows, two LLM providers, and a platform migration in
flight simultaneously means nothing reaches production depth. One workflow, one deep
implementation, then scale. This discipline is unpopular in month one; it is the reason
there is something real to show in month three. Note what this rule does not say: the
architecture stays LLM-agnostic, routing different models to different jobs behind one
adapter. Focus is a statement about workflows and team attention, not a commitment to a
vendor.

**The advisory drift.** Somewhere around week six, someone asks the pod for a strategy
readout, and a pod that starts producing decks stops producing code. Fixed rule: pod
output is measured in shipped changes and paired sessions, and the only decks are the
three gate reviews.

**Replatform-first paralysis.** "We can't do AI until we fix our data" is half wisdom,
half stall. Sometimes the plumbing genuinely blocks the workflow; more often the
interoperability layer can normalize around the mess, the way this repository's reference
implementation does with entity resolution over inconsistent systems, and the plumbing fix
proceeds in parallel on its own merits. The diligence scorecard in this repository exists
to make that call analytically instead of ideologically.

**Starting where errors are expensive.** Leading with the highest-stakes workflow,
underwriting decisions, clinical steps, customer-facing money movement, because "that's
where the value is." The value is there, but trust is not yet, and the first visible error
ends the program. Boring first. Regulated-space workflows come after the team has an
evaluation habit and a human-gate reflex, and some of them should stay human-gated
permanently.

**Extension by inertia.** If there is no defined exit test, the pod becomes a permanent
staff augmentation billed at fund economics, and the portco team never takes the keys.
The exit test below is agreed in writing before day one.

---

## Exit criteria: the self-sufficiency test

The pod leaves when the portco passes a test, not when a date arrives. The test has five
checks, all observable:

1. **Second workflow shipped without the pod writing code.** The team selected it,
   built it on the existing rails, and put it in production. The pod reviewed pull
   requests and nothing else. This is the single strongest predictor that the capability
   survives; it is the equivalent of the moment IBM's CP4I team ran my transformation
   process without my task force in the room.
2. **The owner has handled a live incident or a model upgrade unaided**, following the
   runbook, including at least one cost-guardrail halt resumed correctly. If no real
   incident occurred, run a game day and treat it as real.
3. **Evals gate merges in the team's own CI**, and the team has added new eval cases
   without being asked, because a growing golden dataset means they actually trust it.
4. **The cost dashboard is reviewed in the team's own operating cadence**, with the pod
   absent, and someone can explain last month's per-transaction number and its movement.
5. **The artifacts are alive.** Runbook and ADRs have portco-authored edits dated after
   the pod's last commit. Documentation only the pod ever touched is documentation that
   dies at exit; the IBM lesson was that a single searchable, maintained knowledge view
   outperforms any volume of handover material.

Fail any check at day 90 and the response is a focused two-to-four-week remediation aimed
at that specific check, agreed with the sponsor, not a rolling extension. Pass all five
early and the pod leaves early; finishing at day 70 is a better outcome for everyone,
including the fund's next portco in the queue.

After exit, the pod tapers rather than vanishes: a weekly office hour for a month, then
on-call advisory at the fund level. The portfolio effect compounds here, because every
playbook artifact, eval pattern, and routing table the pod leaves behind becomes the
starting template for the next company, the same way one product's transformation process
became the division's.

---

## Cadence at a glance

| Week | Pod focus | Portco visible commitment |
|---|---|---|
| 1–2 | System access; baseline instrumentation from systems of record | Sponsor secures access; owner candidates identified |
| 3–4 | Baseline published; workflow selected and scored; guardrail budget agreed | **Day-30 gate review** |
| 5 | Build in the open ("watch me"); ADRs daily; workshops begin | Engineers attend and interrupt |
| 6–7 | Pairing rotations ("do it with me"); workflow hardens toward production | Half-time engineer allocation honored |
| 8 | Owner-led changes ("I watch you"); handover artifacts complete | **Day-60 gate review, demoed by the owner** |
| 9–12 | Weekly metric checkpoints; tuning; attribution analysis; second-workflow scoping with the team | Owner runs the weekly review by week 12 |
| 13 | ROI deck delivered; self-sufficiency test administered | **Day-90 gate review**; exit or targeted remediation |

---

*This playbook is paired with the [AI Diligence Scorecard](AI_DILIGENCE_SCORECARD.md),
which covers the pre-acquisition assessment that decides whether and where to deploy the
pod, and with the reference implementation in [`src/`](../src), which demonstrates the
interoperability, orchestration, guardrail, and evaluation patterns the pod deploys.*
