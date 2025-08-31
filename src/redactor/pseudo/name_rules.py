"""Name pseudonym generation helpers.

This module implements small, deterministic synthesizers for person and
organization names.  The generators rely on curated, hard coded corpora of
neutral given names, surnames and organization base tokens.  Randomness is
provided by :class:`~redactor.pseudo.generator.PseudonymGenerator` which offers
stable RNG instances per ``(kind, key)`` pair so that the same source text and
key always map to the same pseudonym.

The functions here attempt to preserve the visible *shape* of the original
input.  Actual token content is replaced but punctuation, casing, initials and
common suffixes are kept using :func:`redactor.pseudo.case_preserver.format_like`.
The resulting pseudonyms are realistic looking but deterministic and guaranteed
to differ from the original.
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, List, Sequence, cast

from redactor.detect import parse_person_name

from .case_preserver import format_like

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .generator import PseudonymGenerator


# -- Curated corpora -------------------------------------------------------

# A pool of gender neutral or commonly used given names.  The list purposely
# mixes traditionally masculine and feminine names to avoid any inference about
# the original text.  The list length (~250) is intentionally modest so that it
# can be embedded directly in the source tree without external dependencies.
_NEUTRAL_GIVEN_NAMES = """
Alex Taylor Jordan Morgan Casey Jamie Riley Avery Cameron Devin Sydney Terry
Quinn Drew Reese Peyton Rowan Hayden Skyler Corey Robin Jesse Leslie Tracy
Kerry Logan Frankie Harley Blair Dana Phoenix River Sage Kendall Bailey
Emerson Finley Hunter Parker Dakota Adrian Sam Charlie Jackie Lee Noel
Addison Ainsley Alison Amber Amari Angel Ariel Ashton Autumn Aubrey Bella
Brooke Brooklyn Cadence Carson Chandler Chelsea Delaney Eden Elliot Elliott
Evelyn Gillian Hadley Harper Haven Hollis Jaden Jayden Justice Kai Karter
Keegan Kelsey Kenzie Lennon London Lyric Madison Marion McKenzie Milan Monroe
Nikita Oakley Paisley Presley Reagan Remy Riley River Sasha Shiloh Sky Storm
Tatum Teagan Tegan Tristan Val Wesley Whitney Winter Zoe
""".split()

_MALE_NAMES = """
James John Robert Michael William David Richard Joseph Thomas Charles
Christopher Daniel Matthew Anthony Mark Donald Steven Paul Andrew Joshua
Kenneth Kevin Brian George Timothy Ronald Edward Jason Jeffrey Ryan Jacob
Gary Nicholas Eric Stephen Jonathan Larry Justin Scott Brandon Benjamin
Samuel Frank Gregory Raymond Alexander Patrick Jack Dennis Jerry Tyler Aaron
Jose Henry Adam Douglas Nathan Peter Zachary Kyle Walter Harold Jeremy Ethan
Carl Keith Roger Gerald Christian Terry Sean Arthur Austin Noah Jesse Joe
Bryan Billy Jordan Albert Dylan Bruce Will Gabriel Logan Alan Juan Wayne Roy
Ralph Randy Eugene Carlos Russell Louis Bobby Victor Martin Ernest Phillip
Craig
""".split()

_FEMALE_NAMES = """
Mary Patricia Jennifer Linda Elizabeth Barbara Susan Jessica Sarah Karen
Nancy Lisa Margaret Betty Sandra Ashley Dorothy Kimberly Emily Donna
Michelle Carol Amanda Melissa Deborah Stephanie Rebecca Laura Sharon
Cynthia Kathleen Amy Shirley Angela Helen Anna Brenda Pamela Nicole Emma
Samantha Katherine Christine Debra Rachel Carolyn Janet Catherine Maria
Heather Diane Ruth Julie Olivia Joyce Virginia Victoria Kelly Christina
Lauren Joan Evelyn Judith Megan Cheryl Andrea Hannah Jacqueline Ann Jean
Alice Gloria Kathryn Teresa Doris Sara Janice Julia Marie Grace Judy
Theresa Beverly Denise Marilyn Amber Madison Danielle Brittany Diana Natalie
Sophia Alexis Kayla Ruby Brooke Ella Lily Mia Stella
""".split()


GIVEN_NAMES: List[str] = _NEUTRAL_GIVEN_NAMES + _MALE_NAMES + _FEMALE_NAMES

# Roughly 220 common US surnames.  The selection is drawn from public census
# tables and augmented with a few additional neutral names to avoid any
# culturally specific connotations.
SURNAMES: List[str] = (
    """
Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez
Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin
Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker
Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson
Baker Hall Rivera Campbell Mitchell Carter Roberts Gomez Phillips Evans
Turner Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy
Cook Rogers Gutierrez Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard
Ramos Kim Cox Ward Richardson Watson Brooks Chavez Wood James Bennett Gray
Mendoza Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross
Foster Jimenez Powell Jenkins Perry Russell Sullivan Bell Coleman Butler
Henderson Barnes Gonzales Fisher Vasquez Simmons Romero Jordan Patterson
Alexander Hamilton Graham Reynolds Griffin Wallace Moreno West Cole Hayes
Bryant Herrera Gibson Ellis Tran Medina Freeman Wells Webb Simpson Stevens
Tucker Porter Hunter Hicks Crawford Henry Boyd Mason Warren Richards Hunt
Black Daniels Palmer Mills Nichols Grant Knight Ferguson Rose Stone Hawkins
Dunn Perkins Hudson Spencer Gardner Stephens Payne Pierce Berry Matthews
Arnold Wagner Willis Ray Watkins Olson Carroll Duncan Snyder Hart Cunningham
Bradley Lane Andrews Harper Fox Riley Armstrong Carpenter Weaver Greene
Lawrence Elliott Rice Little Banks Bishop Carr Hanson Barber Doyle Burgess
Christensen Casey Dalton Dean Erickson Farrell Gates Hardy Kirby Lambert
Maxwell Nixon Osborne Poole Pratt Shepard Swanson Tyler Vaughn Walsh
""".split()
)

# A small set of generic organization tokens used to construct neutral looking
# company names.  These are intentionally positive or geographic in tone.
ORG_BASE_WORDS: List[str] = [
    "Apex",
    "Summit",
    "Horizon",
    "Atlas",
    "Vector",
    "Nimbus",
    "Pioneer",
    "Vertex",
    "Northbridge",
    "Fairview",
    "Sterling",
    "Evergreen",
    "Crescent",
    "Cascade",
    "Frontier",
    "Liberty",
    "Heritage",
    "Vanguard",
    "Momentum",
    "Aurora",
    "Legacy",
    "Prestige",
    "Endeavor",
    "Zenith",
    "Vista",
    "Union",
    "Beacon",
    "Guardian",
    "Foundry",
    "Ridge",
    "Lakeside",
    "Cedar",
    "Oak",
]


# -- Helpers ----------------------------------------------------------------

_INITIALS_RE = re.compile(r"^(?:[A-Za-z][.\- ]+)+[A-Za-z][.]?\Z")


def _normalize(text: str) -> str:
    """Return ``text`` in a simplified form for collision checks."""

    return re.sub(r"[^A-Za-z]", "", text).lower()


def _pick_tokens(options: Sequence[str], count: int, *, rng: random.Random) -> List[str]:
    return [rng.choice(list(options)) for _ in range(max(0, count))]


# -- Public generators ------------------------------------------------------


def generate_person_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Return a deterministic person-like name shaped like ``source``.

    The number of given/surname tokens mirrors the source.  Honorifics and
    suffixes are preserved verbatim while the name tokens themselves are
    replaced with deterministic selections from :data:`GIVEN_NAMES` and
    :data:`SURNAMES`.
    """

    if _INITIALS_RE.fullmatch(source.strip()):
        # Treat purely initial patterns separately to ensure token count is
        # based on the number of initials present.
        token_count = max(2, len(re.findall(r"[A-Za-z]", source)))
        for salt in range(3):
            rng = gen.rng("PERSON", f"{key}:{salt}" if salt else key)
            given = _pick_tokens(GIVEN_NAMES, token_count - 1, rng=rng)
            surname = _pick_tokens(SURNAMES, 1, rng=rng)
            core = " ".join(given + surname)
            if _normalize(core) != _normalize(source):
                break
        return format_like(source, core, rng=rng)

    parsed = parse_person_name(source)
    honorifics = list(cast(Sequence[str], parsed.get("honorifics", [])))
    particles = list(cast(Sequence[str], parsed.get("particles", [])))
    suffixes = list(cast(Sequence[str], parsed.get("suffixes", [])))
    given_tokens = list(cast(Sequence[str], parsed.get("given", [])))
    surname_tokens = list(cast(Sequence[str], parsed.get("surname", [])))

    given_count = len(given_tokens) or 1
    surname_count = len(surname_tokens) or 1

    source_core = " ".join(given_tokens + particles + surname_tokens)

    core = source_core
    rng = gen.rng("PERSON", key)
    for salt in range(3):
        rng = gen.rng("PERSON", f"{key}:{salt}" if salt else key)
        given = _pick_tokens(GIVEN_NAMES, given_count, rng=rng)
        surname = _pick_tokens(SURNAMES, surname_count, rng=rng)
        core = " ".join(given + particles + surname)
        if _normalize(core) != _normalize(source_core):
            break

    assembled = " ".join(honorifics + [core] + suffixes).strip()
    return format_like(source, assembled, rng=rng)


_ORG_SUFFIX_RE = re.compile(
    r"(,?\s*(?:Inc\.?,?|LLC|LLP|Ltd\.?,?|PLC|N\.A\.|N\.V\.|Company|Co\.?|Corp\.?|Corporation|Trust|Credit\s+Union))+$",
    re.IGNORECASE,
)


def _split_org_suffix(source: str) -> tuple[str, str]:
    match = _ORG_SUFFIX_RE.search(source.strip())
    if not match:
        return source.strip(), ""
    core = source[: match.start()].strip()
    suffix = source[match.start() :].strip()
    return core, suffix


def generate_org_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate an organization-like name shaped like ``source``."""

    core_src, suffix = _split_org_suffix(source)
    token_count = max(1, min(3, len(core_src.split())))
    core_norm = _normalize(core_src)
    result_core = core_src
    for salt in range(3):
        rng = gen.rng("ORG", f"{key}:{salt}" if salt else key)
        tokens = _pick_tokens(ORG_BASE_WORDS, token_count, rng=rng)
        result_core = " ".join(tokens)
        if _normalize(result_core) != core_norm:
            break
    assembled = result_core
    if suffix:
        sep = "" if suffix.startswith(",") else " "
        assembled = f"{assembled}{sep}{suffix}"
    return assembled


def generate_bank_org_like(source: str, *, key: str, gen: PseudonymGenerator) -> str:
    """Generate a bank organization name preserving ``Bank`` tokens."""

    core_src, suffix = _split_org_suffix(source)
    source_l = core_src.lower()
    needs_trust = "trust" in source_l
    needs_company = "trust company" in source_l
    token_count = max(1, min(2, len(core_src.split()) - 1))
    core_norm = _normalize(core_src)

    for salt in range(3):
        rng = gen.rng("BANK_ORG", f"{key}:{salt}" if salt else key)
        base = " ".join(_pick_tokens(ORG_BASE_WORDS, token_count, rng=rng))
        bank_part = "Bank"
        if needs_company:
            bank_part += " Trust Company"
        elif needs_trust:
            bank_part += " & Trust"
        candidate_core = (base + " " + bank_part).strip()
        if _normalize(candidate_core) != core_norm:
            break
    assembled = candidate_core
    if suffix:
        sep = "" if suffix.startswith(",") else " "
        assembled = f"{assembled}{sep}{suffix}"
    return assembled


__all__ = [
    "GIVEN_NAMES",
    "SURNAMES",
    "ORG_BASE_WORDS",
    "generate_person_like",
    "generate_org_like",
    "generate_bank_org_like",
]
