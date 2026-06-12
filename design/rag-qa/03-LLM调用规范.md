结合你项目里的 `1-情感分析-Qwen.py`，把问答系统里**所有 LLM 调用**统一为 **阿里云 DashScope（通义千问）** 方案如下（仍属设计，不写业务代码）。

---

# LLM 调用规范（对齐 `1-情感分析-Qwen.py`）

## 1. 统一调用方式

与现有脚本保持一致：

| 项 | 约定 |
|----|------|
| **SDK** | `dashscope` |
| **鉴权** | `dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")`（不写死在代码里） |
| **调用入口** | `dashscope.Generation.call(...)` |
| **消息格式** | `messages=[{"role":"system"|"user"|"assistant", "content": "..."}]` |
| **返回格式** | `result_format="message"`，取 `response.output.choices[0].message.content` |
| **封装** | 项目内统一 `get_response(messages, model=..., **kwargs)`，各步骤只换 `model` 与 `messages` |

```text
环境变量：DASHSCOPE_API_KEY=sk-xxx
```

情感分析示例中的模式可直接复用到 Router / Generator 等步骤。

---

## 2. 各步骤：DashScope 模型与是否用 LLM

| 步骤 | 是否 LLM | 推荐 `model`（DashScope） | 调用说明 |
|------|----------|---------------------------|----------|
| **0.5 Embedding 建库** | 否（Embedding API） | `text-embedding-v3` 或 `text-embedding-v2` | `dashscope.TextEmbedding.call`，非 `Generation` |
| **2 Router（CoT 检索计划）** | 是 | `qwen-turbo` 或 `qwen-plus` | `Generation.call` + JSON 约束（system 要求只输出 JSON） |
| **3a 目录检索** | 否 | — | SQL / BM25 |
| **3b 图谱检索** | 否（默认） | — | 别名表 + SQL；抽不出实体时再调 LLM |
| **3b 实体识别（可选）** | 是 | `qwen-turbo` | 同 `get_response`，输出实体列表 JSON |
| **3c 混合检索** | 否 | — | 向量 + BM25 |
| **5 Rerank** | 否（Rerank API） | `gte-rerank` 等 DashScope 重排模型 | `dashscope` 重排接口（与 Generation 不同产品线） |
| **6 答案生成（Generator）** | 是 | `qwen-plus` 或 `qwen-max` | `Generation.call`，`result_format="message"`，建议 `stream=True` 给前端 |
| **6 查询改写（可选）** | 是 | `qwen-turbo` | 仅模糊问句时 |
| **多轮摘要（可选）** | 是 | `qwen-turbo` | 压缩历史 messages |

**与你现有脚本对齐的默认分工**

- **轻量 / 结构化**：`qwen-turbo`（Router、NER、摘要）— 与 `1-情感分析-Qwen.py` 相同  
- **最终回答**：`qwen-plus` 或 `qwen-max`（质量更好、略贵）  
- **非对话**：Embedding、Rerank 走 DashScope 对应 API，不走 `Generation.call`

---

## 3. LangChain 中的接法（设计层）

两种路线，二选一即可：

| 方案 | 做法 |
|------|------|
| **A. 官方适配器** | `langchain-community` 的 `ChatTongyi` / `Tongyi`，底层仍用 DashScope；`api_key` 读 `DASHSCOPE_API_KEY` |
| **B. 薄封装（更贴近你现有代码）** | 自定义 `BaseChatModel`，内部调用 `get_response(messages, model=...)`，LangGraph 节点只调该封装 |

建议：**Router / Generator 用 B**，与 `1-情感分析-Qwen.py` 完全一致，便于调试；检索、Rerank 仍用工具类，不经过 ChatModel。

---

## 4. 各步骤 Prompt 与 messages 结构（示意）

### 4.1 Router（`qwen-turbo`）

```text
system: 你是检索路由器。根据用户问题，用 CoT 在 reasoning 里简要分析，再输出 JSON：
paths[catalog|graph|hybrid], hybrid.top_k, rerank.top_n, seed_entities...
user: {query}
```

- 可用 `response_format` / 强约束 JSON（若 DashScope 模型支持）；否则 system 要求「仅 JSON」+ 解析校验。  
- **持久化**：`retrieval_logs.router_plan` 存 JSON + 原始 `reasoning`。

### 4.2 Generator（`qwen-plus` / `qwen-max`）

```text
system: 你是《三国演义》知识助手。仅依据下列检索材料回答；无依据则说明不知道。
      引用格式：[回目/路径]。不得编造。
user: 检索材料：\n{doc1}\n{doc2}...\n\n问题：{query}
```

- 流式：`Generation.call(..., stream=True)` → Web SSE。  
- **持久化**：`chat_messages` 存 assistant 全文 + `retrieval_trace`。

### 4.3 可选：实体识别（`qwen-turbo`）

```text
system: 从问题中抽取三国人物/地点/势力规范名，输出 JSON 数组。
user: {query}
```

优先用 `character_relations.ALIASES` 规则匹配，匹配不到再调此 LLM。

---

## 5. 与持久化、工具的配合（不变）

| 组件 | 技术 | 说明 |
|------|------|------|
| 会话 | PostgreSQL | `chat_messages` 存多轮 messages 可还原为 DashScope `messages` |
| 检索日志 | PostgreSQL | 存 Router JSON、rerank 分，与 LLM 无关 |
| Embedding | `dashscope.TextEmbedding` | 建库一次写入 `chunks.embedding` |
| Rerank | DashScope Rerank API | 非 `Generation` |
| 追踪 | LangSmith（可选） | 记录每次 `model`、token、延迟 |

---

## 6. 配置清单（`.env` 设计）

```bash
# 与 1-情感分析-Qwen.py 一致
DASHSCOPE_API_KEY=your_key

# 可选：按步骤覆盖模型名
QWEN_MODEL_ROUTER=qwen-turbo
QWEN_MODEL_GENERATOR=qwen-plus
QWEN_MODEL_NER=qwen-turbo
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3
DASHSCOPE_RERANK_MODEL=gte-rerank
```

应用启动时：`dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")`，与情感分析脚本同一套环境。

---

## 7. 更新后的「LLM / 工具」总表

| 角色 | 实现 | API |
|------|------|-----|
| Router | **LLM** `qwen-turbo` | `dashscope.Generation.call` |
| Generator | **LLM** `qwen-plus` / `qwen-max` | 同上，可 `stream=True` |
| NER（可选） | **LLM** `qwen-turbo` | 同上 |
| 情感分析（已有） | **LLM** `qwen-turbo` | `1-情感分析-Qwen.py` |
| Embedding | **工具** | `dashscope.TextEmbedding` |
| Rerank | **工具** | DashScope Rerank |
| 检索三路 | **工具** | PostgreSQL / LangChain Retriever |

---

## 8. 实施时注意

1. **密钥**：仅 `DASHSCOPE_API_KEY`，与情感分析共用，勿提交仓库。  
2. **错误处理**：对 `response.status_code`、空 `choices` 做统一重试/降级（Router 失败 → 默认 `hybrid top_k=40`）。  
3. **费用**：Router 用小模型；Generator 用大模型；检索与 Rerank 不占 Generation 额度。  
4. **LangChain**：若用 `ChatTongyi`，在配置里显式 `dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")`，与全局 `dashscope.api_key` 二选一即可，避免重复设置。

这样整条问答链路的 LLM 都与 `1-情感分析-Qwen.py` 的 **DashScope + `Generation.call` + 环境变量 API Key** 保持一致；只有 Embedding / Rerank 使用 DashScope 的其他 API。若你确定 Generator 也用 `qwen-turbo`（与情感分析完全同款），把上表里的 `qwen-plus` 改成 `qwen-turbo` 即可。

> 说明：实现代码见 `rag/llm.py`、`rag/config.py`，与本文约定一致。