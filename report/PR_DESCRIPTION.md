# Lab 9 — Evaluation & Failure Analysis

Trần Thành Nam — 2A202603564. PR từ `starter/d09` vào `main` **trong fork cá nhân**.

## Nội dung

- Chép `src/` Day 8 gốc, giữ nguyên `src/lab8/`; hoàn thiện stats, graders, eval set v1/v2, slice và integrity gate.
- Thêm failure taxonomy, trace case, judge audit, eval card, PRD v1.1 và report cá nhân.
- Commit report JSON sinh bằng script: baseline v1/v2, fixed, seeded regression và slice regression.

## Kiểm tra

- `python -m lab9.smoke`: M0 PASS.
- `pytest -q -m student -o addopts= -k lab9`: 24 passed.
- `lab9.evalset --check` và `--v2 --check`: 0 problem(s).
- `lab9.mutation --detect`: detection 100%, false alarms 0%.
- Scorecard v2: `mutation score 3/3 · false alarms 0`.
- A/A seeds 66/77/88/99/110: Δ=0 cho mọi metric trong MockLLM.

## Gate v1: hồi quy bị chặn

```text
gate: PR E-seeded_regression-20261118-4366 vs main E-swarm-20261118-4366 · eval set 436688bbe4ae
  refund_amount_correct  0.8571  Δ -0.129 CI [-0.315, +0.000] BLOCK
  proposal_correct       0.7857  Δ -0.200 CI [-0.414, +0.000] BLOCK
  pass_rate              0.7143  Δ -0.271 CI [-0.500, -0.057] BLOCK
  reply_ledger_correct   0.7857  Δ -0.214 CI [-0.429, +0.000] BLOCK
exit 1 — blocked: refund_amount_correct, proposal_correct, pass_rate, reply_ledger_correct
```

`fixed` qua gate với `exit 0 — merge`.

## Gate v2 và integrity

```text
fixed                expect merge got merge ok
honest_refactor      expect merge got merge ok
seeded_regression    expect block got block ok
slice_regression     expect block got block ok          proposal_correct, slice:money_movement/pass_rate
flaky_regression     expect block got block ok          proposal_correct, pass_rate, pass_hat_5, slice:money_movement/pass_rate
mutation score 3/3 · false alarms 0
```

Bốn trap, mỗi lệnh `lab9.gate` đều trả exit code 1:

```text
evaluator_errors_as_nan: exit 1 — blocked: integrity
dropped_failing_rows:    exit 1 — blocked: integrity
cherry_picked_seeds:     exit 1 — blocked: integrity
loosened_spec:           exit 1 — blocked: integrity (ratchet)
```

Giới hạn: MockLLM, tập công khai nhỏ, judge replay; chưa có dữ liệu người dùng thật hoặc kết quả test ẩn.
