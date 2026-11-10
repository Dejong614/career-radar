"""Transparent subject relevance for a transportation PhD + statistics master's.

Uses title and extracted skill names, so historical snapshots can be re-scored
under the same rule. This is subject relevance, not hiring eligibility or a
probability of getting an interview. No LLM/API calls.
"""
import re

PROFILE_VERSION = "transport-statistics-v2"
STAT_SKILLS = {"Statistics", "Causal inference", "Experimentation", "Risk modeling", "Pricing models", "Optimization", "Travel demand modeling", "Traffic simulation"}


def background_match(job):
    title = job["title"].lower()
    skills = {s["name"] for s in job.get("skills", [])}
    reasons = []
    core = {
        "traffic": r"research|scientist|model|data|analyst|safety|simulation|demand|operations|planning",
        "insurance": r"research|scientist|risk.*model|pricing|predictive|actuar",
        "av": r"safety|validat|evaluat|data scien|statistic|prediction|forecast|planning|simulation|behavior|risk|operations research",
    }
    if re.search(core.get(job["track"], r"(?!)"), title):
        reasons.append({"kind": "title", "label": "职位主题与交通 / 统计研究相关", "evidence": job["title"]})
    shared = sorted(skills & STAT_SKILLS)
    if shared:
        reasons.append({"kind": "skill", "label": "统计、建模或优化", "evidence": " / ".join(shared)})
    if job["track"] == "traffic" and not reasons:
        reasons.append({"kind": "title", "label": "交通工程领域背景", "evidence": job["title"]})
    # Generic perception/infrastructure roles are retained in the ledger but
    # hidden by the default subject filter unless quantitative evidence exists.
    level = "core" if len(reasons) >= 2 else "related" if reasons else "adjacent"
    flags = []
    if re.search(r"\b(?:staff|principal|director|head|senior|sr\.?|manager)\b", title):
        flags.append("资深岗位：请核对工作年限")
    if "Actuarial" in skills or "actuar" in title:
        flags.append("精算方向：请核对考试 / 资格要求")
    return {"version": PROFILE_VERSION, "level": level, "reasons": reasons, "flags": flags}


def job_kind(job):
    text = job.get("title", "") + " " + job.get("employment", "")
    if re.search(r"\b(?:intern(?:ship)?s?|co[ -]?op)\b", text, re.I):
        return "intern"
    if re.search(r"contract|temporary|part.time|student worker", text, re.I):
        return "other"
    # Some public boards omit employment metadata. Do not label those full-time.
    return "job" if re.search(r"full[ -]?time|permanent", text, re.I) else "unspecified"
