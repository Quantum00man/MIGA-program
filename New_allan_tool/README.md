# Allan 方差分析器

基于 `Python + tkinter + matplotlib + allantools` 的桌面小工具，用于读取 CSV 中的一列数据并计算稳定度。

## 功能

- 默认读取 CSV 第 1 列数值，也可以手动指定列号
- 计算前可设置采样间隔 `t`
- 支持重叠与不重叠 Allan 方差
- 支持绝对 Allan 方差与相对 Allan 方差
- 支持 X/Y 轴在线性与对数坐标之间切换
- 左侧参数栏，右侧绘图区域

## 安装

```bash
python3 -m pip install -r requirements.txt
```

## 运行

```bash
python3 allan_ui.py
```

## 说明

- 程序内部默认使用 `allantools.oadev()` 或 `allantools.adev()` 计算 Allan 偏差，再平方后绘制 Allan 方差。
- 相对 Allan 方差会将数据按均值归一化，因此要求数据均值不能接近 0。
- CSV 中空行、表头和非数字内容会自动跳过。
