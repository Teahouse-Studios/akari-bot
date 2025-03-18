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
            "superuser": false
        }
    ]
}
```

---

## 参数说明 (Parameter Description)

### 必填参数 (Required Params)
- **`api_key`**：大语言模型 API 的 API Key。
  - The API Key for the LLM API.
- **`api_url`**：大语言模型 API 的 URL。
  - The URL of the LLM API.
- **`model_name`**：大语言模型的名称。
  - The name of the LLM.

### 可选参数 (Optional Params)
- **`name`**：向用户展示的名称。
  - The display name shown to users.
  - 如果留空，默认与 `model_name` 相同。
    - If left empty, it defaults to `model_name`.
  - 若多个配置的 `name` 相同，则这些配置都不会被载入。
    - If multiple configurations have the same `name`, none of them will be loaded.
- **`superuser`**：是否仅限超级用户使用。
  - Whether only superusers can use this configuration.
  - **`true`**：仅限超级用户使用。
    - **`true`**: Restricted to superusers only.
  - **`false`** 或 **`null`**：无须权限。
    - **`false`** or **`null`**: No permissions required.
---

请务必正确配置 `llm_api_list.json`，确保模块能够正常访问大语言模型。

Make sure to correctly configure `llm_api_list.json` to ensure that the module can access the LLMs properly.


