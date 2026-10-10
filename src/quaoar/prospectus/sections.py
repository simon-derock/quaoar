# section locator: titles and their order come from the table of contents, start pages from
# headings near the top of a page, found strictly in that order; a section is never guessed
import re
from dataclasses import dataclass

from quaoar.prospectus.pdf import Page

TARGETS: dict[str, re.Pattern[str]] = {
    "general_information": re.compile(r"^GENERAL INFORMATION$"),
    "objects": re.compile(r"^OBJECTS? (OF|FOR) THE (ISSUE|OFFER)$"),
    "business": re.compile(r"^(OUR )?BUSINESS( OVERVIEW)?$"),
    "promoters": re.compile(r"^OUR PROMOTERS?( AND PROMOTERS?[' ]?S? GROUPS?)?$"),
    "group_companies": re.compile(
        r"^(INFORMATION WITH RESPECT TO )?(OUR )?GROUP (COMPAN(Y|IES)|ENTIT(Y|IES))"
        r"( OF OUR COMPANY)?( ?/ ?ENTITIES)?$"
    ),
    # filings misspell this one ("DEVELOPEMENT", "DEVLOPMENTS"), so any DEV... word counts
    "litigation": re.compile(r"^OUTSTANDING LITIGATIONS? AND MATERIAL DEV\w*$"),
    "regulatory": re.compile(r"^OTHER REGULATORY AND STATUTORY DISCL\w+$"),
}
TOC_TITLE = re.compile(r"^((TABLE( OF)? )?CONTENTS?|INDEX( OF CONTENTS?)?)$")
LEADER = re.compile(r"^(?P<title>.+?)\s*[._]{3,}\s*\d{0,4}$")
# some filings print no dotted leaders: "GENERAL INFORMATION 81"; a title carries no digits, which keeps body text out
# a part heading ("I. GENERAL", "SECTION III - INTRODUCTION") is its own line, never the first half of a wrapped title
PART = re.compile(r"^([IVXL]+[.:]\s|SECTION\s)")
PLAIN = re.compile(r"^(?P<title>[A-Z][^\d]*?[A-Z)])\s+\d{1,4}$")
PAGE_HEADER = re.compile(
    r"^(\d{1,4}\s*\|\s*P\s*A\s*G\s*E|PAGE\s+\d{1,4}(\s+OF\s+\d{1,4})?|\d{1,4})$"
)
TOP_LINES = 4
TOC_SEARCH_PAGES = 15


@dataclass(frozen=True, slots=True)
class Section:
    name: str
    title: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SectionMap:
    sections: dict[str, Section]
    missing: tuple[str, ...]
    toc_page: int | None


def locate_sections(pages: list[Page]) -> SectionMap:
    toc_page, titles = read_toc(pages)
    starts = find_starts(pages, titles, after=toc_page or 0)

    found: dict[str, Section] = {}
    ordered = sorted(starts.items(), key=lambda item: item[1])
    for index, (title, start) in enumerate(ordered):
        name = target_name(title)
        if name is None or name in found:
            continue
        # a section runs until the next located title, whatever that title is
        end = ordered[index + 1][1] - 1 if index + 1 < len(ordered) else pages[-1].number
        found[name] = Section(name, title, start, max(start, end))
    missing = tuple(sorted(set(TARGETS) - set(found)))
    return SectionMap(found, missing, toc_page)


def read_toc(pages: list[Page]) -> tuple[int | None, list[str]]:
    for page in pages[:TOC_SEARCH_PAGES]:
        lines = clean_lines(page.text)
        if not any(TOC_TITLE.match(line) for line in lines):
            continue
        titles = toc_titles(lines)
        # a contents list can spill onto the next page
        follow = next((p for p in pages if p.number == page.number + 1), None)
        if follow is not None:
            titles += toc_titles(clean_lines(follow.text))
        return page.number, titles
    return None, []


def toc_titles(lines: list[str]) -> list[str]:
    titles: list[str] = []
    pending = ""
    for line in lines:
        match = LEADER.match(line) or PLAIN.match(line)
        if match:
            # a title that normalises to nothing (a lone full stop) must not match any page
            if title := normal(f"{pending} {match.group('title')}"):
                titles.append(title)
            pending = ""
        elif PART.match(line):
            pending = ""
        elif line.isupper() and not TOC_TITLE.match(line) and not any(c.isdigit() for c in line):
            # a long title wraps: its first half has no dotted leader
            pending = f"{pending} {line}".strip()
    return titles


def find_starts(pages: list[Page], titles: list[str], after: int) -> dict[str, int]:
    starts: dict[str, int] = {}
    cursor = after + 1
    tops = [(page.number, top_lines(page)) for page in pages]
    for title in titles:
        # a part heading and its first chapter often share a page, so the cursor page counts
        for number, lines in tops:
            if number >= cursor and title in lines:
                starts[title] = number
                cursor = number
                break
    return starts


def top_lines(page: Page) -> set[str]:
    lines = [line for line in clean_lines(page.text) if not PAGE_HEADER.match(line)]
    return {normal(line) for line in lines[:TOP_LINES]}


SECTION_PREFIX = re.compile(r"^SECTION (- )?[IVXL]+ ?[-:] ?")


def target_name(title: str) -> str | None:
    # some prospectuses title a chapter "SECTION V - GENERAL INFORMATION"; the prefix is not part of the name
    bare = SECTION_PREFIX.sub("", title)
    return next((name for name, pattern in TARGETS.items() if pattern.match(bare)), None)


def clean_lines(text: str) -> list[str]:
    return [" ".join(line.split()).upper() for line in text.splitlines() if line.strip()]


def normal(text: str) -> str:
    # en and em dashes and the curly apostrophe all read as their plain forms
    text = text.upper().replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    text = re.sub(r"\s*-\s*", " - ", text)
    # a contents list and the heading it points to often differ in these small ways only
    text = (
        text.replace(" & ", " AND ")
        .replace("LITIGATIONS", "LITIGATION")
        .replace(" OTHER MATERIAL", " MATERIAL")
    )
    return " ".join(text.split()).strip(" .")
