# 中证A500估值监控系统 部署手册

## 系统概述
本系统每日自动拉取中证A500指数（000510）的PE/PB数据，结合10年期国债收益率计算估值分位和股债性价比，并通过微信推送日报及极端警报。

## 部署步骤

### 1. 创建GitHub仓库（私有）
- 登录GitHub，新建仓库，名称自定，选择Private。

### 2. 上传代码
将本目录下所有文件（除history_data.csv外）上传至仓库根目录。

### 3. 配置PushPlus Token
- 注册 [PushPlus](https://www.pushplus.plus) 并获取token。
- 在GitHub仓库 Settings → Secrets and variables → Actions 中添加 `PUSH_TOKEN`。

### 4. 首次运行（手动触发）
- 进入 Actions 页面，选择 "Daily Valuation Update" 工作流，点击 "Run workflow"。
- **⏳ 首次运行耗时约20-30秒**（全量拉取自2004年至今的历史数据），请勿中断。

### 5. 验证结果
- 成功后您将收到微信推送的日报，内含估值结论和走势图。
- 若失败，可在Actions日志中查看错误详情，或下载Artifacts中的备份。

## 日常使用
- 系统在每个工作日北京时间08:30自动运行，无需干预。
- 若遇数据异常（PE/PB变动超阈值），将自动熔断并仅推送告警。

## 手动更新数据
- 若网络异常，系统会使用本地缓存（history_data.csv）继续运行。
- 您也可手动替换CSV文件（格式：date,pe_ttm,pb,bond_yield_10y），提交后手动触发工作流。

## 常见问题
- **首次运行失败**：检查网络是否可访问中证官网（csindex.com.cn），若超时可重试。
- **推送未收到**：确认PUSH_TOKEN配置正确，且PushPlus账户未欠费。
- **数据缺失**：若API改版，请及时联系维护者更新数据拉取逻辑。

## 技术维护
- 所有可调参数在 config.yaml 中，修改后提交即可生效。
- 日志输出在Actions控制台，便于排查。
