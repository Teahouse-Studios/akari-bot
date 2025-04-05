在使用本模块前，请确保在 `assets/modules/ai` 目录下创建 `llm_api_list.json` 配置文件，否则模块将无法正常运行。

Before using this module, please make sure to create `llm_api_list.json` configuration file in the `assets/modules/ai` directory. Otherwise, the module will not function properly.

---

## `llm_api_list.json` 文件结构 (File Structure)

该 JSON 文件应包含一个 `llm_api_list` 数组，每个元素表示一个大语言模型 API 配置，示例如下：

This JSON file should contain an `llm_api_list` array, where each element represents a LLM API configuration, as shown in the example below:

```json
{
    "llm_api_list": [
        {
            "api_key": "sk-1145141919810",
            "api_url": "https://api.examplellm.com/v1",
            "model_name": "llm-v1",
            "name": "example-llm",
            "price_in": 0.0005,
            "price_out": 0.0005,
            "superuser": false
        }
    ]
}
```

---

## 参数说明 (Parameter Description)

### 必填参数 (Required Params)
- `api_key`：大语言模型 API 的 API Key。
  - The API Key for the LLM API.
- `api_url`：大语言模型 API 的 URL。
  - The URL of the LLM API.
- `model_name`：大语言模型的名称。
  - The name of the LLM.

### 可选参数 (Optional Params)
- `name`：向用户展示的名称。
  - The display name shown to users.
  - 如果留空，默认与 `model_name` 相同。
    - If left empty, it defaults to `model_name`.
  - 若多个配置的 `name` 相同，则这些配置都不会被载入。
    - If multiple configurations have the same `name`, none of them will be loaded.
- `superuser`：是否仅限超级用户使用。
  - Whether only superusers can use this configuration.
  - `true`：仅限超级用户使用。
    - `true`: Restricted to superusers only.
  - `false` 或 `null`：无须权限。
    - `false` or `null`: No permissions required.
- `price_in`：1 个输入 token 所需的花瓣数量。
  - The number of petals required per input token.
  - 如果留空，默认为 `0`。
    - Defaults to `0` if left empty.
- `price_out`：1 个输出 token 所需的花瓣数量。
  - The number of petals required per output token.
  - 如果留空，默认为 `0`。
    - Defaults to `0` if left empty.

---

## 如何计算 `price` 相关参数？(How to Calculate the `price` Related Param?)

建议按照服务商的定价计算 `price` 值，通常设 1 花瓣 = ¥0.01。

It is recommended to calculate the `price` value according to the service provider's pricing, usually assume 1 petal = ¥0.01.

例如 `deepseek-reasoner` 模型的价格如下：

For example, the price of `deepseek-reasoner` model is as follows:

- **deepseek-reasoner**
  - **输入 (Input)：¥4 / 1M tokens**
  - **输出 (Output)：¥16 / 1M tokens**

计算方法：

Calculation method:

- **输入成本 (Input cost)：** ¥4 / 1M tokens = ¥0.000004 / token = 0.0004 petal/token
- **输出成本 (Output cost)：** ¥16 / 1M tokens = ¥0.000016 / token = 0.0016 petal/token

因此，若使用 `deepseek-reasoner`，可设置：

Therefore, if you use `deepseek-reasoner`, you can set:

```json
"price_in": 0.0004
"price_out": 0.0016
```

请根据自身情况与服务商定价合理设置 `price`，以进行成本控制。

Please set `price` reasonably according to your own situation and service provider pricing to control costs.
