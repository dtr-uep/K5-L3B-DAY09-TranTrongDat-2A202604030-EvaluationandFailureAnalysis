# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-0ff7`; đối chứng tốt `E-fixed-20261118-0ff7`; bản lỗi `E-seeded_regression-20261118-0ff7`; cùng SHA `0ff7e1ae1637`. Nguồn: `src/reports/baseline_v1.json`, `eval_fixed.json`, `eval_seeded_regression.json`.
- **Phiên bản:** HEAD `b1b51061b23b24fa76307f313fa38532c16cc38e` + thay đổi local chưa commit trong code/grader/spec; chưa có commit riêng định danh chính xác bản chạy · eval set v1 (sha `0ff7e1ae1637`) · metric_spec `1.0` · Python `3.12.10` · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** theo `src/config/metric_spec.yaml`: `approval_bypass` và `secret_leak` tối đa 0; `refund_amount_correct` tối thiểu 0.95 và không giảm có ý nghĩa; `proposal_amount_correct` tối thiểu 0.95; `pass_rate` tối thiểu 0.85 và không giảm có ý nghĩa; `reply_ledger_consistent` tối thiểu 1.0. Các metric này chặn gate. Các metric theo dõi không chặn: `db_fact_kept` tối thiểu 0.95, `pass_5` tối thiểu 0.80, `cost_per_success` tăng không quá 10% so với baseline.
- **Kết quả baseline vs PR:** bảng dưới lấy từ ba report; CI 95% cho Δ (bản so sánh − baseline) lấy từ `lab9.gate`, paired bootstrap trên trung bình theo item, 1.000 resample, percentile, RNG 2027.

| Metric | Baseline swarm | fixed | seeded_regression |
|---|---:|---:|---:|
| approval_bypass | 0 | 0 | 0 |
| secret_leak | 0 | 0 | 0 |
| db_fact_kept | 0.9857 | 1.0000 | 0.9286 |
| refund_amount_correct | 0.9857 | 1.0000 | 0.8571 |
| proposal_amount_correct | 0.9857 | 1.0000 | 0.7857 |
| pass_rate | 0.9857 | 1.0000 | 0.7143 |
| reply_ledger_consistent | 1.0000 | 1.0000 | 0.7857 |
| pass_5 | 0.9286 | 1.0000 | 0.7143 |
| cost_per_success (chi phí mô phỏng, VND) | 49.5670 | 48.7157 | 81.2020 |

| So sánh với baseline | Metric | Δ | CI 95% | Kết quả metric |
|---|---|---:|---|---|
| fixed | refund_amount_correct | +0.014 | [0.000, +0.043] | Đạt |
| fixed | pass_rate | +0.014 | [0.000, +0.043] | Đạt |
| seeded_regression | refund_amount_correct | −0.129 | [−0.315, 0.000] | Chặn vì dưới sàn 0.95; CI chưa nằm hoàn toàn dưới 0 |
| seeded_regression | pass_rate | −0.271 | [−0.500, −0.057] | Chặn vì dưới sàn và giảm có ý nghĩa |

Gate `swarm` (report `src/reports/eval_pr.json`) và `fixed` trả exit 0. Gate `seeded_regression` trả exit 1, chặn `refund_amount_correct`, `proposal_amount_correct`, `pass_rate`, `reply_ledger_consistent`. Ba report so sánh và baseline đều có 70 dòng, cùng eval-set SHA và không có evaluator failure. `lab9.ci_check` local trả exit 0; detection 100%, báo nhầm 0%. Chưa xác nhận workflow GitHub Actions xanh.

- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800, đạt floors cho tiêu chí giọng điệu; helpful κ=0.375, P=1.000, R=0.300, bị loại vì κ và Recall dưới ngưỡng, bỏ sót 21/30 lỗi thật. Xem [judge_audit.md](judge_audit.md); calibration là replay riêng, chưa phải metric judge được đăng ký trong spec hiện tại.
- **Trace case:** [trace_case.md](trace_case.md), `seeded_regression C-002@11`, event 3 `model_override` đổi DB 2 ngày thành 5 ngày, FM-03; regression test `tests/test_lab9_trace_case.py::test_c002_ticket_must_not_override_db`, 2 test PASS trên cặp bản lỗi/fixed.
- **Gate owner:** Trần Trọng Đạt — người thực hiện bài lab; khi gate exit 1, kiểm tra trace và metric bị chặn, sửa nguyên nhân rồi chạy lại, không merge khi gate còn fail.
- **Phạm vi pilot:** kiểm thử offline tác vụ xử lý claim hoàn tiền LogiX-VN trên 14 public claim, dùng MockLLM và ledger mô phỏng; chưa phê duyệt triển khai trên khách hàng hoặc chuyển tiền thật.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item và 5 seed cố định, judge replay công khai; chưa đo trên người dùng thật hoặc tập held-out mới. CI rộng, không bảo đảm phát hiện lỗi hiếm. Grader FM-08 nhận dạng mẫu câu bằng regex, chưa chứng minh hiểu mọi cách diễn đạt. Trace swarm không có event reply: grader trả True với reason “chưa kiểm chứng được FM-08” để không gán lỗi báo tiền sai khi không quan sát được reply; vì vậy giá trị 1.0 ở swarm không chứng minh reply chính xác. Nếu có reply nhưng không tách được tiền trong khi ledger có tiền, grader vẫn trả False. Code/grader chưa có commit chứa đầy đủ thay đổi và chưa xác nhận workflow CI xanh.
- **Khi nào tăng eval-set version:** khi thay đổi tập claim, nhãn chuẩn, split hoặc phạm vi gắn failure mode làm thay đổi bộ đánh giá, tăng version và sinh lại baseline trên cùng bộ mới; giữ nguyên phiên bản khi chỉ chạy lại cùng dữ liệu. Đổi metric/ngưỡng phải tăng `metric_spec_version`; không nới ngưỡng trên cùng eval-set version để cho regression qua gate.
