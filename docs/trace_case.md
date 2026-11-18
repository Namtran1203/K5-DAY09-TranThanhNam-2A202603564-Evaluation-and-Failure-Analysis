# Trace case cá nhân: C-002@11

| Trường | Quan sát |
|---|---|
| Trial | `seeded_regression C-002@11`, report `E-seeded_regression-20261118-4366` |
| Triệu chứng | Lab 8 FAIL: `status resolved != denied`; ledger hoàn 20.000đ trong khi nhãn 0đ. Reply xác nhận 20.000đ. |
| Bước sai đầu tiên | Event 3 `model_override`: `{"delay_days": 5}`. |
| Vì sao đầu tiên | Event 1 bàn giao đúng claim; event 2 `investigator` đã đọc đơn O-202 từ DB. Event 3 đi trước quote sai ở event 4. |
| Failure mode | FM-03 `ticket_trust`. |
| Đối chứng | `fixed C-002@11`: không có override; event 3 `quote` trả `amount_vnd=0`, status `denied`, ledger 0đ, Lab 8 PASS. |
| Regression test | Item `E-002` của eval set v1 mang FM-03. `DbFactKept` phát hiện override; `TrialPass` và `RefundAmountCorrect` fail trên variant, pass trên `fixed`. Gate chặn variant tại `pass_rate`. |
| Chưa chắc chắn | Trace MockLLM chứng minh đường chạy thử này; chưa xác nhận tần suất lỗi với model thật. |

Tái hiện bằng `python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11`, rồi thay shape bằng `fixed`.
