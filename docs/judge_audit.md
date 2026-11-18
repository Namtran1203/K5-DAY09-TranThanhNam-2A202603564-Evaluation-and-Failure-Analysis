# Judge audit — replay CSV

FAIL là lớp dương. FLOORS: κ≥0.6, precision≥0.8, recall≥0.7.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Quyết định |
|---|---:|---|---:|---:|---:|---|
| `tone_ok` | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | Qua calibration |
| `helpful` | 100 | 9 / 0 / 21 / 70 | 0.375 | 1.000 | 0.300 | Loại khỏi gate |

Tone có tỉ lệ FAIL quan sát 0.28, hiệu chỉnh Rogan–Gladen thành 0.30. Helpful có 21 false negative nên không thể làm cổng chặn dù precision 1.0.

| Case | Judge / người | Kết luận và sửa rubric |
|---|---|---|
| H-008 | PASS / FAIL | Theo nhãn người, “anh check giúp em” quá thân mật; thêm ví dụ. |
| H-017 | PASS / FAIL | “bạn ơi…nha” thiếu trang trọng; chuẩn hóa quy tắc. |
| H-029 | PASS / FAIL | “không cần nhắn thêm” mang tính áp đặt; thêm quy tắc cấm. |
| H-042 | FAIL / PASS | Thông báo tiền về 3–5 ngày là tone phù hợp; không phạt nội dung tiền. |
| H-051 | FAIL / PASS | Từ “refund” không tự động làm tone sai; tách thuật ngữ khỏi tone. |
| H-063 | PASS / FAIL | Lời hứa hoàn thêm thiếu căn cứ; thêm ví dụ kiểm tra lời hứa. |
| H-070 | PASS / FAIL | Emoji cười trong ngữ cảnh hoàn tiền không phù hợp; thêm ví dụ. |
| H-081 | FAIL / PASS | Từ chối lịch sự vẫn là tone đạt; thêm ví dụ. |
| HL-015 | PASS / FAIL | Câu chỉ báo đã hoàn thiếu hướng dẫn tiếp theo; rubric helpful cần hành động cụ thể. |
| HL-047 | PASS / FAIL | “Xử lý rồi nhé” không nêu kết quả hoặc bước kế tiếp; thêm ví dụ. |

Những kết luận này dùng nhãn replay công khai. Cần người gán nhãn độc lập cho tập held-out mới.
