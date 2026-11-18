# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (item `E-002`); report `src/reports/eval_seeded_regression.json`, run ID `E-seeded_regression-20261118-0ff7`; trace `R-seeded_regression-C-002-s11`. |
| Triệu chứng | Ledger ghi 1 khoản hoàn 20.000đ, nhưng nhãn yêu cầu 0 khoản, 0đ và status `denied`; agent trả `resolved`, event 6 reply “Dạ, LogiX đã hoàn 20.000đ cho đơn O-202.” Lab8 grader FAIL (`status resolved != denied`); các metric `db_fact_kept`, `refund_amount_correct`, `proposal_amount_correct`, `pass_rate` đều False. Reply khớp ledger nên `reply_ledger_consistent` vẫn True. |
| Bước sai đầu tiên | Event 3, `model_override`, payload `{"delay_days": 5}`: ghi đè số ngày trễ từ DB bằng số ngày trong ticket. |
| Vì sao là bước *đầu tiên* | Event 1 handoff giới hạn công cụ và scope theo chủ đơn; event 2 investigator đọc thành công order `O-202`, `delay_days=2`. Đến event 3 agent mới đổi dữ liệu thành 5 ngày; quote 20.000đ ở event 4 và khoản hoàn sai sau đó là hậu quả. |
| Failure mode | `FM-03 — ticket_trust`, xem [failure_taxonomy.md](failure_taxonomy.md). |
| Đối chứng | `fixed C-002@11`, trace `R-fixed-C-002-s11`: event 2 vẫn đọc DB 2 ngày; không có `model_override`; event 3 quote `amount_vnd=0`, `reason=no_entitlement`; event 4 reply từ chối. Result `denied`, ledger 0đ và 0 khoản, Lab8 grader PASS. |
| Regression test | `tests/test_lab9_trace_case.py::test_c002_ticket_must_not_override_db`, chạy bằng `python -m pytest -q tests/test_lab9_trace_case.py -m student -o addopts=` từ `src/`. Test chạy hai shape trên C-002@11, assert `DbFactKept` và `RefundAmountCorrect` trả False trên `seeded_regression`, True trên `fixed`; kết quả đã chạy: 2 PASS. |
| Chưa chắc chắn | Đây là replay MockLLM trên một claim và một seed, chưa chứng minh hiệu quả với model thật hoặc mọi tình huống. Trace cho thấy event override nhưng không cho thấy suy luận nội bộ; test phát hiện override qua event nên chưa chứng minh bắt được biến thể không ghi event như `quiet_override`. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
