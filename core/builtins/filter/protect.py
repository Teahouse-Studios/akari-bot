import re

AT_CODE_PATTERN = re.compile(r"<(?:AT|@):[^>]*>")
KE_CODE_PATTERN = re.compile(r"\[KE:[^\]]*\]")
I18N_PLACEHOLDER_PATTERN = re.compile(r"\{I18N:[^}]*\}")


def get_protected_intervals(content: str) -> list[tuple[int, int]]:
    protected: list[tuple[int, int]] = []

    # ---------------------------------------------------------
    # AT / @ 码：整体豁免
    # ---------------------------------------------------------
    for match in AT_CODE_PATTERN.finditer(content):
        protected.append((match.start(), match.end()))

    # ---------------------------------------------------------
    # KE 码：只豁免结构和 key，value 参与过滤
    # ---------------------------------------------------------
    for match in KE_CODE_PATTERN.finditer(content):
        start = match.start()
        end = match.end()

        # "[KE:" 整体属于结构
        prefix_end = start + 4
        protected.append((start, prefix_end))

        body_start = prefix_end
        body_end = end - 1  # 排除 "]"

        # 第一个字段是 element，整体属于结构
        first_comma = content.find(",", body_start, body_end)

        if first_comma == -1:
            # 没有键值对
            protected.append((body_start, body_end))
        else:
            # element
            protected.append((body_start, first_comma))

            # 解析后续 key=value
            cursor = first_comma

            while cursor < body_end:
                # 当前字段从 "," 后开始
                if content[cursor] == ",":
                    protected.append((cursor, cursor + 1))
                    cursor += 1

                if cursor >= body_end:
                    break

                comma = content.find(",", cursor, body_end)
                field_end = comma if comma != -1 else body_end

                equal = content.find("=", cursor, field_end)

                if equal != -1:
                    # key
                    protected.append((cursor, equal))

                    # "="
                    protected.append((equal, equal + 1))

                    # value 不加入 protected
                else:
                    # 无 "=" 的部分作为结构处理
                    protected.append((cursor, field_end))

                if comma == -1:
                    break

                cursor = comma

        # "]"
        protected.append((end - 1, end))

    # ---------------------------------------------------------
    # I18N 占位符
    # ---------------------------------------------------------
    for match in I18N_PLACEHOLDER_PATTERN.finditer(content):
        start = match.start()
        end = match.end()

        # "{I18N:" 是结构
        prefix_end = start + len("{I18N:")
        protected.append((start, prefix_end))

        body_start = prefix_end
        body_end = end - 1  # 排除 "}"

        # 第一个字段 message.example 属于占位符主体，豁免
        first_comma = content.find(",", body_start, body_end)

        if first_comma == -1:
            # 没有键值对，整个剩余主体豁免
            protected.append((body_start, body_end))
        else:
            # message.example
            protected.append((body_start, first_comma))

            # 解析后续 key=value
            cursor = first_comma

            while cursor < body_end:
                # 当前字段前面的 ","
                if content[cursor] == ",":
                    protected.append((cursor, cursor + 1))
                    cursor += 1

                if cursor >= body_end:
                    break

                comma = content.find(",", cursor, body_end)
                field_end = comma if comma != -1 else body_end

                equal = content.find("=", cursor, field_end)

                if equal != -1:
                    # key
                    protected.append((cursor, equal))

                    # "="
                    protected.append((equal, equal + 1))

                    # value 不加入 protected
                else:
                    # 没有 "=" 的部分作为结构处理
                    protected.append((cursor, field_end))

                if comma == -1:
                    break

                cursor = comma

        # "}"
        protected.append((end - 1, end))

    protected.sort()

    merged: list[tuple[int, int]] = []

    for start, end in protected:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (
                merged[-1][0],
                max(merged[-1][1], end),
            )

    return merged


def is_protected(protected_intervals: list[tuple[int, int]], start: int, end: int):
    return any(start < p_end and end > p_start for p_start, p_end in protected_intervals)
