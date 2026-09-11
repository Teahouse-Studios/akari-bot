在使用本模块前，请确保在 `modules/ai/assets/` 目录下创建 `llm_api_list.yaml` 配置文件，否则模块将无法正常运行。

---

## `llm_api_list.yaml` 文件结构

该 YAML 文件应包含一个 `llm_api_list` 数组，每个元素表示一个大语言模型 API 配置。

### 基础配置示例

对于仅需要按照 Token 数量计费的模型，可以继续使用旧版配置格式。

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    endpoint: openai
    price_in: 50
    price_out: 50
    price_cache_read: 20
    price_cache_write: 40
    superuser: false
```

### 新版计费配置示例

对于需要按次计费、混合计费、阶梯计费或峰谷计费的模型，可以使用 `billing` 配置。

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: new-model
    name: example-llm
    endpoint: openai
    superuser: false

    billing:
      type: token
      price_in: 50
      price_out: 50
      price_cache_read: 20
      price_cache_write: 40
      # 可选
      call_price: 10
      # 可选
      tiers:
        - context_threshold: 131072
          price_in: 100
          price_out: 100
          price_cache_read: 50
          price_cache_write: 80
      # 可选
      time_rules:
        - time_range: "00:00-08:30"
          week: [1, 2, 3, 4, 5, 6, 7]
          price_in: 20
          price_out: 20
          price_cache_read: 10
          price_cache_write: 20
```

---

## 参数说明

### 基础参数

* `api_key`：大语言模型 API 的 API Key。
* `api_url`：大语言模型 API 的 URL。
* `model_name`：大语言模型的名称。
* `endpoint`：大语言模型 API 的类型，支持以下取值：

  * `openai`（默认）：OpenAI Chat Completions API。
  * `openai-response`：OpenAI Responses API。
  * `anthropic`：Anthropic Messages API。

### 可选参数

* `name`：向用户展示的名称。

  * 如果留空，默认与 `model_name` 相同。
  * 若多个配置的 `name` 相同，则这些配置都不会被载入。

* `superuser`：是否仅限超级用户使用。

  * `true`：仅限超级用户使用。
  * `false` 或 `null`：无须权限。

---

## 计费配置

新版配置可以通过 `billing` 指定模型的计费方式：

```yaml
billing:
  type: token
```

`type` 支持以下三种值：

| 类型         | 说明              |
| ---------- | --------------- |
| `token`    | 按 Token 数量计费    |
| `per_call` | 按 API 调用次数计费    |
| `hybrid`   | Token 计费 + 按次计费 |

### `token`

`token` 为默认的 Token 计费模式。

```yaml
billing:
  type: token
  price_in: 50
  price_cache_read: 20
  price_cache_write: 40
  price_out: 50
```

该模式按照输入 Token、缓存命中 Token 和输出 Token 分别计算费用。

### `per_call`

`per_call` 按 API 调用次数收取固定费用。

```yaml
billing:
  type: per_call
  call_price: 10
```

每次调用扣除 `call_price` 数量的花瓣。

### `hybrid`

`hybrid` 同时启用按次计费和 Token 计费。

```yaml
billing:
  type: hybrid
  call_price: 10
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

每次 API 调用的最终费用由固定调用费用和 Token 使用费用共同组成。

---

## Token 价格参数

以下参数的单位均为 **花瓣 / 1M token**：

* `price_in`：百万输入 Token 所需的花瓣数量。
* `price_cache_read`：百万输入缓存命中 Token 所需的花瓣数量。
* `price_cache_write`：百万输入缓存写入 Token 所需的花瓣数量。
* `price_out`：百万输出 Token 所需的花瓣数量。

旧版的 `price_cache` 等同于 `price_cache_read`，仍可继续使用。缓存写入价格只有在模型 API 返回缓存写入 token 数量时才会应用。

如果未设置，默认值为 `0`。

---

## 按次计费参数

### `call_price`

`call_price` 表示每次 API 调用固定扣除的花瓣数量。

```yaml
billing:
  type: per_call
  call_price: 10
```

在 `hybrid` 模式下，`call_price` 与 Token 费用同时计算：

```yaml
billing:
  type: hybrid
  call_price: 10
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

---

## 阶梯计费

可以通过 `tiers` 根据上下文长度设置不同的 Token 单价。

```yaml
tiers:
  - context_threshold: 131072
    price_in: 100
    price_out: 100
    price_cache_read: 40
    price_cache_write: 80
```

### `context_threshold`

`context_threshold` 表示上下文长度阈值，单位为 Token。

例如：

```yaml
context_threshold: 131072
```

表示超过 128K Token 后进入该阶梯价格。

阶梯规则中的：

* `price_in`
* `price_cache`
* `price_out`

分别覆盖该阶梯对应的输入、缓存输入和输出 Token 单价。

如果某个价格未设置，则使用基础价格。

---

## 峰谷/时段计费

可以通过 `time_rules` 根据 UTC 时间和星期设置不同的 Token 单价。

```yaml
time_rules:
  - time_range: "00:00-08:30"
    week: [1, 2, 3, 4, 5, 6, 7]
    price_in: 25
    price_out: 25
    price_cache_read: 10
    price_cache_write: 20
```

### `time_range`

`time_range` 表示适用的时间范围，使用 UTC 时间。

例如：

```yaml
time_range: "00:00-08:30"
```

表示服务器时间 00:00 至 08:30 期间使用该价格。

### `week`

`week` 用于指定适用的星期。

```yaml
week: [1, 2, 3, 4, 5, 6, 7]
```

其中：

* `1`：星期一
* `2`：星期二
* `3`：星期三
* `4`：星期四
* `5`：星期五
* `6`：星期六
* `7`：星期日

---

## 阶梯计费与峰谷计费的冲突规则

`tiers` 和 `time_rules` **不能同时生效**。

如果同一个模型同时配置了 `tiers` 和 `time_rules`，则 `tiers` 和 `time_rules` **均不生效**，不会按照优先级选择其中一种，也不会进行价格叠加。

因此，如果需要使用阶梯计费，请不要同时配置 `time_rules`；如果需要使用峰谷计费，请不要同时配置 `tiers`。

---

## 向下兼容

为了兼容旧版配置，可以直接在模型配置的顶层使用：

```yaml
price_in: 50
price_cache: 20
price_out: 50
```

例如：

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    price_in: 50
    price_out: 50
    price_cache_read: 20
    price_cache_write: 40
```

该方式等价于基础的 Token 计费配置：

```yaml
billing:
  type: token
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

如果使用新的 `billing` 配置，建议优先使用新版结构，以便支持更多计费方式和计费规则。

---

## 如何计算 `price` 相关参数？

建议按照服务商的实际定价计算 `price` 值，通常可以按照：

**1 花瓣 = ¥0.01**

例如 `deepseek-v4-pro` 模型的价格如下：

* **输入：¥9 / 1M token**
* **缓存输入：¥0.3 / 1M token**
* **输出：¥27 / 1M token**

计算方法：

* **输入成本：** ¥9 / 1M token = 900 花瓣 / 1M token
* **缓存成本：** ¥0.3 / 1M token = 30 花瓣 / 1M token
* **输出成本：** ¥27 / 1M token = 2700 花瓣 / 1M token

因此可以设置：

```yaml
billing:
  type: token
  price_in: 900
  price_out: 2700
  price_cache_read: 30
```

请根据自身情况与服务商定价合理设置 `price`，以进行成本控制。

---

Before using this module, please make sure to create the `llm_api_list.yaml` configuration file in the `modules/ai/assets/` directory. Otherwise, the module will not function properly.

---

## `llm_api_list.yaml` File Structure

The YAML file should contain an `llm_api_list` array, where each element represents an LLM API configuration.

### Basic Configuration Example

For models that only require token-based billing, the legacy configuration format can still be used.

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    price_in: 50
    price_out: 50
    price_cache_read: 20
    price_cache_write: 40
    superuser: false
```

### Advanced Billing Configuration Example

For models that require per-call billing, hybrid billing, tiered pricing, or time-based pricing, the `billing` configuration can be used.

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: new-model
    name: new-model
    superuser: false

    billing:
      type: token
      price_in: 50
      price_out: 50
      price_cache_read: 20
      price_cache_write: 40

      # Optional
      call_price: 10

      # Optional
      tiers:
        - context_threshold: 131072
          price_in: 100
          price_out: 100
          price_cache_read: 40
          price_cache_write: 80

      # Optional
      time_rules:
        - time_range: "00:00-08:30"
          week: [1, 2, 3, 4, 5, 6, 7]
          price_in: 25
          price_out: 25
          price_cache_read: 10
          price_cache_write: 20
```

---

## Parameter Description

### Basic Parameters

* `api_key`: The API Key for the LLM API.
* `api_url`: The URL of the LLM API.
* `model_name`: The name of the LLM.
* `endpoint`: The type of the LLM API. Supported values:

  * `openai` (default): OpenAI Chat Completions API.
  * `openai-response`: OpenAI Responses API.
  * `anthropic`: Anthropic Messages API.

### Optional Parameters

* `name`: The display name shown to users.

  * If omitted, it defaults to `model_name`.
  * If multiple configurations have the same `name`, none of them will be loaded.

* `superuser`: Whether only superusers can use this configuration.

  * `true`: Restricted to superusers only.
  * `false` or `null`: No special permission required.

---

## Billing Configuration

The new configuration uses `billing` to specify the billing method:

```yaml
billing:
  type: token
```

The `type` parameter supports the following three values:

| Type       | Description                                        |
| ---------- | -------------------------------------------------- |
| `token`    | Billing based on token usage                       |
| `per_call` | Billing based on the number of API calls           |
| `hybrid`   | Token-based billing combined with per-call billing |

### `token`

`token` is the default token-based billing mode.

```yaml
billing:
  type: token
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

This mode calculates the cost based on input tokens, cached input tokens, and output tokens.

### `per_call`

`per_call` charges a fixed amount for each API call.

```yaml
billing:
  type: per_call
  call_price: 10
```

Each API call costs `call_price` petals.

### `hybrid`

`hybrid` enables both per-call billing and token-based billing.

```yaml
billing:
  type: hybrid
  call_price: 10
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

The final cost of each API call consists of the fixed per-call fee and the token usage cost.

---

## Token Pricing Parameters

The following parameters are measured in **petals per 1M tokens**:

* `price_in`: Number of petals required per 1M input tokens.
* `price_cache_read`: Number of petals required per 1M cached input tokens.
* `price_cache_write`: Number of petals required per 1M input tokens written to cache.
* `price_out`: Number of petals required per 1M output tokens.

The legacy `price_cache` option is treated as `price_cache_read`. Cache write pricing is applied when the model API reports cache creation token usage.

If omitted, the default value is `0`.

---

## Per-Call Pricing

### `call_price`

`call_price` specifies the fixed number of petals charged for each API call.

```yaml
billing:
  type: per_call
  call_price: 10
```

In `hybrid` mode, `call_price` is charged in addition to the token usage cost:

```yaml
billing:
  type: hybrid
  call_price: 10
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

---

## Tiered Pricing

The `tiers` parameter can be used to define different token prices based on context length.

```yaml
tiers:
  - context_threshold: 131072
    price_in: 100
    price_out: 100
    price_cache_read: 40
    price_cache_write: 80
```

### `context_threshold`

`context_threshold` specifies the context length threshold, measured in tokens.

For example:

```yaml
context_threshold: 131072
```

This means that the specified tiered pricing is activated when the context length exceeds 128K tokens.

The following parameters inside a tier:

* `price_in`
* `price_cache`
* `price_out`

override the corresponding input, cached input, and output token prices for that tier.

If a price is omitted, the corresponding base price is used.

---

## Time-Based Pricing

The `time_rules` parameter can be used to define different token prices based on UTC time and weekdays.

```yaml
time_rules:
  - time_range: "00:00-08:30"
    week: [1, 2, 3, 4, 5, 6, 7]
    price_in: 25
    price_out: 25
    price_cache_read: 10
    price_cache_write: 20
```

### `time_range`

`time_range` specifies the applicable time range in UTC.

For example:

```yaml
time_range: "00:00-08:30"
```

This means that the specified prices apply from 00:00 to 08:30 server time.

### `week`

`week` specifies the applicable days of the week.

```yaml
week: [1, 2, 3, 4, 5, 6, 7]
```

Where:

* `1`: Monday
* `2`: Tuesday
* `3`: Wednesday
* `4`: Thursday
* `5`: Friday
* `6`: Saturday
* `7`: Sunday

---

## Conflict Between Tiered and Time-Based Pricing

`tiers` and `time_rules` **cannot be active at the same time**. If both `tiers` and `time_rules` are configured for the same model, **neither `tiers` nor `time_rules` will take effect**. No priority is applied between them, and their prices will not be combined.

Therefore, if you want to use tiered pricing, do not configure `time_rules` at the same time. Likewise, if you want to use time-based pricing, do not configure `tiers`.

---

## Backward Compatibility

For backward compatibility, the following legacy parameters can still be placed directly in the model configuration:

```yaml
price_in: 50
price_out: 50
price_cache_read: 20
price_cache_write: 40
```

For example:

```yaml
llm_api_list:
  - api_key: sk-1145141919810
    api_url: https://api.examplellm.com/v1
    model_name: llm-v1
    name: example-llm
    price_in: 50
    price_out: 50
    price_cache_read: 20
    price_cache_write: 40
```

This is equivalent to the basic token-based billing configuration:

```yaml
billing:
  type: token
  price_in: 50
  price_out: 50
  price_cache_read: 20
  price_cache_write: 40
```

When using the new `billing` configuration, the new structure is recommended to support additional billing methods and pricing rules.

---

## How to Calculate `price` Related Parameters

It is recommended to calculate the `price` values according to the service provider's actual pricing. A common conversion is:

**1 petal = ¥0.01**

For example, suppose the pricing of `deepseek-v4-pro` is:

* **Input: ¥9 / 1M tokens**
* **Cached Input: ¥0.3 / 1M tokens**
* **Output: ¥27 / 1M tokens**

Calculation:

* **Input cost:** ¥9 / 1M tokens = 900 petals / 1M tokens
* **Cached input cost:** ¥0.3 / 1M tokens = 30 petals / 1M tokens
* **Output cost:** ¥27 / 1M tokens = 2700 petals / 1M tokens

Therefore:

```yaml
billing:
  type: token
  price_in: 900
  price_out: 2700
  price_cache_read: 30
```

Please set the `price` values reasonably according to your own requirements and the service provider's pricing to control costs.