# 安装 aria2
apt-get update && apt-get install aria2 -y
# 下载 qwen_image_edit_bf16.safetensors
#aria2c -x 16 -s 16 -d models -o qwen_image_edit_bf16.safetensors "https://cnb.cool/ai-models/Comfy-Org/Qwen-Image-Edit_ComfyUI/-/lfs/f133f246ba14ba2a24e1a9df64fe4da35281e684b467c992059429bfb6187625?name=qwen_image_edit_bf16.safetensors"
aria2c -x 16 -s 16 -d ./models -o qwen_image_vae.safetensors "https://modelscope.cn/models/Qwen/Qwen-Image/resolve/master/vae/diffusion_pytorch_model.safetensors"
# 下载 qwen_image_bf16.safetensors
aria2c -x 16 -s 16 -d ./models -o qwen_image_bf16.safetensors "https://cnb.cool/lrxy.site/CNB-Qwen-Image/-/lfs/d08fb5d68026c0d87325f9a7b3ad6454061113a2bc73cc883114dae172937ae7?name=qwen_image_bf16.safetensors"
# 下载 qwen_2.5_vl_7b_fp8_scaled.safetensors
aria2c -x 16 -s 16 -d ./models -o qwen_2.5_vl_7b.safetensors "https://cnb.cool/lrxy.site/CNB-Qwen-Image/-/lfs/cfafd739459bc86257397259f612a9aee88e5b98e85b5c0d0d1717e898b3463a?name=qwen_2.5_vl_7b.safetensors"