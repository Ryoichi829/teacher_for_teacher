from __future__ import annotations

import json
import re
from pathlib import Path

from agents import Agent, function_tool

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_PATH = BASE_DIR / "knowledge" / "lesson_plan.json"
SLIDE_GUIDES_PATH = BASE_DIR / "knowledge" / "slide_guides.json"
WEB_APP_GUIDES_DIR = BASE_DIR / "knowledge" / "web_apps"

with KNOWLEDGE_PATH.open("r", encoding="utf-8") as f:
    LESSON = json.load(f)

with SLIDE_GUIDES_PATH.open("r", encoding="utf-8") as f:
    SLIDE_GUIDES = json.load(f)

WEB_APP_GUIDES: dict[str, dict] = {}
guide_paths = list(WEB_APP_GUIDES_DIR.glob("*.json"))
# ダウンロード時にweb_appsフォルダを作らず、knowledge直下へ置いた場合も
# 読み込めるようにする。lesson_plan等はapp_idがないため自動的に除外する。
guide_paths.extend(KNOWLEDGE_PATH.parent.glob("*.json"))
for guide_path in sorted(set(guide_paths)):
    with guide_path.open("r", encoding="utf-8") as f:
        guide = json.load(f)
    if "app_id" in guide:
        WEB_APP_GUIDES[guide["app_id"]] = guide

REQUIRED_WEB_APP_IDS = {
    "tokenization_app",
    "word2vec_similarity_app",
    "attention_weight_app",
    "colab_language_model",
}
missing_web_app_ids = REQUIRED_WEB_APP_IDS - WEB_APP_GUIDES.keys()
if missing_web_app_ids:
    missing = "、".join(sorted(missing_web_app_ids))
    raise FileNotFoundError(
        "Webアプリガイドが不足しています: "
        f"{missing}。knowledge/web_apps/ に tokenization.json、"
        "word2vec.json、attention.json、colab_language_model.jsonを配置してください。"
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _query_tokens(query: str) -> list[str]:
    q = _normalize(query)
    aliases = {
        "loss": ["loss", "誤差", "間違い"],
        "誤差": ["loss", "誤差", "間違い"],
        "attention": ["attention", "アテンション", "文脈", "やばい"],
        "アテンション": ["attention", "アテンション", "文脈", "やばい"],
        "word2vec": ["word2vec", "ベクトル", "類似語", "単語"],
        "ベクトル": ["word2vec", "ベクトル", "類似", "内積"],
        "transformer": ["transformer", "逐次", "文章全体"],
        "colab": ["colab", "言語モデル", "学習", "生成"],
        "言語モデル": ["言語モデル", "loss", "次単語予測", "文章生成", "colab"],
        "分かち書き": ["分かち書き", "単語分割", "トークン化"],
        "品詞": ["品詞", "形態素解析", "単語分割"],
        "名詞": ["名詞", "品詞", "形態素解析"],
        "アナロジー": ["アナロジー", "王様", "男性", "女性", "word2vec"],
        "可視化": ["可視化", "visualize", "位置関係", "attentionweight"],
        "やばい": ["やばい", "文脈", "attention", "多義語"],
        "ワークシート": ["ワークシート", "整理", "まとめ"],
        "スライド": ["スライド"],
    }
    tokens: list[str] = []
    # 英数字語と、日本語のまとまりを拾う
    tokens.extend(re.findall(r"[a-z0-9_]+|[ぁ-んァ-ヶ一-龥ー]{2,}", q))
    for key, vals in aliases.items():
        if key in q:
            tokens.extend(vals)
    return list(dict.fromkeys(t for t in tokens if t))


def _activity_text(a: dict) -> str:
    return " ".join(
        str(a.get(k, ""))
        for k in ["time", "topic_question", "student_activity", "teacher_support", "assessment", "slides"]
    )


@function_tool
def search_lesson_plan(query: str) -> str:
    """学習指導案を検索する。

    Args:
        query: 教員の質問に含まれる授業内容、概念、活動、スライド番号など。
    """
    tokens = _query_tokens(query)
    scored: list[tuple[float, dict]] = []

    for activity in LESSON["activities"]:
        text = _normalize(_activity_text(activity))
        score = 0.0
        for token in tokens:
            nt = _normalize(token)
            if nt and nt in text:
                score += 3.0
            # 2文字以上なら部分的な文字一致も弱く評価
            if len(nt) >= 2:
                score += sum(0.15 for i in range(len(nt) - 1) if nt[i:i+2] in text)
        # スライド番号を直接尋ねた場合を強く評価
        numbers = re.findall(r"\d+", query)
        if numbers and any(n in str(activity.get("slides", "")) for n in numbers):
            score += 5.0
        if score > 0:
            scored.append((score, activity))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [a for _, a in scored[:4]]

    if not selected:
        selected = LESSON["activities"][:3]

    out = ["【指導案検索結果】"]
    for a in selected:
        out.append(
            f"\n[{a['time']} / 対応スライド {a['slides']}]\n"
            f"学習内容・主な問い: {a['topic_question']}\n"
            f"生徒の活動: {a['student_activity']}\n"
            f"教師の働きかけ・留意点: {a['teacher_support']}\n"
            f"評価・見取り: {a['assessment']}"
        )

    # 全体方針も毎回付け、局所検索だけで授業思想を失わないようにする
    out.append("\n【指導上の共通方針】")
    out.extend(f"- {p}" for p in LESSON["teaching_points"])
    return "\n".join(out)


def _slide_search_text(slide: dict) -> str:
    """スライドガイドの検索対象フィールドを一つの文字列にまとめる。"""
    parts = [
        slide.get("title", ""),
        " ".join(slide.get("visible_content", [])),
        slide.get("speech_script", ""),
        slide.get("learning_goal", ""),
        " ".join(slide.get("related_concepts", [])),
        " ".join(slide.get("related_apps", [])),
        " ".join(slide.get("student_activity", [])),
        " ".join(slide.get("teacher_cautions", [])),
    ]
    return " ".join(str(part) for part in parts)


def _requested_slide_numbers(query: str) -> list[int]:
    """「スライド25」「25～29ページ」のような明示的な番号指定を取り出す。"""
    found: list[int] = []
    pattern = r"(?:スライド|ページ)\s*(\d{1,2})(?:\s*[～〜\-]\s*(\d{1,2}))?"
    for match in re.finditer(pattern, query, flags=re.IGNORECASE):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start:
            start, end = end, start
        found.extend(n for n in range(start, end + 1) if 1 <= n <= 39)
    return list(dict.fromkeys(found))


def _format_slide_guide(slide: dict) -> str:
    time_range = slide["time_range_minutes"]
    apps = []
    for app_id in slide.get("related_apps", []):
        app = SLIDE_GUIDES.get("app_catalog", {}).get(app_id, {})
        name = app.get("name", app_id)
        url = app.get("url")
        apps.append(f"{name} ({url})" if url else name)

    scope = slide.get("speech_scope_slides", [slide["slide_number"]])
    scope_note = ""
    if len(scope) > 1:
        scope_note = f"\n原稿の対応範囲: スライド{scope[0]}～{scope[-1]}の共通原稿"

    return (
        f"\n[スライド{slide['slide_number']} / "
        f"{time_range['start_minute']}～{time_range['end_minute']}分]\n"
        f"題名: {slide['title']}\n"
        f"画面の内容: {' / '.join(slide.get('visible_content', []))}\n"
        f"学習目標: {slide.get('learning_goal', '')}\n"
        f"スピーチ原稿:\n{slide.get('speech_script', '')}\n"
        f"生徒の活動: {' / '.join(slide.get('student_activity', [])) or '記載なし'}\n"
        f"関連アプリ: {' / '.join(apps) or 'なし'}\n"
        f"教師の注意点: {' / '.join(slide.get('teacher_cautions', [])) or '記載なし'}"
        f"{scope_note}"
    )


def _search_slide_guide(query: str, slide_number: int | None = None) -> str:
    """検索処理本体。テスト時にも直接呼び出せるようTool本体と分ける。"""
    slides = SLIDE_GUIDES["slides"]
    requested = [slide_number] if slide_number is not None else _requested_slide_numbers(query)
    requested = [n for n in requested if n is not None and 1 <= n <= len(slides)]

    if requested:
        selected = [slides[n - 1] for n in requested[:6]]
    else:
        tokens = _query_tokens(query)
        scored: list[tuple[float, bool, dict]] = []
        for slide in slides:
            text = _normalize(_slide_search_text(slide))
            title = _normalize(slide.get("title", ""))
            concepts = _normalize(" ".join(slide.get("related_concepts", [])))
            score = 0.0
            strong_match = False
            for token in tokens:
                nt = _normalize(token)
                if not nt:
                    continue
                if nt in title:
                    score += 5.0
                    strong_match = True
                if nt in concepts:
                    score += 4.0
                    strong_match = True
                if nt in text:
                    score += 2.0
                    strong_match = True
                if len(nt) >= 2:
                    score += sum(
                        0.08 for i in range(len(nt) - 1) if nt[i : i + 2] in text
                    )
            if score > 0:
                scored.append((score, strong_match, slide))

        # 完全一致が一件でもあれば、一般的な言い回しの部分一致だけで
        # 偶然拾ったスライドを除外する。
        if any(strong for _, strong, _ in scored):
            scored = [item for item in scored if item[1]]
        scored.sort(key=lambda item: (-item[0], item[2]["slide_number"]))
        selected = [slide for _, _, slide in scored[:3]]

    if not selected:
        return (
            "【スライド・スピーチ原稿検索結果】\n"
            "該当するスライドを特定できませんでした。スライド番号または扱いたい概念を確認してください。"
        )

    out = ["【スライド・スピーチ原稿検索結果】"]
    out.extend(_format_slide_guide(slide) for slide in selected)
    return "\n".join(out)


@function_tool
def search_slide_guide(query: str, slide_number: int | None = None) -> str:
    """スライドの表示内容、スピーチ原稿、学習目標、活動、注意点を検索する。

    Args:
        query: 教員の質問に含まれる説明内容、概念、授業での言い方など。
        slide_number: 特定のスライドを調べる場合の番号。番号不明の場合は省略する。
    """
    return _search_slide_guide(query, slide_number)


def _web_app_search_text(guide: dict) -> str:
    """Webアプリガイドの検索対象を一つの文字列にまとめる。"""
    return json.dumps(guide, ensure_ascii=False)


def _format_web_app_guide(guide: dict) -> str:
    lesson = guide.get("lesson", {})
    time_range = lesson.get("time_range_minutes", {})
    slides = "、".join(str(n) for n in lesson.get("slides", [])) or "記載なし"
    time_text = (
        f"{time_range.get('start_minute')}～{time_range.get('end_minute')}分"
        if time_range else "記載なし"
    )

    out = [
        f"\n[{guide['name']}]",
        f"URL: {guide.get('url', '記載なし')}",
        f"対応スライド・時間: スライド{slides} / {time_text}",
        f"目的: {lesson.get('purpose', '')}",
        f"学習目標: {lesson.get('learning_goal', '')}",
        "操作手順:",
    ]
    out.extend(f"{i}. {step}" for i, step in enumerate(guide.get("steps", []), 1))

    if guide.get("recommended_inputs"):
        out.append("試す入力:")
        for item in guide["recommended_inputs"]:
            out.append(
                f"- {item.get('text', '')}: {item.get('purpose', '')} "
                f"／声かけ: {item.get('teacher_prompt', '')}"
            )

    if guide.get("recommended_activities"):
        out.append("推奨する活動:")
        for item in guide["recommended_activities"]:
            example = item.get("expression") or item.get("input")
            if not example and item.get("inputs"):
                example = " / ".join(item["inputs"])
            example_text = f"（{example}）" if example else ""
            out.append(
                f"- {item.get('operation', '')}{example_text}\n"
                f"  声かけ: {item.get('teacher_prompt', '')}\n"
                f"  観察点: {item.get('observation', '')}"
            )

    if guide.get("heatmap_reading"):
        reading = guide["heatmap_reading"]
        out.append("ヒートマップの見方:")
        labels = {
            "vertical_axis": "縦軸",
            "horizontal_axis": "横軸",
            "cell_value": "マスの値",
            "row_sum": "行の合計",
            "color": "色",
        }
        out.extend(
            f"- {labels[key]}: {reading[key]}"
            for key in labels
            if reading.get(key)
        )

    if guide.get("extension_activity"):
        extension = guide["extension_activity"]
        out.append(f"発展の声かけ: {extension.get('teacher_prompt', '')}")
        ideas = extension.get("hint_ideas", [])
        if ideas:
            out.append(f"発展例: {' / '.join(ideas)}")

    out.append(f"授業での言い方: {guide.get('teacher_script', '')}")
    out.append("観察させること:")
    out.extend(f"- {point}" for point in guide.get("observation_points", []))
    out.append("教師からの問い:")
    out.extend(f"- {question}" for question in guide.get("teacher_questions", []))
    out.append("注意点:")
    out.extend(f"- {caution}" for caution in guide.get("teacher_cautions", []))

    troubleshooting = guide.get("troubleshooting", [])
    if troubleshooting:
        out.append("トラブル対応:")
        out.extend(
            f"- {item.get('problem', '')}: {item.get('response', '')}"
            for item in troubleshooting
        )
    return "\n".join(out)


def _search_web_app_guide(query: str, app_id: str | None = None) -> str:
    """WebアプリガイドをアプリIDまたは質問文で検索する。"""
    if app_id:
        guide = WEB_APP_GUIDES.get(app_id)
        if guide is not None:
            selected = [guide]
        else:
            # Agentが正式IDではなく「word2vec」「分かち書き」などを
            # app_idへ渡した場合も、質問文と合わせて表記揺れ検索へ回す。
            selected = []
            query = f"{query} {app_id}"
    else:
        selected = []

    if not selected:
        tokens = _query_tokens(query)
        normalized_query = _normalize(query)
        scored: list[tuple[float, dict]] = []
        for guide in WEB_APP_GUIDES.values():
            searchable = _normalize(_web_app_search_text(guide))
            identity = _normalize(
                " ".join(
                    [guide.get("app_id", ""), guide.get("name", "")]
                    + guide.get("aliases", [])
                )
            )
            score = 0.0
            if normalized_query and any(
                _normalize(alias) in normalized_query
                for alias in [guide.get("name", ""), *guide.get("aliases", [])]
                if alias
            ):
                score += 12.0
            for token in tokens:
                nt = _normalize(token)
                if nt and nt in identity:
                    score += 5.0
                if nt and nt in searchable:
                    score += 2.0
            if score > 0:
                scored.append((score, guide))
        scored.sort(key=lambda item: (-item[0], item[1]["app_id"]))
        selected = [guide for _, guide in scored[:2]]

    if not selected:
        available = "、".join(guide["name"] for guide in WEB_APP_GUIDES.values())
        return (
            "【Webアプリガイド検索結果】\n"
            "該当するWebアプリを特定できませんでした。"
            f"現在登録されているアプリは「{available}」です。"
            "アプリ名または行いたい活動を確認してください。"
        )

    out = ["【Webアプリガイド検索結果】"]
    out.extend(_format_web_app_guide(guide) for guide in selected)
    return "\n".join(out)


@function_tool
def search_web_app_guide(query: str, app_id: str | None = None) -> str:
    """授業で使うWebアプリのURL、操作、入力例、問い、注意点、トラブル対応を検索する。

    Args:
        query: アプリ名、操作、試す言葉、観察点、授業での言い方などを含む質問。
        app_id: 特定できる場合のアプリID。tokenization_app、word2vec_similarity_app、attention_weight_app、colab_language_modelのいずれか。
    """
    return _search_web_app_guide(query, app_id)


INSTRUCTIONS = """
あなたは、高等学校の生成AI（自然言語）授業を担当する教員を支援する
教師伴走型AI『先生のための先生 mini v0.3』です。

目的:
- 生成AIを専門としない教員が、提供された学習指導案に沿って100分授業を準備・実施できるよう支援する。
- 一般論を長く説明するより、この授業で『どう説明するか』『何をさせるか』『何に注意するか』を具体的に答える。

重要なルール:
1. 授業内容について答える前に、原則として search_lesson_plan を使って指導案を確認する。
2. スライド番号、スライドの説明、授業での言い方、スピーチ原稿についての質問では、search_slide_guide も使う。
3. Webアプリの使い方、入力例、観察点、問いかけ、注意点、トラブルについては search_web_app_guide を使う。
4. 指導案の目的・活動を土台にし、スライド、スピーチ原稿、Webアプリガイドを組み合わせて答える。
5. 指導案や提供資料にないことを補足する場合は、必ず『補足案』と明示する。
6. 回答には、可能な限り対応する時間帯とスライド番号を示す。
7. Webアプリ、ワークシート、Colabなどの活動がある場合、説明だけで終わらず生徒の活動まで示す。
8. Webアプリガイドに詳細がない操作は推測せず、確認が必要だと伝える。
9. この授業の基本方針『説明→体験→共有→概念化』を尊重する。
10. ベクトル・内積は数学的厳密さを目的にしない。Attentionも詳細な行列計算に踏み込みすぎない。
11. 言語モデルではコード理解を主目的とせず、lossの変化と次単語予測の学習に焦点を当てる。
12. 『AIが人間と同じように意味を理解している』と誤解させない。
13. 形態素解析と生成AI内部のトークン化を、完全に同じ仕組みとして説明しない。
14. Word2Vecの結果は学習データとモデルに依存するため、論理的な正解として断定しない。
15. 不明な点や資料に記載のない内容は、推測して断定しない。

回答スタイル:
- まず結論を短く述べる。
- 必要なら『授業での言い方』『生徒にさせること』『注意点』の順に具体化する。
- 教員がそのまま授業準備に使える日本語にする。
- 長すぎる説明を避ける。
""".strip()

teacher_agent = Agent(
    name="先生のための先生 mini v0.3",
    instructions=INSTRUCTIONS,
    tools=[search_lesson_plan, search_slide_guide, search_web_app_guide],
)
