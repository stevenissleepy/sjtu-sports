# SJTU 体育场馆预约工具

## Install

在虚拟环境里：

```sh
pip install -e .
playwright install chromium
```

## 抢场地

先登录一次保存 cookie（仅 cookie 过期时需要重跑）：

```sh
python -m sjtu_sports login
```

然后：

```sh
# 查看全部场馆
python -m sjtu_sports list-venues

# 查看指定场馆的运动类型
python -m sjtu_sports list-sports --venue 霍英东体育中心

# 试跑：只查询并构造请求体，不真正提交
python -m sjtu_sports reserve \
  --venue 霍英东体育中心 \
  --sport 羽毛球 \
  --date 2026-09-26 \
  --time 13:00-14:00 \ 
  --dry-run

# 真正抢：--wait 会一直轮询，目标时段一变可用就立即提交
python -m sjtu_sports reserve \
  --venue 霍英东体育中心 \
  --sport 羽毛球 \
  --date 2026-09-26 \
  --time 13:00-14:00 \
  --wait
```

参数：

- `--venue`  场馆名称，必填；通过 `list-venues` 查看
- `--sport`  运动类型名称或 id，必填；通过 `list-sports` 查看
- `--date`   目标日期 `YYYY-MM-DD`
- `--time`   目标时段，如 `13:00-14:00`（不填则抢任意可用时段）
- `--field`  指定场地名，如 `场地1`
- `--wait`   轮询等待目标时段可用
- `--dry-run` 只构造请求体，不提交

## 抓包分析（analyze）

使用包级命令启动以下两个功能：

**1. `capture.py` 抓包**

打开浏览器 → 手动登录并完整走一遍抢订流程 → 关闭窗口后，所有接口请求（URL、方法、请求头、请求体、响应）会存到 `output/captured.json`。

```powershell
python -m sjtu_sports capture
```

**2. `analyze.py` 分析**

读取 `captured.json`，打印两类内容：

- 去噪后的完整请求清单（过滤掉高德地图等无关请求）
- 关键请求（登录 / 查场地 / 抢订 / 验证码）的请求头、请求体与响应摘要

```powershell
python -m sjtu_sports analyze
```

### 分析结论

抢订完整链路：

```
jaccount 登录
  → queryVenueById（拿运动类型 + 紧张度 tension）
  → queryFieldReserveSituationIsFull（拿加密的 dateId）
  → queryFieldSituation（拿场地时段 priceList，含 price/sign/status）
  → /venue/personal/ConfirmOrder（提交抢订）
```

核心加密机制：`ConfirmOrder` 请求体用 **AES-ECB** 加密，密钥是每次随机生成的 16 位字符串，再经 **RSA-2048** 加密后放进 `sid` 请求头；服务器先解 RSA 拿到 AES 密钥，再解密请求体。

> 注：高峰期服务器可能返回 `code 1002` 要求滑块验证码，纯 HTTP 脚本暂无法自动处理（验证码校验的服务器端密钥派生未能从黑盒逆出），此时会提示改用浏览器手动提交。
