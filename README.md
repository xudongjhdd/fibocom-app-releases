# Fibocom Android APK Releases

此公开仓库用于分发 Android APK。网站及后台的业务源码在独立私有仓库管理。

下载页：https://fibocom-firmware.web.app/downloads.html

管理页：https://fibocom-firmware.web.app/apk.html

## 发布 APK

1. 打开本仓库的 **Releases → Draft a new release**，创建唯一标签，例如 `v1.2.3` 或 `v1.2.4-beta.1`，目标分支选 `main`。
2. 填写版本标题、更新说明，在附件区域上传一个 `.apk` 文件。每个 Release 只附一个 APK；等待附件上传完毕再发布。
3. 正式版不要勾选 **Set as a pre-release**；测试版必须勾选该选项。
4. 点击 **Publish release**。GitHub Actions 会更新 `releases.json`；等待 Actions 成功及缓存刷新后，网站会显示该渠道按发布时间排序的最新版本。

GitHub 要求每个 Release 附件小于 2 GiB，145 MB APK 可作为一个完整附件上传。APK 不进入 Git 提交历史。仅有此仓库写权限的 GitHub 账号能上传或管理 Release；网站管理员账号不会自动授予 GitHub 权限。公开 Release 及测试版 APK 均对外公开。

## 更新与删除

通过 Releases 页面编辑发布说明、切换 pre-release 状态，或删除一个 Release。发布、编辑、删除及取消发布事件会重新生成目录。直接增删附件未必产生 Release 事件：请在 Actions 中选择 **Update APK catalog → Run workflow** 手动同步。上传失败时先处理草稿，未发布草稿不会显示在网站。

不要在相同版本标签下替换安装包；创建新的唯一版本标签，便于缓存、回滚及核验。删除最新版本后，同步目录将自动选择该渠道上一条有效版本。远端 CDN 缓存可能使目录和已删除链接短暂滞后。

## 自动目录

`.github/workflows/catalog.yml` 使用仓库自带的 `GITHUB_TOKEN`，仅有本仓库 `contents: write` 权限。目录只包含已发布版本的公开信息，不包含草稿、账号、Token 或业务源码。不直接手工编辑 `releases.json`。
