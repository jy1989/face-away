# FaceAway

**Windows 桌面人脸感知隐私工具。** 你离开电脑时，自动最小化当前打开的普通窗口；重新识别到你的脸后，尝试恢复原来的窗口状态。**首次只要拍一张照片**，不需要训练模型、注册账号或上传人脸。

[English](README.md) | **简体中文**

> **MVP / 实验阶段：** 这是日常便捷隐藏窗口的工具，**不是安全认证或真正锁屏**，不能代替 Windows 的 Win + L。普通摄像头可能被照片或视频欺骗。

## 功能

- **一张照片录入**：只保存由照片提取的 128 维人脸特征向量，不保存原始照片。
- **离开自动隐藏**：连续约 3 秒没有认出本人时，记录窗口状态并最小化当前可见的普通窗口。
- **回来自动恢复**：连续约 1 秒确认本人回来后，尝试恢复 FaceAway 隐藏过的窗口。
- **尽量保留原状态**：原本已最小化的窗口不会主动恢复；尽量保持正常、最大化和窗口位置状态。
- **更流畅的预览**：独立 Qt 工作线程采集摄像头，目标约 15 FPS；每约 700ms 执行一次识别。界面缩到托盘后减少预览开销。
- **响应式布局**：摄像头预览与状态区固定分离，小窗口或高 DPI 缩放时可滚动查看设置，避免控件重叠。
- **完全本地处理**：摄像头画面、人脸匹配均在本机运行；用 Windows DPAPI 加密特征向量。
- **启动自动监控（默认开启）**：已经录入人脸时，启动后会自动开始监控；设置界面可以取消勾选。首次未录入时不会自动隐藏窗口，拍照录入成功后开始监控。\n- **托盘控制**：暂停或启用监控、手动恢复窗口、退出程序；支持修改离开/返回判断时间。

## 运行要求

- Windows 10 / 11，有可用摄像头。
- [uv](https://docs.astral.sh/uv/getting-started/installation/) 管理 Python 环境（项目开发机器已有）。
- **首次安装**需要联网安装依赖、下载人脸模型；日常识别无需联网。
- 不需要显卡，也不需要自己训练模型。主要依赖 Python 3.11、PySide6 Essentials、标准版 OpenCV（不再需要 contrib 扩展）、NumPy、pywin32。

## 单文件 Windows EXE

先运行一次 `setup.bat`，之后双击 `build_exe.bat`，可以打包成 **无命令行窗口的单文件** `dist/FaceAway-v0.2.exe`。目前实测构建约 **120 MiB**（已包含两个人脸模型）。其他电脑可以直接双击 EXE，不必安装 Python，也不用保留 BAT；原来本机 `%LOCALAPPDATA%/FaceAway/` 下的加密人脸特征仍可以使用。

PyInstaller 单文件运行时会先将内部原生库解压到临时目录，因此启动可能稍慢。构建结果暂未进行代码签名，Windows SmartScreen 可能提示未知发布者。使用 EXE 前，请先从托盘退出旧版 Python 程序，避免两个版本同时监控桌面。

## 安装与启动

```powershell
git clone https://github.com/jy1989/face-away.git
cd face-away
.\setup.bat
.\run.bat
```

已有本地项目可直接双击 `run.bat`；如果从未下载模型，则先运行一次 `setup.bat`。

1. 打开后等待摄像头画面出现。
2. 首次使用点击 **「拍一张照片录入 / 重录」**。请正对摄像头，确保画面中只有自己的一张清晰人脸。
3. **默认启动自动开启监控**，不需要再按「开始监控」。已经有录入的人脸时，模型就绪后自动开始；首次录入成功后也会自动开始。取消勾选 **「启动后自动开启监控（默认开启）」** 可关闭这项设置。
4. 可以点击 **「收起到托盘」**。右键托盘图标可暂停监控、手动恢复窗口、退出。
5. **更新版本前**先通过托盘菜单退出旧版，再双击 `run.bat`。已经录入的人脸不会丢失，无需重新拍照。

## 实现原理

```text
摄像头 → OpenCV YuNet 人脸检测 → OpenCV SFace 提取人脸特征
                                           ↓
                                    本地 DPAPI 加密
                                     的人脸特征模板
                                           ↓
                                   本地余弦相似度对比
                                           ↓
                                  离开/返回时间防抖
                                           ↓
                                Win32 最小化 / 恢复窗口
```

人脸识别运行在独立线程，避免阻塞图形界面。摄像头帧不会上传网络，也不会写入磁盘。只有加密的人脸特征模板和时间设置存储在本机。

## 隐私与局限

- 人脸模板路径：`%LOCALAPPDATA%\FaceAway\face.dat`，由 Windows DPAPI 加密，仅当前 Windows 账户可解密。
- 设置文件：`%LOCALAPPDATA%\FaceAway\settings.json`。
- 原始照片与摄像头视频：**不保存**。
- 目前没有登录、云上传、数据分析或遥测功能。
- `setup.bat` 会下载 Python 依赖和预训练 ONNX 模型，程序会使用 SHA-256 校验模型。
- 某些管理员窗口、游戏、特殊应用、虚拟桌面、多显示器场景不能保证完整恢复；窗口前后层级也不能保证一致。
- 摄像头断开时会暂停监控并尝试恢复窗口。
- 如果程序被强行结束，隐藏窗口的记录仅在内存中，可能无法自动恢复。
- 目前没有活体检测，**不能作为计算机访问控制或安全锁屏**。

## 测试

```powershell
uv run --python 3.11 --with-requirements requirements.txt python -m unittest -v test_presence.py test_auto_monitor.py
uv run --python 3.11 --with-requirements requirements.txt python smoke_test.py
uv run --python 3.11 --with-requirements requirements.txt python test_camera_worker.py
uv run --python 3.11 --with-requirements requirements.txt python -m compileall -q .
```

模拟摄像头测试不会触发真实的窗口最小化操作。实际画面帧率取决于设备与驱动。

## 项目结构

| 文件 | 用途 |
|---|---|
| `app.py` | PySide6 界面、托盘、程序状态 |
| `camera_worker.py` | 摄像头后台采集和人脸识别 |
| `face_engine.py` | YuNet / SFace 模型处理 |
| `presence.py` | 离开和返回时间判断 |
| `window_manager.py` | Win32 窗口记录、最小化与恢复 |
| `profile_store.py` | 使用 DPAPI 加密存储人脸特征 |
| `models.py` | 预训练模型下载与 SHA-256 校验 |
| `setup.bat`、`run.bat` | Windows 安装与启动 |
| `test_*.py`、`smoke_test.py` | 自动化测试 |

## 开源许可证与第三方组件

FaceAway **程序源码**采用 [MIT License](LICENSE) 开源。ONNX 模型文件**没有上传到此 GitHub 仓库**，首次运行由用户下载，保留其各自的许可证。模型来源：[OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) 与 [OpenCV Zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)（SFace 采用 Apache-2.0）。依赖库也遵循各自的许可证；分发安装包或商业使用前请核查第三方许可及训练数据来源。

欢迎反馈问题和提交代码，但请不要在 Issue 里上传个人照片、人脸特征文件或敏感日志。
