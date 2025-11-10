#!/bin/bash
set -euo pipefail  # 严格模式，遇错即停

# 颜色输出工具
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }


# 1. 交互选择是否使用sudo
green "=== 权限设置 ==="
read -p "是否需要使用sudo命令执行安装操作？(y/n，默认n) " use_sudo
use_sudo=${use_sudo:-n}

# 设置sudo命令变量
if [[ $use_sudo == [yY] ]]; then
    SUDO="sudo"
    green "将使用sudo权限执行后续安装操作"
else
    SUDO=""
    yellow "不使用sudo权限（若出现权限错误，请重新运行并选择使用sudo）"
fi


# 2. 检测Python版本（仅支持3.10/3.11/3.12）
green "\n=== 检测Python版本（需3.10/3.11/3.12） ==="
declare -a SUPPORTED_PY_VERSIONS=("3.12" "3.11" "3.10")  # 优先高版本
PY_CMD=""
PY_VERSION=""

# 遍历支持的版本，优先选择最高可用版本
for ver in "${SUPPORTED_PY_VERSIONS[@]}"; do
    if command -v "python$ver" &>/dev/null; then
        PY_CMD="python$ver"
        PY_VERSION=$ver
        break
    fi
done

# 若未找到上述版本，检查python3是否符合（可能存在python3.10等别名）
if [ -z "$PY_CMD" ] && command -v python3 &>/dev/null; then
    DETECTED_VER=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    if [[ " ${SUPPORTED_PY_VERSIONS[@]} " =~ " $DETECTED_VER " ]]; then
        PY_CMD="python3"
        PY_VERSION=$DETECTED_VER
    fi
fi

# 版本验证
if [ -z "$PY_CMD" ]; then
    red "错误：未检测到支持的Python版本（需3.10/3.11/3.12）"
    exit 1
fi
green "已找到兼容Python版本：$PY_VERSION（命令：$PY_CMD）"


# 3. 检测并安装pip（核心修复：改用官方脚本安装）
green "\n=== 检测并安装pip ==="
# 检查pip是否可用
PIP_AVAILABLE=$($PY_CMD -c "import pip" 2>/dev/null && echo "yes" || echo "no")

if [ "$PIP_AVAILABLE" = "no" ]; then
    green "未检测到pip，使用官方脚本安装..."
    
    # 检查下载工具（wget或curl）
    if command -v wget &>/dev/null; then
        DOWNLOAD_CMD="wget -q -O get-pip.py"
    elif command -v curl &>/dev/null; then
        DOWNLOAD_CMD="curl -sSL -o get-pip.py"
    else
        red "错误：未找到wget或curl，请先安装其中一个下载工具"
        exit 1
    fi

    # 下载官方get-pip.py
    $DOWNLOAD_CMD https://bootstrap.pypa.io/get-pip.py || {
        red "错误：下载get-pip.py失败"
        exit 1
    }

    # 安装pip（不使用sudo时会安装到用户目录）
    $SUDO $PY_CMD get-pip.py || {
        red "错误：pip安装失败"
        rm -f get-pip.py  # 清理临时文件
        exit 1
    }

    # 清理临时文件
    rm -f get-pip.py

    # 再次验证pip是否可用
    PIP_AVAILABLE=$($PY_CMD -c "import pip" 2>/dev/null && echo "yes" || echo "no")
    if [ "$PIP_AVAILABLE" = "no" ]; then
        red "错误：pip安装失败，请手动运行以下命令安装："
        red "$PY_CMD https://bootstrap.pypa.io/get-pip.py"
        exit 1
    fi
fi

# 确定对应pip命令
if command -v "pip$PY_VERSION" &>/dev/null; then
    PIP_CMD="pip$PY_VERSION"
else
    PIP_CMD="$PY_CMD -m pip"
fi
green "对应pip命令：$PIP_CMD"


# 4. 检测CUDA版本
green "\n=== 检测CUDA版本 ==="
CUDA_VERSION=""
CUDA_WHL_TAG=""

if command -v nvcc &>/dev/null; then
    # 从nvcc提取主版本（如12.4 -> 12.4）
    CUDA_FULL=$(nvcc --version | grep -oP 'release \K\d+\.\d+')
    CUDA_MAJOR=$(echo $CUDA_FULL | cut -d. -f1)
    CUDA_MINOR=$(echo $CUDA_FULL | cut -d. -f2)
    CUDA_VERSION="$CUDA_MAJOR.$CUDA_MINOR"
    
    # 映射PyTorch支持的CUDA标签（匹配最新兼容版本）
    if [[ $CUDA_VERSION == 11.7 || $CUDA_VERSION == 11.8 ]]; then
        CUDA_WHL_TAG="cu118"  # 11.7/11.8共用cu118
    elif [[ $CUDA_VERSION == 12.* ]]; then
        if (( $(echo "$CUDA_VERSION >= 12.1" | bc -l) )); then
            CUDA_WHL_TAG="cu121"  # 12.1+最新兼容标签
        else
            red "错误：CUDA 12.0不支持，需11.7+/12.1+"
            exit 1
        fi
    else
        red "错误：不支持的CUDA版本$CUDA_VERSION（需11.7+/12.1+）"
        exit 1
    fi
    green "检测到CUDA版本：$CUDA_VERSION，使用标签：$CUDA_WHL_TAG"
else
    yellow "未检测到CUDA（nvcc未找到），将安装CPU版本PyTorch"
    CUDA_WHL_TAG="cpu"
fi


# 5. 检测并安装PyTorch和torchvision（已安装则跳过）
green "\n=== 检测并安装PyTorch & torchvision ==="
# 检查是否已安装
TORCH_INSTALLED=$($PY_CMD -c "import torch; print('installed')" 2>/dev/null || echo "not installed")
VISION_INSTALLED=$($PY_CMD -c "import torchvision; print('installed')" 2>/dev/null || echo "not installed")

if [[ $TORCH_INSTALLED == "installed" && $VISION_INSTALLED == "installed" ]]; then
    TORCH_VER=$($PY_CMD -c "import torch; print(torch.__version__)")
    green "PyTorch和torchvision已安装（版本：$TORCH_VER），跳过安装"
else
    # 未安装，执行安装
    TORCH_INDEX="https://download.pytorch.org/whl/$CUDA_WHL_TAG"
    INSTALL_CMD="$SUDO $PIP_CMD install torch torchvision --index-url $TORCH_INDEX"

    green "执行安装命令：$INSTALL_CMD"
    eval $INSTALL_CMD

    # 验证安装
    if ! $PY_CMD -c "import torch; import torchvision" &>/dev/null; then
        red "错误：PyTorch/torchvision安装失败"
        exit 1
    fi
    TORCH_VER=$($PY_CMD -c "import torch; print(torch.__version__)")
    green "PyTorch安装成功：$TORCH_VER（$([ $CUDA_WHL_TAG = "cpu" ] && echo "CPU版" || echo "CUDA版")）"
fi


# 6. 部署musubi-tuner项目
green "\n=== 部署musubi-tuner项目 ==="
if [ ! -d "musubi-tuner" ]; then
    red "错误：未找到musubi-tuner目录，请确保脚本在项目同级目录运行"
    exit 1
fi

cd musubi-tuner || { red "错误：进入musubi-tuner目录失败"; exit 1; }
green "安装项目 editable模式依赖..."
$SUDO $PIP_CMD install -e .
green "项目部署完成！"


# 7. 交互选择是否安装模型
green "\n=== 模型安装选择 ==="
read -p "是否需要安装模型（运行model.sh）？(y/n，默认n) " install_model
install_model=${install_model:-n}

if [[ $install_model == [yY] ]]; then
    if [ ! -f "model.sh" ]; then
        red "错误：musubi-tuner目录下未找到model.sh脚本"
        exit 1
    fi
    green "运行model.sh下载模型..."
    # 模型脚本可能需要权限，根据sudo选择决定
    $SUDO bash model.sh || { red "错误：model.sh执行失败"; exit 1; }
    green "模型下载完成"
else
    green "安装完成"
fi


green "\n=== 所有流程执行完毕 ==="