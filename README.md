# Fibocom Android APK Releases

公开 Android APK 发布仓库。业务源码在独立私有仓库管理。

下载页：https://fibocom-firmware.web.app/downloads.html

管理页：https://fibocom-firmware.web.app/apk.html

## 发布 APK

在管理页登录网站管理员账号，选择正式或测试渠道，填写版本号、说明并选择 APK。页面完成分片上传后进入后台发布队列；同事无需 GitHub 账号。完成发布后下载页自动更新。队列每五分钟调度一次，GitHub 调度与目录缓存可能有延迟。

GitHub 要求每个附件小于 2 GiB。临时上传还受后台存储剩余容量约束；成功后清理分片。正式和测试 APK 都公开，不要发布保密包。APK 不进入 Git 提交历史。

## 自动发布

`publish.yml` 从私有暂存区读取完整任务，逐片验证 SHA-256，合并文件并核对 GitHub 返回的附件 SHA-256 后再公开 Release。版本标签为 `apk-<stable|beta>-<version>`，每个版本一个完整 APK。已有任务重复运行时核对任务 ID 和文件摘要，不覆盖其他发布。

Actions 使用受限 Supabase 发布账号和运行时 `GITHUB_TOKEN`。不要把 Supabase service_role 或长期 GitHub Token 放入此仓库。四个初始化 Secrets 是 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`APK_PUBLISHER_EMAIL`、`APK_PUBLISHER_PASSWORD`。

`catalog.yml` 在手工编辑发布后更新目录；自动发布工作流也显式运行目录脚本。不要手工覆盖 `releases.json`。

## 运维

失败任务可在网站重试。未完成上传可取消，或者在 24 小时后自动过期。任务发布成功后临时文件清理可重试。GitHub 长时间无仓库活动可能暂停定时工作流；管理员需恢复 Actions 调度。必要时手动运行 `Publish website APK uploads`。

编辑或删除已发布 Release 目前仍由仓库维护者在 GitHub 完成。直接增删附件后请手动运行 `Update APK catalog`。不要在相同版本标签下替换安装包。
