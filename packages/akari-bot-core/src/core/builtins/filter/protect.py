import re

from core.builtins.message.mention import spans_at_code

KE_CODE_PATTERN = re.compile(r"\[KE:[^\]]*\]")
I18N_PLACEHOLDER_PATTERN = re.compile(r"\{I18N:[^}]*\}")


def get_protected_intervals(content: str) -> list[tuple[int, int]]:
    protected: list[tuple[int, int]] = []

    protected.extend(spans_at_code(content))

    # KE 码：只豁免结构和 key，value 参与过滤
    for match in KE_CODE_PATTERN.finditer(content):
        start = match.start()
        end = match.end()

        prefix_end = start + 4
        protected.append((start, prefix_end))

        body_start = prefix_end
        body_end = end - 1

        first_comma = content.find(",", body_start, body_end)

        if first_comma == -1:
            protected.append((body_start, body_end))
        else:
            protected.append((body_start, first_comma))

            cursor = first_comma

            while cursor < body_end:
                if content[cursor] == ",":
                    protected.append((cursor, cursor + 1))
                    cursor += 1

                if cursor >= body_end:
                    break

                comma = content.find(",", cursor, body_end)
                field_end = comma if comma != -1 else body_end

                equal = content.find("=", cursor, field_end)

                if equal != -1:
                    protected.append((cursor, equal))

                    protected.append((equal, equal + 1))

                else:
                    protected.append((cursor, field_end))

                if comma == -1:
                    break

                cursor = comma

        protected.append((end - 1, end))

    # I18N 占位符
    for match in I18N_PLACEHOLDER_PATTERN.finditer(content):
        start = match.start()
        end = match.end()

        prefix_end = start + len("{I18N:")
        protected.append((start, prefix_end))

        body_start = prefix_end
        body_end = end - 1

        # 第一个字段 message.example 属于占位符主体，豁免
        first_comma = content.find(",", body_start, body_end)

        if first_comma == -1:
            protected.append((body_start, body_end))
        else:
            protected.append((body_start, first_comma))

            cursor = first_comma

            while cursor < body_end:
                if content[cursor] == ",":
                    protected.append((cursor, cursor + 1))
                    cursor += 1

                if cursor >= body_end:
                    break

                comma = content.find(",", cursor, body_end)
                field_end = comma if comma != -1 else body_end

                equal = content.find("=", cursor, field_end)

                if equal != -1:
                    protected.append((cursor, equal))

                    protected.append((equal, equal + 1))

                else:
                    # 没有 "=" 的部分作为结构处理
                    protected.append((cursor, field_end))

                if comma == -1:
                    break

                cursor = comma

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


def is_protected(protected_intervals: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < p_end and end > p_start for p_start, p_end in protected_intervals)
