"""ReWrite 测试套件。

运行方式（项目根目录）::

    python -m unittest discover -s tests -t .      # 全部测试
    python -m unittest tests.test_snapshots -v     # 单个文件

约定：

- 只用标准库 ``unittest``，不引入 pytest 等新依赖；
- 只测 **不依赖 Qt 事件循环** 的纯逻辑，因此无需 QApplication、无窗口弹出；
- 所有落盘测试都在 ``tempfile.TemporaryDirectory`` 里做，绝不触碰 ``works/``。
"""
