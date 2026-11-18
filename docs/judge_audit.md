# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | Dùng cho tiêu chí giọng điệu |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không: κ < 0.6 và Recall < 0.7 | Loại khỏi gate |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 (tone) | PASS | FAIL | Người | “Em”, “nha”, “anh check giúp em” quá suồng sã trong ngữ cảnh CSKH của bộ dữ liệu. Sửa rubric: yêu cầu cách xưng hô chuyên nghiệp; không coi thân mật là đủ để PASS. |
| 2 | H-017 (tone) | PASS | FAIL | Người | “Bạn ơi ... rồi nha” không phù hợp với khách lớn tuổi theo ghi chú của case. Sửa rubric: đánh giá cách xưng hô theo ngữ cảnh khách hàng; chỉ có từ “Dạ” chưa đủ để PASS, không mặc định mọi cách gọi “bạn” đều sai. |
| 3 | H-029 (tone) | PASS | FAIL | Người | “Không cần nhắn thêm” mang giọng ra lệnh và ngăn khách trao đổi. Sửa rubric: đọc toàn bộ câu để phát hiện thái độ áp đặt, không chỉ dựa vào “Dạ, vui lòng”. |
| 4 | H-042 (tone) | FAIL | PASS | Người | Câu trả lời ngắn nhưng lịch sự, có số tiền và thời gian nhận tiền. Sửa rubric: không bắt buộc mọi câu đều phải có lời xin lỗi; chấm giọng điệu theo ngữ cảnh. |
| 5 | H-051 (tone) | FAIL | PASS | Người | Theo ghi chú CSV, CS LogiX cho phép từ “refund”; câu vẫn lịch sự và rõ nghĩa. Sửa rubric: bổ sung danh sách thuật ngữ được phép, không tự động FAIL chỉ vì có từ tiếng Anh. |
| 6 | HL-015 (helpful) | PASS | FAIL | Người, theo ledger được ghi chú trong CSV | Reply báo hoàn 55.000đ nhưng ghi chú ledger là 40.000đ. Sửa rubric: helpful phải chính xác về kết quả thực tế; kiểm tra tiền bằng code đối chiếu ledger, không cho PASS chỉ vì câu văn lịch sự. |
| 7 | HL-016 (helpful) | PASS | FAIL | Người, theo ledger được ghi chú trong CSV | Reply có nhiều lời xin lỗi nhưng báo hoàn 55.000đ trong khi ghi chú ledger là 35.000đ. Sửa rubric: tách giọng điệu khỏi độ chính xác; lời xin lỗi và độ dài không bù được sai tiền, dùng code kiểm tra ledger. |

## Kết luận
- Với FAIL là lớp positive, tone có TP=24, FP=4, FN=6, TN=66; đạt cả ba ngưỡng nên dùng cho tiêu chí giọng điệu, không dùng để xác nhận tiền hay approval.
- Loại helpful khỏi gate: TP=9, FP=0, FN=21, TN=70. Precision=1.000 nhưng chỉ phát hiện 9/30 lỗi thật, bỏ sót 21/30; Recall=0.300 và κ=0.375 đều dưới ngưỡng. Các case HL-015 và HL-016 cho thấy reply sai tiền vẫn được PASS. Tỷ lệ lỗi quan sát 0.090 được Rogan–Gladen hiệu chỉnh thành 0.300; hiệu chỉnh tỷ lệ tổng thể không sửa được các phán quyết sai ở từng case và không làm judge đạt điều kiện gate.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
