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

# 短轮询，用于高峰期抢场地
python -m sjtu_sports reserve \
  --venue 霍英东体育中心 \
  --sport 羽毛球 \
  --date 2026-09-26 \
  --time 13:00-14:00

# 长轮询，用于长期运行捡漏空场
python -m sjtu_sports reserve \
  --venue 霍英东体育中心 \
  --sport 羽毛球 \
  --date 2026-09-26 \
  --time 13:00-14:00 \
  --long-run
```

参数：

- `--venue`  场馆名称，必填；通过 `list-venues` 查看
- `--sport`  运动类型名称或 id，必填；通过 `list-sports` 查看
- `--date`   目标日期 `YYYY-MM-DD`
- `--time`   目标时段，如 `13:00-14:00`（不填则抢任意可用时段）
- `--field`  指定场地名，如 `场地1`
- `--long-run` 长轮询模式，每 1 分钟查询一次；默认模式每 0.8 秒查询一次

## QQ 通知（可选）

长轮询模式支持可选的 QQ 私聊通知。配置 QQ 官方机器人后，成功提交预约时会通过机器人发送一条消息。

在 [QQ 机器人开放平台](https://q.qq.com/)用自己的 QQ 创建个人机器人，保存 AppID 和 AppSecret。机器人会自动出现在创建者的 QQ 消息列表中。

启动下面这个脚本，给机器人发一条消息，脚本会输出接受者的 user_openid 然后结束

```sh
python -m sjtu_sports qq-openid
```

在仓库根目录下创建 `.env` 文件然后填入

```dotenv
QQ_BOT_APP_ID="机器人的AppID"
QQ_BOT_APP_SECRET="机器人的AppSecret"
QQ_BOT_USER_OPENID="接受者的user_openid"
```

然后在仓库根目录下执行：

```sh
python -m sjtu_sports reserve \
  --venue 霍英东体育中心 \
  --sport 羽毛球 \
  --date 2026-09-26 \
  --time 13:00-14:00 \
  --long-run
```

## 抓包分析

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
