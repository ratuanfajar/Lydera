from datetime import datetime, timezone

from app.domains.clarifier.schemas.chat import ChatAnswerResponse, ChatMessageResponse


def test_jawaban_tanpa_message_markup_bernilai_none():
    answer = ChatAnswerResponse(status="answered", message="teks", scope_klass="inti")
    assert answer.message_markup is None


def test_jawaban_membawa_message_markup():
    answer = ChatAnswerResponse(status="answered", message="x kuadrat", message_markup="$x^2$", scope_klass="inti")
    assert answer.model_dump()["message_markup"] == "$x^2$"


def test_riwayat_pesan_lama_tanpa_content_markup_tetap_valid():
    message = ChatMessageResponse(id=1, role="assistant", content="teks", created_at=datetime.now(timezone.utc))
    assert message.content_markup is None


def test_sitasi_lama_dengan_trust_tier_tetap_terbaca():
    message = ChatMessageResponse(
        id=1, role="assistant", content="teks", created_at=datetime.now(timezone.utc),
        citations=[{"source_type": "web", "label": "l", "reference": "r", "trust_tier": 3, "evidence": "e", "justification": "j", "verified": True}],
    )
    assert message.citations[0].source_type == "web"
