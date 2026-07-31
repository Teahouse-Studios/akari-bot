"""modules.core.analytics 单元测试 - 折线图数值标注的排版。"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from core.tester import func_case, Tester
from modules.core.analytics import annotate_points

FIGSIZES = ((6.4, 4.8), (4, 3), (12, 8))
CASES = (
    [0] * 20 + [3, 5, 2, 8, 4, 1, 6, 9, 12, 7],
    [0] * 29 + [999],  # 峰值出现在末尾
    [0] * 30,  # 全零，此时不该反过来压缩坐标区
    [5, 3, 8, 2, 9, 1, 7, 4, 6, 11, 0, 2],  # year 分支的 12 个点
)


def _max_overflow(data_y: list[int], figsize: tuple[float, float]) -> float:
    """
    按 analytics 折线图的画法出图，返回标注顶端超出坐标区上沿的最大像素数。
    """
    data_x = [str(i) for i in range(1, len(data_y) + 1)]
    figure = plt.figure(figsize=figsize)
    try:
        plt.plot(data_x, data_y, "-o")
        plt.plot(data_x[-1], data_y[-1], "-ro")
        plt.tick_params(axis="x", labelrotation=45, which="major", labelsize=10)
        plt.gca().yaxis.get_major_locator().set_params(integer=True)
        annotate_points(data_x, data_y)

        ax = plt.gca()
        figure.canvas.draw()
        return max(text.get_window_extent().y1 for text in ax.texts) - ax.get_window_extent().y1
    finally:
        plt.close(figure)


def _test_annotation_stays_inside_axes():
    """测试 analytics 折线图 - 最高点的数值标注不应顶出坐标区"""
    try:
        # 标注按像素偏移放置，不参与坐标轴自动缩放，因此要覆盖不同数据量级与图幅。
        return all(_max_overflow(data_y, figsize) < 0 for data_y in CASES for figsize in FIGSIZES)

    except Exception:
        return False


@func_case
async def test_analytics_plot(tester: Tester):
    """modules.core.analytics: 折线图标注排版测试"""
    await tester.test(_test_annotation_stays_inside_axes, "数值标注不超出坐标区测试")

    return tester
