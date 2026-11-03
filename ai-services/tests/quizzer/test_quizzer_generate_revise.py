import pytest

from quizzer import config, generate, prompts, quizzer_regenerate, revise

POINT = {"kind": "rumus", "text": "Poin.", "order_start": 10, "order_end": 30}
SOAL = {
    "id": 1, "question_text": "Soal?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_option": "B",
    "langkah": ["l1"], "kesimpulan": "k",
}


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def complete_json(system, user, **kwargs):
        seen.update(system=system, user=user, **kwargs)
        return dict(seen.get("answer", {}))

    monkeypatch.setattr(generate.llm, "complete_json", complete_json)
    monkeypatch.setattr(revise.llm, "complete_json", complete_json)
    return seen


def test_generate_lots_memakai_batas_token_kecil_tanpa_effort_khusus(captured):
    generate.generate_soal(POINT, "sumber", 2, "CP")
    assert (captured["max_tokens"], captured["effort"]) == (generate.LOTS_MAX_TOKENS, None)
    assert captured["system"] is prompts.GENERATE_SYSTEM and captured["model"] == config.QUIZ_MODEL


def test_generate_hots_memakai_batas_token_besar_dan_effort_hots(captured):
    generate.generate_soal(POINT, "sumber", 5, "CP")
    assert (captured["max_tokens"], captured["effort"]) == (generate.HOTS_MAX_TOKENS, config.HOTS_EFFORT)


def test_generate_menambah_level_dan_rentang_sumber_ke_keluaran(captured):
    data = generate.generate_soal(POINT, "sumber", 4, "CP")
    assert (data["bloom_level"], data["reading_order_start"], data["reading_order_end"]) == (4, 10, 30)
    assert captured["required_keys"] == [*generate.REQUIRED_KEYS, "pilihan_stimulus"] and captured["latex"] is True


def test_generate_lots_tidak_mewajibkan_pilihan_stimulus(captured):
    generate.generate_soal(POINT, "sumber", 3, "CP")
    assert captured["required_keys"] == generate.REQUIRED_KEYS


def test_generate_input_hanya_meminta_stimulus_untuk_level_hots():
    assert prompts.STIMULUS_INSTRUCTION in prompts.generate_input(POINT, "sumber", 4)
    assert prompts.STIMULUS_INSTRUCTION not in prompts.generate_input(POINT, "sumber", 3)


def test_revise_soal_meminta_kunci_yang_wajib(captured):
    revise.revise_soal("sumber", "stimulus", SOAL, "perbaiki")
    assert "needs_stimulus_change" in captured["required_keys"] and captured["system"] is prompts.REVISE_SOAL_SYSTEM


def test_revise_stimulus_mengembalikan_teks(captured):
    captured["answer"] = {"readable_text": "stimulus baru"}
    assert revise.revise_stimulus("sumber", "lama", "ubah") == "stimulus baru"


def test_recheck_memakai_prompt_recheck(captured):
    revise.recheck_soal_for_new_stimulus("sumber", "baru", SOAL)
    assert captured["system"] is prompts.RECHECK_SOAL_SYSTEM


def test_soal_content_equal_mengabaikan_field_lain_dan_membandingkan_isi():
    same = {**SOAL, "id": 99, "extra": 1}
    assert quizzer_regenerate._soal_content_equal(SOAL, same)
    assert not quizzer_regenerate._soal_content_equal(SOAL, {**SOAL, "kesimpulan": "lain"})
    assert not quizzer_regenerate._soal_content_equal(SOAL, {**SOAL, "options": {**SOAL["options"], "A": "z"}})


@pytest.fixture
def regen(monkeypatch):
    state = {"edit": dict(SOAL, needs_stimulus_change=False), "verify": []}
    monkeypatch.setattr(quizzer_regenerate.revise, "revise_soal", lambda *args: state["edit"])
    monkeypatch.setattr(quizzer_regenerate.revise, "revise_stimulus", lambda *args: state.get("new_markup", "stimulus baru"))
    monkeypatch.setattr(quizzer_regenerate.revise, "recheck_soal_for_new_stimulus", lambda source, markup, soal: dict(soal, kesimpulan=state.get("recheck", soal["kesimpulan"])))
    monkeypatch.setattr(quizzer_regenerate, "review_soal", lambda source, data, stimulus="": state["verify"])
    return state


BLOCKS = [{"reading_order": 10, "block_type": "text", "readable_text": "sumber"}]


def regenerate(state, sibling=()):
    return quizzer_regenerate.compute_regeneration(BLOCKS, 10, 10, "", "stimulus lama", SOAL, list(sibling), "feedback")


def test_regenerasi_tanpa_perubahan_isi_tidak_menghasilkan_pembaruan(regen):
    assert regenerate(regen) == {"new_stimulus": None, "soal_updates": []}


def test_regenerasi_hanya_soal_memperbarui_satu_soal_dengan_temuan(regen):
    regen["edit"] = dict(SOAL, kesimpulan="baru", needs_stimulus_change=False)
    regen["verify"] = ["masalah verifikasi"]
    result = regenerate(regen)
    [(soal_id, data, issues)] = result["soal_updates"]
    assert (soal_id, data["kesimpulan"], issues) == (1, "baru", ["masalah verifikasi"])
    assert result["new_stimulus"] is None


def test_revisi_soal_tidak_valid_melempar_error(regen):
    regen["edit"] = {"needs_stimulus_change": False, "question_text": "", "options": {}, "correct_option": "A", "langkah": [], "kesimpulan": ""}
    with pytest.raises(ValueError, match="revisi tidak valid"):
        regenerate(regen)


def test_perubahan_stimulus_memeriksa_ulang_semua_soal_dan_menyimpan_stimulus_baru(regen):
    regen["edit"] = {"needs_stimulus_change": True}
    regen["recheck"] = "kesimpulan disesuaikan"
    sibling = dict(SOAL, id=2)
    result = regenerate(regen, [sibling])
    assert result["new_stimulus"]["readable_text"] == "stimulus baru"
    assert sorted(update[0] for update in result["soal_updates"]) == [1, 2]
    assert all(update[1]["stimulus"]["readable_text"] == "stimulus baru" for update in result["soal_updates"])


def test_perubahan_stimulus_tanpa_soal_berubah_tetap_mengembalikan_stimulus_baru(regen):
    regen["edit"] = {"needs_stimulus_change": True}
    result = regenerate(regen)
    assert result["new_stimulus"] is not None and result["soal_updates"] == []
