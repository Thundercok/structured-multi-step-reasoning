# RAT Mini — vòng kiểm chứng tương thích đầu tiên

Ngày 2026-10-26 (Asia/Ho_Chi_Minh). Đây là bằng chứng development trên máy dev
arm64/macOS 26.5.2, **không phải acceptance của Mac M3 8GB hoặc macOS 14**.
User chốt chưa biết OS máy đích: nhắm base compatibility macOS 14 Sonoma.

## Kết quả và quyết định kỹ thuật

| Hạng mụ  c | Quan sát thật | Quyết định / giới hạn |
| --- | --- | --- |
| Spotlight metadata | Scope đúng repo, query AGENTS.md, 6 file. đọc được | Nguồn fast khả thi; không suy ra coverage toàn máy |
| Spotlight full-text | Query tên AGENTS.md AND từ REASONING, 5 hits; có file gốc mong đợi, tất cả trong scope | Chứng minh content query trên Markdown đã index; PDF/importer cần thử riêng |
| Sandbox | mdutil trong sandbox báo disabled, ngoài sandbox báo enabled và mdfind có kết quả | Không nhầm hạn chế môi trường kiểm tra thành lỗi Spotlight máy người dùng |
| SQLite stdlib | Python 3.12.6 / SQLite 3.45.3 không có enable_load_extension | Không dùng connection hiện tại để load sqlite-vec |
| Vector store | APSW 3.54.1.0 + SQLite 3.54.1 + sqlite-vec 0.1.9 chạy SQL KNN trên 2 vector synthetic | Semantic provider có thể sở hữu connection APSW riêng; không đổi driver toàn RAT |
| Packaging vector store | Cùng probe chạy qua executable PyInstaller, không dùng Python của repo | Storage/extension loading smoke PASS trên máy dev, chưa main app hoặc máy đích |
| Helper dịch hiện có | rat/bin/apple_translate khai báo minimum macOS 26 | Không thể dựa vào helper hiện có cho base macOS 14 |
| Probe framework mới | Build target arm64-apple-macos14.0; Translation là LC_LOAD_WEAK_DYLIB | Có thiết kế availability gate; binary metadata không thay test thật trên OS 14 |
| Native EN→VI | Ngoài sandbox: framework có sẵn, pair supported nhưng chưa installed; Vietnamese thuộc supported languages | Không tải pack, không dịch trong probe; cloud fallback vẫn cần thiết |
| Embedding bundle | Tác giả intfloat, MIT metadata, revision pin, 135.430.819 bytes; tất cả checksum đúng | Qua byte/hash/development ARM64 smoke; chưa freeze làm production default |
| Embedding CPU ARM64 | ONNX Runtime 1.27.0, batch 4 câu tự soạn → shape 4×384, finite/unit norm | Output hợp lệ không chứng minh chất lượng tìm file mờ |
| Embedding timing/RSS | Init 0,252s; batch runs 22,99 / 13,94 / 19,34 / 22,88ms; peak process RSS 640.385.024 bytes (~611MiB) | 4 lần batch cùng input trên máy dev; không p95, không app idle, không M3 8GB claim |
| Native dependency minima | ONNX .so/.dylib minos 14.0; tokenizers 11.0; probe 14.0; packaged vec0 14.0 | Các native assets đã inspect không đòi OS mới hơn 14; chưa audit toàn dependency graph/app |

Đã ưu tiên ONNX quantized trực tiếp từ tác giả thay ứng viên Xenova:
upstream khai MIT; repo conversion không khai license trong model metadata đã
đọc. `embedding_candidate.json` giữ lịch sử candidate metadata, không tải weights
candidate đó. `embedding_upstream_candidate.json` là bundle đã tải và kiểm tra.
Tên upstream có `avx512_vnni` nhưng graph thực sự chạy được qua ONNX CPU trên
ARM64 trong smoke; không tự suy khả năng/không khả năng ARM64 chỉ từ filename.
Redistribution production vẫn cần đóng gói license notices đầy đủ.

## Bằng chứng

- `dev_probe.json`: source-mode local probe; embedding không được load bởi probe này.
- `packaged_probe.json`: standalone diagnostic executable; model weights không được kèm.
- `spotlight_fulltext_probe.json`: full-text query thật; không lưu đường dẫn hits.
- `native_assets.json`: kích thước, SHA256, minimum OS của các assets native chính trong executable chẩn đoán.
- `embedding_native_assets.json`: ONNX Runtime/tokenizers native dependency minima.
- `embedding_upstream_candidate.json`: repo/revision, byte sizes, LFS SHA256/Git blob IDs và license metadata.
- `embedding_download_receipt.json`: receipt tải weights vào /private/tmp, không đưa weights vào repo.
- `embedding_smoke.json`: inference thật trên câu tự soạn; source texts, cosine scores, timing, RSS; quality_acceptance=false.
- `package_receipt.json`: ZIP diagnostic 15.406.458 bytes và checksum; không notarized.

`limits.no_models=true` trong preflight report nói về tiến trình **preflight**.
Inference embedding là một run riêng, ghi trong embedding_smoke.json. Vector
storage dùng hai vector synthetic để test SQL, không giả làm model embeddings.

## Mã có thể tái sử dụng

- `scripts/check_rat_mini.py`: inventory + scoped Spotlight + subprocess-isolated
  vector storage + native availability; mặc định không tìm file cá nhân, không
  đọc clipboard/chụp màn hình/request permission/gọi cloud/tải model.
- `tools/apple_translation_probe.swift`: availability-only, macOS 14 deployment
  target, #available gate cho framework 15 và installedSource session 26.
- `scripts/check_rat_mini_embedding.py`: explicit local inference smoke; xác minh
  bytes/hash trước khi import inference libraries; không download, không remote code.
- `tools/build_rat_mini_preflight.sh`: đóng gói diagnostic CLI; không phải app Mini.
- `tests/test_rat_mini_preflight.py`: 10 tests về explicit scope, import isolation,
  symlink escape, lỗi native/timeout, frozen child dispatch, model corruption.

Không thay business runtime/UI/capability registration trong vòng này. Chưa có
TranslationCapability, Mini profile hoặc Finder provider nối vào vòng model.
Không có live UI acceptance hay ảnh UI mới trong vòng kiểm tra headless này.

## Chạy lại

Các dependency dưới đây chỉ dùng thư mục tạm, không thay .venv chính:

```bash
.venv/bin/python -m pip install --only-binary=:all: --no-deps \
  --target /private/tmp/rat-mini-spike-deps apsw==3.54.1.0 sqlite-vec==0.1.9
RAT_MINI_SPIKE_DEPS=/private/tmp/rat-mini-spike-deps \
  zsh tools/build_rat_mini_preflight.sh
dist/rat-mini-preflight/rat-mini-preflight \
  --scope "$PWD" --known-name AGENTS.md --output /private/tmp/mini-report.json
.venv/bin/python -m pytest tests/test_rat_mini_preflight.py -q
```

Artifact: `dist/RAT-Mini-Preflight.zip`, một CLI chẩn đoán có Python/runtime riêng.
Giải nén rồi chạy executable; nếu bỏ --scope/--known-name thì bỏ qua tìm kiếm.
Exit code 0 chỉ xác nhận thu được report, không phải release gate PASS.
Không yêu cầu bạn của người dùng cài Python/Homebrew để chạy executable.

Để chạy inference smoke, chuẩn bị đúng các files trong upstream manifest ở
model-dir, tải từ `https://huggingface.co/{repo_id}/resolve/{revision}/{rfilename}`,
không tải cả repo chứa mọi biến thể weights. Script kiểm tra lại checksums:

```bash
.venv/bin/python -m scripts.check_rat_mini_embedding \
  --model-dir /private/tmp/rat-mini-upstream-e5-smoke \
  --manifest audit/rat_mini_spike_20261026/embedding_upstream_candidate.json \
  --output /private/tmp/embedding-smoke.json
```

Preflight source và packaged chạy ngoài sandbox cho quan sát native chính xác.
Build cache và dependencies nằm trong /private/tmp; build scripts không cần ghi
cache vào home. Bản chẩn đoán chưa là một sản phẩm hỗ trợ notarization.

## Gate còn mở trước release

1. Máy đích thật/macOS 14: chạy binary và native-unavailable fallback; quyền TCC
   đúng identity của app cài; không suy từ deployment target thành runtime PASS.
2. Corpus file/PDF thật có provenance, kiểm tra Spotlight importer/coverage và
   semantic top5 theo AC; chưa có corpus acceptance hoặc quality claims.
3. Đóng gói ONNX/tokenizers/Qt và model manifest vào app thực; RAM/latency theo
   process tree khi search/index/OCR/API cùng hoạt động trên M3 8GB.
4. Cloud credentials/tool-call loop của OpenAI/DeepSeek/Groq; TranslationCapability,
   scope revocation, worker lifecycle và verifiers xuyên suốt UI.

Bước code tiếp theo: profile/registry/import boundary chỉ hai capability, không
khởi tạo timetable/work-notes hoặc indexer/model khi cloud mini startup. Bộ
test/headless diagnostic ở đây được giữ để kiểm tra bản chính lẫn mini.

Nguồn đối chiếu: [sqlite-vec Python](https://alexgarcia.xyz/sqlite-vec/python.html),
[APSW isolation/install](https://rogerbinns.github.io/apsw/install.html),
[upstream ONNX files](https://huggingface.co/intfloat/multilingual-e5-small/tree/main/onnx).
API availability được đối chiếu thêm với Translation.swiftinterface trong SDK
Xcode trên máy dev; code probe chứa explicit availability checks.
