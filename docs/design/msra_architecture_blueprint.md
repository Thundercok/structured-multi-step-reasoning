# Metacognitive Structured Reasoning Agent (MSRA)
## Master Blueprint & Architecture Specification

> **Trạng thái tài liệu:** Tài liệu thiết kế kỹ thuật / Đề xuất mở rộng tương lai (Phase 2 / Future Architecture).  
> **Mục đích:** Lưu trữ bản đặc tả toán học, cấu trúc dữ liệu, thuật toán tạo dữ liệu và kiến trúc thực thi đầy đủ để Claude / Agent đọc và kế thừa khi chuyển giao sang giai đoạn mở rộng tiếp theo của đề tài.  
> **Quan hệ với kế hoạch hiện tại (`docs/research_plan.md`):** Đề tài NCKH hiện tại tập trung vào đo đạc độ trung thực nhân quả (Causal Faithfulness) và phát hiện lỗi bằng chương trình độc lập vs. chương trình dịch trên mô hình nhỏ (Qwen3-8B). MSRA kế thừa trực tiếp phát hiện của Giả thuyết 3 (ngày 2026-11-05: *chương trình độc lập bắt lỗi lập luận mà chương trình dịch chép lại*) để nâng cấp mô hình thành một hệ thống tự nhận thức giới hạn năng lực (Epistemic Help-Seeking) có thể mở rộng.

---

## 1. Định nghĩa Toán học Tổng thể (Formal Problem Formulation)

### 1.1. Biểu diễn Trạng thái Lập luận dạng Đồ thị có hướng (Structured Reasoning DAG)

Cho một bài toán đầu vào $x \in \mathcal{X}$ và ngân sách chi phí tính toán tối đa $B_0 \in \mathbb{R}^+$. Quá trình suy luận đa bước không phải là việc sinh chuỗi token phẳng, mà là quá trình xây dựng tuần tự một đồ thị có hướng không chu trình (DAG) qua các bước thời gian rời rạc $t \in \{1, 2, \dots, K\}$:

$$\mathcal{G}_t = (\mathcal{V}_t, \mathcal{E}_t)$$

Trong đó mỗi đỉnh (node) $v_t \in \mathcal{V}_t$ đại diện cho một **Đơn vị Lập luận Đóng gói (Encapsulated Reasoning Unit)**:

$$v_t = \langle g_t, \tau_t, \mathcal{D}_t, y_t, \sigma_t \rangle$$

* **$g_t$ (Subgoal Specification):** Phát biểu tường minh của bài toán con tại bước $t$.
* **$\tau_t \in \mathcal{T}$ (Capability Tag):** Nhãn phân loại năng lực cốt lõi cần thiết để giải quyết $g_t$ (phục vụ định tuyến mở rộng không phụ thuộc vào tên Helper cứng).
* **$\mathcal{D}_t = \{(j, y_j) \mid (v_j, v_t) \in \mathcal{E}_t\}$ (Markovian Context Dependencies):** Tập hợp chỉ gồm các kết quả đầu ra đã xác thực $y_j$ từ các bước cha trực tiếp mà bước $t$ phụ thuộc vào ($\vert{}\mathcal{D}_t\vert{} \le d_{\max} \ll K$).
* **$y_t$ (Resolved Artifact):** Kết quả suy luận của bước $t$ (do mô hình gốc tự giải hoặc do Helper trả về).
* **$\sigma_t \in \{\texttt{PENDING}, \texttt{VERIFIED}, \texttt{REJECTED}\}$ (Epistemic Status):** Trạng thái kiểm chứng của bước $t$.

### 1.2. Quá trình Quyết định Markov Phân tách 2 Pha (Two-Phase Factored MDP)

Tại mỗi bước suy luận $t$, trạng thái hệ thống được định nghĩa là $s_t = (\mathcal{G}_{t-1}, g_t, \tau_t, \mathcal{D}_t, B_t)$. Mô hình chính sách $\pi_\theta$ (chính là mô hình ngôn ngữ nhỏ được fine-tune) thực hiện quyết định qua 2 pha:

1. **Pha Thực thi / Ủy quyền ($a_t^{(1)} \sim \pi_\theta(\cdot \mid s_t)$):**

$$a_t^{(1)} \in \left\{ \texttt{SOLVE\_LOCAL}, \quad \texttt{ASK\_HELP}(\tau_t, q_t) \right\}$$

Trong đó $q_t = \text{Pack}(g_t, \mathcal{D}_t)$ là gói truy vấn cô lập chỉ chứa đề bài con $g_t$ và các biến đầu vào $\mathcal{D}_t$. Bộ điều phối (Adaptive Controller) sẽ ánh xạ nhãn năng lực $\tau_t$ tới chuyên gia tối ưu $h^* \in \mathcal{H}$ thỏa mãn ràng buộc ngân sách $c(h^*) \le B_t$.

2. **Pha Kiểm chứng & Tích hợp ($a_t^{(2)} \sim \pi_\theta(\cdot \mid s_t, y_t^{\text{cand}})$):**
Sau khi nhận kết quả ứng viên $y_t^{\text{cand}}$ (từ chính nó hoặc từ Helper $h^*$), mô hình kiểm tra tính nhất quán với điều kiện biên của $\mathcal{D}_t$:

$$a_t^{(2)} \in \left\{ \texttt{COMMIT}(y_t^{\text{cand}}), \quad \texttt{REVISE\_OR\_ESCALATE}(\text{critique}_t) \right\}$$

### 1.3. Hàm Mục tiêu Tối ưu hóa Toàn cục (Constrained Utility Objective)

Mục tiêu huấn luyện là tìm bộ tham số $\theta^*$ tối đa hóa kỳ vọng độ chính xác lập luận cuối cùng đồng thời tối thiểu hóa chi phí gọi trợ giúp và độ dài chuỗi suy luận:

$$\max_{\theta} \mathcal{J}(\theta) = \mathbb{E}_{\tau \sim \pi_\theta} \left[ \mathbb{I}(\hat{Y}(\mathcal{G}_K) = Y^*) - \lambda_{\text{cost}} \sum_{t=1}^{K} \mathbb{I}(a_t^{(1)} = \texttt{ASK\_HELP}) \cdot c(h_t) - \lambda_{\text{step}} K \right]$$

---

## 2. Sơ đồ Kiến trúc Hệ thống (Publication-Ready TikZ Architecture)

```latex
\documentclass[tikz,border=12pt]{standalone}
\usetikzlibrary{shapes.geometric, arrows.meta, positioning, fit, backgrounds, calc}
\begin{document}
\begin{tikzpicture}[
    node distance=1.1cm and 1.6cm,
    font=\sffamily\small,
    basebox/.style={rectangle, rounded corners=4pt, draw=black!80, thick, minimum width=3.4cm, minimum height=0.9cm, align=center},
    modelnode/.style={basebox, fill=blue!10},
    decnode/.style={diamond, aspect=2.2, draw=orange!80!black, thick, fill=orange!12, inner sep=2pt, align=center, font=\sffamily\footnotesize},
    helpernode/.style={basebox, fill=purple!10, draw=purple!80!black, dashed, minimum width=2.8cm},
    verifynode/.style={basebox, fill=green!10, draw=green!60!black},
    statenode/.style={rectangle, draw=gray!80, thick, fill=gray!10, minimum width=4.2cm, minimum height=0.8cm, align=center, font=\ttfamily\footnotesize},
    arrow/.style={-{Stealth[scale=1.1]}, thick, draw=black!80},
    dasharrow/.style={-{Stealth[scale=1.1]}, thick, dashed, draw=purple!80!black}
]

% State DAG Header
\node[statenode] (dag) {Structured DAG State: $\mathcal{G}_{t-1} = \{v_1, \dots, v_{t-1}\}$, Budget $B_t$};

% Step 1: Propose Subgoal
\node[modelnode, below=0.8cm of dag] (propose) {\textbf{1. Subgoal Generator ($\pi_\theta$)}\\Sinh $g_t$, Capability Tag $\tau_t$, Deps $\mathcal{D}_t$};

% Step 2: Phase 1 Decision Gate
\node[decnode, below=0.9cm of propose] (gate1) {\textbf{Phase 1 Policy}\\$a_t^{(1)} \sim \pi_\theta(\cdot \mid s_t)$};

% Left Branch: Local CoT
\node[modelnode, below left=1.3cm and 1.4cm of gate1] (local) {\textbf{Local CoT Execution}\\Tự suy luận nội tại $\rightarrow y_t^{\text{local}}$};

% Right Branch: Help-Seeking Controller
\node[helpernode, below right=1.3cm and 1.4cm of gate1] (router) {\textbf{Capability Router}\\Ánh xạ $(\tau_t, B_t) \mapsto h^* \in \mathcal{H}$\\Đóng gói $q_t = (g_t, \mathcal{D}_t)$};

% Helper Pool
\node[helpernode, below=0.8cm of router, minimum width=4.6cm, font=\sffamily\scriptsize] (pool) {
    \textbf{Heterogeneous Helper Pool $\mathcal{H}$}\\
    $[h_{\text{sym}}]$ Python/SymPy \quad $[h_{\text{peer}}]$ Specialist \quad $[h_{\text{oracle}}]$ Frontier LLM
};

% Step 3: Phase 2 Verification Gate
\node[verifynode, below=3.6cm of gate1, minimum width=4.5cm] (verify) {\textbf{2. Phase 2 Epistemic Verifier ($\pi_\theta$)}\\Kiểm tra điều kiện biên $a_t^{(2)} \sim \pi_\theta(\cdot \mid s_t, y_t^{\text{cand}})$};

% Commit vs Revise
\node[modelnode, below=0.9cm of verify] (commit) {\textbf{Commit Node $v_t \to \mathcal{G}_t$}\\Cập nhật $B_{t+1} = B_t - c(h^*)$, tiến tới $t+1$};

% Connections
\draw[arrow] (dag) -- (propose);
\draw[arrow] (propose) -- (gate1);
\draw[arrow] (gate1) -| node[above left, font=\scriptsize\ttfamily] {SOLVE\_LOCAL} (local);
\draw[arrow] (gate1) -| node[above right, font=\scriptsize\ttfamily] {ASK\_HELP($\tau_t, q_t$)} (router);
\draw[dasharrow] (router) -- node[right, font=\scriptsize] {Isolated Query $q_t$} (pool);
\draw[arrow] (local) |- node[below left, font=\scriptsize] {$y_t^{\text{local}}$} (verify);
\draw[dasharrow] (pool) |- node[below right, font=\scriptsize] {$y_t^{\text{help}}$} (verify);
\draw[arrow] (verify) -- node[right, font=\scriptsize\ttfamily] {COMMIT} (commit);

% Feedback loop for Revision
\draw[arrow, draw=red!70!black] (verify.west) -- ++(-2.8,0) |- node[pos=0.25, left, font=\scriptsize\ttfamily, text=red!70!black, align=center] {REJECT /\\REPLAN} (propose.west);

\end{tikzpicture}
\end{document}
```

---

## 3. Thiết kế Ngôn ngữ Giao thức (Structured CoT Grammar & Capability Taxonomy)

### 3.1. Bảng phân loại Capability Tags ($\mathcal{T}$)

Hệ thống định nghĩa 5 nhãn năng lực trực giao (orthogonal) bao phủ toàn bộ nhu cầu suy luận đa bước, loại bỏ việc hardcode danh tính công cụ:

| Capability Tag ($\tau_t$) | Bản chất nút thắt suy luận (Subgoal Bottleneck) | Helper ánh xạ mặc định ($h^*$) | Chi phí chuẩn hóa $c(h)$ |
| --- | --- | --- | --- |
| **`[CAP:DECOMPOSE]`** | Lập kế hoạch, chia nhỏ bài toán, biến đổi bước cơ bản. | Tự giải nội tại ($\mathcal{M}_{\text{base}}$) | $0.0$ |
| **`[CAP:SYMBOLIC_CALC]`** | Giải hệ phương trình, đạo hàm, số học lớn, tổ hợp chính xác. | Python / SymPy Sandbox ($h_{\text{sym}}$) | $0.1$ |
| **`[CAP:DOMAIN_FACT]`** | Tra cứu định lý toán học hiếm, hằng số hóa lý, công thức chuyên ngành. | RAG / Domain Specialist ($h_{\text{spec}}$) | $0.2$ |
| **`[CAP:DEEP_DEDUCTION]`** | Bước suy diễn logic trừu tượng, tìm phản ví dụ, chứng minh bất đẳng thức khó. | Frontier Reasoning LLM ($h_{\text{oracle}}$) | $1.0$ |
| **`[CAP:SANITY_CHECK]`** | Kiểm tra nghiệm ngoại lai, thế ngược kết quả vào điều kiện biên. | Tự giải nội tại hoặc Python ($h_{\text{sym}}$) | $0.05$ |

### 3.2. Cấu trúc Chuỗi Sinh Token của Mô hình (Structured Trace Schema)

```xml
<step id="1" budget_remaining="2.0">
  <subgoal>Thiết lập phương trình bảo toàn năng lượng và rút gọn biểu thức vận tốc theo góc alpha.</subgoal>
  <deps>None</deps>
  <capability>CAP:DECOMPOSE</capability>
  <decision>SOLVE_LOCAL</decision>
  <execution>
    Áp dụng định luật bảo toàn cơ năng giữa vị trí ban đầu và góc alpha:
    m*g*R*(1 - cos(alpha)) = 1/2*m*v^2 => v^2 = 2*g*R*(1 - cos(alpha)).
  </execution>
  <verification status="COMMIT">Thứ nguyên hai vế đều là [L^2 T^-2], khi alpha=0 thì v=0 (khớp điều kiện biên).</verification>
  <output_var>v_sq = 2*g*R*(1 - cos(alpha))</output_var>
</step>

<step id="2" budget_remaining="2.0">
  <subgoal>Giải phương trình lượng giác bậc 4 để tìm nghiệm chính xác của cos(alpha) khi lực căng dây triệt tiêu.</subgoal>
  <deps>v_sq = 2*g*R*(1 - cos(alpha))</deps>
  <capability>CAP:SYMBOLIC_CALC</capability>
  <decision>ASK_HELP</decision>
  <query_payload>
    Solve for x = cos(alpha) in the interval [0, 1]: 9*x^4 - 6*x^3 + 2*x - 1 = 0. Return exact algebraic roots.
  </query_payload>
  <helper_response source="h_sym">
    Exact roots in [0, 1]: x = 1/3 * (1 + 2^(1/3)) approx 0.7533.
  </helper_response>
  <verification status="COMMIT">Nghiệm x = 0.7533 nằm trong khoảng hợp lệ [0, 1]. Thế ngược vào đa thức gốc: 9*(0.7533)^4 - 6*(0.7533)^3 + 2*(0.7533) - 1 ≈ 0.0001 (Hợp lệ).</verification>
  <output_var>cos_alpha = 0.7533</output_var>
</step>
```

---

## 4. Thuật toán Tạo dữ liệu $\mathcal{O}(\log K)$ (Counterfactual Bottleneck Binary Search - CBBS)

```latex
\documentclass{article}
\usepackage{amsmath, amssymb}
\usepackage{algorithm}
\usepackage{algpseudocode}
\begin{document}

\begin{algorithm}
\caption{Counterfactual Bottleneck Binary Search (CBBS) for SFT/DPO Data Generation}
\begin{algorithmic}[1]
\Require Dataset $\mathcal{D} = \{(x_i, y^*_i)\}$, Base Model $\mathcal{M}_{\text{base}}$, Helper Pool $\mathcal{H}$, Cost weight $\lambda$
\Ensure Supervised Trace Set $\mathcal{S}_{\text{SFT}}$, Preference Pair Set $\mathcal{S}_{\text{DPO}}$
\For{each problem $(x, y^*) \in \mathcal{D}$}
    \State Generate initial structured local trajectory $\tau_{\text{init}} = (v_1, v_2, \dots, v_K) \sim \mathcal{M}_{\text{base}}(x)$
    \If{$\text{ExtractAnswer}(\tau_{\text{init}}) == y^*$}
        \State Label all steps $t \in [1, K]$ with $a_t^{(1)} = \texttt{SOLVE\_LOCAL}$
        \State $\mathcal{S}_{\text{SFT}} \leftarrow \mathcal{S}_{\text{SFT}} \cup \{\tau_{\text{init}}\}$ \Comment{Zero helper calls required}
    \Else
        \State Initialize binary search bounds: $L \leftarrow 1, R \leftarrow K, t^* \leftarrow K$
        \While{$L \le R$} \Comment{$\mathcal{O}(\log_2 K)$ search for first broken subgoal}
            \State $m \leftarrow \lfloor (L + R) / 2 \rfloor$
            \State Query appropriate helper $h^* \in \mathcal{H}$ on isolated payload $q_m = (g_m, \mathcal{D}_m)$ to get $y_m^{\text{help}}$
            \State Resume rollout from step $m+1$ to $K$ using $\mathcal{M}_{\text{base}}$ conditioned on $y_m^{\text{help}}$
            \If{$\text{FinalAnswer}(\tau_{\text{resumed}}) == y^*$}
                \State $t^* \leftarrow m$; \quad $R \leftarrow m - 1$ \Comment{Intervention at $m$ fixed the trajectory; check earlier}
            \Else
                \State $L \leftarrow m + 1$ \Comment{Error occurred after step $m$ or required deeper intervention}
            \EndIf
        \EndWhile
        \If{valid bottleneck $t^*$ found where $\Delta U(s_{t^*}, h^*) > 0$}
            \State Construct hybrid trace $\tau^*$: steps $< t^*$ as $\texttt{SOLVE\_LOCAL}$, step $t^*$ as $\texttt{ASK\_HELP}(\tau_{t^*}, q_{t^*})$
            \State $\mathcal{S}_{\text{SFT}} \leftarrow \mathcal{S}_{\text{SFT}} \cup \{\tau^*\}$
            \State $\mathcal{S}_{\text{DPO}} \leftarrow \mathcal{S}_{\text{DPO}} \cup \{(s_{t^*}, a_{\text{win}}=\texttt{ASK\_HELP}, a_{\text{lose}}=\texttt{SOLVE\_LOCAL})\}$
        \EndIf
    \EndIf
\EndFor
\end{algorithmic}
\end{algorithm}
\end{document}
```

> **Lưu ý kỹ thuật quan trọng cho Claude/Implementer:**  
> Thuật toán CBBS đòi hỏi tính đơn điệu (monotonicity). Nếu một bước sớm ($t < m$) đã làm sai lệch biến phụ thuộc $\mathcal{D}_m$, việc can thiệp tại $m$ có thể thất bại dù $m$ được cấp Helper chuẩn. Khi triển khai, cần áp dụng cơ chế **Golden-Context Guided CBBS** (dùng ngữ cảnh sạch) hoặc **Forward-Exponential Search** để tránh việc gán nhãn sai.

---

## 5. Kiến trúc Code Thực thi (Execution Harness)

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import re

@dataclass
class ReasoningNode:
    step_id: int
    subgoal: str
    deps: Dict[str, str]
    capability_tag: str
    decision: str  # "SOLVE_LOCAL" or "ASK_HELP"
    query_payload: Optional[str] = None
    execution_result: str = ""
    verification_status: str = "PENDING"  # "COMMIT" or "REJECT"
    output_var: Dict[str, str] = field(default_factory=dict)

class CapabilityRouter:
    """Ánh xạ Capability Tag sang Helper tối ưu mà không cần hardcode tên Helper vào LLM."""
    def __init__(self):
        self.helpers: Dict[str, tuple[Callable[[str], str], float]] = {}

    def register_helper(self, capability_tag: str, fn: Callable[[str], str], cost: float):
        self.helpers[capability_tag] = (fn, cost)

    def dispatch(self, capability_tag: str, payload: str, remaining_budget: float) -> tuple[str, float]:
        if capability_tag not in self.helpers:
            raise ValueError(f"Unsupported capability tag: {capability_tag}")
        helper_fn, cost = self.helpers[capability_tag]
        if cost > remaining_budget:
            return "[SYSTEM_WARNING: BUDGET_EXCEEDED_SOLVE_LOCALLY]", 0.0
        return helper_fn(payload), cost

class MetacognitiveReasoningHarness:
    """Bộ khung thực thi vòng lặp Structured CoT tích hợp Help-Seeking."""
    def __init__(self, base_model_generate: Callable[[str, List[str]], str], router: CapabilityRouter):
        self.generate = base_model_generate
        self.router = router

    def solve(self, problem: str, max_steps: int = 10, budget: float = 2.0) -> Dict:
        dag_nodes: List[ReasoningNode] = []
        verified_memory: Dict[str, str] = {}
        total_cost = 0.0
        context_trace = f"<problem>{problem}</problem>\n"

        for step_idx in range(1, max_steps + 1):
            budget_rem = max(0.0, budget - total_cost)
            step_header = f"<step id=\"{step_idx}\" budget_remaining=\"{budget_rem:.2f}\">\n"
            
            # 1. Cho Base Model sinh đến thẻ </decision> hoặc </query_payload>
            step_prefix = self.generate(
                context_trace + step_header,
                stop_sequences=["</decision>", "</query_payload>", "</problem_solved>"]
            )
            
            if "<final_answer>" in step_prefix:
                context_trace += step_prefix
                break

            cap_match = re.search(r"<capability>(.*?)</capability>", step_prefix, re.DOTALL)
            dec_match = re.search(r"<decision>(.*?)</decision>", step_prefix, re.DOTALL)
            capability = cap_match.group(1).strip() if cap_match else "CAP:DECOMPOSE"
            decision = dec_match.group(1).strip() if dec_match else "SOLVE_LOCAL"

            context_trace += step_header + step_prefix

            # 2. Xử lý nhánh ASK_HELP vs SOLVE_LOCAL
            if decision == "ASK_HELP":
                if "</query_payload>" not in step_prefix:
                    payload_chunk = self.generate(context_trace, stop_sequences=["</query_payload>"])
                    context_trace += payload_chunk + "</query_payload>\n"
                
                q_match = re.search(r"<query_payload>(.*?)</query_payload>", context_trace.split(f"<step id=\"{step_idx}\"")[-1], re.DOTALL)
                isolated_query = q_match.group(1).strip() if q_match else problem

                # Gọi Helper với Isolated Query (O(1) Context Complexity)
                helper_out, step_cost = self.router.dispatch(capability, isolated_query, budget - total_cost)
                total_cost += step_cost
                context_trace += f"  <helper_response>{helper_out}</helper_response>\n"

            # 3. Cho Base Model chạy pha Verification và xuất Output Variable
            step_suffix = self.generate(context_trace, stop_sequences=["</step>"])
            context_trace += step_suffix + "</step>\n"

        return {
            "trace": context_trace,
            "total_cost": total_cost,
            "budget_remaining": budget - total_cost
        }
```

---

## 6. Quy trình Huấn luyện 3 Giai đoạn (Training Pipeline)

1. **Giai đoạn 1 — Structural Cold-Start SFT (Huấn luyện Định dạng & Phân rã):**
   * **Dữ liệu:** $5.000$ chuỗi lập luận chuẩn từ tập train của MATH và GSM8K chuyển đổi sang định dạng thẻ XML (`<subgoal>`, `<deps>`, `<capability>`, `<decision>`, `<verification>`).
   * **Mục tiêu:** Dạy mô hình thói quen phân rã bài toán thành các bước có cấu trúc cô lập biến $\mathcal{D}_t$ trước khi tính toán.

2. **Giai đoạn 2 — Counterfactual Utility SFT (Học Ranh giới Năng lực):**
   * **Dữ liệu:** Chạy mô hình Giai đoạn 1 qua thuật toán CBBS để thu thập quỹ đạo lai $\tau^*$, nơi mô hình tự giải bước dễ và gọi `ASK_HELP` ở đúng bước gãy $t^*$.
   * **Loss Masking quan trọng:** Khi tính Cross-Entropy, **bắt buộc mask (trọng số = 0 / label = -100) toàn bộ token trong thẻ `<helper_response>...</helper_response>**`. Mô hình không được học vẹt tri thức của Helper, mà chỉ học cách phát ra `<decision>`, `<query_payload>` và `<verification>`.

3. **Giai đoạn 3 — Cost- & Verification-Aware DPO / SimPO (Tinh chỉnh Chính sách):**
   * Thay vì DPO đầy đủ (dễ OOM trên 16GB RAM), khuyến nghị dùng **SimPO** với 3 loại cặp đối kháng $(y_w, y_l)$:
     * **Cặp 1 (Chống lười biếng / Over-delegation):** $y_w = \texttt{SOLVE\_LOCAL}$ vs. $y_l = \texttt{ASK\_HELP}$ tại các bước mô hình tự giải đúng 100%.
     * **Cặp 2 (Chống bảo thủ / Under-delegation):** $y_w = \texttt{ASK\_HELP}$ vs. $y_l = \texttt{SOLVE\_LOCAL}$ tại các bước nút thắt $t^*$ mà mô hình tự giải bị sai.
     * **Cặp 3 (Chống tin mù quáng / Adversarial Verification):** Bơm kết quả sai từ Helper vào `<helper_response>`, huấn luyện $y_w = \texttt{verification status="REJECT"}$ thắng $y_l = \texttt{verification status="COMMIT"}$.

---

## 7. Ma trận Thí nghiệm Mục tiêu (Experimental Matrix)

| Research Question | Thí nghiệm cụ thể | Chỉ số đo lường (Metrics) | Kết quả kỳ vọng để chứng minh luận điểm |
| --- | --- | --- | --- |
| **RQ1: Pareto Optimality** | So sánh MSRA-8B với Base-8B, Self-Refine, RouteLLM, React trên MATH-500, BBH, SciBench. | Accuracy (%) vs. Average Normalized FLOPs/Token Cost. | Đạt 85–90% hiệu năng của 70B nhưng chỉ tốn 20–25% chi phí nhờ gọi trợ giúp đúng bước gãy. |
| **RQ2: Metacognitive Precision** | Đánh giá ma trận nhầm lẫn của quyết định xin trợ giúp so với năng lực thực tế của Base-8B. | HSP (Precision), HSR (Recall), Over-delegation Rate (%). | Vượt qua phương pháp đo ngưỡng Entropy/Confidence tự báo cáo $>18\%$ F1-score. |
| **RQ3: Scalability Analysis** | Horizon Scaling ($3 \to 12$ bước) & Zero-Shot Helper Swap (đổi Helper lúc inference). | Token Overhead per Call & Accuracy Drop. | Chi phí mỗi lần gọi Helper giữ phẳng $\mathcal{O}(1)$ nhờ query cô lập; tận dụng được Helper mới ngay lập tức qua Capability Tag. |
| **RQ4: Robustness to Noisy Helpers** | Bơm lỗi ngẫu nhiên ($15\%, 30\%$) vào phản hồi của Helper để thử thách pha Verification. | Error Catch Rate (%) & Final Accuracy Retention. | Phát hiện và từ chối kết quả sai từ Helper thay vì bị cuốn theo như CoT chuỗi thông thường. |
