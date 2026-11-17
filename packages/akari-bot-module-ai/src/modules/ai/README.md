使用本模块前，需在 `modules/ai/data/` 下创建 `llm_api_list.yaml`；如需图片生成与编辑，再创建 `image_api.yaml`。修改配置后需重启机器人或重载 `ai` 模块。

## `llm_api_list.yaml`

文件包含一个 `llm_api_list` 数组，每项为一个模型配置：

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    endpoint: openai
    superuser: false
    # 可选，覆盖模块配置中的默认值
    temperature: 0.3
    top_p: 0.9
    top_logprobs: 5
    reasoning_effort: high
    billing:
      type: token
      price_in: 50
      price_out: 50
      price_cache_read: 20
      price_cache_write: 40
```

| 字段 | 说明 |
| --- | --- |
| `api_key` / `api_url` / `model_name` | 模型 API 的密钥、地址与模型名。 |
| `endpoint` | API 类型：`openai`（默认，Chat Completions）、`openai-response`、`anthropic`、`gemini`、`gemini-interaction`。 |
| `name` | 展示名称，默认同 `model_name`。名称重复的配置均不会被载入。 |
| `superuser` | 为 `true` 时仅限超级用户使用。 |
| `temperature` / `top_p` / `top_logprobs` | 采样参数。显式设为 `null` 时不向模型传入该参数，适用于不支持相应参数的模型。 |
| `reasoning_effort` | 思考强度，`none` 表示不启用思维链。 |

## 计费

`billing.type` 支持以下取值：

- `token`（默认）：按输入、缓存读取、缓存写入与输出 Token 分别计费。
- `per_call`：每次调用固定扣除 `call_price`。
- `hybrid`：`call_price` 与 Token 费用叠加。

Token 价格单位为**花瓣 / 1M token**，未设置时为 `0`。缓存写入价格仅在 API 返回缓存写入用量时生效。`price_in` 等价格字段也可直接写在模型配置顶层，等价于 `type: token`。

### 阶梯与时段计费

`tiers` 按上下文长度调整单价，`time_rules` 按时段与星期调整单价；规则中未设置的价格沿用基础价格。

```yaml
billing:
  type: token
  price_in: 50
  price_out: 50
  tiers:
    - context_threshold: 131072  # 上下文达到该 Token 数后生效
      price_in: 100
      price_out: 100
  # time_rules:
  #   - time_range: "00:00-08:30"  # 支持跨零点
  #     week: [1, 2, 3, 4, 5, 6, 7]  # 1 为星期一，默认全周
  #     price_in: 20
  #     price_out: 20
```

时段按机器人配置的时区（`timezone_offset`）判断。**`tiers` 与 `time_rules` 同时配置时两者均不生效**。

### 价格换算

建议按 **1 花瓣 = ¥0.01** 换算服务商定价。例如输入 ¥9、缓存输入 ¥0.3、输出 ¥27（均为每百万 Token）的模型：

```yaml
billing:
  type: token
  price_in: 900
  price_cache_read: 30
  price_out: 2700
```

## `image_api.yaml`

配置存在且 `model_name` 非空时，模型会获得 `generate_image` 与 `edit_image` 工具。

```yaml
image_api:
  model_name: gpt-image-1
  base_url: https://api.openai.com/v1
  api_key: sk-xxxxxxxx
  costs:
    low: 4
    medium: 8
    high: 16
    default: 8
```

- `base_url`、`api_key` 留空时沿用当前对话模型的地址与密钥。
- `costs` 可为固定数值或对照表，查找顺序为 `尺寸:品质` → 品质 → 尺寸 → `default` → `auto` → 第一个数值。

---

Before using this module, create `llm_api_list.yaml` in `modules/ai/data/`. To enable image generation and editing, also create `image_api.yaml`. Restart the bot or reload the `ai` module after changing either file.

## `llm_api_list.yaml`

The file contains an `llm_api_list` array, with one model configuration per item:

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    endpoint: openai
    superuser: false
    # Optional, overrides the module configuration defaults
    temperature: 0.3
    top_p: 0.9
    top_logprobs: 5
    reasoning_effort: high
    billing:
      type: token
      price_in: 50
      price_out: 50
      price_cache_read: 20
      price_cache_write: 40
```

| Field | Description |
| --- | --- |
| `api_key` / `api_url` / `model_name` | API key, URL, and model name. |
| `endpoint` | API type: `openai` (default, Chat Completions), `openai-response`, `anthropic`, `gemini`, `gemini-interaction`. |
| `name` | Display name, defaults to `model_name`. Configurations with duplicate names are not loaded. |
| `superuser` | If `true`, restricted to superusers. |
| `temperature` / `top_p` / `top_logprobs` | Sampling parameters. Set to `null` to omit the parameter from requests, for models that do not support it. |
| `reasoning_effort` | Reasoning effort; `none` disables the chain of thought. |

## Billing

`billing.type` supports:

- `token` (default): Charges input, cache read, cache write, and output tokens separately.
- `per_call`: Charges a fixed `call_price` per call.
- `hybrid`: Charges `call_price` plus the token cost.

Token prices are in **petals per 1M tokens** and default to `0`. Cache write pricing only applies when the API reports cache write usage. Price fields such as `price_in` may also be placed at the top level of a model configuration, which is equivalent to `type: token`.

### Tiered and Time-Based Pricing

`tiers` adjusts prices by context length, and `time_rules` adjusts prices by time of day and weekday. Prices not set in a rule fall back to the base prices.

```yaml
billing:
  type: token
  price_in: 50
  price_out: 50
  tiers:
    - context_threshold: 131072  # Applies once the context reaches this many tokens
      price_in: 100
      price_out: 100
  # time_rules:
  #   - time_range: "00:00-08:30"  # May span midnight
  #     week: [1, 2, 3, 4, 5, 6, 7]  # 1 is Monday; defaults to every day
  #     price_in: 20
  #     price_out: 20
```

Time ranges use the bot's configured timezone (`timezone_offset`). **If both `tiers` and `time_rules` are configured, neither takes effect.**

### Price Conversion

A common conversion is **1 petal = ¥0.01**. For a model priced at ¥9 input, ¥0.3 cached input, and ¥27 output (per 1M tokens):

```yaml
billing:
  type: token
  price_in: 900
  price_cache_read: 30
  price_out: 2700
```

## `image_api.yaml`

When the file exists and `model_name` is non-empty, the model receives the `generate_image` and `edit_image` tools.

```yaml
image_api:
  model_name: gpt-image-1
  base_url: https://api.openai.com/v1
  api_key: sk-xxxxxxxx
  costs:
    low: 4
    medium: 8
    high: 16
    default: 8
```

- If `base_url` or `api_key` is empty, the current chat model's URL or key is used.
- `costs` may be a fixed number or a lookup table. Lookup order: `size:quality`, `quality`, `size`, `default`, `auto`, then the first numeric value.
