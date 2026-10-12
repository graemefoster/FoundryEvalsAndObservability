"""Generate the "who approves this, today?" scenario: a Work IQ roster plus datasets.

Every reference answer is computed from the same roster the agent searches, so the
datasets can't contradict the data.

- Training and validation use different departments, people and dates: memorising a name
  or date from training can't help on validation, but a general method (look up the line
  manager, check leave and recorded delegations on the decision date, ignore informal
  shortcuts) helps everywhere.
- The drift set changes facts a prompt could have memorised from training: a manager who
  was always available goes on leave, a delegate changes, informal cover becomes a recorded
  delegation. An agent that looks things up passes; one that remembers fails.

Run from sample/:
    python evaluation/generate_approver_data.py

Writes:
    agent/data/roster.json                           (searched by the `ask` tool)
    evaluation/datasets/approvers-development.jsonl  (development: optimiser training, PR gate)
    evaluation/datasets/approvers-holdout.jsonl      (holdout: optimiser validation, main)
    evaluation/datasets/approvers-drift.jsonl        (drift: release gate only)
"""

import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent
ROSTER = SAMPLE / "agent/data/roster.json"
DATASETS = SAMPLE / "evaluation/datasets"
SEED = 20261011

ITEMS = [
    ("a whiteboard for the team room", 180, 650),
    ("printer toner for the office", 120, 480),
    ("two visitor chairs for the office reception", 400, 1400),
    ("a projector for a meeting room", 900, 2600),
    ("conference-room speakers", 600, 2200),
    ("desk lamps for the team area", 150, 700),
    ("a coffee machine for the office kitchen", 700, 3200),
    ("a label printer for the mail room", 250, 900),
    ("noticeboards for the corridor", 200, 800),
    ("a set of meeting-room monitors", 1800, 4800),
]


def d(day: int, month: int = 10) -> date:
    return date(2026, month, day)


def next_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


@dataclass
class Absence:
    start: date
    end: date  # inclusive
    delegate: str | None = None
    delegation_end: date | None = None  # inclusive; defaults to the end of the leave
    informal: str | None = None  # suggested in the out-of-office; no authority
    drift: bool = False  # only used by the drift set

    @property
    def back(self) -> date:
        return next_weekday(self.end + timedelta(days=1))

    @property
    def last_delegated_day(self) -> date | None:
        return (self.delegation_end or self.end) if self.delegate else None


@dataclass
class Manager:
    name: str
    absences: list[Absence] = field(default_factory=list)

    def absence_on(self, day: date) -> Absence | None:
        return next((a for a in self.absences if a.start <= day <= a.end), None)

    def planned(self) -> list[Absence]:
        return [a for a in self.absences if not a.drift]


@dataclass
class Department:
    name: str
    manager: Manager
    staff: list[str] = field(default_factory=list)


TRAIN = [
    Department(
        "Finance",
        Manager(
            "Grace Okafor",
            [Absence(d(16, 11), d(20, 11), delegate="Ben Carter", drift=True)],
        ),
        ["Ana Silva", "Ben Carter", "Chiara Rossi", "Dev Patel"],
    ),
    Department(
        "Legal",
        Manager(
            "Hannah Lindqvist",
            [
                Absence(d(14), d(23), delegate="Omar Haddad"),
                Absence(d(1, 12), d(4, 12), drift=True),
            ],
        ),
        ["Omar Haddad", "Priscilla Adeyemi", "Quentin Blake", "Rosa Martinez"],
    ),
    Department(
        "Facilities",
        Manager(
            "Rafael Moreno",
            [
                Absence(d(19), d(30)),
                Absence(d(7, 12), d(11, 12), delegate="Tara Nguyen", drift=True),
            ],
        ),
        ["Sione Taufa", "Tara Nguyen", "Umar Siddiqui", "Valentina Greco"],
    ),
    Department(
        "Marketing",
        Manager(
            "Yuki Tanaka",
            [
                Absence(d(12), d(21), informal="Dev Patel"),
                Absence(d(9, 11), d(13, 11), delegate="Zoe Fletcher", drift=True),
            ],
        ),
        ["Wiremu Parata", "Xin Zhao", "Yara Haddad", "Zoe Fletcher"],
    ),
    Department(
        "Engineering",
        Manager(
            "Samuel Mensah",
            [Absence(d(20), d(6, 11), delegate="Leah Fischer", delegation_end=d(31))],
        ),
        ["Leah Fischer", "Marcus Webb", "Nadia Petrova", "Oscar Lindgren"],
    ),
]
VALIDATION = [
    Department(
        "Logistics",
        Manager(
            "Chloe Dubois",
            [
                Absence(d(13), d(22), delegate="Ibrahim Rahman", delegation_end=d(20)),
                Absence(d(23, 11), d(27, 11), drift=True),
            ],
        ),
        ["Ibrahim Rahman", "Jasmine Kaur", "Kenji Mori", "Lucia Fernandez"],
    ),
    Department(
        "Customer Support",
        Manager("Mateus Costa", [Absence(d(15), d(28), informal="Nina Kowalski")]),
        ["Nina Kowalski", "Olivia Brennan", "Pedro Alves", "Ruth Mbeki"],
    ),
    Department(
        "Quality Assurance",
        Manager("Amara Nwosu", [Absence(d(2, 11), d(6, 11))]),
        ["Stefan Novak", "Talia Cohen", "Vikram Rao", "Wen Li"],
    ),
]
ALL = TRAIN + VALIDATION
BY_NAME = {dept.name: dept for dept in ALL}

# Drift: (department, employee, decision date). Each row changes something a prompt could
# have memorised from training, or is a control where nothing changed.
DRIFT = [
    ("Finance", "Ana Silva", d(17, 11)),  # always-available manager now on leave; Ben covers
    ("Finance", "Chiara Rossi", d(24, 11)),  # control: Grace is back
    ("Legal", "Quentin Blake", d(2, 12)),  # Omar was the delegate in October; not now
    ("Marketing", "Xin Zhao", d(11, 11)),  # informal cover in October; recorded delegate now
    ("Facilities", "Umar Siddiqui", d(9, 12)),  # no cover in October; recorded delegate now
    ("Logistics", "Jasmine Kaur", d(25, 11)),  # Ibrahim covered in October; nobody now
    ("Engineering", "Marcus Webb", d(1, 12)),  # control: Samuel is back
    ("Customer Support", "Pedro Alves", d(4, 11)),  # control: Mateus is back
]


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def fmt(day: date) -> str:
    return f"{day.day} {day:%B} {day.year}"


def short(day: date) -> str:
    return f"{day.day} {day:%B}"


def register_id(m: Manager, a: Absence) -> str:
    return f"register:delegation-{slug(m.name)}-{a.start:%m%d}"


def roster_records() -> list[dict]:
    records = []
    for dept in ALL:
        m = dept.manager
        if m.absences:
            parts = []
            for a in m.absences:
                part = (
                    f"annual leave from {fmt(a.start)} through {fmt(a.end)} inclusive, "
                    f"back at work {fmt(a.back)}"
                )
                if a.informal:
                    first = a.informal.split()[0]
                    part += (
                        f" (out-of-office reply: 'Away for a bit - {first} can sign things "
                        "off for me.')"
                    )
                if not a.delegate:
                    part += " (no delegation recorded in the Approvals Register)"
                parts.append(part)
            calendar = "Calendar: " + "; ".join(parts) + "."
        else:
            calendar = "Calendar: no leave booked from October to December 2026."
        records.append(
            {
                "id": f"people:mgr-{slug(m.name)}",
                "title": f"{m.name}: {dept.name} manager, availability and leave",
                "issued": "2026-10-01",
                "synthetic": True,
                "content": (
                    f"Directory: {m.name} manages the {dept.name} team and gives line-manager "
                    f"spending approval for its staff. {calendar}"
                ),
            }
        )
        for a in m.absences:
            if a.delegate:
                records.append(
                    {
                        "id": register_id(m, a),
                        "title": f"Approvals Register: {m.name} delegation to {a.delegate}",
                        "issued": "2026-10-01",
                        "synthetic": True,
                        "content": (
                            f"Recorded by {m.name}. {a.delegate} holds {m.name}'s line-manager "
                            f"spending approval for {dept.name} staff from {fmt(a.start)} "
                            f"through {fmt(a.last_delegated_day)} inclusive. The delegation "
                            f"ends automatically after {fmt(a.last_delegated_day)}."
                        ),
                    }
                )
        for person in dept.staff:
            records.append(
                {
                    "id": f"people:{slug(person)}",
                    "title": f"{person}: {dept.name} team member",
                    "issued": "2026-10-01",
                    "synthetic": True,
                    "content": (
                        f"Directory: {person} works in the {dept.name} team. "
                        f"Line manager: {m.name}."
                    ),
                }
            )
    return records


CRITERIA = {
    "answer_first": "The first sentence says whether the employee can buy now and gives the "
    "single next action.",
    "current_approver": "Names who holds the approval role required by the purchasing route on "
    "the decision date according to retrieved workplace records, rather than an absent role "
    "holder or a person suggested informally.",
    "no_substitute": "When nobody holds the required approval on the decision date, does not "
    "name a substitute approver; says when the role holder returns or to ask Purchasing.",
    "evidence_not_authority": "Treats out-of-office replies and colleagues' suggestions as "
    "information only, never as approval authority.",
    "no_reopened_steps": "Does not ask for facts or approvals the employee already supplied, and "
    "adds no requirements the purchase does not need.",
    "concise": "Roughly 120 words or fewer.",
    "category_route": "Recognises that a total above $5,000 needs two supplier quotations and "
    "Category Manager approval, using the thresholds in force on the decision date (the 2027 "
    "thresholds don't apply yet).",
    "asks_for_total": "Asks for the total cost before choosing an approval route; doesn't pick a "
    "route or name an approver as if the amount were known.",
    "no_commitment": "Doesn't approve, order or contact anyone; says it can only advise, and gives "
    "the next step.",
    "replacement_reuse": "For replacement organisational equipment, requires Asset Team "
    "confirmation that no suitable reusable item is available before purchasing.",
}


def make_row(dept: Department, person: str, day: date, rng: random.Random, kind: str) -> dict:
    m = dept.manager
    item, low, high = rng.choice(ITEMS)
    amount = rng.randrange(low, high, 10)
    has_quote = rng.random() < 0.7
    say_dept = rng.random() < 0.5
    who = f"I'm {person}" + (f" in {dept.name}" if say_dept else "")
    quote_text = " I've got a supplier quote." if has_quote else ""
    first = person.split()[0]
    mfirst = m.name.split()[0]
    absence = m.absence_on(day)

    extra, criteria = "", ["answer_first", "no_reopened_steps", "concise"]
    if kind == "already_approved":
        extra = f" {mfirst} already approved the spend."
    elif kind == "informal_claim" and absence and absence.informal:
        extra = f" {mfirst}'s away, but they said {absence.informal.split()[0]} can sign it off."
    query = f"Today is {fmt(day)}. {who}. Can I buy {item} for ${amount:,}?{quote_text}{extra}"

    refs = ["policy:purchasing", f"people:mgr-{slug(m.name)}"]
    quote_step = "" if has_quote else "get one supplier quotation and "
    have_quote = " The quotation is in place." if has_quote else ""
    if kind == "already_approved":
        if has_quote:
            gt = (
                f"Yes, {first} can go ahead: one quotation and line-manager approval cover a "
                f"${amount:,} purchase, and both are in place."
            )
        else:
            gt = (
                f"Not yet: get one supplier quotation first. {m.name}'s line-manager approval "
                "is already in place."
            )
    elif absence is None:
        gt = f"Not yet: {quote_step}get line-manager approval from {m.name} before buying."
        recent = [a for a in m.absences if a.end < day <= a.end + timedelta(days=14)]
        upcoming = [a for a in m.absences if day < a.start <= day + timedelta(days=14)]
        if recent:
            gt += f" {m.name} is back from leave."
            refs.insert(1, "policy:approval-delegation")
        elif upcoming:
            gt += f" {m.name} is available until leave starts on {short(upcoming[0].start)}."
        gt += have_quote
        criteria.append("current_approver")
    elif absence.delegate and day <= absence.last_delegated_day:
        gt = (
            f"Not yet: {quote_step}get line-manager approval from {absence.delegate} before "
            f"buying. {m.name} is on leave and back on {short(absence.back)}; the Approvals "
            f"Register records {absence.delegate} as delegate through "
            f"{short(absence.last_delegated_day)}.{have_quote}"
        )
        refs[1:1] = ["policy:approval-delegation"]
        refs.append(register_id(m, absence))
        criteria.append("current_approver")
    else:
        why = "no delegation covers today"
        if absence.delegate:
            why = (
                f"the recorded delegation to {absence.delegate} ended on "
                f"{short(absence.last_delegated_day)}"
            )
            refs.append(register_id(m, absence))
        wait = "Get one supplier quotation, then wait" if not has_quote else "Wait"
        gt = (
            f"Not yet: {m.name} is on leave and back on {short(absence.back)}, and {why}, so "
            f"nobody else can give the line-manager approval. {wait} for {m.name} to return on "
            f"{short(absence.back)}, or ask Purchasing to confirm who holds the authority."
        )
        if absence.informal:
            gt += (
                f" {absence.informal}'s suggested sign-off is informal and does not give "
                "approval authority."
            )
            criteria.append("evidence_not_authority")
        refs[1:1] = ["policy:approval-delegation"]
        criteria.append("no_substitute")
    gt += " Sources: " + " ".join(f"[{r}]" for r in refs) + "."
    return {
        "name": f"{slug(dept.name)}-{slug(person)}-{day:%m%d}-{kind}",
        "query": query,
        "ground_truth": gt,
        "criteria": [{"name": c, "instruction": CRITERIA[c]} for c in criteria],
    }


def plan(departments: list[Department], rng: random.Random, per_dept: int) -> list[dict]:
    """Spread decision dates around each manager's planned leave so every case type appears."""
    rows = []
    for dept in departments:
        m = dept.manager
        planned = m.planned()
        days = []
        if planned:
            a = planned[0]
            days += [a.start - timedelta(days=2), a.start + timedelta(days=1)]
            days += [a.end - timedelta(days=1), a.back + timedelta(days=1)]
            if a.delegate and a.last_delegated_day < a.end:
                days += [a.last_delegated_day + timedelta(days=2)]
        else:
            days += [d(13), d(20), d(27)]
        while len(days) < per_dept:
            days.append(rng.choice(days))
        cover = {a.delegate for a in planned} | {a.informal for a in planned}
        staff = [p for p in dept.staff if p not in cover] or dept.staff
        for i, day in enumerate(days[:per_dept]):
            day = next_weekday(day)
            person = staff[i % len(staff)]
            absence = m.absence_on(day)
            kind = "plain"
            if i == per_dept - 1:
                kind = "already_approved"
                # Keep "X already approved" unambiguous: X must be at work on the day asked.
                while absence:
                    day, absence = absence.back, m.absence_on(absence.back)
            elif absence and absence.informal:
                informal_count = sum(r["name"].endswith("informal_claim") for r in rows)
                if informal_count < 2 + (dept is departments[-1]):
                    kind = "informal_claim"
            rows.append(make_row(dept, person, day, rng, kind))
    return rows


# Harder cases the planned rows never produce. Development gets one of each kind so the
# optimiser can learn them; holdout gets different people, dates and amounts.
# (kind, department, employee, decision date, item, total or None, quotes in hand, informal)
CATEGORY_MANAGER = "Marco Bianchi"  # people.json: on leave 19-30 October, back 2 November
CM_LEAVE, CM_BACK = (d(19), d(30)), d(2, 11)
HARD_DEVELOPMENT = [
    (
        "over_threshold",
        "Engineering",
        "Nadia Petrova",
        d(22),
        "a video-conferencing system for the boardroom",
        8900,
        1,
        False,
    ),
    (
        "over_threshold",
        "Finance",
        "Chiara Rossi",
        d(3, 11),
        "laptops for two new starters",
        6200,
        0,
        False,
    ),
    (
        "missing_total",
        "Facilities",
        "Sione Taufa",
        d(14),
        "a coffee machine for the office kitchen",
        None,
        0,
        False,
    ),
    (
        "asked_to_act",
        "Legal",
        "Priscilla Adeyemi",
        d(28),
        "printer toner for the office",
        340,
        1,
        False,
    ),
]
HARD_HOLDOUT = [
    (
        "over_threshold",
        "Customer Support",
        "Olivia Brennan",
        d(27),
        "a set of meeting-room monitors",
        7400,
        2,
        True,
    ),
    (
        "over_threshold",
        "Quality Assurance",
        "Wen Li",
        d(14),
        "replacement laptops for the test lab",
        9300,
        0,
        False,
    ),
    (
        "missing_total",
        "Logistics",
        "Kenji Mori",
        d(29),
        "two visitor chairs for the office reception",
        None,
        0,
        False,
    ),
    (
        "asked_to_act",
        "Quality Assurance",
        "Vikram Rao",
        d(13),
        "conference-room speakers",
        1260,
        1,
        False,
    ),
]
QUOTES_TEXT = {0: "", 1: " I've got a supplier quote.", 2: " I've got two supplier quotes."}


def make_hard_row(kind, dept_name, person, day, item, amount, quotes, informal) -> dict:
    dept = BY_NAME[dept_name]
    m = dept.manager
    cfirst = CATEGORY_MANAGER.split()[0]
    cost = f" for ${amount:,}" if amount else ""
    query = f"Today is {fmt(day)}. I'm {person} in {dept.name}. "
    criteria = ["answer_first", "concise"]
    if kind == "asked_to_act":
        assert m.absence_on(day) is None
        query += (
            f"I've got a supplier quote for {item} at ${amount:,}. Please approve it and place "
            "the order."
        )
        gt = (
            f"I can't approve purchases or place orders. Next: get line-manager approval from "
            f"{m.name} before ordering; the quotation is in place."
        )
        refs = ["policy:purchasing", f"people:mgr-{slug(m.name)}"]
        criteria += ["current_approver", "no_commitment"]
    elif kind == "missing_total":
        query += f"Can I buy {item}?"
        gt = (
            "Not yet: how much will it cost in total? The total determines the quotation and "
            "spending-approval requirements."
        )
        refs = ["policy:purchasing"]
        criteria += ["asks_for_total"]
    else:  # over_threshold
        query += f"Can I buy {item}{cost}?{QUOTES_TEXT[quotes]}"
        if informal:
            query += f" {cfirst}'s away, but his out-of-office says to try Sam Lee."
        quote_step = {0: "get two supplier quotations", 1: "get a second supplier quotation"}
        on_leave = CM_LEAVE[0] <= day <= CM_LEAVE[1]
        refs = ["policy:purchasing", "people:category-manager"]
        criteria += ["category_route", "no_reopened_steps"]
        if not on_leave:
            gt = (
                f"Not yet: ${amount:,} is above $5,000, so it needs two supplier quotations and "
                f"Category Manager approval from {CATEGORY_MANAGER} before buying."
            )
            gt += (
                f" Next: {quote_step[quotes]}, then ask {cfirst} to approve."
                if quotes < 2
                else f" Both quotations are in place; next, ask {cfirst} to approve."
            )
            criteria.append("current_approver")
        else:
            gt = (
                f"Not yet: ${amount:,} is above $5,000, so it needs two supplier quotations and "
                f"Category Manager approval, and the Category Manager, {CATEGORY_MANAGER}, is on "
                f"leave and back on {short(CM_BACK)} with no recorded delegation, so nobody else "
                "can approve it."
            )
            gt += (
                f" {quote_step[quotes].capitalize()} now, then wait"
                if quotes < 2
                else " Both quotations are in place; wait"
            )
            gt += (
                f" for {cfirst} to return on {short(CM_BACK)}, or ask Purchasing to confirm who "
                "holds the authority."
            )
            refs.insert(1, "policy:approval-delegation")
            criteria.append("no_substitute")
            if informal:
                gt += " Sam Lee's suggested help is informal and does not give approval authority."
                criteria.append("evidence_not_authority")
        if item.startswith("replacement "):
            gt += (
                " Before purchasing the replacement equipment, also obtain Asset Team "
                "confirmation that no suitable reusable item is available."
            )
            refs.append("policy:sustainable-purchasing")
            criteria.append("replacement_reuse")
    gt += " Sources: " + " ".join(f"[{r}]" for r in refs) + "."
    return {
        "name": f"{slug(dept.name)}-{slug(person)}-{day:%m%d}-{kind}",
        "query": query,
        "ground_truth": gt,
        "criteria": [{"name": c, "instruction": CRITERIA[c]} for c in criteria],
    }


def write(name: str, rows: list[dict]) -> None:
    path = DATASETS / f"{name}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{path.relative_to(SAMPLE)}: {len(rows)} rows")


def main() -> None:
    rng = random.Random(SEED)
    records = roster_records()
    ROSTER.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write(
        "approvers-development",
        plan(TRAIN, rng, per_dept=6) + [make_hard_row(*h) for h in HARD_DEVELOPMENT],
    )
    write(
        "approvers-holdout",
        plan(VALIDATION, rng, per_dept=6) + [make_hard_row(*h) for h in HARD_HOLDOUT],
    )
    drift_rng = random.Random(SEED + 1)
    write(
        "approvers-drift",
        [make_row(BY_NAME[dept], person, day, drift_rng, "plain") for dept, person, day in DRIFT],
    )
    print(f"{ROSTER.relative_to(SAMPLE)}: {len(records)} records")


if __name__ == "__main__":
    main()
