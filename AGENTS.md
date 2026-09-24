# Repository Guidelines

## 项目结构与模块组织

```text
.
├── src/sjtu_sports/         # Python 包源码
│   ├── analyze/             # 浏览器抓包与请求分析
│   ├── reserve/             # 登录状态保存与场地预约
│   └── utils/               # AES、RSA 与路径工具
├── output/                  # 本地运行数据（不提交）
├── auth/                    # 登录态与浏览器配置（不提交）
├── pyproject.toml           # 包元数据与依赖声明
└── README.md                # 安装和使用说明
```

新增的可复用逻辑应放入 `src/sjtu_sports/utils/`，避免在多个模块中重复实现。

## 构建、测试与开发命令

先激活 `.venv` 并运行 `python -m pip install -e .` 安装开发版本，再在仓库根目录执行：

- `python -m sjtu_sports login`：打开浏览器并更新登录状态。
- `python -m sjtu_sports list-venues`：列出全部场馆名称和 id。
- `python -m sjtu_sports list-sports --venue 霍英东体育中心`：列出指定场馆的运动类型。
- `python -m sjtu_sports reserve --help`：查看预约参数；实际预约默认每 0.3 秒查询一次，`--long-run` 每 0.8 秒查询一次。
- `python -m sjtu_sports capture`：捕获 XHR 和 Fetch 请求。
- `python -m sjtu_sports analyze`：分析 `output/captured.json`。
