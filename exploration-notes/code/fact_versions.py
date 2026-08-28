"""fact_versions.py — latest-number-wins: 版本化数字事实的 supersedence 签名解析 (Research #091)

零依赖 Python 3.10+。核心问题：同一 (entity, predicate) 出现多个不同数值时，
哪个是"现在"的值？——答题时（answer-time）确定性仲裁，而非写入时 LLM 失效
（Zep/Graphiti 路线）。

Supersedence 签名 = (entity, predicate, unit_domain)。
单位语义域是版本边界：2 hours 与 120 minutes 是同一事实的两个版本；
$90k 与 €90k 是两个共存事实（域不同，永不互斥）。
显式撤回无替代 → ABSTAIN（不是旧值）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 单位语义域（#090 判分侧洞察搬到检索侧：单位域是等价/版本的边界）
# ---------------------------------------------------------------------------

_TIME_TO_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400, "week": 604800, "weeks": 604800,
}

# 距离/货币不做换算（#090 判分纪律：5 miles ≢ 8 km, $5 ≢ €5）
# → 距离按单位分域，货币按币种分域


def unit_domain(value: float, unit: str) -> tuple[str, float]:
    """返回 (语义域, 规范化值)。同域内值可比；跨域永不互斥。"""
    u = unit.strip().lower()
    if u in _TIME_TO_SECONDS:
        return ("time:s", value * _TIME_TO_SECONDS[u])
    if u in {"$", "usd", "dollars", "dollar"}:
        return ("currency:usd", value)
    if u in {"€", "eur", "euros", "euro"}:
        return ("currency:eur", value)
    if u in {"¥", "jpy", "yen"}:
        return ("currency:jpy", value)
    if u in {"km", "kilometers", "kilometres"}:
        return ("distance:km", value)
    if u in {"miles", "mile", "mi"}:
        return ("distance:mile", value)
    if u in {"kg", "kilograms"}:
        return ("mass:kg", value)
    if u in {"lbs", "pounds"}:
        return ("mass:lb", value)
    if u in {"", "count", "people", "followers", "items", "times", "x"}:
        return ("count", value)
    return (f"raw:{u}", value)  # 未识别单位：按字面分域（保守，永不误合并）


@dataclass(frozen=True)
class Fact:
    """一条从会话流抽取的（数字型）事实。seq = 会话序，即系统时间钟。"""
    entity: str          # 已 canonicalize 的实体（amg: resolve_entity_variants 之后的形态）
    predicate: str       # 归一化谓词短语，如 "followers" / "rent" / "commute"
    value: float
    unit: str
    seq: int             # ingestion order — LME haystack 的 session/turn 序
    session: str
    text: str = ""       # evidence


@dataclass(frozen=True)
class Retraction:
    """显式撤回（"I don't ... anymore" / "I paid it off"），不带新值。"""
    entity: str
    predicate: str
    seq: int
    session: str
    text: str = ""


@dataclass
class Resolution:
    status: str                       # LATEST_WON | NO_CHANGE | INVALIDATED | TIE | MULTI_DOMAIN
    value: float | None = None
    domain: str | None = None
    seq: int | None = None
    session: str | None = None
    superseded: list[dict] = field(default_factory=list)
    domains: list[dict] = field(default_factory=list)   # MULTI_DOMAIN 时填充
    evidence: str | None = None

    @property
    def answerable(self) -> bool:
        return self.status in {"LATEST_WON", "NO_CHANGE"}


def _signature(f: Fact) -> tuple[str, str, str]:
    domain, _norm = unit_domain(f.value, f.unit)
    return (f.entity, f.predicate, domain)


def resolve(
    facts: list[Fact],
    retractions: list[Retraction],
    entity: str,
    predicate: str,
) -> Resolution:
    """按 supersedence 签名解析某 (entity, predicate) 的当前值。

    返回 Resolution：answerable=True 才可作答；否则按弃权家族处理。
    """
    pool = [f for f in facts if f.entity == entity and f.predicate == predicate]
    if not pool:
        return Resolution(status="INVALIDATED", evidence="no facts")  # 空集=机制门前弃权

    by_domain: dict[str, list[Fact]] = {}
    for f in pool:
        sig = _signature(f)
        by_domain.setdefault(sig[2], []).append(f)

    # 多语义域共存 → 交给问题里的单位提示选择（"the question is the join condition"）
    if len(by_domain) > 1:
        listing = []
        for dom, fs in sorted(by_domain.items()):
            latest = max(fs, key=lambda f: (f.seq, f.session))
            listing.append({
                "domain": dom, "latest": latest.value, "seq": latest.seq,
                "session": latest.session, "text": latest.text,
            })
        return Resolution(status="MULTI_DOMAIN", domains=listing)

    dom = next(iter(by_domain))
    versions = sorted(by_domain[dom], key=lambda f: f.seq)

    # 显式撤回：签名级（entity, predicate）匹配，撤回 seq 晚于最新事实 seq 才生效
    latest_fact = versions[-1]
    last_retraction = max(
        (r for r in retractions if r.entity == entity and r.predicate == predicate),
        key=lambda r: r.seq, default=None,
    )
    if last_retraction is not None and last_retraction.seq > latest_fact.seq:
        return Resolution(
            status="INVALIDATED", domain=dom, seq=last_retraction.seq,
            session=last_retraction.session, evidence=last_retraction.text,
        )

    latest, canonical = unit_domain(latest_fact.value, latest_fact.unit)
    norm = lambda f: unit_domain(f.value, f.unit)[1]
    superseded = [
        {"value": f.value, "seq": f.seq, "session": f.session, "text": f.text}
        for f in versions[:-1]
    ]

    if len({norm(f) for f in versions}) > 1:
        return Resolution(  # 真版本冲突：最新 seq 胜
            status="LATEST_WON", value=latest_fact.value, domain=dom,
            seq=latest_fact.seq, session=latest_fact.session,
            superseded=superseded, evidence=latest_fact.text,
        )
    return Resolution(  # 多次陈述但值相同：无冲突
        status="NO_CHANGE", value=latest_fact.value, domain=dom,
        seq=latest_fact.seq, session=latest_fact.session,
        superseded=superseded, evidence=latest_fact.text,
    )


def resolve_with_hint(
    facts: list[Fact], retractions: list[Retraction],
    entity: str, predicate: str, unit_hint: str,
) -> Resolution:
    """问题带单位提示时（"how much ... in dollars"），先选域再解析。"""
    r = resolve(facts, retractions, entity, predicate)
    if r.status != "MULTI_DOMAIN":
        return r
    want, _ = unit_domain(0.0, unit_hint)
    match = [d for d in r.domains if d["domain"] == want]
    if match:
        d = match[0]
        return Resolution(status="LATEST_WON", value=d["latest"],
                          domain=d["domain"], seq=d["seq"],
                          session=d["session"], evidence=d["text"])
    return r  # 提示与任何域都不匹配 → 仍 MULTI_DOMAIN，调用方弃权


# ---------------------------------------------------------------------------
# 自测（12 用例，覆盖 LME kupdate 真实形态 + 劫持陷阱）
# ---------------------------------------------------------------------------

def _self_test() -> None:
    F, R = Fact, Retraction
    # 1. 精确复刻 LME kupdate 形态 a2f3aa27："1250→1300 followers"
    facts = [
        F("alex", "followers", 1250, "count", 2, "s2", "I hit 1250 followers"),
        F("alex", "followers", 1300, "count", 8, "s8", "1300 followers now"),
    ]
    r = resolve(facts, [], "alex", "followers")
    assert r.status == "LATEST_WON" and r.value == 1300 and len(r.superseded) == 1, r
    assert r.superseded[0]["value"] == 1250

    # 2. 时间域归一化：2 hours 与 120 minutes 是同一事实（同域同值 → NO_CHANGE）
    facts2 = [
        F("sam", "commute", 2, "hours", 1, "s1", "takes 2 hours"),
        F("sam", "commute", 120, "minutes", 5, "s5", "actually 120 minutes"),
    ]
    r2 = resolve(facts2, [], "sam", "commute")
    assert r2.status == "NO_CHANGE" and r2.value == 120, r2

    # 3. 货币域隔离：$90k 与 €90k 共存，不互斥 → MULTI_DOMAIN
    facts3 = [
        F("kim", "salary", 90000, "$", 1, "s1", "salary hit $90k"),
        F("kim", "salary", 90000, "€", 3, "s3", "euro side pays €90k"),
    ]
    r3 = resolve(facts3, [], "kim", "salary")
    assert r3.status == "MULTI_DOMAIN" and len(r3.domains) == 2, r3
    r3h = resolve_with_hint(facts3, [], "kim", "salary", "usd")
    assert r3h.answerable and r3h.domain == "currency:usd" and r3h.value == 90000, r3h

    # 4. 显式撤回无替代 → INVALIDATED（弃权，绝不回吐旧值 $1200）
    facts4 = [F("lee", "rent", 1200, "$", 3, "s3", "rent is $1200")]
    ret4 = [R("lee", "rent", 9, "s9", "I don't rent in Tokyo anymore")]
    r4 = resolve(facts4, ret4, "lee", "rent")
    assert r4.status == "INVALIDATED" and not r4.answerable, r4

    # 5. 撤回后又给新值 → 新值胜（撤回被新事实取代）
    facts5 = [
        F("lee", "rent", 1200, "$", 3, "s3", "rent $1200"),
        F("lee", "rent", 1500, "$", 7, "s7", "new place, $1500"),
    ]
    ret5 = [R("lee", "rent", 4, "s4", "moved out")]
    r5 = resolve(facts5, ret5, "lee", "rent")
    assert r5.status == "LATEST_WON" and r5.value == 1500, r5

    # 6. 撤回早于后续事实 → 撤回无效（旧顺序陈述）
    ret6 = [R("lee", "rent", 2, "s2", "no rent mention backward")]
    r6 = resolve(facts5, ret6, "lee", "rent")
    assert r6.status == "LATEST_WON" and r6.value == 1500, r6

    # 7. 值不变重复陈述 → NO_CHANGE（不是冲突）
    facts7 = [
        F("ana", "followers", 800, "count", 1, "s1", ""),
        F("ana", "followers", 800, "count", 6, "s6", ""),
    ]
    r7 = resolve(facts7, [], "ana", "followers")
    assert r7.status == "NO_CHANGE" and r7.value == 800, r7

    # 8. 不同谓词永不冲突（followers vs following 劫持陷阱）
    facts8 = [
        F("max", "followers", 1250, "count", 2, "s2", ""),
        F("max", "following", 480, "count", 8, "s8", ""),
    ]
    r8 = resolve(facts8, [], "max", "followers")
    assert r8.status == "NO_CHANGE" and r8.value == 1250, r8

    # 9. 不同实体永不冲突（人名域隔离：Raj 的 followers 不劫持 Priya 的问题）
    facts9 = [
        F("raj", "followers", 1250, "count", 2, "s2", ""),
        F("priya", "followers", 1300, "count", 8, "s8", ""),
    ]
    r9 = resolve(facts9, [], "raj", "followers")
    assert r9.status == "NO_CHANGE" and r9.value == 1250, r9

    # 10. 距离单位分域（5 miles ≢ 8 km，不换算 → MULTI_DOMAIN）
    facts10 = [
        F("tom", "commute", 5, "miles", 1, "s1", "5 miles"),
        F("tom", "commute", 8, "km", 4, "s4", "8 km"),
    ]
    r10 = resolve(facts10, [], "tom", "commute")
    assert r10.status == "MULTI_DOMAIN", r10

    # 11. 同签名真版本冲突：数值递进链，全链可审计
    facts11 = [
        F("zoe", "weight", 70, "kg", 1, "s1", ""),
        F("zoe", "weight", 68, "kg", 3, "s3", ""),
        F("zoe", "weight", 65, "kg", 9, "s9", ""),
    ]
    r11 = resolve(facts11, [], "zoe", "weight")
    assert r11.status == "LATEST_WON" and r11.value == 65 and len(r11.superseded) == 2, r11

    # 12. 空集 → 机制门前弃权
    r12 = resolve([], [], "ghost", "followers")
    assert not r12.answerable, r12

    print("fact_versions self-test: 12/12 PASS")


if __name__ == "__main__":
    _self_test()
