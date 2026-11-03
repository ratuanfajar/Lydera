from common import table_spec
from quizzer import config
from quizzer.stimulus.base import Narration, StimulusKind

PROMPT_SCHEMA = (
    'jenis "tabel": isi "spesifikasi" dengan {"judul": "...", "kolom": ["..."], "baris": [["..."]]} (tabel ditaruh di dalam '
    '"spesifikasi", bukan di kunci lain) dengan jumlah sel tiap baris sama dengan jumlah '
    "kolom; semua sel dan nama kolom berupa teks (bilangan ditulis sebagai teks), dan rumus ditulis sebagai LaTeX di antara "
    "tanda dolar bila perlu."
)
KEYS = ("judul", "kolom", "baris")


def validate(spec: dict) -> list[str]:
    return table_spec.spec_issues(spec, config.STIMULUS_MAX_CHARS)


def narrate(spec: dict) -> Narration:
    readable, spoken, summary = table_spec.narrate_spec(spec)
    return Narration(readable, spoken, summary)


KIND = StimulusKind("tabel", 1, PROMPT_SCHEMA, KEYS, validate, narrate, raw_keys=KEYS)
