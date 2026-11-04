# Tailscale OHOS core

从 MeshArc 提取的 HarmonyOS Tailscale 原生核心，提供 C 接口和可复现的依赖补丁。

这是**开发者预览**，不是完整 VPN 应用，也不是 Tailscale 官方发行版。当前目标为 **Tailscale 1.104.5、HarmonyOS API 26、arm64**；工具链固定到独立 Go 仓库的具体提交。公开核心的验证范围见 [validation](docs/validation.md)，不能直接把原应用的所有真机结果当作新仓库已经复测。

## 从哪里开始

1. 阅读 [英文首页](README.md) 的 Linux 主机测试命令。
2. 按 [构建文档](docs/build.md) 准备 Go 移植工具链和 API 26 native SDK，生成共享库、头文件与构建回执。
3. 按 [接入文档](docs/integration.md) 实现 N-API、VPN Extension、系统权限和用户界面。

本仓库保留 41 个 C 导出与已有响应格式。Go 核心负责编排 Tailscale；应用负责创建系统 TUN、配置路由、获得 VPN 授权和管理后台生命周期。MagicDNS 尚未由这里接通系统 DNS。

## 更新方式

每日检查上游正式标签和主线提交，有变化时更新同一条跟踪 issue。合入新版本前必须重放补丁、运行测试并记录目标平台结果，不会把“主机编译通过”写成“真机已验收”。详细流程见 [维护规范](docs/maintenance.md)。

本仓库与 [Go 工具链](https://github.com/flypigJ/go-ohos)、[MeshArc 应用](https://github.com/flypigJ/Tailscale-OHOS) 分开维护；不包含签名材料或用户账户数据。贡献来源见 [NOTICE](NOTICE.md)。
