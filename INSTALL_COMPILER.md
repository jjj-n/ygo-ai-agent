# 安装 Visual Studio Build Tools & 编译 ygopro-core

## 步骤 1: 下载 Visual Studio Build Tools

访问: https://visualstudio.microsoft.com/visual-cpp-build-tools/

点击 "Download Build Tools" 下载安装程序。

## 步骤 2: 运行安装程序

1. 运行下载的 `vs_BuildTools.exe`
2. 选择 "工作负载" 标签
3. 勾选 **"使用 C++ 的桌面开发"** (Desktop development with C++)
4. 点击 "安装"

## 步骤 3: 打开 x64 Developer Command Prompt

**重要**: 必须使用 x64 版本，不要用普通的 Developer Command Prompt!

方法 1: 从开始菜单
1. 打开开始菜单
2. 搜索 **"x64 Native Tools Command Prompt for VS 2022"** (或类似名称)
3. 以管理员身份运行

方法 2: 从普通 CMD 切换
```bash
# 找到 vcvarsall.bat 并调用
"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
```

## 步骤 4: 验证环境

在 x64 Developer Command Prompt 中运行:

```bash
cl
```

应该看到类似输出 (注意 x64):
```
Microsoft (R) C/C++ Optimizing Compiler x64
```

验证 meson 可用:
```bash
meson --version
ninja --version
```

## 步骤 5: 编译 ygopro-core

在 x64 Developer Command Prompt 中运行:

```bash
cd C:\Users\22956\Desktop\ygo\libs\ygopro-core

# 清理旧的 build 目录 (如果存在)
rmdir /s /q build

# 配置 (静态库)
meson setup build --default-library=static

# 编译
ninja -C build
```

编译成功后，`build/` 目录下会有 `ocgcore.lib` (静态库)。

如果需要 DLL:
```bash
meson setup build --default-library=shared
ninja -C build
```

## 步骤 6: 复制产物

```bash
# 复制到 ygopro-engine 目录
copy build\ocgcore.lib ..\ygopro-engine\deps\
# 或者如果是 DLL
copy build\ocgcore.dll ..\ygopro-engine\deps\
```

## 常见问题

### Q: "lua-5.4 找不到"
A: 已修改 meson.build 使用内置 Lua 源码，无需安装 Lua。

### Q: "编译目标是 x86"
A: 必须使用 **x64 Native Tools Command Prompt**，不是普通的 Developer Command Prompt。

### Q: "meson 找不到编译器"
A: 确保在 x64 Developer Command Prompt 中运行 meson，这样 meson 才能找到 MSVC。
