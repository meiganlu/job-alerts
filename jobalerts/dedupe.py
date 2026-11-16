"""Separates new jobs from ones already seen or copies of seen ones."""
import hashlib
import re

from jobalerts.models import Job
from jobalerts.store import SeenStore


def _clean(text: str) -> str:
    """Lowercase, collapse runs of whitespace into one space & trim the ends."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def fingerprint(job: Job) -> str:
    """A hash for the job's content. Note: the same job posted in several cities gets the same fingerprint."""
    parts = [_clean(job.company), _clean(job.title), _clean(job.description)]
    text = "|".join(parts)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def split_new(jobs: list[Job], store: SeenStore) -> tuple[list[Job], list[tuple[Job, str]]]:
    """Returns (new_jobs, copies). Each copy is (job, key of the original it duplicates)."""
    new_jobs = []
    copies = []
    for job in jobs:
        if store.has_key(job.key):
            continue  # check 1: seen this exact listing before
        store.add_key(job.key)

        fp = fingerprint(job)
        original_key = store.first_key_for(fp)
        if original_key:
            copies.append((job, original_key))  # check 2: same content, different listing
        else:
            store.add_fingerprint(fp, job.key)
            new_jobs.append(job)
    store.save()
    return new_jobs, copies


def title_key_of(company: str, title: str) -> str:
    """Company + title, ignoring parentheses: '(NYC)' and '(SF)' versions match."""
    return f"{_clean(company)}|{_clean(re.sub(r'\([^)]*\)', '', title))}"


def title_key(job: Job) -> str:
    return title_key_of(job.company, job.title)