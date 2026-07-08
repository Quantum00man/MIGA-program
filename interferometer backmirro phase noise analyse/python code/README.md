
# 地震引起的原子相位噪声桌面程序

这是一个使用 Tkinter 创建的本地桌面程序，不需要浏览器，也不需要启动服务器。

## Ubuntu 安装依赖

```bash
sudo apt update
sudo apt install python3-venv python3-tk
```

进入程序目录后创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 运行

```bash
python app_desktop.py
```

程序会直接打开桌面窗口。

## Excel 支持

- `.xls`
- `.xlsx`
- 可选择工作表
- 可选择频率列
- 可选择任意加速度 ASD 列
- 支持法式小数逗号，例如 `1,32736E-4`

## 计算内容

\[
x_{\rm ASD}(f)=\frac{a_{\rm ASD}(f)}{(2\pi f)^2}
\]

\[
\phi_{\rm laser,ASD}(f)=\frac{R\pi}{\lambda}x_{\rm ASD}(f)
\]

\[
H_{\rm AI}(\omega)
=8\sin(\omega T/2)\sin^2(\omega T/4)
\]

\[
|H_{\rm diff}(\omega)|^2
=C\sin^2(\omega T_c/2)
\]

\[
S_{\phi,\rm atom}(f)
=|H_{\rm diff}|^2 |H_{\rm AI}|^2
\phi_{\rm laser,ASD}^2(f)
\]

\[
\phi_{\rm RMS}
=\sqrt{\int S_{\phi,\rm atom}(f)\,df}
\]

其中 $T_c$ 表示相邻两次实验循环之间的 cycling time（循环周期），默认值为 `1 s`。
