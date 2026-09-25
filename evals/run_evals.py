"""
Ejecutor automático de las 40 preguntas de regresión del Chat (`evals/run_evals.py`).
Comprueba que:
1. Cada respuesta pase el verificador numérico (`verification["passed"] == True`).
2. Se utilice el indicador correcto (incluyendo las reglas de reemplazo ADR-001).
3. Las preguntas fuera de catálogo sean marcadas con `out_of_catalog: True`.
"""

from __future__ import annotations
import sys
from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from etl.chat_engine import SnapshotStore, answer_question


def run_all_evals() -> int:
    with open(ROOT_DIR / "evals" / "chat-preguntas.yaml", "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    cases = doc["eval_cases"]
    store = SnapshotStore()

    passed = 0
    failed = 0

    for c in cases:
        qid = c["id"]
        q = c["question"]
        res = answer_question(q, store=store)

        ver_ok = bool(res["verification"]["passed"])
        if c.get("expect_out_of_catalog"):
            ind_ok = bool(res.get("out_of_catalog"))
        else:
            chosen_ind = res["chart"]["indicator"] if res.get("chart") else None
            ind_ok = (chosen_ind == c["expected_indicator"])

        if ver_ok and ind_ok:
            passed += 1
        else:
            failed += 1
            print(
                f"[FAIL] {qid}: ver_ok={ver_ok} (unverified={res['verification']['unverified_numbers']}), "
                f"ind_ok={ind_ok} (got={res.get('chart', {}).get('indicator')}, expected={c.get('expected_indicator')})"
            )

    print(f"[EVALS OK] {passed}/{len(cases)} preguntas superaron verificación de cifras y selección de herramientas.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_evals())
