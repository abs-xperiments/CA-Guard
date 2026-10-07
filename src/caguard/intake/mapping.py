"""Mapping arbitrary ledger headers onto the canonical schema.

Indian exports vary: Tally writes "Vch Type" and "Particulars", an SAP extract
writes "document_type" and "gl_account", and a hand-built Excel sheet writes
whatever the article did. The aliases below cover what we have actually seen;
anything else is asked about rather than guessed at.

The rule that matters: **when a header could plausibly be two canonical fields,
raise.** Silently picking one is how a credit column becomes a debit column and
every downstream number is wrong in a way nobody notices.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# Canonical field -> header spellings seen in the wild, all lower-cased and
# stripped of punctuation before comparison.
ALIASES: dict[str, frozenset[str]] = {
    "voucher_id": frozenset(
        {
            "voucher id",
            "voucher",
            "voucher number",
            "vch",
            "vchno",
            "document no",
            "doc id",
            "entry id",
            "je no",
            "transaction id",
            "txn id",
            "ref no",
            "reference no",
            "voucher no",
            "vch no",
            "vch no.",
            "document id",
            "document_id",
            "doc no",
            "entry no",
            "journal id",
            "je id",
        }
    ),
    "line_number": frozenset({"line number", "line_number", "line no", "sr no", "srno", "line"}),
    "voucher_date": frozenset(
        {
            "date",
            "voucher date",
            "txn date",
            "dated",
            "vch date",
            "document date",
            "document_date",
            "transaction date",
            "entry date",
        }
    ),
    "posted_at": frozenset(
        {
            "posted at",
            "posted_at",
            "posting date",
            "posting_date",
            "created on",
            "entry time",
            "posting timestamp",
        }
    ),
    "voucher_type": frozenset(
        {"voucher type", "vch type", "type", "document type", "document_type", "journal type"}
    ),
    "account_code": frozenset(
        {
            "account code",
            "account_code",
            "gl account",
            "gl_account",
            "ledger code",
            "account no",
            "code",
        }
    ),
    "account_name": frozenset(
        {
            "account name",
            "account_name",
            "ledger",
            "ledger name",
            "ledger account",
            "head",
            "account head",
            "gl description",
            "particulars",
            "account description",
            "account_description",
            "account",
        }
    ),
    "account_group": frozenset(
        {
            "account group",
            "account_group",
            "group",
            "financial statement category",
            "financial_statement_category",
        }
    ),
    "debit": frozenset(
        {"debit", "debit amount", "debit_amount", "dr", "dr amount", "debit inr", "debit rs"}
    ),
    "credit": frozenset(
        {"credit", "credit amount", "credit_amount", "cr", "cr amount", "credit inr", "credit rs"}
    ),
    "amount": frozenset({"amount", "transaction amount", "local amount", "local_amount", "value"}),
    # CA-Guard's own export format: already in paise, and kept apart from the
    # rupee columns above because confusing the two is a hundred-fold error.
    "debit_paise": frozenset({"debit_paise", "debit paise"}),
    "credit_paise": frozenset({"credit_paise", "credit paise"}),
    "currency": frozenset({"currency", "curr", "currency code"}),
    "created_by": frozenset(
        {"created by", "created_by", "user", "user id", "entered by", "preparer", "maker"}
    ),
    "approved_by": frozenset(
        {"approved by", "approved_by", "approver", "checker", "authorised by"}
    ),
    "document_ref": frozenset(
        {
            "document ref",
            "document_ref",
            "reference",
            "ref",
            "supporting document",
            "bill no",
            "invoice no",
            "voucher ref",
        }
    ),
    "narration": frozenset(
        {
            "narration",
            "particulars description",
            "line text",
            "line_text",
            "header text",
            "header_text",
            "description",
            "remarks",
        }
    ),
    "cost_centre": frozenset(
        {"cost centre", "cost center", "cost_center", "cost_centre", "department"}
    ),
    "entity_id": frozenset(
        {"entity", "entity id", "entity_id", "company", "company code", "company_code", "branch"}
    ),
}

# "particulars" is a Tally column that means the ledger name, but some exports
# use it for the narration. Listed under account_name; flagged if both appear.
_AMBIGUOUS_NOTE = {
    "particulars": "In Tally exports 'Particulars' is the ledger name; "
    "in others it is the narration. Map it explicitly.",
}


@dataclass
class ColumnMapping:
    """The resolved header -> canonical-field mapping, and what could not be resolved."""

    resolved: dict[str, str] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)
    ambiguous: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        """Whether the minimum needed to build a ledger is present."""
        return not self.missing_required

    @property
    def missing_required(self) -> list[str]:
        needed = {"voucher_id", "voucher_date", "account_name"}
        has_amount = has_amount_columns(self.resolved.values())
        missing = sorted(needed - set(self.resolved.values()))
        if not has_amount:
            missing.append("debit/credit or amount")
        return missing


def has_amount_columns(targets: Iterable[str]) -> bool:
    """Whether mapped columns can produce debits and credits.

    One rule, used everywhere: either side of a rupee or paise debit/credit
    pair (the other side is then zero), or a single signed amount.
    """
    found = set(targets)
    return bool(found & {"debit", "credit", "debit_paise", "credit_paise", "amount"})


def normalise(header: str) -> str:
    """Lower-case, collapse punctuation and whitespace, for tolerant comparison."""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in header.lower())
    return " ".join(cleaned.split())


def infer_mapping(headers: list[str], *, overrides: dict[str, str] | None = None) -> ColumnMapping:
    """Infer a canonical mapping from column headers.

    ``overrides`` maps a header to a canonical field and always wins, which is
    how the UI will let a reviewer correct a guess.
    """
    overrides = overrides or {}
    mapping = ColumnMapping()
    claimed: dict[str, str] = {}

    for header in headers:
        if header in overrides:
            mapping.resolved[header] = overrides[header]
            continue

        key = normalise(header)
        matches = sorted(fld for fld, names in ALIASES.items() if key in names)

        if not matches:
            mapping.unmapped.append(header)
        elif len(matches) > 1:
            mapping.ambiguous[header] = matches
        else:
            field_name = matches[0]
            if field_name in claimed:
                # Two headers both claim one field: refuse rather than pick.
                mapping.ambiguous[header] = [field_name]
                mapping.ambiguous[claimed[field_name]] = [field_name]
            else:
                claimed[field_name] = header
                mapping.resolved[header] = field_name

    return mapping


def explain_ambiguity(header: str) -> str | None:
    """A human note about why a header is hard to place, if we have one."""
    return _AMBIGUOUS_NOTE.get(normalise(header))
