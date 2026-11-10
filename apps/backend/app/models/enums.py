from enum import StrEnum


class Stage(StrEnum):
    found = "found"
    applied = "applied"
    screening = "screening"
    interview_scheduled = "interview_scheduled"
    interviewing = "interviewing"
    offer = "offer"
    accepted = "accepted"
    rejected = "rejected"
    ghosted = "ghosted"
    parked = "parked"


class Source(StrEnum):
    naukri = "naukri"
    linkedin = "linkedin"
    referral = "referral"
    recruiter = "recruiter"
    walkin = "walkin"
    other = "other"


class WorkMode(StrEnum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class ContactRole(StrEnum):
    recruiter = "recruiter"
    hr = "hr"
    manager = "manager"
    referrer = "referrer"


class InteractionType(StrEnum):
    call = "call"
    email = "email"
    linkedin = "linkedin"
    whatsapp = "whatsapp"
    interview = "interview"
    nudge = "nudge"
    # Not in the original brief: system-generated record written by POST /move.
    # It is excluded from "days since contact" because it is not real contact.
    stage_change = "stage_change"


class Direction(StrEnum):
    in_ = "in"
    out = "out"


class FollowupChannel(StrEnum):
    email = "email"
    call = "call"
    linkedin = "linkedin"
    whatsapp = "whatsapp"


class FollowupStatus(StrEnum):
    pending = "pending"
    done = "done"
    skipped = "skipped"


class PrepCategory(StrEnum):
    python = "python"
    fastapi = "fastapi"
    db = "db"
    react = "react"
    ai = "ai"
    system_design = "system-design"
    behavioral = "behavioral"


class PrepStatus(StrEnum):
    todo = "todo"
    doing = "doing"
    done = "done"
