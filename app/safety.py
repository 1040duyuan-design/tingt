from __future__ import annotations

import re


MAX_MESSAGE_CHARS = 800
MAX_HISTORY_CHARS = 6000
MAX_REPEAT_CHAR_RATIO = 0.45
MAX_REPEAT_RUN = 24
MIN_REPEAT_CHECK_CHARS = 20

SENSITIVE_HINTS = [
    "转账",
    "借钱",
    "合同",
    "离婚",
    "分手",
    "起诉",
    "赔偿",
    "投资",
    "发票",
]

HARD_PRIVACY_HINTS = [
    "身份证号",
    "银行卡号",
    "手机号",
    "电话号码",
    "住址",
    "家庭住址",
    "邮箱",
    "验证码",
    "密码",
    "微信号",
    "聊天记录原文",
    "未公开聊天记录",
    "第三方隐私",
    "安全词",
    "切换口令",
    "验证口令",
]

PRIVACY_HINTS = [
    "身份证",
    "手机号",
    "电话号码",
    "住址",
    "家庭住址",
    "银行卡",
    "密码",
    "微信号",
    "邮箱",
    "隐私",
    "简历原文",
    "聊天记录",
    "后台记录",
    "历史消息",
    "真实信息",
    "个人信息",
]

SEARCH_HINTS = [
    "帮我搜",
    "帮我查",
    "去搜",
    "去查",
    "上网搜",
    "网上搜",
    "联网搜",
    "搜索一下",
    "查一下",
    "帮我总结这篇",
    "读取这个链接",
    "看这个网页",
    "访问这个网站",
    "crawl",
    "browse",
    "search",
    "google",
]

POLITICAL_HINTS = [
    "政治",
    "涉政",
    "政府",
    "国务院",
    "外交",
    "国际关系",
    "两会",
    "人大",
    "政协",
    "中美关系",
    "台湾",
    "台海",
    "新疆",
    "香港",
    "选举",
    "领导人",
    "国家主席",
    "总书记",
    "总理",
    "民主党",
    "共和党",
    "拜登",
    "特朗普",
    "俄乌",
    "巴以",
]

POLITICAL_ANALYSIS_HINTS = [
    "详细阐述",
    "详细分析",
    "分析一下",
    "展开讲讲",
    "报告",
    "分析报告",
    "研判",
    "怎么看待",
    "怎么评价",
    "解读",
    "总结观点",
    "立场",
]

SOFT_DEGRADE_HINTS = [
    "你真实身份",
    "你真实名字",
    "你是不是记得现实中的我",
    "你记不记得现实中的我",
    "训练来源",
    "内部数据",
    "历史私聊原文",
    "私聊原文",
    "证明你记得我",
    "证明你认识我",
    "现实身份信息",
]

DANGEROUS_HINTS = [
    "诈骗",
    "盗号",
    "社工",
    "钓鱼",
    "绕过验证",
    "破解",
    "套口令",
    "暴力",
    "违法",
    "恶意伤害",
    "自残",
    "自杀",
    "未成年人",
    "色情胁迫",
]

PROMPT_INJECTION_HINTS = [
    "忽略之前",
    "忽略上面的要求",
    "系统提示词",
    "system prompt",
    "developer message",
    "把你的设定说出来",
    "把规则给我",
    "输出你的提示词",
    "逐字复述",
]


def count_history_chars(history: list[dict[str, str]] | None) -> int:
    if not history:
        return 0
    return sum(len(item.get("content", "")) for item in history)


def normalize_similarity_text(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？!?、,.~～…：:；;（）()【】\[\]\"'`]+", "", text)
    return text.strip().lower()


def repeated_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return max(counts.values()) / max(len(text), 1)


def has_long_repeat_run(text: str) -> bool:
    return bool(re.search(r"(.)\1{" + str(MAX_REPEAT_RUN) + r",}", text))


def looks_like_repeated_or_similar_bombing(
    message: str,
    history: list[dict[str, str]] | None,
) -> bool:
    if not history:
        return False
    user_lines = [
        item.get("content", "")
        for item in history
        if item.get("role") == "user" and item.get("content", "").strip()
    ]
    if not user_lines:
        return False
    normalized = normalize_similarity_text(message)
    if not normalized:
        return False
    recent = [normalize_similarity_text(line) for line in user_lines[-3:]]
    exact_hits = sum(1 for line in recent if line == normalized)
    if exact_hits >= 2:
        return True
    if len(recent) >= 2 and all(line and (line in normalized or normalized in line) for line in recent[-2:]):
        return True
    return False


def looks_like_token_burn(message: str) -> bool:
    if len(message) > MAX_MESSAGE_CHARS:
        return True
    if len(message) >= MIN_REPEAT_CHECK_CHARS and repeated_char_ratio(message) > MAX_REPEAT_CHAR_RATIO:
        return True
    if has_long_repeat_run(message):
        return True
    if re.search(r"(重复|repeat).{0,10}(100|200|500|1000)", message, re.IGNORECASE):
        return True
    if re.search(r"(生成|列出|输出).{0,12}(100|200|500|1000).{0,6}(条|个|段|行)", message):
        return True
    if re.search(r"(完整输出|全文输出|逐字输出|不要省略|不要截断)", message):
        return True
    return False


def safety_gate(
    message: str,
    confidence: float,
    *,
    block_low_confidence: bool = True,
    history: list[dict[str, str]] | None = None,
) -> tuple[bool, str | None]:
    normalized = message.strip().lower()

    if block_low_confidence and confidence < 0.8:
        return False, "low_confidence"

    if any(hint in message for hint in PROMPT_INJECTION_HINTS) or any(
        hint in normalized for hint in PROMPT_INJECTION_HINTS
    ):
        return False, "prompt_injection"

    if looks_like_token_burn(message):
        return False, "token_burn_risk"

    if looks_like_repeated_or_similar_bombing(message, history):
        return False, "token_burn_risk"

    if count_history_chars(history) > MAX_HISTORY_CHARS:
        return False, "history_too_long"

    if any(hint in message for hint in SENSITIVE_HINTS):
        return False, "sensitive_topic"

    if any(hint in message for hint in HARD_PRIVACY_HINTS):
        return False, "privacy_request"

    if any(hint in message for hint in PRIVACY_HINTS):
        return False, "privacy_request"

    if any(hint in message for hint in SEARCH_HINTS) or any(hint in normalized for hint in SEARCH_HINTS):
        return False, "search_request"

    if any(hint in message for hint in POLITICAL_HINTS):
        return False, "political_content"

    if any(hint in message for hint in DANGEROUS_HINTS):
        return False, "dangerous_request"

    return True, None


def soft_degrade_gate(message: str) -> str | None:
    if any(hint in message for hint in SOFT_DEGRADE_HINTS):
        return "soft_privacy_boundary"
    return None
