"""The title and department patterns that decide what counts as a tech IC role.

Every entry here was added because a real posting was classified wrongly
without it, and the comments say which. That matters more than usual: this is
the filter that decides what the salary statistics are *about*, and a word added
carelessly moves every published median.

The three lists are not symmetric, and the asymmetry is the design — see
:mod:`etl.roles.filter`.
"""

from __future__ import annotations

import re

__all__ = ["HARD_DENY", "SOFT_DENY", "ALLOW", "TECH_DEPARTMENT"]

#: Roles that are adjacent to engineering and are not it. A hard deny wins over
#: any allow signal, because these titles *contain* tech words: "Solutions
#: Engineer" and "Technical Program Manager" both match the allow list.
#:
#: The data-annotation entries are here for a different reason: gig labelling
#: work advertises at a median around $29k against a $221k IC median, and left
#: in it dragged the junior bucket down by a third.
HARD_DENY = re.compile(
    r"\b(product manager|program manager|product owner|technical program|"
    r"designer|ux designer|ui designer|product designer|graphic designer|"
    r"design lead|sales engineer|solutions engineer|solutions consultant|"
    r"solutions architect|sales development|account executive|account manager|"
    r"partnerships|go[- ]to[- ]market|\bgtm\b|"
    r"labeler|labelling|annotator|data annotation)\b",
    re.I,
)

#: Non-technical functions. Only applies when the title carries no allow signal,
#: so "Data Engineer, Marketing Analytics" survives and "Marketing Manager" does
#: not.
SOFT_DENY = re.compile(
    r"\b(sales|recruit|talent|\bhr\b|people ops|human resources|legal|counsel|"
    r"finance|accounting|marketing|content|community|customer success|"
    r"customer support|\bsupport\b|\boffice\b|coordinator|facilities|"
    r"executive assistant|administrative|receptionist)\b",
    re.I,
)

#: What makes a title technical. Broad on purpose: a title this misses can still
#: be rescued by its department, while a title it wrongly matches is only
#: rescued by a hard deny.
ALLOW = re.compile(
    r"\b(engineer|engineering|developer|programmer|software|backend|back[- ]end|"
    r"front[- ]?end|full[- ]?stack|sde|mobile|android|ios|data|machine learning|"
    r"\bml\b|\bai\b|mlops|devops|sre|site reliability|platform|infrastructure|"
    r"cloud|\bqa\b|quality assurance|sdet|test engineer|security|infosec|"
    r"applied scientist|research engineer|research scientist|analytics|"
    r"member of technical staff|\bmts\b)\b",
    re.I,
)

#: The last resort. Boards let a company name its departments freely, so this is
#: weaker evidence than a title and is only consulted when the title said
#: nothing either way.
TECH_DEPARTMENT = re.compile(
    r"engineering|data|infrastructure|platform|security|technolog|research|r&d", re.I
)
