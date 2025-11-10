#!/bin/bash
set -euo pipefail  # 严格模式，遇到错误立即退出

# 询问用户是否使用sudo命令
echo "是否需要使用sudo权限进行安装操作？(y/n，默认y)"
read -r use_sudo
use_sudo=${use_sudo:-y}  # 默认使用sudo

# 根据用户选择设置sudo命令变量
if [ "$use_sudo" = "y" ] || [ "$use_sudo" = "Y" ]; then
    SUDO_CMD="sudo"
    echo "将使用sudo权限执行安装操作"
else
    SUDO_CMD=""
    echo "不使用sudo权限执行安装操作（可能需要手动处理权限问题）"
fi


# 检测包管理器类型（apt或yum）
detect_pkg_manager() {
    if [ -x "$(command -v apt)" ]; then
        echo "apt"
    elif [ -x "$(command -v yum)" ]; then
        echo "yum"
    else
        echo "Unsupported package manager (requires apt or yum)" >&2
        exit 1
    fi
}
PKG_MANAGER=$(detect_pkg_manager)


# 通用函数：更新apt源（确保源可用）
update_apt_sources() {
    echo "更新apt软件源索引..."
    $SUDO_CMD apt update -y
    # 确保main和universe源启用（libgl相关包通常在main源）
    if ! command -v add-apt-repository &> /dev/null; then
        $SUDO_CMD apt install -y software-properties-common
    fi
    $SUDO_CMD add-apt-repository main -y  # 核心包源
    $SUDO_CMD add-apt-repository universe -y  # 社区包源
    $SUDO_CMD apt update -y  # 再次更新以应用源配置
}


# 1. 检测并安装git
echo -e "\n=== 检测git ==="
if ! command -v git &> /dev/null; then
    echo "未找到git，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        update_apt_sources
        $SUDO_CMD apt install -y git
    else
        $SUDO_CMD yum install -y git
    fi
else
    echo "git已安装"
fi


# 2. 检测并安装python、pip及虚拟环境工具
echo -e "\n=== 检测python/pip/虚拟环境 ==="
# 优先检测python3，若不存在则检测python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "未找到python，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        update_apt_sources
        $SUDO_CMD apt install -y python3 python3-pip
    else
        $SUDO_CMD yum install -y python3 python3-pip
    fi
    PYTHON_CMD="python3"
fi

# 检测pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "未找到pip，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        update_apt_sources
        $SUDO_CMD apt install -y python3-pip
    else
        $SUDO_CMD yum install -y python3-pip
    fi
fi

# 检测虚拟环境功能（优先使用python内置venv，无则安装virtualenv）
echo "检测虚拟环境功能..."
if ! $PYTHON_CMD -m venv --help &> /dev/null; then
    echo "未找到虚拟环境工具，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        $SUDO_CMD apt install -y python3-venv  # Debian/Ubuntu专用venv包
    else
        # CentOS用pip安装virtualenv（yum无python3-venv包）
        $SUDO_CMD $PYTHON_CMD -m pip install --upgrade pip
        $SUDO_CMD $PYTHON_CMD -m pip install virtualenv
    fi
else
    echo "虚拟环境功能已就绪"
fi


# 3. 检测并安装aria2（优化apt源配置）
echo -e "\n=== 检测aria2 ==="
if ! command -v aria2c &> /dev/null; then
    echo "未找到aria2，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        update_apt_sources  # 确保源已更新
        $SUDO_CMD apt install -y aria2
    else
        # yum系统直接安装（aria2在默认源）
        $SUDO_CMD yum install -y aria2
    fi
else
    echo "aria2已安装"
fi


# 4. 检测并安装OpenGL库（解决libgl1-mesa-glx不可用问题）
echo -e "\n=== 检测OpenGL图形库 ==="
if [ "$PKG_MANAGER" = "apt" ]; then
    # 优先尝试安装libgl1-mesa-glx，失败则用替代包libgl1（通用OpenGL库）
    if ! dpkg -s libgl1-mesa-glx &> /dev/null && ! dpkg -s libgl1 &> /dev/null; then
        echo "未找到OpenGL库，开始安装..."
        # 临时关闭严格模式，允许安装命令失败
        set +e
        # 尝试安装原包
        $SUDO_CMD apt install -y libgl1-mesa-glx
        install_result=$?
        set -e  # 恢复严格模式

        # 如果原包安装失败，尝试替代包libgl1
        if [ $install_result -ne 0 ]; then
            echo "libgl1-mesa-glx安装失败，尝试安装替代包libgl1..."
            $SUDO_CMD apt install -y libgl1
        fi

        # 验证最终是否安装成功
        if ! dpkg -s libgl1-mesa-glx &> /dev/null && ! dpkg -s libgl1 &> /dev/null; then
            echo "错误：OpenGL库安装失败，请手动执行以下命令尝试修复：" >&2
            echo "$SUDO_CMD apt install -y libgl1" >&2
            exit 1
        fi
    else
        echo "OpenGL库已安装"
    fi
else
    # CentOS对应包名为mesa-libGL
    if ! rpm -q mesa-libGL &> /dev/null; then
        echo "未找到mesa-libGL（对应OpenGL库），开始安装..."
        $SUDO_CMD yum install -y mesa-libGL
    else
        echo "mesa-libGL已安装"
    fi
fi


# 5. 检测并安装gcc
echo -e "\n=== 检测gcc ==="
if ! command -v gcc &> /dev/null; then
    echo "未找到gcc，开始安装..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        update_apt_sources
        $SUDO_CMD apt install -y gcc
    else
        $SUDO_CMD yum install -y gcc
    fi
else
    echo "gcc已安装"
fi


echo -e "\n=== 所有组件检测与安装完成 ==="