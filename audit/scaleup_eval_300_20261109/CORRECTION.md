# Đính chính ngày 2026-11-09

`REPORT.md` được giữ nguyên làm bản ghi gốc. Không nên trích số trong đó như kết quả trên câu chưa thấy.

## Sai ở đâu

- 101 câu `heldout_tail` lấy từ `train_pool[-101:]`, tức chính nhóm câu dùng để huấn luyện. 100/101 câu có trong `train.jsonl` của cả bản thường và bản phản thực. Với 2.000 vòng, batch 1, mô hình chỉ xem tối đa 2.000 mẫu nên có thể chưa gặp hết, nhưng không gọi được là held-out.
- 99 câu valid được dùng khi theo dõi huấn luyện và so checkpoint. Commit `767ec9b8` đã ghi valid không còn sạch.
- 100 câu dev đã được đọc khi phân tích lỗi. Vì vậy cả 199 câu còn lại chỉ là kết quả thăm dò.

## Số liệu sau khi bỏ 101 câu `heldout_tail`

| Phép đo | Cả 300 câu (bản gốc) | 199 câu ngoài file huấn luyện |
| --- | --- | --- |
| Độ đúng, CF và Plain | 251 và 244 / 300, p = 0,3817 | 165 và 164 / 199, p = 1,0 |
| `follows` chính xác | 136 và 119 / 167, p = 0,00599 | 93 và 81 / 114, p = 0,0227 |
| Quét theo bước, D | 20 và 8, p = 0,0357 | 17 và 7, p = 0,0639 |

Bước quét gồm 162 lượt từ 94 câu. Các lượt cùng một câu không độc lập nên p ở dòng này chỉ là gần đúng.

Tái lập, chạy từ thư mục gốc của repo:

```bash
.venv/bin/python audit/scaleup_eval_300_20261109/recompute_without_training_overlap.py
```

## Các câu đã bỏ

- "Zero capability tax", "preserves capability": p lớn chỉ cho biết chưa thấy khác biệt.
- "Substantially reducing unfaithful rationalizations": số `reverted` chỉ là 3 và 4 trên 114.
- "Refutation of Contextual Inertia", "attention head": chỉ có 6 lần `reverted`, và phép đo không nhìn vào cơ chế bên trong.
