"""웹 UI 랜덤 단어 버튼과 eval/build_words.py 큐레이션 목록."""
import random

WORD_LISTS = {
    "기관명": [
        "한국천문연구원",
        "한국전자통신연구원",
        "식품의약품안전처",
        "한국원자력안전기술원",
        "국립국어원",
        "한국지능정보사회진흥원",
        "정보통신기획평가원",
        "한국과학기술원",
        "한국저작권위원회",
        "개인정보보호위원회",
    ],
    "기술용어": [
        "양자 얽힘",
        "초전도체",
        "벡터 데이터베이스",
        "RAG",
        "트랜스포머 아키텍처",
        "쿠버네티스",
        "도커 컨테이너",
        "차등 프라이버시",
        "연합학습",
        "뉴로모픽 칩",
    ],
    "한국어 신조어": [
        "갓생",
        "스불재",
        "어쩔티비",
        "무지성",
        "킹받네",
        "삼귀다",
        "꾸안꾸",
        "점메추",
        "알잘딱깔센",
        "어그로",
    ],
    "논문 제목": [
        "Attention Is All You Need",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "Language Models are Few-Shot Learners",
        "Diffusion Models Beat GANs on Image Synthesis",
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        " Constitutional AI: Harmlessness from AI Feedback",
    ],
    "최신 AI뉴스나 논란": [
        "생성형 AI 저작권 소송",
        "AI 딥페이크 선거 논란",
        "인공지능 기본법 시행 논란",
        "AI 학습데이터 무단수집 논란",
        "거대언어모델 할루시네이션 의료사고 논란",
        "AI 면접 채용 공정성 논란",
        "오픈소스 AI 모델 규제 논란",
    ],
}


def pick_random_word(category: str | None = None) -> dict:
    if category and category in WORD_LISTS:
        cat = category
    else:
        cat = random.choice(list(WORD_LISTS.keys()))
    return {"category": cat, "word": random.choice(WORD_LISTS[cat])}
